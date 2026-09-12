"""Generate ten deterministic artwork/mask/DST fixtures and readback previews."""
import os
os.environ.setdefault("QT_QPA_PLATFORM","offscreen")
import json
import numpy as np
from pathlib import Path
from PIL import Image,ImageDraw
import pyembroidery as pe
from PySide6.QtWidgets import QApplication
from embroidery_app.examples import fixture,proof_design
from embroidery_app.embroidery.engine import digitize
from embroidery_app.embroidery.models import EmbroideryDesign,Stitch,Command
from embroidery_app.exporters.dst import export_dst,CODES
from embroidery_app.ui.stitch_preview import StitchPreview

app=QApplication([])
output=Path("examples/logos")
output.mkdir(parents=True,exist_ok=True)
preview=StitchPreview()
preview.resize(520,390)
preview.show()
reports=[]
contact=Image.new("RGB",(1300,1000),"#f5f3ed")
draw=ImageDraw.Draw(contact)
names=["Square","Circle","Concave L","Ring with hole","Three colors","Narrow column",
       "Triangle","Disconnected circles","Star","Text"]
for i,name in enumerate(names):
    image,mask=fixture(i)
    Image.fromarray(image).save(output/f"{i:02d}-source.png")
    Image.fromarray(mask).save(output/f"{i:02d}-mask.png")
    ys,xs=np.nonzero(mask)
    w,h=xs.max()-xs.min()+1,ys.max()-ys.min()+1
    width,height=80*w/max(w,h),80*h/max(w,h)
    design,metrics=digitize(image,mask,width,height,colors=3,length=4,angle=25)
    report=export_dst(design,output/f"{i:02d}.dst")
    restored=pe.read_dst(str(output/f"{i:02d}.dst"))
    reverse={value:key for key,value in CODES.items()}
    readback=EmbroideryDesign(width,height,thread_colors=design.thread_colors,
        stitches=[Stitch(x/10,y/10,reverse[c & pe.COMMAND_MASK]) for x,y,c in restored.stitches
                  if (c & pe.COMMAND_MASK) in reverse])
    preview.display(readback)
    app.processEvents()
    preview.grab().save(str(output/f"{i:02d}-readback.png"))
    tile=Image.open(output/f"{i:02d}-readback.png").convert("RGB")
    tile.thumbnail((260,190))
    x=(i%5)*260;y=(i//5)*500
    original=Image.fromarray(image);original.thumbnail((230,180))
    contact.paste(original,(x+15,y+30))
    contact.paste(tile,(x,y+220))
    draw.text((x+12,y+8),name,fill="#233e42")
    draw.text((x+12,y+425),f"{report['stitches']} stitches / readback",fill="#233e42")
    reports.append(dict(name=name,**report,metrics=metrics,thread_colors=design.thread_colors,
                        stitch_types=[o.stitch_type.value for o in design.objects]))
(output/"verification.json").write_text(json.dumps(reports,indent=2))
contact.save(output/"contact-sheet.png")
print(f"Verified and rendered {len(reports)} DST designs")
