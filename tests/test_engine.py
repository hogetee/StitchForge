import math
import numpy as np
import pytest
from PIL import Image,ImageDraw
from shapely.geometry import Polygon,box,LineString
from embroidery_app.image_processing.vectorization import vectorize
from embroidery_app.embroidery.generators.tatami import tatami
from embroidery_app.embroidery.exceptions import DigitizeCancelled
from embroidery_app.embroidery.generators.satin import satin
from embroidery_app.embroidery.models import Command,StitchType,EmbroideryObject,Stitch
from embroidery_app.embroidery.planner import plan
from embroidery_app.embroidery.optimizer import optimize,travel
from embroidery_app.embroidery.engine import digitize
from embroidery_app.embroidery.validation import validate
from embroidery_app.exporters.dst import export_dst


def test_vector_hole_and_disconnected():
    image=np.zeros((100,100,3),np.uint8)
    mask=np.zeros((100,100),np.uint8)
    mask[5:70,5:70]=255
    mask[20:50,20:50]=0
    mask[80:95,80:95]=255
    regions=vectorize(image,mask,90,90,1)
    assert len(regions)==2
    assert sum(len(p.interiors) for p,c in regions)==1
    assert all(p.is_valid for p,c in regions)
    assert sum(p.area for p,c in regions)==pytest.approx(3550,rel=0.06)


@pytest.mark.parametrize("angle",[0,25,90,145])
@pytest.mark.parametrize("poly",[box(0,0,20,20),
    Polygon([(0,0),(20,0),(20,5),(5,5),(5,20),(0,20)]),
    Polygon([(0,0),(20,0),(20,20),(0,20)],holes=[[(5,5),(15,5),(15,15),(5,15)]])])
def test_fill_containment(poly,angle):
    path=tatami(poly,0.4,3,angle)
    assert len(path)>30
    for a,b in zip(path,path[1:]):
        if b.command==Command.STITCH:
            line=LineString([(a.x,a.y),(b.x,b.y)])
            assert poly.buffer(1e-6).covers(line)
            assert line.length<=3.00001


def test_satin_two_rails():
    poly=box(0,0,2,30)
    obj=plan([(poly,"#000000")],length=4)[0]
    assert obj.stitch_type==StitchType.SATIN
    path=satin(poly,0.4,4,obj.angle)
    xs=[s.x for s in path]
    assert min(xs)==pytest.approx(0)
    assert max(xs)==pytest.approx(2)
    assert all(abs(a.x-b.x)==pytest.approx(2) for a,b in zip(path,path[1:]))
    assert len(path)>60


def test_planner_fallback_and_outline():
    assert plan([(box(0,0,10,10),"#000000")])[0].stitch_type==StitchType.TATAMI
    assert plan([(box(0,0,0.4,20),"#000000")])[0].stitch_type==StitchType.RUNNING
    assert plan([(box(0,0,10,10),"#000000")],mode="Outline")[0].stitch_type==StitchType.RUNNING


def test_optimizer():
    blocks=[]
    for i,x in enumerate([80,10,50,20]):
        obj=EmbroideryObject(str(i),box(x,0,x+1,1),"#000000")
        blocks.append((obj,[Stitch(x,0,Command.JUMP),Stitch(x+1,0)]))
    ordered=optimize(blocks)
    assert travel(ordered)["jump_distance_mm"]<travel(blocks)["jump_distance_mm"]
    assert {o.id for o,p in ordered}=={o.id for o,p in blocks}


from embroidery_app.examples import fixture


@pytest.mark.parametrize("index",range(10))
def test_logo_end_to_end(index,tmp_path):
    image,mask=fixture(index)
    design,metrics=digitize(image,mask,80,60,colors=3,angle=25,length=4)
    errors,warnings=validate(design,4)
    assert not errors
    assert design.objects
    assert 1<=len(design.thread_colors)<=3
    assert export_dst(design,tmp_path/f"logo-{index}.dst")["stitches"]>0


def test_dense_and_long_validation():
    from embroidery_app.embroidery.models import EmbroideryDesign
    obj=EmbroideryObject("dense",box(0,0,10,10),"#000000",density=0.15)
    design=EmbroideryDesign(10,10,objects=[obj],stitches=[Stitch(0,0,Command.JUMP),Stitch(10,10)])
    errors,warnings=validate(design,3)
    assert any("maximum" in e for e in errors)
    assert any("dense" in w for w in warnings)


def test_digitize_reports_monotonic_progress():
    image,mask=fixture(0)
    updates=[]
    design,metrics=digitize(image,mask,80,60,colors=2,length=4,
                            progress=lambda fraction,message:updates.append((fraction,message)))
    assert design.stitches
    assert metrics["after"]["jumps"] >= 0
    assert updates[0][0] > 0
    assert updates[-1] == (1.0,"Digitizing complete")
    assert all(a[0] <= b[0] for a,b in zip(updates,updates[1:]))
    assert any("Generating stitches" in message for _,message in updates)


def test_fill_reports_rows_and_can_cancel():
    updates=[]
    path=tatami(box(0,0,30,30),0.4,3,25,
                progress=lambda fraction,message:updates.append((fraction,message)))
    assert path and len(updates)>10
    assert updates[-1][0]==pytest.approx(1)
    assert updates[-1][1].startswith('fill row')
    cancelled=[]
    with pytest.raises(DigitizeCancelled):
        tatami(box(0,0,30,30),0.4,3,25,
               progress=lambda fraction,message:cancelled.append(fraction),
               cancel_check=lambda:len(cancelled)>=3)
