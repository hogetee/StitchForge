"""Two-rail satin for simple columns; rejection delegates to tatami."""
from math import hypot
from shapely.geometry import LineString
from embroidery_app.embroidery.models import Stitch,Command
from embroidery_app.embroidery.generators.tatami import scan_rows


def satin(polygon,spacing=0.4,max_length=6,angle=0,progress=None,cancel_check=None):
    if polygon.interiors:
        raise ValueError("Satin columns cannot contain holes")
    rails=[]
    for row in scan_rows(polygon,spacing,angle,progress,cancel_check):
        if len(row)!=1:
            raise ValueError("Satin requires a single continuous column")
        ends=list(row[0].coords)
        # scan_rows reverses odd rows; restore a consistent rail ordering.
        if len(rails)%2:
            ends.reverse()
        rails.append((ends[0],ends[-1]))
    if len(rails)<2:
        raise ValueError("Too few satin rail samples")
    # A rail endpoint on alternating sides at each longitudinal station.
    points=[pair[i%2] for i,pair in enumerate(rails)]
    for a,b in zip(points,points[1:]):
        if hypot(b[0]-a[0],b[1]-a[1])>max_length or not polygon.buffer(1e-7).covers(LineString([a,b])):
            raise ValueError("Unsafe satin span; use tatami")
    return [Stitch(*points[0],Command.JUMP)]+[Stitch(*p) for p in points[1:]]


def column_stitches(obj):
    """Use local-normal rails already validated by the planning stage."""
    points=[pair[i%2] for i,pair in enumerate(zip(obj.left_rail,obj.right_rail))]
    if len(points)<2:
        raise ValueError('No satin rails')
    for a,b in zip(points,points[1:]):
        line=LineString([a,b])
        if line.length>obj.stitch_length or not obj.geometry.buffer(1e-7).covers(line):
            raise ValueError('Unsafe turning satin span')
    return [Stitch(*points[0],Command.JUMP)]+[Stitch(*p) for p in points[1:]]
