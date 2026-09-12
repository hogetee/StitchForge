from embroidery_app.embroidery.models import EmbroideryDesign,Command,Stitch,StitchType
from embroidery_app.embroidery.generators.running import running
from embroidery_app.embroidery.generators.tatami import tatami
from embroidery_app.embroidery.generators.satin import satin
from embroidery_app.embroidery.planner import plan
from embroidery_app.embroidery.optimizer import optimize,travel
from embroidery_app.image_processing.vectorization import vectorize


def digitize(image,mask,width=80,height=80,colors=3,spacing=0.4,length=3,angle=0,
             min_area=0.3,mode="Auto",reverse_colors=False):
    regions=vectorize(image,mask,width,height,colors,min_area)
    design=EmbroideryDesign(width,height,(image.shape[1],image.shape[0]),regions=[p for p,c in regions])
    if sum(p.area for p,c in regions)/(spacing*length)>150000:
        raise ValueError("Design would exceed the 150,000-stitch V1 limit; reduce size or increase spacing")
    blocks=[]
    for obj in plan(regions,spacing,length,angle,mode):
        if obj.stitch_type==StitchType.RUNNING:
            path=[]
            for ring in [obj.geometry.exterior,*obj.geometry.interiors]:
                stitches=running(ring.coords,length)
                path.append(Stitch(stitches[0].x,stitches[0].y,Command.JUMP))
                path.extend(stitches[1:])
        elif obj.stitch_type==StitchType.SATIN:
            try:
                path=satin(obj.geometry,spacing,length,obj.angle)
            except ValueError:
                obj.stitch_type=StitchType.TATAMI
                obj.angle=angle
                path=tatami(obj.geometry,spacing,length,angle)
        else:
            path=tatami(obj.geometry,spacing,length,angle)
        if path and any(s.command==Command.STITCH for s in path):
            obj.entry_point=(path[0].x,path[0].y)
            obj.exit_point=(path[-1].x,path[-1].y)
            blocks.append((obj,path))
            if sum(len(p) for o,p in blocks)>150000:
                raise ValueError("Design exceeds the 150,000-command V1 limit")
    metrics={"before":travel(blocks)}
    blocks=optimize(blocks,reverse_colors)
    metrics["after"]=travel(blocks)
    color=None
    for obj,path in blocks:
        if obj.color!=color:
            if color is not None:
                last=design.stitches[-1]
                design.stitches.append(Stitch(last.x,last.y,Command.COLOR_CHANGE))
            design.thread_colors.append(obj.color)
            color=obj.color
        design.objects.append(obj)
        design.stitches.extend(path)
    if design.stitches:
        last=design.stitches[-1]
        design.stitches.append(Stitch(last.x,last.y,Command.END))
    return design,metrics
