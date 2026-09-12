import os
os.environ.setdefault("QT_QPA_PLATFORM","offscreen")
import numpy as np
from PIL import Image
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt,QPoint
from PySide6.QtTest import QTest
from embroidery_app.ui.image_canvas import ImageCanvas


def test_selection_tools(tmp_path):
    app=QApplication.instance() or QApplication([])
    file=tmp_path/"image.png"
    Image.new("RGB",(100,100),"white").save(file)
    canvas=ImageCanvas()
    canvas.resize(500,500)
    canvas.show()
    canvas.load(file)
    app.processEvents()
    def point(x,y):
        return canvas.mapFromScene(x,y)
    QTest.mousePress(canvas.viewport(),Qt.LeftButton,pos=point(10,10))
    QTest.mouseRelease(canvas.viewport(),Qt.LeftButton,pos=point(60,60))
    assert canvas.mask[30,30]==255 and canvas.mask[80,80]==0
    canvas.set_tool("Brush")
    canvas.subtract=True
    QTest.mouseClick(canvas.viewport(),Qt.LeftButton,pos=point(30,30))
    assert canvas.mask[30,30]==0
    canvas.set_tool("Polygon")
    canvas.subtract=False
    for p in [(70,70),(90,70),(90,90)]:
        QTest.mouseClick(canvas.viewport(),Qt.LeftButton,pos=point(*p))
    QTest.mouseClick(canvas.viewport(),Qt.RightButton,pos=point(90,90))
    assert canvas.mask[75,85]==255
    output=tmp_path/"mask.png"
    canvas.export_mask(output)
    assert np.array_equal(np.array(Image.open(output)),canvas.mask)
    canvas.clear_selection()
    assert not canvas.mask.any()
    canvas.set_tool("Color region")
    QTest.mouseClick(canvas.viewport(),Qt.LeftButton,pos=point(20,20))
    assert canvas.mask.all()
    canvas.close()


def test_full_desktop_workflow(tmp_path,monkeypatch):
    from embroidery_app.ui.main_window import MainWindow
    from PySide6.QtWidgets import QFileDialog,QMessageBox
    from embroidery_app.exporters.dst import export_dst
    from PIL import ImageDraw
    app=QApplication.instance() or QApplication([])
    source=tmp_path/"logo.png"
    im=Image.new("RGB",(220,180),"#f9f8f2")
    draw=ImageDraw.Draw(im)
    draw.ellipse((20,20,160,160),fill="#147d92")
    draw.ellipse((60,60,120,120),fill="#f9f8f2")
    draw.rectangle((175,40,185,145),fill="#c96b3c")
    im.save(source)
    window=MainWindow()
    window.show()
    app.processEvents()
    monkeypatch.setattr(QFileDialog,"getOpenFileName",lambda *a,**k:(str(source),""))
    window.open_image()
    window.tools.setCurrentText("Color region")
    for x,y in [(40,90),(180,90)]:
        QTest.mouseClick(window.canvas.viewport(),Qt.LeftButton,pos=window.canvas.mapFromScene(x,y))
    assert window.canvas.mask[90,90]==0
    window.generate_button.click()
    from PySide6.QtCore import QEventLoop,QTimer
    loop=QEventLoop()
    window.thread.finished.connect(loop.quit)
    QTimer.singleShot(30000,loop.quit)
    loop.exec()
    app.processEvents()
    assert window.thread is None
    assert window.design is not None
    assert window.export_button.isEnabled()
    assert window.progress_bar.value()==100
    assert "complete" in window.estimate_label.text().lower()
    assert len(window.design.thread_colors)==2
    output=tmp_path/"desktop.dst"
    monkeypatch.setattr(QFileDialog,"getSaveFileName",lambda *a,**k:(str(output),""))
    monkeypatch.setattr(QMessageBox,"information",lambda *a,**k:QMessageBox.Ok)
    monkeypatch.setattr(QMessageBox,"warning",lambda *a,**k:QMessageBox.Yes)
    window.export_button.click()
    assert output.exists()
    window.preview.layers["polygons"]=True
    window.preview.layers["order"]=True
    window.preview.display(window.design)
    app.processEvents()
    from pathlib import Path
    Path("examples").mkdir(exist_ok=True)
    window.grab().save("examples/workflow-preview.png")
    window.width.setValue(90)
    assert not window.export_button.isEnabled()
    window.close()


def test_layer_desktop_workflow(tmp_path,monkeypatch):
    from embroidery_app.ui.main_window import MainWindow
    from PySide6.QtWidgets import QFileDialog,QMessageBox
    from PySide6.QtCore import QEventLoop,QTimer
    from test_layers import character_fixture
    from embroidery_app.project import load_project
    app=QApplication.instance() or QApplication([])
    image,_,_,_=character_fixture()
    source=tmp_path/'character.png'; Image.fromarray(image).save(source)
    window=MainWindow(); window.show(); app.processEvents()
    monkeypatch.setattr(QMessageBox,'question',lambda *a,**k:QMessageBox.Yes)
    monkeypatch.setattr(QMessageBox,'information',lambda *a,**k:QMessageBox.Ok)
    monkeypatch.setattr(QMessageBox,'warning',lambda *a,**k:QMessageBox.Yes)
    monkeypatch.setattr(QFileDialog,'getOpenFileName',lambda *a,**k:(str(source),''))
    window.open_image()
    window.colors.setValue(3); window.min_part.setValue(15)

    def wait_for_worker():
        loop=QEventLoop()
        window.thread.finished.connect(loop.quit)
        QTimer.singleShot(20000,loop.quit)
        loop.exec(); app.processEvents()
        assert window.thread is None

    window.separate(); wait_for_worker()
    assert window.document is not None
    assert len(window.document.layers)>=5
    assert not window.document.foreground[0,0]
    assert not window.export_button.isEnabled()
    eye=next(i for i,p in enumerate(window.document.layers) if p.mask[115,92])
    window.layer_panel.list.setCurrentRow(eye)
    assert np.array_equal(window.canvas.mask,window.document.layers[eye].mask)
    window.layer_panel.list.item(eye).setText('Left eye')
    assert window.document.layers[eye].name=='Left eye'
    size=(window.width.value(),window.height.value())
    window.tools.setCurrentText('Brush'); window.canvas.brush_size=4
    window.subtract.setChecked(True)
    QTest.mouseClick(window.canvas.viewport(),Qt.LeftButton,pos=window.canvas.mapFromScene(92,115))
    assert not window.document.layers[eye].mask[115,92]
    window.layer_action('undo')
    assert window.document.layers[eye].mask[115,92]
    assert (window.width.value(),window.height.value())==size
    window.layer_action('up')
    assert window.document.layers[eye-1].name=='Left eye'
    # Disable a part through the checkbox and keep user ordering through export.
    window.layer_panel.list.item(0).setCheckState(Qt.Unchecked)
    hidden=window.document.layers[0].id
    window.generate(); wait_for_worker()
    assert window.design and window.progress_bar.value()==100
    assert window.export_button.isEnabled()
    assert hidden not in {o.layer_id for o in window.design.objects}
    path=tmp_path/'editable.stitchforge'
    monkeypatch.setattr(QFileDialog,'getSaveFileName',lambda *a,**k:(str(path),''))
    window.save_layer_project()
    assert path.exists() and not window.project_dirty
    _,_,saved,_=load_project(path)
    assert any(p.name=='Left eye' for p in saved.layers)
    monkeypatch.setattr(QFileDialog,'getOpenFileName',lambda *a,**k:(str(path),''))
    window.open_layer_project()
    assert not window.project_dirty and not window.export_button.isEnabled()
    window.generate(); wait_for_worker()
    dst=tmp_path/'layer-output.dst'
    monkeypatch.setattr(QFileDialog,'getSaveFileName',lambda *a,**k:(str(dst),''))
    window.export_button.click()
    assert dst.exists()
    window.project_dirty=False
    window.close()
