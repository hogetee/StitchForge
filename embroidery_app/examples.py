from math import cos, sin, tau
from embroidery_app.embroidery.models import EmbroideryDesign, Stitch, Command
from embroidery_app.embroidery.generators.running import running


def proof_design(kind="multicolor"):
    design = EmbroideryDesign(80, 50, thread_colors=["#147d92", "#db663b"])
    paths = []
    if kind in ("square", "multicolor"):
        paths.append([(5,5),(35,5),(35,35),(5,35),(5,5)])
    if kind in ("circle", "multicolor"):
        paths.append([(57+15*cos(tau*i/120),22+15*sin(tau*i/120)) for i in range(121)])
    for i,path in enumerate(paths):
        if i:
            last = design.stitches[-1]
            design.stitches.append(Stitch(last.x,last.y,Command.COLOR_CHANGE))
        design.stitches.append(Stitch(*path[0],Command.JUMP))
        design.stitches.extend(running(path))
    last = design.stitches[-1]
    design.stitches.append(Stitch(last.x,last.y,Command.END))
    return design


def fixture(index):
    import numpy as np
    from PIL import Image,ImageDraw
    im=Image.new("RGB",(160,120),"white")
    mask=Image.new("L",im.size,0)
    draw=ImageDraw.Draw(im)
    selected=ImageDraw.Draw(mask)
    color=["#147d92","#d26643","#32415b"][index%3]
    if index==0:
        draw.rectangle((15,15,100,100),fill=color); selected.rectangle((15,15,100,100),fill=255)
    elif index==1:
        draw.ellipse((15,15,110,105),fill=color); selected.ellipse((15,15,110,105),fill=255)
    elif index==2:
        points=[(20,15),(130,15),(130,40),(50,40),(50,100),(20,100)]
        draw.polygon(points,fill=color); selected.polygon(points,fill=255)
    elif index==3:
        draw.ellipse((10,10,110,110),fill=color); selected.ellipse((10,10,110,110),fill=255)
        selected.ellipse((35,35,85,85),fill=0)
    elif index==4:
        for x,c in [(10,color),(65,"#c77f28"),(120,"#32415b")]:
            draw.rectangle((x,20,x+25,95),fill=c); selected.rectangle((x,20,x+25,95),fill=255)
    elif index==5:
        draw.rectangle((70,10,74,110),fill=color); selected.rectangle((70,10,74,110),fill=255)
    elif index==6:
        points=[(80,10),(140,100),(20,100)]
        draw.polygon(points,fill=color); selected.polygon(points,fill=255)
    elif index==7:
        for x in [15,65,115]:
            draw.ellipse((x,30,x+25,65),fill=color); selected.ellipse((x,30,x+25,65),fill=255)
    elif index==8:
        points=[(80,5),(94,40),(135,40),(102,65),(115,105),(80,80),(45,105),(58,65),(25,40),(66,40)]
        draw.polygon(points,fill=color); selected.polygon(points,fill=255)
    else:
        draw.text((20,40),"LOCAL",fill=color,stroke_width=1)
        selected.text((20,40),"LOCAL",fill=255,stroke_width=1)
    return np.array(im),np.array(mask)

