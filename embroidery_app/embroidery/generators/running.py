from math import ceil, hypot, isfinite
from embroidery_app.embroidery.models import Stitch


def running(points, length=2.5, minimum_length=0.05, maximum_length=None, preserve_nodes=False):
    """Resample a polyline, retaining corners and explicitly repeated closure."""
    if not isfinite(length) or length <= 0:
        raise ValueError("Stitch length must be positive and finite")
    if not isfinite(minimum_length) or minimum_length<0:
        raise ValueError('Minimum stitch length must be finite and non-negative')
    if maximum_length is not None:
        if not isfinite(maximum_length) or maximum_length<=0:
            raise ValueError('Maximum stitch length must be positive and finite')
        length=min(length,maximum_length)
    if minimum_length>length:
        raise ValueError('Minimum stitch length exceeds maximum')
    points = list(points)
    if not points:
        return []
    # Remove redundant collinear nodes so spacing does not restart at every pixel.
    simplified=[]
    for point in points:
        if not all(isfinite(v) for v in point):
            raise ValueError('Invalid running stitch coordinate')
        if simplified and hypot(point[0]-simplified[-1][0],point[1]-simplified[-1][1])<1e-9:
            continue
        while len(simplified)>=2 and not preserve_nodes:
            a,b=simplified[-2:]; u=(b[0]-a[0],b[1]-a[1]); v=(point[0]-b[0],point[1]-b[1])
            if abs(u[0]*v[1]-u[1]*v[0])<1e-9 and u[0]*v[0]+u[1]*v[1]>=0:
                simplified.pop()
            else: break
        simplified.append(point)
    points=simplified
    result = [Stitch(*points[0])]
    for end in points[1:]:
        start = result[-1]
        distance = hypot(end[0] - start.x, end[1] - start.y)
        if distance < 1e-9:
            continue
        count = max(1, ceil(distance / length))
        result.extend(Stitch(start.x + (end[0]-start.x)*i/count,
                             start.y + (end[1]-start.y)*i/count)
                      for i in range(1, count+1))
    return result
