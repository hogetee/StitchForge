import numpy as np
from embroidery_app.embroidery.models import EmbroideryDesign,Command,Stitch,StitchType
from embroidery_app.embroidery.generators.running import running
from embroidery_app.embroidery.generators.tatami import tatami
from embroidery_app.embroidery.generators.satin import satin,column_stitches
from embroidery_app.embroidery.generators.underlay import underlay
from embroidery_app.embroidery.profiles import get_profile
from embroidery_app.embroidery.planning import prepare
from embroidery_app.embroidery.decomposition import decompose
from embroidery_app.embroidery.routing import join,choose_entry
from shapely.ops import unary_union
from embroidery_app.embroidery.planner import plan
from embroidery_app.embroidery.optimizer import optimize,travel
from embroidery_app.image_processing.vectorization import vectorize
from embroidery_app.embroidery.exceptions import DigitizeCancelled


def _report(progress, fraction, message):
    """Send a bounded progress update without coupling the engine to Qt."""
    if progress is not None:
        progress(max(0.0, min(1.0, float(fraction))), message)


def _check_cancel(cancel_check):
    if cancel_check is not None and cancel_check():
        raise DigitizeCancelled()


def digitize(image,mask,width=80,height=80,colors=3,spacing=0.4,length=3,angle=0,
             min_area=0.3,mode="Auto",reverse_colors=False,progress=None,layer_document=None,
             cancel_check=None,fabric=None,auto_direction=True):
    profile=get_profile(fabric)
    _check_cancel(cancel_check)
    _report(progress, 0.02, "Preparing selected artwork")
    fill_angles={}
    if layer_document is None:
        regions=vectorize(image,mask,width,height,colors,min_area)
        planned=plan(regions,spacing,length,angle,mode)
    else:
        if not layer_document.foreground.any():
            raise ValueError("No foreground in the layer project")
        ys,xs=np.nonzero(layer_document.foreground)
        frame=(xs.min(),ys.min(),xs.max()+1,ys.max()+1)
        regions,planned=[],[]
        for index,layer in enumerate(layer_document.layers):
            _check_cancel(cancel_check)
            if not layer.enabled or not layer.mask.any():
                continue
            try:
                parts=vectorize(image,layer.mask,width,height,1,
                                min(min_area,0.03) if layer.protect_details else min_area,
                                0.04 if layer.protect_details else 0.12,
                                frame=frame,solid_color=layer.color)
            except ValueError as error:
                if str(error)=="No regions survive the minimum-area filter":
                    continue
                raise
            objects=plan(parts,spacing,length,layer.angle if layer.angle is not None else angle,
                         mode if layer.mode=="Auto" else layer.mode)
            for obj in objects:
                obj.id=f"{layer.id}:{obj.id}"
                obj.layer_id=layer.id
                obj.layer_name=layer.name
                obj.priority=index
                obj.layer=index
                obj.role=layer.role
                fill_angles[obj.id]=layer.angle if layer.angle is not None else angle
            regions.extend(parts)
            planned.extend(objects)
            _report(progress,0.02+0.23*(index+1)/len(layer_document.layers),
                    f"Vectorizing layer {index+1}/{len(layer_document.layers)}")
        if not planned:
            raise ValueError("No enabled layer survives the minimum-region filter")
    _report(progress, 0.25, f"Found {len(regions)} geometric regions")
    design=EmbroideryDesign(width,height,(image.shape[1],image.shape[0]),regions=[p for p,c in regions])
    for obj in planned:
        manual_layer_angle=layer_document is not None and next(
            (p.angle for p in layer_document.layers if p.id==obj.layer_id),None) is not None
        obj.angle_mode='AUTO' if profile and auto_direction and not manual_layer_angle else 'MANUAL'
    if profile:
        planned=decompose(planned)
        design.plan=prepare(planned,profile,width,height,layer_document is not None,cancel_check)
        planned=design.plan.objects
        design.warnings.extend(design.plan.warnings)
    if sum(p.area for p,c in regions)/(spacing*length)>150000:
        raise ValueError("Design would exceed the 150,000-stitch V1 limit; reduce size or increase spacing")
    blocks=[]
    _report(progress, 0.35, f"Planning {len(planned)} embroidery objects")
    total=max(1, len(planned))
    for index,obj in enumerate(planned):
        _check_cancel(cancel_check)
        object_start=0.35 + 0.48 * index / total
        object_span=0.48 / total
        def row_progress(local, message, object_index=index):
            _report(progress, object_start + object_span * local,
                    f"Generating stitches {object_index + 1}/{len(planned)} · {message}")
        if obj.stitch_type==StitchType.RUNNING:
            path=[]
            for ring in [obj.geometry.exterior,*obj.geometry.interiors]:
                stitches=running(ring.coords,length)
                path.append(Stitch(stitches[0].x,stitches[0].y,Command.JUMP))
                path.extend(stitches[1:])
        elif obj.stitch_type==StitchType.SATIN:
            try:
                path=(column_stitches(obj) if obj.left_rail else
                      satin(obj.geometry,spacing,length,obj.angle,row_progress,cancel_check))
            except ValueError as error:
                design.warnings.append(f'{obj.id}: satin fallback to tatami: {error}')
                obj.stitch_type=StitchType.TATAMI
                obj.underlay_types=('CONTOUR','SPARSE_FILL') if obj.underlay else ()
                obj.angle=fill_angles.get(obj.id,angle)
                path=tatami(obj.geometry,spacing,length,obj.angle,row_progress,cancel_check,
                            stagger_period=profile.stagger_period if profile else 1,internal_travel=bool(profile),
                            internal_travel_limit=profile.internal_travel_limit_mm if profile else 12)
        else:
            path=tatami(obj.geometry,spacing,length,obj.angle,row_progress,cancel_check,
                        stagger_period=profile.stagger_period if profile else 1,internal_travel=bool(profile),
                        internal_travel_limit=profile.internal_travel_limit_mm if profile else 12)
        path=[Stitch(s.x,s.y,s.command,s.phase,obj.id) for s in path]
        if profile and obj.underlay:
            path=underlay(obj,profile,cancel_check)+path
        if profile:
            previous=(blocks[-1][1][-1].x,blocks[-1][1][-1].y) if blocks else (0,0)
            path=choose_entry(obj,path,previous)
        if path and any(s.command==Command.STITCH for s in path):
            obj.entry_point=(path[0].x,path[0].y)
            obj.exit_point=(path[-1].x,path[-1].y)
            blocks.append((obj,path))
            if sum(len(p) for o,p in blocks)>150000:
                raise ValueError("Design exceeds the 150,000-command V1 limit")
        _check_cancel(cancel_check)
        _report(progress, 0.35 + 0.48 * (index + 1) / total,
                f"Generating stitches {index + 1}/{len(planned)}")
    metrics={"before":travel(blocks)}
    _report(progress, 0.87, "Optimizing stitch order")
    if profile:
        # Objects have already been sorted subject to the dependency graph.
        pass
    elif layer_document is None:
        blocks=optimize(blocks,reverse_colors)
    else:
        # User layer order is a sewing constraint; optimize only within each layer.
        blocks=[block for layer in layer_document.layers
                for block in optimize([b for b in blocks if b[0].layer_id==layer.id])]
    metrics["after"]=travel(blocks)
    _report(progress, 0.93, "Assembling thread colors")
    color=None
    for index,(obj,path) in enumerate(blocks):
        _check_cancel(cancel_check)
        if obj.color!=color:
            if color is not None:
                last=design.stitches[-1]
                if profile:
                    design.stitches.append(Stitch(last.x,last.y,Command.TRIM,'TRAVEL',obj.id))
                design.stitches.append(Stitch(last.x,last.y,Command.COLOR_CHANGE))
            design.thread_colors.append(obj.color)
            color=obj.color
        design.objects.append(obj)
        if profile:
            future=unary_union([other.geometry for other,_ in blocks[index+1:]
                                if other.stitch_type!=StitchType.RUNNING])
            for stitch in path:
                if stitch.command==Command.JUMP and design.stitches:
                    last=design.stitches[-1]
                    same_color=last.command!=Command.COLOR_CHANGE
                    # Before underlay the whole current top is still ahead. During
                    # top stitching only later objects provide assured coverage.
                    coverage=future.union(obj.geometry) if stitch.phase=='UNDERLAY' else future
                    design.stitches.extend(join((last.x,last.y),(stitch.x,stitch.y),
                        coverage if obj.allow_hidden_travel and same_color else None,
                        length,profile.trim_distance_mm,object_id=obj.id))
                else:
                    design.stitches.append(stitch)
        else:
            design.stitches.extend(path)
    if design.stitches:
        last=design.stitches[-1]
        if profile:
            design.stitches.append(Stitch(last.x,last.y,Command.TRIM,'TRAVEL'))
        design.stitches.append(Stitch(last.x,last.y,Command.END))
    if len(design.stitches)>150000:
        raise ValueError('Design exceeds the 150,000-command limit including underlay and travel')
    metrics['counts']={command.value:sum(s.command==command for s in design.stitches) for command in Command}
    if profile:
        metrics['after']={'jumps':metrics['counts']['JUMP'],'color_changes':metrics['counts']['COLOR_CHANGE'],
            'jump_distance_mm':round(sum(np.hypot(b.x-a.x,b.y-a.y) for a,b in
                zip(design.stitches,design.stitches[1:]) if b.command==Command.JUMP),2)}
    metrics['phases']={phase:sum(s.command==Command.STITCH and s.phase==phase for s in design.stitches)
                       for phase in ('TOP','UNDERLAY','TRAVEL')}
    metrics['types']={kind.value:sum(s.command==Command.STITCH and s.phase=='TOP' and s.object_id in
                     {o.id for o in design.objects if o.stitch_type==kind} for s in design.stitches)
                     for kind in StitchType}
    metrics['objects']=len(design.objects)
    metrics['hidden_travel_mm']=round(sum(np.hypot(b.x-a.x,b.y-a.y) for a,b in
        zip(design.stitches,design.stitches[1:]) if b.command==Command.STITCH and b.phase=='TRAVEL'),2)
    metrics['warnings']=design.warnings
    _report(progress, 1.0, "Digitizing complete")
    if layer_document is not None:
        emitted={obj.layer_id for obj in design.objects}
        metrics['omitted_layers']=[layer.name for layer in layer_document.layers
                                  if layer.enabled and layer.id not in emitted]
    return design,metrics
