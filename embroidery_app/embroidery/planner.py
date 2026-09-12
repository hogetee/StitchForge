from dataclasses import dataclass
import cv2
import numpy as np
from math import atan2,degrees,hypot
from embroidery_app.embroidery.models import EmbroideryObject,StitchType


@dataclass(frozen=True)
class PlannerRules:
    running_width: float = 0.65
    satin_min_width: float = 0.8
    satin_max_width: float = 6.0
    satin_min_aspect: float = 3.0
    satin_min_convexity: float = 0.97


def dimensions(polygon):
    rectangle=cv2.minAreaRect(np.asarray(polygon.exterior.coords,dtype=np.float32))
    corners=cv2.boxPoints(rectangle).tolist()
    points=corners+[corners[0]]
    edges=[(hypot(b[0]-a[0],b[1]-a[1]),degrees(atan2(b[1]-a[1],b[0]-a[0])))
           for a,b in zip(points,points[1:])]
    narrow=min(edges,key=lambda e:e[0])
    return narrow[0],max(e[0] for e in edges),narrow[1]


def plan(regions,spacing=0.4,length=3,angle=0,mode="Auto",rules=PlannerRules()):
    objects=[]
    for i,(polygon,color) in enumerate(regions):
        width,long,cross_angle=dimensions(polygon)
        kind=StitchType.TATAMI
        if mode=="Outline" or (mode=="Auto" and width<rules.running_width):
            kind=StitchType.RUNNING
        elif (mode=="Auto" and not polygon.interiors and
              rules.satin_min_width<=width<=min(rules.satin_max_width,length) and
              long/max(width,0.001)>=rules.satin_min_aspect and
              polygon.area/polygon.convex_hull.area>=rules.satin_min_convexity):
            kind=StitchType.SATIN
        objects.append(EmbroideryObject(str(i),polygon,color,kind,spacing,length,
                                       cross_angle if kind==StitchType.SATIN else angle))
    return objects
