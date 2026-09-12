"""Object preparation, direction, underlay and controlled overlaps."""
from math import hypot
from shapely import affinity
from shapely.geometry import box,Polygon
from shapely.ops import unary_union
from embroidery_app.embroidery.models import EmbroideryPlan,StitchType
from embroidery_app.embroidery.planner import dimensions
from embroidery_app.embroidery.sequence import dependencies,sequence
from embroidery_app.embroidery.columns import centerline,rails
from embroidery_app.embroidery.exceptions import DigitizeCancelled


def prepare(objects,profile,width,height,preserve_layers=False,cancel_check=None):
    notes=[]
    for obj in objects:
        if cancel_check and cancel_check():
            raise DigitizeCancelled()
        obj.source_region_id=obj.source_region_id or obj.id
        obj.artwork_geometry=obj.geometry
        narrow,long,cross=dimensions(obj.geometry)
        if obj.role=='FILL' and obj.stitch_type==StitchType.RUNNING:
            obj.role='OUTLINE'
        elif obj.role=='FILL' and obj.stitch_type==StitchType.SATIN:
            obj.role='COLUMN'
        if not profile:
            continue
        if narrow<profile.minimum_detail_mm:
            obj.warnings.append(f'{obj.id}: detail narrower than fabric profile recommendation')
        # Try turning rails only on narrow regions; a rejected inference stays fill.
        average_width=2*obj.geometry.area/max(obj.geometry.length,1e-6)
        if obj.stitch_type==StitchType.SATIN or (obj.auto_stitch and
                obj.role not in ('OUTLINE','TEXT') and average_width<obj.stitch_length*0.85
                and long>3*average_width and not obj.geometry.interiors):
            try:
                points=obj.centerline or centerline(obj.geometry,cancel_check=cancel_check)
                obj.centerline,obj.left_rail,obj.right_rail=rails(obj.geometry,points,obj.density,obj.stitch_length)
                obj.stitch_type=StitchType.SATIN; obj.angle_mode='TURNING'; obj.role='COLUMN'
            except ValueError as error:
                if obj.stitch_type==StitchType.SATIN:
                    obj.stitch_type=StitchType.TATAMI
                obj.warnings.append(f'{obj.id}: satin inference fallback to fill: {error}')
        if obj.stitch_type==StitchType.TATAMI and obj.angle_mode=='AUTO' and profile.auto_direction:
            obj.angle=cross%180
            # Deterministic variation on touching, similar-angle fill neighbors.
            for other in objects[:objects.index(obj)]:
                if (other.stitch_type==StitchType.TATAMI and other.geometry.distance(obj.geometry)<0.2
                    and abs((obj.angle-other.angle+90)%180-90)<15):
                    obj.angle=(obj.angle+45)%180; break
        obj.pull_compensation=profile.pull_compensation_mm if obj.stitch_type!=StitchType.RUNNING else 0
        if obj.pull_compensation:
            # Extrusion along stitch direction, preserving the orthogonal dimension.
            if obj.stitch_type==StitchType.SATIN:
                expanded=obj.geometry.buffer(obj.pull_compensation)
            else:
                rotated=affinity.rotate(obj.geometry,-obj.angle,origin=(0,0))
                d=obj.pull_compensation
                pieces=[affinity.translate(rotated,xoff=-d),affinity.translate(rotated,xoff=d),rotated]
                for ring in [rotated.exterior,*rotated.interiors]:
                    for a,b in zip(ring.coords,list(ring.coords)[1:]):
                        sweep=Polygon([(a[0]-d,a[1]),(a[0]+d,a[1]),(b[0]+d,b[1]),(b[0]-d,b[1])])
                        if sweep.area>1e-9: pieces.append(sweep)
                expanded=unary_union(pieces)
                expanded=affinity.rotate(expanded,obj.angle,origin=(0,0))
            expanded=expanded.intersection(box(0,0,width,height))
            if expanded.geom_type=='Polygon' and expanded.is_valid:
                obj.geometry=expanded
                if obj.centerline:
                    try:
                        obj.centerline,obj.left_rail,obj.right_rail=rails(expanded,obj.centerline,obj.density,obj.stitch_length)
                    except ValueError as error:
                        obj.stitch_type=StitchType.TATAMI; obj.centerline=[]; obj.left_rail=[]; obj.right_rail=[]
                        obj.warnings.append(f'{obj.id}: compensated satin fallback: {error}')
        if profile.underlay_enabled and obj.stitch_type!=StitchType.RUNNING and obj.geometry.area>=profile.minimum_underlay_area_mm2:
            obj.underlay=True
            if obj.stitch_type==StitchType.SATIN:
                obj.underlay_types=(('CENTER_RUN',) if narrow<profile.narrow_satin_mm else
                    ('CONTOUR',) if narrow<profile.wide_satin_mm else ('CONTOUR','ZIGZAG'))
            else:
                obj.underlay_types=('CONTOUR','SPARSE_FILL')
    graph=dependencies(objects,preserve_layers)
    # Overlap direction comes from an existing valid order, never from color alone.
    ordered=sequence(objects,graph)
    if profile:
        for i,lower in enumerate(ordered):
            for upper in ordered[i+1:]:
                if lower.geometry.intersection(upper.geometry).area>1e-6:
                    graph.edges.add((lower.id,upper.id))
                if (lower.stitch_type!=StitchType.RUNNING and lower.artwork_geometry.distance(upper.artwork_geometry)<1e-6
                    and lower.color!=upper.color and profile.underlap_mm>0):
                    extra=lower.artwork_geometry.buffer(profile.underlap_mm).intersection(upper.artwork_geometry)
                    merged=lower.geometry.union(extra)
                    # Do not mutate rail columns after rail validation.
                    if merged.geom_type=='Polygon' and lower.stitch_type==StitchType.TATAMI:
                        lower.geometry=merged; graph.edges.add((lower.id,upper.id))
    for obj in objects:
        notes.extend(obj.warnings)
    return EmbroideryPlan(sequence(objects,graph),graph,notes)
