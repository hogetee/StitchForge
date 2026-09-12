from PySide6.QtWidgets import QGraphicsView, QGraphicsScene
from PySide6.QtGui import QColor, QPen, QPainter,QPainterPath
from PySide6.QtCore import Qt,QTimer,Signal
from math import cos,sin,radians
from embroidery_app.embroidery.models import Command


class StitchPreview(QGraphicsView):
    position_changed=Signal(int)
    def __init__(self):
        super().__init__()
        self.setScene(QGraphicsScene(self))
        self.setRenderHint(QPainter.Antialiasing)
        self.setBackgroundBrush(QColor("#f5f3ed"))
        self.setDragMode(QGraphicsView.ScrollHandDrag)
        self.design = None
        self.layers = dict(stitches=True, jumps=False, polygons=False, order=False,
                           underlay=True,travel=False,trims=False,entries=False,directions=False)
        self.position=1.0
        self.timer=QTimer(self); self.timer.setInterval(100); self.timer.timeout.connect(self.advance)

    def toggle_play(self):
        if self.timer.isActive(): self.timer.stop()
        elif self.design:
            if self.position>=1: self.position=0
            self.timer.start()

    def advance(self):
        self.position=min(1,self.position+0.02)
        self.display(self.design,fit=False)
        self.position_changed.emit(round(self.position*1000))
        if self.position>=1: self.timer.stop()

    def scrub(self,value):
        self.timer.stop(); self.position=value/1000
        if self.design: self.display(self.design,fit=False)

    def display(self, design,fit=True):
        if design is not self.design:
            self.timer.stop(); self.position=1
            self.position_changed.emit(1000)
        self.design = design
        self.scene().clear()
        pen = QPen(QColor("#9caaa9"), 0)
        self.scene().addRect(0,0,design.width_mm,design.height_mm,pen)
        previous, color_index = None, 0
        paths={}
        for s in design.stitches[:int(len(design.stitches)*self.position)]:
            if s.command == Command.COLOR_CHANGE:
                color_index += 1
            if previous and s.command in (Command.STITCH,Command.JUMP):
                jump = s.command == Command.JUMP
                layer='jumps' if jump else 'underlay' if s.phase=='UNDERLAY' else 'travel' if s.phase=='TRAVEL' else 'stitches'
                if self.layers[layer]:
                    color = ('#b1b7bb' if jump else '#518da4' if s.phase=='UNDERLAY' else '#db5596' if s.phase=='TRAVEL'
                             else design.thread_colors[color_index % len(design.thread_colors)] if design.thread_colors else '#333333')
                    key=(color,jump); path=paths.setdefault(key,QPainterPath())
                    path.moveTo(previous.x,previous.y); path.lineTo(s.x,s.y)
            if s.command==Command.TRIM and self.layers['trims']:
                self.scene().addEllipse(s.x-0.3,s.y-0.3,0.6,0.6,QPen(QColor('#c83d30'),0))
            previous = s
        for (color,jump),path in paths.items():
            pen=QPen(QColor(color),0)
            if jump: pen.setStyle(Qt.DashLine)
            self.scene().addPath(path,pen)
        for i,obj in enumerate(design.objects):
            if self.layers["polygons"]:
                for ring in [obj.geometry.exterior,*obj.geometry.interiors]:
                    points = list(ring.coords)
                    for a,b in zip(points,points[1:]):
                        self.scene().addLine(*a,*b,QPen(QColor("#292e37"),0))
            if self.layers["order"]:
                p = obj.geometry.representative_point()
                text = self.scene().addText(f'{i+1} · {obj.role}\n{obj.stitch_type.value} · layer {obj.layer+1}')
                text.setScale(0.2)
                text.setPos(p.x,p.y)
            if self.layers['entries']:
                for point,color in [(obj.entry_point,'#2baf58'),(obj.exit_point,'#d94848')]:
                    if point: self.scene().addEllipse(point[0]-0.4,point[1]-0.4,0.8,0.8,QPen(QColor(color),0))
            if self.layers['directions']:
                p=obj.geometry.representative_point(); a=radians(obj.angle)
                self.scene().addLine(p.x-2*cos(a),p.y-2*sin(a),p.x+2*cos(a),p.y+2*sin(a),QPen(QColor('#bd3997'),0))
                for left,right in list(zip(obj.left_rail,obj.right_rail))[::5]:
                    self.scene().addLine(*left,*right,QPen(QColor('#bd3997'),0))
        bounds=self.scene().itemsBoundingRect().adjusted(-2,-2,2,2)
        self.scene().setSceneRect(bounds)
        if fit: self.fitInView(bounds,Qt.KeepAspectRatio)

    def wheelEvent(self,event):
        factor = 1.2 if event.angleDelta().y()>0 else 1/1.2
        self.scale(factor,factor)
