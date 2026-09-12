import zipfile
import numpy as np
from embroidery_app.image_processing.layers import ArtworkLayer,LayerDocument
from embroidery_app.exporters.emb import export_emb
from embroidery_app.project import load_project


def test_threadform_emb_roundtrip(tmp_path):
    image=np.full((40,60,3),240,np.uint8)
    mask=np.zeros((40,60),np.uint8); mask[8:30,12:45]=255
    detail=np.zeros_like(mask); detail[14:20,22:29]=255
    body=mask.copy(); body[detail>0]=0
    document=LayerDocument(mask,[
        ArtworkLayer('Body','#aa6633',body),
        ArtworkLayer('Detail','#221100',detail.copy(),protect_details=True),
    ])
    path=tmp_path/'design.emb'
    report=export_emb(image,np.full(mask.shape,255,np.uint8),document,{'width':80},path)
    assert path.exists() and report['parts']==2
    with zipfile.ZipFile(path) as archive:
        assert 'project.json' in archive.namelist()
        assert '"format": "threadform-emb"' in archive.read('project.json').decode()
    loaded_image,loaded_alpha,restored,settings=load_project(path)
    assert np.array_equal(loaded_image,image)
    assert np.array_equal(loaded_alpha,np.full(mask.shape,255,np.uint8))
    assert settings['width']==80
    assert [layer.name for layer in restored.layers]==['Body','Detail']
    assert np.array_equal(restored.layers[1].mask,detail)
