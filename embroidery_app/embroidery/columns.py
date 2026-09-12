"""Conservative raster skeleton inference and local-normal satin rails in mm."""
from math import ceil,hypot
from collections import deque
import cv2
import numpy as np
from shapely.geometry import LineString,Point
from embroidery_app.embroidery.generators.tatami import line_parts
from embroidery_app.embroidery.exceptions import DigitizeCancelled


def centerline(polygon,resolution=0.15,cancel_check=None):
    if polygon.interiors:
        raise ValueError('Column contains holes; split the object manually')
    x0,y0,x1,y1=polygon.bounds
    scale=max(resolution,max(x1-x0,y1-y0)/250)
    a=np.zeros((ceil((y1-y0)/scale)+5,ceil((x1-x0)/scale)+5),np.uint8)
    coords=np.asarray(polygon.exterior.coords)
    pts=np.round((coords-[x0,y0])/scale+2).astype(np.int32)
    cv2.fillPoly(a,[pts],1)
    # Zhang-Suen thinning preserves topology; boundary pixels are padded zeros.
    for iteration in range(256):
        if cancel_check and cancel_check():
            raise DigitizeCancelled()
        changed=False
        for step in (0,1):
            p=[a[:-2,1:-1],a[:-2,2:],a[1:-1,2:],a[2:,2:],
               a[2:,1:-1],a[2:,:-2],a[1:-1,:-2],a[:-2,:-2]]
            n=sum(p); transitions=sum((p[i]==0)&(p[(i+1)%8]==1) for i in range(8))
            condition=((p[0]*p[2]*p[4]==0)&(p[2]*p[4]*p[6]==0) if step==0
                       else (p[0]*p[2]*p[6]==0)&(p[0]*p[4]*p[6]==0))
            remove=(a[1:-1,1:-1]>0)&(n>=2)&(n<=6)&(transitions==1)&condition
            if remove.any():
                a[1:-1,1:-1][remove]=0; changed=True
        if not changed:
            break
    pixels=set(map(tuple,np.argwhere(a)))
    if len(pixels)<3:
        raise ValueError('No stable column centerline')
    def neighbors(p):
        y,x=p
        return sorted((y+dy,x+dx) for dy in (-1,0,1) for dx in (-1,0,1)
                      if (dy or dx) and (y+dy,x+dx) in pixels)
    def farthest(start):
        parents={start:None}; queue=deque([start]); last=start
        while queue:
            last=queue.popleft()
            for nxt in neighbors(last):
                if nxt not in parents:
                    parents[nxt]=last; queue.append(nxt)
        return last,parents
    end,_=farthest(min(pixels)); end,parents=farthest(end)
    chain=[]
    while end is not None:
        chain.append(end); end=parents[end]
    if len(chain)<0.8*len(pixels):
        raise ValueError('Branched column; split into simpler objects')
    line=LineString([(x0+(x-2)*scale,y0+(y-2)*scale) for y,x in chain]).simplify(scale)
    if not polygon.buffer(scale).covers(line) or line.length<1:
        raise ValueError('Unstable column centerline')
    return list(line.coords)


def rails(polygon,points,spacing=0.4,max_width=6):
    line=LineString(points)
    count=max(2,ceil(line.length/spacing)+1)
    if count>20000:
        raise ValueError('Too many satin stations')
    left=[]; right=[]; centers=[]
    for i in range(count):
        distance=line.length*i/(count-1)
        p=line.interpolate(distance)
        a=line.interpolate(max(0,distance-spacing))
        b=line.interpolate(min(line.length,distance+spacing))
        dx,dy=b.x-a.x,b.y-a.y; norm=hypot(dx,dy)
        if norm<1e-8:
            raise ValueError('Duplicate centerline station')
        nx,ny=-dy/norm,dx/norm
        axis=LineString([(p.x-nx*max_width*2,p.y-ny*max_width*2),
                         (p.x+nx*max_width*2,p.y+ny*max_width*2)])
        parts=[part for part in line_parts(polygon.intersection(axis)) if part.distance(p)<1e-6]
        if len(parts)!=1 or not 0.15<=parts[0].length<=max_width:
            raise ValueError('Invalid or excessive satin width')
        ends=list(parts[0].coords)
        ends.sort(key=lambda q:(q[0]-p.x)*nx+(q[1]-p.y)*ny)
        left.append(ends[0]); right.append(ends[-1]); centers.append((p.x,p.y))
    from shapely.ops import unary_union
    strips=[LineString([l,r]).buffer(spacing) for l,r in zip(left,right)]
    if polygon.intersection(unary_union(strips)).area<polygon.area*0.8:
        raise ValueError('Satin rails do not cover enough of the object')
    return centers,left,right
