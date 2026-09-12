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
