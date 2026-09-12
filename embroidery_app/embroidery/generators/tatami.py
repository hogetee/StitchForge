from math import ceil, isfinite
from shapely import affinity
from shapely.geometry import LineString
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


def tatami(polygon,spacing=0.4,length=3,angle=0,progress=None,cancel_check=None,max_stitches=150000):
    result=[]
    for row in scan_rows(polygon,spacing,angle,progress,cancel_check):
        for segment in row:
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
                    result.append(Stitch(first.x,first.y,Command.JUMP))
            else:
                result.append(Stitch(first.x,first.y,Command.JUMP))
            result.extend(path[1:])
            if len(result)>max_stitches:
                raise ValueError("Fill region exceeds the 150,000-stitch limit; increase row spacing")
    return result
