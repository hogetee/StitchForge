from embroidery_app.embroidery.models import Stitch,Command
from embroidery_app.embroidery.generators.running import running
from embroidery_app.embroidery.generators.tatami import tatami
from shapely.geometry import LineString
from math import ceil,hypot


def underlay(obj,profile,cancel_check=None):
    result=[]
    inset=obj.geometry.buffer(-profile.underlay_inset_mm)
    simplified=inset.simplify(min(profile.contour_tolerance_mm,profile.underlay_inset_mm/2),preserve_topology=True)
    if obj.geometry.buffer(1e-7).covers(simplified):
        inset=simplified
    for kind in obj.underlay_types:
        if kind=='CENTER_RUN' and obj.centerline:
            path=running(obj.centerline,obj.stitch_length)
            result.extend([Stitch(path[0].x,path[0].y,Command.JUMP)]+path[1:])
        elif kind=='CONTOUR' and not inset.is_empty:
            parts=[inset] if inset.geom_type=='Polygon' else list(inset.geoms)
            for polygon in parts:
                for ring in [polygon.exterior,*polygon.interiors]:
                    path=running(ring.coords,obj.stitch_length)
                    result.extend([Stitch(path[0].x,path[0].y,Command.JUMP)]+path[1:])
        elif kind=='ZIGZAG' and obj.left_rail:
            stride=max(1,ceil(profile.underlay_spacing_mm/obj.density))
            points=[]
            for i,(left,right) in enumerate(list(zip(obj.left_rail,obj.right_rail))[::stride]):
                width=hypot(right[0]-left[0],right[1]-left[1])
                fraction=min(0.4,profile.underlay_inset_mm/max(width,1e-6))
                if i%2: fraction=1-fraction
                points.append((left[0]+fraction*(right[0]-left[0]),left[1]+fraction*(right[1]-left[1])))
            for a,b in zip(points,points[1:]):
                if obj.geometry.buffer(1e-7).covers(LineString([a,b])):
                    path=running([a,b],obj.stitch_length)
                    if not result or hypot(result[-1].x-a[0],result[-1].y-a[1])>1e-6:
                        result.append(Stitch(*a,Command.JUMP))
                    result.extend(path[1:])
                else:
                    result.append(Stitch(*b,Command.JUMP))
        elif kind=='SPARSE_FILL' and not inset.is_empty:
            result.extend(tatami(inset,profile.underlay_spacing_mm,obj.stitch_length,
                                 (obj.angle+90)%180,cancel_check=cancel_check))
    return [Stitch(s.x,s.y,s.command,'UNDERLAY',obj.id) for s in result]
