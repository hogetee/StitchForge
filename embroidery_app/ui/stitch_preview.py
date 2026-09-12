from PySide6.QtWidgets import QGraphicsView, QGraphicsScene
from PySide6.QtGui import QColor, QPen, QPainter
from PySide6.QtCore import Qt
from embroidery_app.embroidery.models import Command


class StitchPreview(QGraphicsView):
    def __init__(self):
        super().__init__()
        self.setScene(QGraphicsScene(self))
        self.setRenderHint(QPainter.Antialiasing)
        self.setBackgroundBrush(QColor("#f5f3ed"))
        self.setDragMode(QGraphicsView.ScrollHandDrag)
        self.design = None
        self.layers = dict(stitches=True, jumps=True, polygons=False, order=False)

    def display(self, design):
        self.design = design
        self.scene().clear()
        pen = QPen(QColor("#9caaa9"), 0)
        self.scene().addRect(0,0,design.width_mm,design.height_mm,pen)
        previous, color_index = None, 0
        for s in design.stitches:
            if s.command == Command.COLOR_CHANGE:
                color_index += 1
            if previous and s.command in (Command.STITCH,Command.JUMP):
                jump = s.command == Command.JUMP
                if self.layers["jumps" if jump else "stitches"]:
                    color = "#b1b7bb" if jump else design.thread_colors[color_index % len(design.thread_colors)]
                    pen = QPen(QColor(color),0)
                    if jump:
                        pen.setStyle(Qt.DashLine)
                    self.scene().addLine(previous.x,previous.y,s.x,s.y,pen)
            previous = s
        for i,obj in enumerate(design.objects):
            if self.layers["polygons"]:
                for ring in [obj.geometry.exterior,*obj.geometry.interiors]:
                    points = list(ring.coords)
                    for a,b in zip(points,points[1:]):
                        self.scene().addLine(*a,*b,QPen(QColor("#292e37"),0))
            if self.layers["order"]:
                p = obj.geometry.representative_point()
                text = self.scene().addText(str(i+1))
                text.setScale(0.2)
                text.setPos(p.x,p.y)
        bounds=self.scene().itemsBoundingRect().adjusted(-2,-2,2,2)
        self.scene().setSceneRect(bounds)
        self.fitInView(bounds,Qt.KeepAspectRatio)

    def wheelEvent(self,event):
        factor = 1.2 if event.angleDelta().y()>0 else 1/1.2
        self.scale(factor,factor)
