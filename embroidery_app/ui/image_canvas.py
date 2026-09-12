import cv2
import numpy as np
from PIL import Image, ImageOps
from PySide6.QtWidgets import QGraphicsView, QGraphicsScene
from PySide6.QtGui import QImage,QPixmap,QColor,QPen,QPainterPath
from PySide6.QtCore import Qt,Signal


class ImageCanvas(QGraphicsView):
    mask_changed = Signal()
    edit_started = Signal()
    layer_picked = Signal(int,int)

    def __init__(self):
        super().__init__()
        self.setScene(QGraphicsScene(self))
        self.setBackgroundBrush(QColor("#e9e9e4"))
        self.image = None
        self.mask = None
        self.tool = "Rectangle"
        self.subtract = False
        self.brush_size = 16
        self.points = []
        self.start = None
        self.last = None
        self.overlay = None
        self.rubber = None
        self.base = None
        self.overlay_color = (25,180,170)
        self.setMouseTracking(True)
        self.setTransformationAnchor(QGraphicsView.AnchorUnderMouse)

    def load(self,path):
        with Image.open(path) as source:
            source = ImageOps.exif_transpose(source).convert("RGBA")
            # Bound CPU and memory for interactive processing.
            source.thumbnail((1600,1600))
            rgba = np.array(source)
        self.load_array(rgba)

    def load_array(self,rgba):
        self.alpha = rgba[:,:,3].copy()
        self.image = rgba[:,:,:3].copy()
        self.mask = np.zeros(self.image.shape[:2],np.uint8)
        self.scene().clear()
        self.points = []
        self.rubber = None
        h,w = self.mask.shape
        qimage = QImage(rgba.data,w,h,rgba.strides[0],QImage.Format_RGBA8888).copy()
        self.base = self.scene().addPixmap(QPixmap.fromImage(qimage))
        self.overlay = self.scene().addPixmap(QPixmap())
        self.overlay.setZValue(1)
        self.scene().setSceneRect(0,0,w,h)
        self.fit()
        self.mask_changed.emit()

    def display_pixels(self, rgb=None):
        if self.image is None:
            return
        rgba=np.ascontiguousarray(np.dstack((self.image if rgb is None else rgb, self.alpha)))
        h,w=rgba.shape[:2]
        self.base.setPixmap(QPixmap.fromImage(QImage(rgba.data,w,h,rgba.strides[0],QImage.Format_RGBA8888).copy()))

    def set_mask(self,mask):
        self.mask=mask.copy()
        self.points=[]
        self.start=self.last=None
        self.clear_rubber()
        self.update_overlay(emit=False)

    def fit(self):
        self.fitInView(self.sceneRect(),Qt.KeepAspectRatio)

    def reset(self):
        self.resetTransform()
        self.centerOn(self.sceneRect().center())

    def set_tool(self,tool):
        self.tool = tool
        self.points=[]
        self.clear_rubber()
        self.setDragMode(QGraphicsView.ScrollHandDrag if tool=="Pan" else QGraphicsView.NoDrag)

    def clear_rubber(self):
        if self.rubber is not None:
            self.scene().removeItem(self.rubber)
            self.rubber = None

    def update_overlay(self,emit=True):
        if self.mask is None:
            return
        self.mask[self.alpha==0]=0
        h,w = self.mask.shape
        rgba = np.zeros((h,w,4),np.uint8)
        rgba[:,:,:3]=self.overlay_color
        rgba[:,:,3]=np.where(self.mask>0,105,0)
        qimage=QImage(rgba.data,w,h,rgba.strides[0],QImage.Format_RGBA8888).copy()
        self.overlay.setPixmap(QPixmap.fromImage(qimage))
        if emit:
            self.mask_changed.emit()

    def clear_selection(self):
        if self.mask is not None:
            self.edit_started.emit()
            self.mask.fill(0)
            self.points=[]
            self.clear_rubber()
            self.update_overlay()

    def select_all(self):
        if self.mask is not None:
            self.edit_started.emit()
            self.mask[:]=255
            self.update_overlay()

    def clean(self):
        if self.mask is not None:
            self.edit_started.emit()
            kernel=np.ones((3,3),np.uint8)
            self.mask=cv2.morphologyEx(self.mask,cv2.MORPH_OPEN,kernel)
            self.mask=cv2.morphologyEx(self.mask,cv2.MORPH_CLOSE,kernel)
            self.update_overlay()

    def export_mask(self,path):
        if self.mask is None:
            raise ValueError("Open an image first")
        Image.fromarray(self.mask).save(path)

    def pos(self,event):
        p=self.mapToScene(event.position().toPoint())
        h,w=self.mask.shape
        return (int(np.clip(p.x(),0,w-1)),int(np.clip(p.y(),0,h-1)))

    def draw_brush(self,a,b):
        cv2.line(self.mask,a,b,0 if self.subtract else 255,self.brush_size)
        cv2.circle(self.mask,b,max(1,self.brush_size//2),0 if self.subtract else 255,-1)
        self.update_overlay()

    def mousePressEvent(self,event):
        if self.image is None or self.tool=="Pan":
            return super().mousePressEvent(event)
        if event.button()==Qt.RightButton:
            self.finish_polygon()
            return
        if event.button()!=Qt.LeftButton:
            return
        p=self.pos(event)
        if self.tool=="Pick layer":
            self.layer_picked.emit(*p)
            return
        if self.tool!="Polygon" or not self.points:
            self.edit_started.emit()
        if self.tool=="Polygon":
            self.points.append(p)
            self.show_polygon()
        elif self.tool=="Brush":
            self.last=p
            self.draw_brush(p,p)
        elif self.tool=="Color region":
            flood=np.zeros((self.mask.shape[0]+2,self.mask.shape[1]+2),np.uint8)
            cv2.floodFill(self.image.copy(),flood,p,(0,0,0),(20,20,20),(20,20,20),
                          4 | cv2.FLOODFILL_MASK_ONLY | cv2.FLOODFILL_FIXED_RANGE | (255<<8))
            self.mask[flood[1:-1,1:-1]>0]=0 if self.subtract else 255
            self.update_overlay()
        else:
            self.start=p

    def show_polygon(self):
        self.clear_rubber()
        if self.points:
            path=QPainterPath()
            path.moveTo(*self.points[0])
            for p in self.points[1:]:
                path.lineTo(*p)
            self.rubber=self.scene().addPath(path,QPen(QColor("#e45a32"),2))
            self.rubber.setZValue(2)

    def finish_polygon(self):
        if len(self.points)>=3:
            cv2.fillPoly(self.mask,[np.array(self.points,np.int32)],0 if self.subtract else 255)
            self.update_overlay()
        self.points=[]
        self.clear_rubber()

    def mouseDoubleClickEvent(self,event):
        if self.tool=="Polygon" and self.image is not None:
            self.finish_polygon()
        else:
            super().mouseDoubleClickEvent(event)

    def mouseMoveEvent(self,event):
        if self.image is None or self.tool=="Pan":
            return super().mouseMoveEvent(event)
        p=self.pos(event)
        if self.tool=="Brush" and self.last is not None and event.buttons() & Qt.LeftButton:
            self.draw_brush(self.last,p)
            self.last=p
        elif self.tool=="Rectangle" and self.start is not None:
            self.clear_rubber()
            x,y=self.start
            self.rubber=self.scene().addRect(min(x,p[0]),min(y,p[1]),abs(x-p[0]),abs(y-p[1]),
                                            QPen(QColor("#e45a32"),2))
            self.rubber.setZValue(2)

    def mouseReleaseEvent(self,event):
        if self.image is None or self.tool=="Pan":
            return super().mouseReleaseEvent(event)
        if event.button()==Qt.LeftButton and self.start is not None:
            cv2.rectangle(self.mask,self.start,self.pos(event),0 if self.subtract else 255,-1)
            self.start=None
            self.clear_rubber()
            self.update_overlay()
        self.last=None

    def wheelEvent(self,event):
        factor=1.2 if event.angleDelta().y()>0 else 1/1.2
        if 0.03 < self.transform().m11()*factor < 60:
            self.scale(factor,factor)
