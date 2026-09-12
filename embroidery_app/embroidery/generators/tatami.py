from math import ceil, isfinite
from shapely import affinity
from shapely.geometry import LineString,box
from embroidery_app.embroidery.models import Stitch,Command
from embroidery_app.embroidery.generators.running import running
from embroidery_app.embroidery.exceptions import DigitizeCancelled


def line_parts(geometry):
    if geometry.is_empty:
        return []
    if geometry.geom_type=="LineString":
        return [geometry] if geometry.length>0.05 else []
    return [line for part in getattr(geometry,"geoms",[]) for line in line_parts(part)]


def scan_rows(polygon,spacing,angle,progress=None,cancel_check=None):
    if not isfinite(spacing) or spacing<0.15:
        raise ValueError("Row spacing must be at least 0.15 mm")
    rotated=affinity.rotate(polygon,-angle,origin=(0,0))
    x0,y0,x1,y1=rotated.bounds
    count=max(1,ceil((y1-y0)/spacing))
    if count>20000:
        raise ValueError("Too many fill rows; increase spacing or reduce size")
    for row in range(count):
        if cancel_check is not None and cancel_check():
            raise DigitizeCancelled()
        y=y0+(row+0.5)*(y1-y0)/count
        segments=line_parts(rotated.intersection(LineString([(x0-1,y),(x1+1,y)])))
        segments.sort(key=lambda line:line.bounds[0],reverse=bool(row%2))
        yield [affinity.rotate(LineString(list(segment.coords)[::(-1 if row%2 else 1)]),
                               angle,origin=(0,0)) for segment in segments]
        if progress is not None:
            progress((row+1)/count, f"fill row {row+1}/{count}")


def tatami(polygon,spacing=0.4,length=3,angle=0,progress=None,cancel_check=None,max_stitches=150000,
           stagger_period=1,internal_travel=False,internal_travel_limit=12):
    result=[]
    if not isfinite(length) or length<=0 or not 1<=stagger_period<=16:
        raise ValueError('Invalid stitch length or stagger period')
    for row_index,row in enumerate(scan_rows(polygon,spacing,angle,progress,cancel_check)):
        for segment in row:
            if stagger_period>1:
                from math import cos,sin,radians,floor
                # A global phase in the rotated frame avoids resetting phase at each island.
                ends=list(segment.coords); dx=cos(radians(angle)); dy=sin(radians(angle))
                values=[x*dx+y*dy for x,y in ends]
                lo,hi=sorted(values); phase=(row_index%stagger_period)*length/stagger_period
                ticks=[lo]+[phase+k*length for k in range(floor((lo-phase)/length)+1,ceil((hi-phase)/length))]+[hi]
                clean=[ticks[0]]
                for tick in ticks[1:-1]:
                    if tick-clean[-1]>=0.1 and hi-tick>=0.1: clean.append(tick)
                clean.append(hi)
                if values[0]>values[-1]: clean.reverse()
                path=[Stitch(*segment.interpolate(abs(tick-values[0])).coords[0]) for tick in clean]
                # Near endpoints, splitting still respects the configured maximum.
                path=running([(p.x,p.y) for p in path],length,preserve_nodes=True)
            else:
                path=running(segment.coords,length)
            if not path:
                continue
            first=path[0]
            if result:
                last=result[-1]
                connector=LineString([(last.x,last.y),(first.x,first.y)])
                if connector.length<=length and polygon.buffer(1e-7).covers(connector):
                    if connector.length>=0.05:
                        result.append(first)
                else:
                    from embroidery_app.embroidery.routing import internal_route
                    route=None
                    if internal_travel and polygon.geom_type=='Polygon':
                        # Restrict detours to rows still to be sewn. A route anywhere
                        # in the polygon could otherwise lie on top of finished fill.
                        rotated=affinity.rotate(polygon,-angle,origin=(0,0))
                        current_line=affinity.rotate(segment,-angle,origin=(0,0))
                        x0,y0,x1,y1=rotated.bounds
                        remaining=rotated.intersection(box(x0-1,current_line.bounds[1]-1e-7,x1+1,y1+1))
                        remaining=affinity.rotate(remaining,angle,origin=(0,0))
                        if remaining.geom_type=='Polygon':
                            route=internal_route((last.x,last.y),(first.x,first.y),remaining,internal_travel_limit)
                    if route:
                        result.extend(Stitch(s.x,s.y,s.command,'TRAVEL') for s in running(route,length)[1:])
                    else:
                        result.append(Stitch(first.x,first.y,Command.JUMP))
            else:
                result.append(Stitch(first.x,first.y,Command.JUMP))
            result.extend(path[1:])
            if len(result)>max_stitches:
                raise ValueError("Fill region exceeds the 150,000-stitch limit; increase row spacing")
    return result
