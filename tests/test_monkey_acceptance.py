"""Private user-image acceptance; set STITCHFORGE_MONKEY_IMAGE to run locally.

The user source and its derived artifacts are never checked into the repository.
"""
import os
from pathlib import Path
import numpy as np
from PIL import Image
import pytest
import pyembroidery as pe
from embroidery_app.image_processing.segmentation import separate_layers
from embroidery_app.embroidery.engine import digitize
from embroidery_app.exporters.dst import export_dst


@pytest.mark.skipif(not os.environ.get('STITCHFORGE_MONKEY_IMAGE'),reason='Private acceptance image not configured')
def test_user_monkey_features_survive_dst(tmp_path):
    path=Path(os.environ['STITCHFORGE_MONKEY_IMAGE'])
    with Image.open(path) as source:
        image=np.array(source.convert('RGB').resize((1024,1024)))
    document=separate_layers(image,colors=4)
    assert not document.foreground[15,15]
    assert not document.foreground[125,538]  # background inside hanging loop
    indices=[]
    for x,y in [(324,480),(520,490),(400,808)]:
        index=next(i for i,p in enumerate(document.layers) if p.mask[y,x])
        assert document.layers[index].protect_details
        indices.append(index)
    assert len(set(indices))==3  # two eyes and the smile are independently editable
    ys,xs=np.nonzero(document.foreground)
    width=80; height=width*(ys.max()-ys.min()+1)/(xs.max()-xs.min()+1)
    design,metrics=digitize(image,document.foreground,width=width,height=height,
                           length=4,angle=25,layer_document=document)
    assert not metrics['omitted_layers']
    assert len(design.thread_colors)==4
    report=export_dst(design,tmp_path/'monkey.dst')
    assert report['stitches']>1000
    restored=pe.read_dst(str(tmp_path/'monkey.dst'))
    color_index=0; dark_points=[]
    dark_colors={p.color for p in document.layers if p.protect_details}
    for x,y,command in restored.stitches:
        command &= pe.COMMAND_MASK
        if command==pe.COLOR_CHANGE:
            color_index+=1
        elif command==pe.STITCH and design.thread_colors[color_index] in dark_colors:
            dark_points.append((x/10,y/10))
    dark_points=np.array(dark_points)
    for x,y in [(324,480),(520,490),(400,808)]:
        expected=np.array([(x-xs.min())*width/(xs.max()-xs.min()+1),
                           (y-ys.min())*height/(ys.max()-ys.min()+1)])
        assert np.min(np.linalg.norm(dark_points-expected,axis=1))<2.0
