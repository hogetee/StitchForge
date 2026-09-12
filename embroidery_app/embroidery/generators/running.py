from math import ceil, hypot, isfinite
from embroidery_app.embroidery.models import Stitch


def running(points, length=2.5):
    """Resample a polyline, retaining corners and explicitly repeated closure."""
    if not isfinite(length) or length <= 0:
        raise ValueError("Stitch length must be positive and finite")
    points = list(points)
    if not points:
        return []
    result = [Stitch(*points[0])]
    for end in points[1:]:
        start = result[-1]
        distance = hypot(end[0] - start.x, end[1] - start.y)
        if distance < 0.05:
            continue
        count = max(1, ceil(distance / length))
        result.extend(Stitch(start.x + (end[0]-start.x)*i/count,
                             start.y + (end[1]-start.y)*i/count)
                      for i in range(1, count+1))
    return result
