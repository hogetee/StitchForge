import numpy as np
import pytest
from PIL import Image,ImageDraw
from embroidery_app.image_processing.segmentation import separate_layers,extract_foreground
from embroidery_app.image_processing.layers import LayerDocument,ArtworkLayer
from embroidery_app.embroidery.engine import digitize
from embroidery_app.embroidery.models import Command
from embroidery_app.exporters.dst import export_dst
from embroidery_app.project import save_project,load_project


def character_fixture():
    image=Image.new('RGB',(256,256),'#f9ecd0')
    fg=Image.new('L',image.size,0)
    draw=ImageDraw.Draw(image); selection=ImageDraw.Draw(fg)
    for rect in [(25,95,65,165),(190,95,230,165),(45,20,210,230)]:
        draw.ellipse(rect,fill='#94612d'); selection.ellipse(rect,fill=255)
    draw.ellipse((65,75,190,205),fill='#e6b25e')
    eyes=Image.new('L',image.size,0); eye_draw=ImageDraw.Draw(eyes)
    for rect in [(85,105,102,130),(150,105,167,130)]:
        draw.ellipse(rect,fill='#261604'); eye_draw.ellipse(rect,fill=255)
    draw.ellipse((113,140,140,160),fill='#94612d')
    mouth=Image.new('L',image.size,0)
    draw.arc((85,140,170,190),0,180,fill='#261604',width=4)
    ImageDraw.Draw(mouth).arc((85,140,170,190),0,180,fill=255,width=4)
    array=np.array(image).astype(np.int16)
    noise=np.random.default_rng(7).normal(0,4,array.shape[:2])[...,None]
    array=np.clip(array+noise,0,255).astype(np.uint8)
    return array,np.array(fg),np.array(eyes),np.array(mouth)


def test_foreground_and_small_details_preserved():
    image,truth,eyes,mouth=character_fixture()
    document=separate_layers(image,colors=3,min_pixels=15)
    a,b=document.foreground>0,truth>0
    assert np.count_nonzero(a&b)/np.count_nonzero(a|b)>0.97
    assert not document.foreground[0,0]
    dark=[layer for layer in document.layers if layer.protect_details]
    combined=np.logical_or.reduce([layer.mask>0 for layer in dark])
    assert np.mean(combined[eyes>0])>0.93
    assert np.mean(combined[mouth>0])>0.85
    eye_layers=[next(i for i,p in enumerate(document.layers) if p.mask[115,x]) for x in (92,158)]
    assert eye_layers[0]!=eye_layers[1]
    assert max(np.sum([p.mask>0 for p in document.layers],axis=0).ravel())==1
    assert np.array_equal(document.enabled_mask(),document.foreground)
    second=separate_layers(image,colors=3,min_pixels=15)
    assert np.array_equal(document.render(image),second.render(image))


def test_foreground_respects_alpha_and_selection():
    image,fg,_,_=character_fixture()
    selection=np.zeros_like(fg); selection[:,:130]=255
    result=extract_foreground(image,selection,fg)
    assert np.array_equal(result,fg&selection)
    document=separate_layers(image,fg,remove_background=False,colors=3,min_pixels=10)
    assert np.array_equal(document.foreground,fg)
    with pytest.raises(ValueError,match='foreground'):
        extract_foreground(np.full((30,30,3),255,np.uint8))


def small_document():
    image=np.full((100,120,3),240,np.uint8)
    left=np.zeros((100,120),np.uint8); left[20:70,10:40]=255
    right=np.zeros_like(left); right[20:70,80:110]=255
    doc=LayerDocument(left|right,[ArtworkLayer('Left','#aa6633',left),ArtworkLayer('Right','#221100',right)])
    return image,doc


def test_layers_common_coordinates_hidden_and_order(tmp_path):
    image,doc=small_document()
    design,_=digitize(image,doc.foreground,width=100,height=50,layer_document=doc)
    left,right=design.objects
    assert left.geometry.bounds[0]<1
    assert right.geometry.bounds[0]>69
    assert right.geometry.bounds[2]<=100
    assert [o.layer_name for o in design.objects]==['Left','Right']
    report=export_dst(design,tmp_path/'parts.dst')
    assert report['stitches']>0
    doc.layers.reverse()
    reordered,_=digitize(image,doc.foreground,width=100,height=50,layer_document=doc)
    assert [o.layer_name for o in reordered.objects]==['Right','Left']
    doc.layers[1].enabled=False
    hidden,_=digitize(image,doc.foreground,width=100,height=50,layer_document=doc)
    assert all(o.layer_name=='Right' for o in hidden.objects)
    assert hidden.objects[0].geometry.bounds[0]>69  # hiding does not rescale/shift parts
    doc.layers[0].enabled=False
    with pytest.raises(ValueError,match='enabled'):
        digitize(image,doc.foreground,layer_document=doc)


def test_layer_render_can_inspect_one_part_even_when_disabled():
    image,doc=small_document()
    doc.layers[1].enabled=False
    all_view=doc.render(image)
    solo_view=doc.render(image,only={1})
    assert np.array_equal(all_view[30,20],np.array([170,102,51],np.uint8))
    assert np.array_equal(all_view[30,90],np.array([245,245,245],np.uint8))
    assert np.array_equal(solo_view[30,90],np.array([34,17,0],np.uint8))
    assert np.array_equal(solo_view[30,20],np.array([245,245,245],np.uint8))


def test_paint_claims_pixels_and_project_roundtrip(tmp_path):
    image,doc=small_document()
    original=doc.copy()
    painted=doc.layers[0].mask.copy(); painted[25:30,85:90]=255
    doc.replace_mask(0,painted)
    assert doc.layers[0].mask[27,87] and not doc.layers[1].mask[27,87]
    assert original.layers[1].mask[27,87]
    doc.layers[1].enabled=False
    doc.layers[0].name='ตาซ้าย'; doc.layers[0].angle=70
    alpha=np.full(image.shape[:2],255,np.uint8)
    path=tmp_path/'editable.stitchforge'
    save_project(path,image,alpha,doc,{'width':80,'height':40,'maintain_aspect':False})
    loaded,loaded_alpha,restored,settings=load_project(path)
    assert np.array_equal(loaded,image) and np.array_equal(loaded_alpha,alpha)
    assert np.array_equal(restored.foreground,doc.foreground)
    assert settings['maintain_aspect'] is False
    for a,b in zip(doc.layers,restored.layers):
        assert (a.id,a.name,a.enabled,a.color,a.angle)==(b.id,b.name,b.enabled,b.color,b.angle)
        assert np.array_equal(a.mask,b.mask)
    export_dst(digitize(loaded,restored.foreground,layer_document=restored)[0],tmp_path/'reopened.dst')


def test_saved_project_rejects_overlap(tmp_path):
    image,doc=small_document()
    doc.layers[1].mask=doc.layers[0].mask.copy()
    path=tmp_path/'invalid.stitchforge'
    save_project(path,image,np.full(image.shape[:2],255,np.uint8),doc,{})
    with pytest.raises(ValueError,match='overlap'):
        load_project(path)


def test_layer_direction_and_detail_filter():
    image,doc=small_document()
    doc.layers[0].mode='Fill'; doc.layers[0].angle=90
    doc.layers[1].mode='Outline'; doc.layers[1].protect_details=True
    design,_=digitize(image,doc.foreground,width=100,height=50,min_area=100,layer_document=doc)
    assert design.objects[0].angle==90
    assert design.objects[1].stitch_type.value=='RUNNING'
