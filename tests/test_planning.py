from dataclasses import replace
from math import cos,sin
import numpy as np
import pytest
from shapely.geometry import box,LineString,Polygon
from embroidery_app.embroidery.models import EmbroideryObject,Command,StitchType
from embroidery_app.embroidery.sequence import dependencies,sequence
from embroidery_app.embroidery.profiles import FabricProfile,get_profile
from embroidery_app.embroidery.planning import prepare
from embroidery_app.embroidery.columns import centerline,rails
from embroidery_app.embroidery.generators.satin import column_stitches
from embroidery_app.embroidery.generators.tatami import tatami
from embroidery_app.embroidery.routing import internal_route,join
from embroidery_app.embroidery.engine import digitize
from embroidery_app.embroidery.validation import validate
from embroidery_app.image_processing.layers import LayerDocument,ArtworkLayer
from embroidery_app.exporters.dst import export_dst
from embroidery_app.project import save_project,load_project


def objects():
    return [EmbroideryObject('base',box(0,0,12,12),'#111111',role='BASE'),
            EmbroideryObject('detail',box(4,4,8,8),'#ffffff',role='DETAIL'),
            EmbroideryObject('outline',box(0,0,12,12),'#111111',role='OUTLINE')]


def test_dependencies_override_color_and_role():
    a,b,c=objects(); b.must_stitch_after=['base']; c.must_stitch_after=['detail']
    ordered=sequence([c,b,a],dependencies([c,b,a]))
    assert [o.id for o in ordered]==['base','detail','outline']
    a.must_stitch_after=['outline']
    with pytest.raises(ValueError,match='Cyclic'): sequence([a,b,c],dependencies([a,b,c]))
    a.must_stitch_after=['missing']
    with pytest.raises(ValueError,match='Unknown'): dependencies([a,b,c])


def test_decomposition_preserves_region_coverage_and_dependencies():
    from shapely.ops import unary_union
    from embroidery_app.embroidery.decomposition import decompose
    shape=box(0,0,10,10).union(box(9,4,21,6)).union(box(20,0,30,10))
    a=EmbroideryObject('source',shape,'#112233',must_stitch_before=['border'])
    b=EmbroideryObject('border',shape,'#112233',role='BORDER')
    parts=decompose([a,b]); children=[o for o in parts if o.parent_object=='source']
    assert len(children)==2
    assert unary_union([o.geometry for o in children]).symmetric_difference(shape).area<1e-6
    assert all((o.id,'border') in dependencies(parts).edges for o in children)


def test_user_layer_order_overrides_role_priority():
    a,b,c=objects(); a.layer=2; b.layer=0; c.layer=1
    assert [o.id for o in sequence([a,b,c],dependencies([a,b,c],True))]==['detail','outline','base']


def test_curved_column_rotates_and_stays_inside():
    poly=LineString([(12+10*cos(a/30),12+10*sin(a/30)) for a in range(45)]).buffer(1)
    c,l,r=rails(poly,centerline(poly),0.4,4)
    obj=EmbroideryObject('curve',poly,'#000000',stitch_length=4,centerline=c,left_rail=l,right_rail=r)
    path=column_stitches(obj)
    assert len(path)>25
    normals=np.array(r)-np.array(l)
    assert abs(np.dot(normals[2]/np.linalg.norm(normals[2]),normals[-3]/np.linalg.norm(normals[-3])))<0.9
    assert all(poly.buffer(1e-6).covers(LineString([(a.x,a.y),(b.x,b.y)])) for a,b in zip(path,path[1:]))


def test_holes_rejected_by_satin_inference():
    poly=box(0,0,10,10).difference(box(3,3,7,7))
    with pytest.raises(ValueError,match='holes'): centerline(poly)


def test_routing_avoids_empty_gaps_and_holes():
    poly=Polygon([(0,0),(12,0),(12,12),(8,12),(8,4),(4,4),(4,12),(0,12)])
    route=internal_route((2,10),(10,10),poly,30)
    assert route and len(route)>2
    assert all(poly.buffer(1e-7).covers(LineString([a,b])) for a,b in zip(route,route[1:]))
    exposed=join((2,10),(10,10),poly,3)
    assert [s.command for s in exposed]==[Command.TRIM,Command.JUMP]
    hidden=join((2,2),(10,2),poly,3)
    assert all(s.command==Command.STITCH for s in hidden)


def test_underlay_then_top_for_each_object_and_dst(tmp_path):
    image=np.full((100,100,3),180,np.uint8)
    a=np.zeros((100,100),np.uint8); a[10:85,10:50]=255
    b=np.zeros_like(a); b[10:85,50:90]=255
    doc=LayerDocument(a|b,[ArtworkLayer('Base','#cc6633',a,role='BASE'),ArtworkLayer('Front','#112233',b)])
    design,metrics=digitize(image,a|b,40,40,length=4,layer_document=doc,fabric='Woven / Cotton')
    assert not validate(design,4)[0]
    assert design.plan and design.plan.graph.edges
    assert metrics['phases']['UNDERLAY']>0 and metrics['phases']['TOP']>0
    for obj in design.objects:
        phases=[s.phase for s in design.stitches if s.object_id==obj.id and s.command==Command.STITCH and s.phase!='TRAVEL']
        assert phases.index('TOP')>0
        assert 'UNDERLAY' not in phases[phases.index('TOP'):]
    assert export_dst(design,tmp_path/'planned.dst')['stitches']>100


def test_stagger_changes_needle_phase_preserves_length():
    poly=box(0,0,12,5)
    path=tatami(poly,0.4,3,0,stagger_period=4)
    rows={}
    for s in path:
        if 0.1<s.x<11.9: rows.setdefault(round(s.y,5),set()).add(round(s.x%3,3))
    assert len({tuple(sorted(v)) for v in rows.values()})>=3
    for a,b in zip(path,path[1:]):
        if b.command==Command.STITCH:
            assert np.hypot(b.x-a.x,b.y-a.y)<=3.00001


def test_compensation_and_underlap_preserve_valid_order():
    a=EmbroideryObject('a',box(2,2,10,14),'#112233',angle_mode='MANUAL')
    b=EmbroideryObject('b',box(10,2,18,14),'#ffffff',layer=1)
    plan=prepare([a,b],FabricProfile(),20,20,True)
    assert a.geometry.area>a.artwork_geometry.area
    assert a.geometry.intersection(b.geometry).area>0
    assert ('a','b') in plan.graph.edges
    assert all(o.geometry.is_valid for o in plan.objects)


def test_profiles_invalid_and_legacy_emb_recovery(tmp_path):
    with pytest.raises(ValueError): get_profile({'pull_compensation_mm':float('nan')})
    image=np.full((10,10,3),150,np.uint8); mask=np.full((10,10),255,np.uint8)
    doc=LayerDocument(mask,[ArtworkLayer('body','#111111',mask,role='BASE')])
    with pytest.raises(ValueError,match='Wilcom'): save_project(tmp_path/'wrong.emb',image,mask,doc,{})
    path=tmp_path/'good.stitchforge'; save_project(path,image,mask,doc,{'fabric':'Denim'})
    path.rename(tmp_path/'old.emb')
    assert load_project(tmp_path/'old.emb')[2].layers[0].role=='BASE'
    native=tmp_path/'native.emb'; native.write_bytes(bytes.fromhex('d0cf11e0a1b11ae1'))
    with pytest.raises(ValueError,match='native Wilcom'): load_project(native)
