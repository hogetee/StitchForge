import os
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
from dataclasses import asdict
from time import monotonic
import numpy as np
from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QImage,QPainter
from PySide6.QtCore import Qt
from embroidery_app.ui.main_window import MainWindow
from embroidery_app.project import save_project
from embroidery_app.image_processing.layers import ArtworkLayer,LayerDocument
from embroidery_app.embroidery.profiles import FabricProfile
from embroidery_app.embroidery.engine import digitize


def test_fabric_settings_and_preview_reopen(tmp_path):
    app=QApplication.instance() or QApplication([])
    image=np.full((40,40,3),180,np.uint8); mask=np.zeros((40,40),np.uint8); mask[5:35,5:35]=255
    doc=LayerDocument(mask,[ArtworkLayer('Base','#112233',mask,role='BASE')])
    settings={'fabric':asdict(FabricProfile(name='Custom',pull_compensation_mm=0.45,underlap_mm=0.3)),
              'width':30,'height':30,'auto_direction':False}
    path=tmp_path/'fabric.stitchforge'; save_project(path,image,np.full(mask.shape,255,np.uint8),doc,settings)
    window=MainWindow(); window.restore_project(path)
    assert window.fabric.currentText()=='Custom'
    assert window.compensation.value()==0.45
    assert window.underlap.value()==0.3
    assert not window.auto_direction.isChecked()
    assert window.settings()['fabric']['pull_compensation_mm']==0.45
    design,metrics=digitize(image,mask,layer_document=doc,**settings)
    window.accept_design(design,metrics)
    window.preview.layers['underlay']=False
    window.preview.scrub(500); assert window.preview.position==0.5
    window.preview.toggle_play(); assert window.preview.timer.isActive()
    window.preview.advance(); assert window.preview.position>0.5
    window.preview.toggle_play(); assert not window.preview.timer.isActive()
    window.project_dirty=False; window.close()


def test_grouping_preserves_excluded_parts_and_role():
    app=QApplication.instance() or QApplication([])
    image=np.full((40,40,3),180,np.uint8); a=np.zeros((40,40),np.uint8); a[5:15,5:15]=255
    b=np.zeros_like(a); b[20:30,20:30]=255
    doc=LayerDocument(a|b,[ArtworkLayer('Yes','#112233',a),ArtworkLayer('No','#112233',b,enabled=False,role='DETAIL')])
    window=MainWindow(); window.canvas.load_array(np.dstack((image,np.full(a.shape,255,np.uint8)))); window.accept_layers(doc)
    window.layer_action('group_colors')
    assert len(window.document.layers)==2
    assert np.array_equal(window.document.enabled_mask(),a)
    window.layer_panel.list.setCurrentRow(1); window.show_flat.setChecked(False); window.layer_action('solo')
    assert window.show_flat.isChecked()
    window.project_dirty=False; window.close()


def test_separate_keeps_source_canvas_visible(tmp_path):
    """Segmentation results must repaint the source view on the GUI thread."""
    app=QApplication.instance() or QApplication([])
    image=np.zeros((48,48,3),np.uint8)
    image[:,:24]=(210,120,50)
    image[:,24:]=(55,145,170)
    alpha=np.full((48,48),255,np.uint8)
    window=MainWindow(); window.show()
    window.canvas.load_array(np.dstack((image,alpha)))
    window.remove_bg.setChecked(False)
    window.smoothing.setValue(3)
    window.min_part.setValue(2)
    window.canvas.select_all()
    window.separate()
    deadline=monotonic()+10
    while window.thread is not None and monotonic()<deadline:
        app.processEvents()
    for _ in range(10):
        app.processEvents()
    assert window.document is not None
    rendered=QImage(48,48,QImage.Format_ARGB32)
    rendered.fill(Qt.white)
    painter=QPainter(rendered)
    window.canvas.scene().render(painter)
    painter.end()
    assert rendered.pixelColor(24,24).getRgb() != (255,255,255,255)
    window.project_dirty=False
    window.close()
