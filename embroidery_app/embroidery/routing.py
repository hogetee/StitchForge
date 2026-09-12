"""Bounded visibility routing. Never stitch across an uncovered gap or hole."""
from heapq import heappop,heappush
from math import hypot
from shapely.geometry import LineString,Point
from embroidery_app.embroidery.models import Stitch,Command
from embroidery_app.embroidery.generators.running import running


def internal_route(start,end,polygon,max_distance=12):
    line=LineString([start,end])
    if line.length<0.05:
        return [start]
    cover=polygon.buffer(1e-7)
    if cover.covers(line):
        return [start,end] if line.length<=max_distance else None
    vertices=[p for ring in [polygon.exterior,*polygon.interiors] for p in list(ring.coords)[:-1]]
    if len(vertices)>96 or not cover.covers(Point(start)) or not cover.covers(Point(end)):
        return None
    nodes=[start,end]+vertices
    queue=[(0,0)]; distance={0:0}; parent={}
    while queue:
        cost,index=heappop(queue)
        if cost!=distance[index]: continue
        if index==1:
            path=[nodes[index]]
            while index in parent:
                index=parent[index]; path.append(nodes[index])
            return path[::-1]
        for j,p in enumerate(nodes):
            if j==index: continue
            segment=LineString([nodes[index],p]); new=cost+segment.length
            if new<=max_distance and new<distance.get(j,float('inf')) and cover.covers(segment):
                distance[j]=new; parent[j]=index; heappush(queue,(new,j))
    return None


def join(start,end,coverage,length,trim_distance=3,phase='TRAVEL',object_id=None):
    line=LineString([start,end])
    if line.length<0.05: return []
    if coverage is not None and coverage.buffer(1e-7).covers(line):
        return [Stitch(s.x,s.y,s.command,phase,object_id) for s in running([start,end],length)[1:]]
    result=[]
    if line.length>=trim_distance:
        result.append(Stitch(*start,Command.TRIM,'TRAVEL',object_id))
    result.append(Stitch(*end,Command.JUMP,'TRAVEL',object_id))
    return result


def choose_entry(obj,path,current):
    """Reverse only a whole continuous top path; never reverse underlay behind top."""
    if not path: return path
    # Rotate the first closed contour without moving its underlay after top fill.
    end=next((i for i,s in enumerate(path[1:],1) if s.command!=Command.STITCH or s.phase!=path[0].phase),len(path))
    contour=path[:end]
    if len(contour)>3 and hypot(contour[0].x-contour[-1].x,contour[0].y-contour[-1].y)<1e-6:
        ring=contour[:-1]
        index=min(range(len(ring)),key=lambda i:hypot(ring[i].x-current[0],ring[i].y-current[1]))
        rotated=ring[index:]+ring[:index]+[ring[index]]
        first=rotated[0]
        return [Stitch(first.x,first.y,Command.JUMP,first.phase,first.object_id)]+[
            Stitch(s.x,s.y,Command.STITCH,s.phase,s.object_id) for s in rotated[1:]]+path[end:]
    if obj.underlay or any(s.command!=Command.STITCH for s in path[1:]):
        return path
    first,last=path[0],path[-1]
    if hypot(last.x-current[0],last.y-current[1])<hypot(first.x-current[0],first.y-current[1]):
        return [Stitch(last.x,last.y,Command.JUMP,last.phase,last.object_id)]+[
            Stitch(s.x,s.y,Command.STITCH,s.phase,s.object_id) for s in reversed(path[:-1])]
    return path
