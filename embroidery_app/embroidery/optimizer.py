from math import hypot
from embroidery_app.embroidery.models import Command


def travel(blocks):
    previous=(0,0)
    distance=0
    jumps=0
    for obj,path in blocks:
        for s in path:
            if s.command==Command.JUMP:
                distance+=hypot(s.x-previous[0],s.y-previous[1])
                jumps+=1
            previous=(s.x,s.y)
    return {"jump_distance_mm":round(distance,2),"jumps":jumps,
            "color_changes":sum(a[0].color!=b[0].color for a,b in zip(blocks,blocks[1:]))}


def optimize(blocks,reverse_colors=False):
    palette=list(dict.fromkeys(obj.color for obj,path in blocks))
    if reverse_colors:
        palette.reverse()
    result=[]
    current=(0,0)
    for color in palette:
        pending=[block for block in blocks if block[0].color==color]
        while pending:
            index=min(range(len(pending)),key=lambda i:(pending[i][0].priority,
                      hypot(pending[i][1][0].x-current[0],pending[i][1][0].y-current[1])))
            block=pending.pop(index)
            result.append(block)
            current=(block[1][-1].x,block[1][-1].y)
    # Retain original order if grouping offers no color benefit and increases travel.
    if not reverse_colors:
        before,after=travel(blocks),travel(result)
        if after["color_changes"]>=before["color_changes"] and after["jump_distance_mm"]>before["jump_distance_mm"]:
            return blocks
    return result
