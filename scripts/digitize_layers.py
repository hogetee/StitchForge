"""Local image acceptance run: source -> layers -> DST -> actual readback preview.

Usage: .venv/bin/python scripts/digitize_layers.py IMAGE OUTPUT_DIRECTORY
"""
import argparse
import json
import os
from pathlib import Path
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
import numpy as np
from PIL import Image,ImageOps
import pyembroidery as pe
from PySide6.QtWidgets import QApplication
from embroidery_app.image_processing.segmentation import separate_layers
from embroidery_app.embroidery.engine import digitize
from embroidery_app.embroidery.models import EmbroideryDesign,Stitch
from embroidery_app.exporters.dst import export_dst,CODES
from embroidery_app.project import save_project
from embroidery_app.ui.main_window import MainWindow


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('image',type=Path)
    parser.add_argument('output',type=Path)
    parser.add_argument('--colors',type=int,default=4)
    parser.add_argument('--keep-lighting-bands',action='store_true',
                        help='keep photographic highlights/shadows as separate color bands')
    parser.add_argument('--single-material',action='store_true',
                        help='collapse non-dark foreground into one editable material layer')
    parser.add_argument('--width',type=float,default=80)
    parser.add_argument('--fabric',default=None,help='Fabric profile name, e.g. Woven / Cotton; omitted preserves legacy generation')
    args=parser.parse_args()
    with Image.open(args.image) as source:
        source=ImageOps.exif_transpose(source).convert('RGBA')
        source.thumbnail((1600,1600))
        rgba=np.array(source)
    image=rgba[:,:,:3].copy()
    document=separate_layers(image,alpha=rgba[:,:,3],colors=args.colors,
                             merge_shades=not args.keep_lighting_bands,
                             single_material=args.single_material)
    ys,xs=np.nonzero(document.foreground)
    height=round(args.width*(ys.max()-ys.min()+1)/(xs.max()-xs.min()+1),2)
    settings=dict(width=args.width,height=height,colors=args.colors,length=4,spacing=0.4,angle=25,fabric=args.fabric)
    design,metrics=digitize(image,document.foreground,layer_document=document,**settings)
    args.output.mkdir(parents=True,exist_ok=True)
    report=export_dst(design,args.output/'layered.dst')
    save_project(args.output/'editable.stitchforge',image,rgba[:,:,3],document,settings)
    Image.fromarray(document.foreground).save(args.output/'foreground.png')
    Image.fromarray(document.render(image)).save(args.output/'simplified.png')
    restored=pe.read_dst(str(args.output/'layered.dst'))
    codes={v:k for k,v in CODES.items()}
    readback=EmbroideryDesign(args.width,height,thread_colors=design.thread_colors,
        stitches=[Stitch(x/10,y/10,codes[c & pe.COMMAND_MASK]) for x,y,c in restored.stitches
                  if c & pe.COMMAND_MASK in codes])
    app=QApplication.instance() or QApplication([])
    window=MainWindow()
    window.resize(1500,920); window.show(); app.processEvents()
    window.canvas.load_array(rgba)
    window.width.setValue(args.width)
    window.accept_layers(document)
    window.accept_design(design,metrics)
    window.preview.display(readback)
    app.processEvents()
    window.preview.grab().save(str(args.output/'dst-readback.png'))
    window.grab().save(str(args.output/'desktop.png'))
    window.project_dirty=False; window.close()
    report.update(metrics=metrics,parts=[dict(id=p.id,name=p.name,color=p.color,pixels=int(np.count_nonzero(p.mask)))
                                       for p in document.layers])
    (args.output/'verification.json').write_text(json.dumps(report,indent=2))
    print(json.dumps({key:value for key,value in report.items() if key!='parts'},indent=2))


if __name__=='__main__':
    main()
