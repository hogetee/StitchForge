"""Generate a reproducible local ten-design planning benchmark and report."""
import argparse,json,os
from dataclasses import asdict
from pathlib import Path
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
import numpy as np
from PIL import Image,ImageDraw
from shapely.geometry import box,Point,LineString,Polygon
from shapely.ops import unary_union
from PySide6.QtWidgets import QApplication
from embroidery_app.image_processing.layers import ArtworkLayer,LayerDocument
from embroidery_app.embroidery.engine import digitize
from embroidery_app.embroidery.validation import validate
from embroidery_app.exporters.dst import export_dst
from embroidery_app.project import save_project
from embroidery_app.ui.stitch_preview import StitchPreview


def cases():
    a=unary_union([LineString([(8,32),(16,7),(24,32)]).buffer(1.4),box(11,21,21,24)])
    curve=LineString([(10,30),(8,20),(12,10),(23,8),(30,15)]).buffer(1.2)
    logo=[box(4,4,36,36),a,box(5,5,35,35).difference(box(6,6,34,34))]
    return [('circle',[Point(20,20).buffer(14)]),('rectangle',[box(5,5,35,30)]),
      ('concave-u',[Polygon([(5,5),(35,5),(35,35),(27,35),(27,13),(13,13),(13,35),(5,35)])]),
      ('donut',[Point(20,20).buffer(15).difference(Point(20,20).buffer(7))]),
      ('curved-column',[curve]),('letter-a',[a]),
      ('word',[a,LineString([(28,7),(28,32),(37,32)]).buffer(1.4)]),
      ('overlapping-colors',[box(4,4,25,25),box(15,15,36,36)]),
      ('fill-text-border',logo),('complex-logo',logo+[Point(9,30).buffer(2),Point(31,30).buffer(2)])]


def run(out):
    app=QApplication.instance() or QApplication([])
    palette=['#c75e31','#ead693','#222d3d','#37776d','#9967a1']
    summary=[]
    for name,geometries in cases():
        folder=out/name; folder.mkdir(parents=True,exist_ok=True)
        masks=[]; source=Image.new('RGB',(400,400),'#f5f3ed')
        for i,g in enumerate(geometries):
            mask=Image.new('L',source.size); draw=ImageDraw.Draw(mask)
            for polygon in [g] if g.geom_type=='Polygon' else g.geoms:
                draw.polygon([(x*10,y*10) for x,y in polygon.exterior.coords],fill=255)
                for ring in polygon.interiors: draw.polygon([(x*10,y*10) for x,y in ring.coords],fill=0)
            masks.append(np.array(mask)); source.paste(palette[i%len(palette)],mask=mask)
        # Visible raster ownership is disjoint. Sewing underlap is added later in mm.
        for i in range(len(masks)):
            for upper in masks[i+1:]: masks[i][upper>0]=0
        layers=[ArtworkLayer(f'Part {i+1}',palette[i%len(palette)],mask,role='BASE' if i==0 else 'DETAIL') for i,mask in enumerate(masks)]
        doc=LayerDocument(np.bitwise_or.reduce(masks),layers)
        image=np.array(source); settings=dict(width=40,height=40,length=4,fabric='Woven / Cotton')
        design,metrics=digitize(image,doc.foreground,layer_document=doc,**settings)
        errors,warnings=validate(design,4)
        if errors: raise ValueError(f'{name}: {errors}')
        source.save(folder/'artwork.png')
        export=export_dst(design,folder/'design.dst')
        save_project(folder/'editable.stitchforge',image,np.full(image.shape[:2],255,np.uint8),doc,settings)
        plan={'objects':[{'id':o.id,'source_region':o.source_region_id,'parent':o.parent_object,'layer':o.layer,'role':o.role,
              'type':o.stitch_type.value,'geometry_wkt':o.geometry.wkt,'angle':o.angle,'underlay':o.underlay_types,
              'pull_compensation_mm':o.pull_compensation,'entry':o.entry_point,'exit':o.exit_point,
              'centerline':o.centerline,'left_rail':o.left_rail,'right_rail':o.right_rail} for o in design.objects],
              'edges':sorted(design.plan.graph.edges),'vectors':[g.wkt for g in design.regions]}
        (folder/'plan.json').write_text(json.dumps(plan,indent=2))
        preview=StitchPreview(); preview.resize(720,720); preview.show(); preview.display(design); app.processEvents()
        preview.grab().save(str(folder/'preview.png')); preview.close()
        (folder/'metrics.json').write_text(json.dumps({'metrics':metrics,'dst':export,'warnings':warnings},indent=2))
        summary.append({'case':name,'objects':len(design.objects),'stitches':export['stitches'],'warnings':len(warnings)})
    (out/'summary.json').write_text(json.dumps(summary,indent=2)); print(json.dumps(summary,indent=2))


if __name__=='__main__':
    parser=argparse.ArgumentParser(); parser.add_argument('output',type=Path,nargs='?',default=Path('output/planning-benchmark'))
    run(parser.parse_args().output)
