"""Main-window layer actions and background segmentation worker."""
from time import monotonic
from pathlib import Path
import numpy as np
from PySide6.QtCore import QObject, Signal, Slot, QThread
from PySide6.QtWidgets import (QGroupBox,QFormLayout,QCheckBox,QSpinBox,QPushButton,
    QColorDialog,QFileDialog,QMessageBox)
from PySide6.QtGui import QColor
from embroidery_app.image_processing.layers import ArtworkLayer,LayerDocument
from embroidery_app.image_processing.segmentation import separate_layers
from embroidery_app.project import save_project,load_project


class Separator(QObject):
    finished=Signal(object)
    failed=Signal(str)
    progress=Signal(float,str)
    done=Signal()

    def __init__(self,image,mask,alpha,settings):
        super().__init__()
        self.image,self.mask,self.alpha,self.settings=image,mask,alpha,settings

    @Slot()
    def run(self):
        try:
            result=separate_layers(self.image,self.mask,self.alpha,progress=lambda value,message:
                self.progress.emit(value*0.95,'Loading editable layers' if value>=1 else message),**self.settings)
            self.finished.emit(result)
        except Exception as error:
            self.failed.emit(str(error))
        finally:
            self.done.emit()


class LayerWorkflow:
    def segmentation_controls(self):
        group=QGroupBox('2  Separate artwork')
        form=QFormLayout(group)
        self.remove_bg=QCheckBox('Remove background'); self.remove_bg.setChecked(True)
        self.keep_dark=QCheckBox('Preserve dark details'); self.keep_dark.setChecked(True)
        self.smoothing=QSpinBox(); self.smoothing.setRange(3,25); self.smoothing.setValue(11)
        self.min_part=QSpinBox(); self.min_part.setRange(3,5000); self.min_part.setValue(100)
        form.addRow(self.remove_bg); form.addRow(self.keep_dark)
        form.addRow('Texture smoothing',self.smoothing)
        form.addRow('Min part (pixels)',self.min_part)
        button=QPushButton('Separate into layers'); button.clicked.connect(self.separate)
        form.addRow(button)
        button=QPushButton('Edit foreground selection'); button.clicked.connect(self.select_foreground)
        form.addRow(button)
        self.show_flat=QCheckBox('Show simplified layer colors')
        self.show_flat.toggled.connect(self.render_layers)
        form.addRow(self.show_flat)
        return group

    def checkpoint(self):
        if self.document is None:
            return
        self.undo_layers.append((self.document.copy(),self.active_layer))
        self.redo_layers.clear()
        # Keep undo below roughly 96 MB, especially on large multilayer images.
        budget=0
        for i,(document,index) in enumerate(reversed(self.undo_layers)):
            budget+=document.foreground.nbytes+sum(layer.mask.nbytes for layer in document.layers)
            if budget>96_000_000 and i>0:
                self.undo_layers=self.undo_layers[-i:]
                break
        self.undo_layers=self.undo_layers[-20:]

    def reset_layers(self):
        self.document=None; self.active_layer=-1
        self.undo_layers=[]; self.redo_layers=[]
        self.project_dirty=False
        self.layer_panel.refresh(LayerDocument(np.zeros((1,1),np.uint8)))
        self.canvas.overlay_color=(25,180,170)

    def separate(self):
        if self.thread is not None or self.canvas.image is None:
            return
        mask=self.document.foreground if self.document is not None else self.canvas.mask
        mask=mask.copy() if mask is not None and mask.any() else None
        self.checkpoint()
        self.set_busy(True)
        self._progress_started_at=monotonic()
        self.progress_bar.setValue(0)
        self.estimate_label.setText('Separating artwork · estimating time…')
        self.thread=QThread(self)
        self.worker=Separator(self.canvas.image.copy(),mask,self.canvas.alpha.copy(),dict(
            colors=self.colors.value(),remove_background=self.remove_bg.isChecked(),
            smoothing=self.smoothing.value(),min_pixels=self.min_part.value(),preserve_dark=self.keep_dark.isChecked()))
        self.worker.moveToThread(self.thread)
        self.thread.started.connect(self.worker.run)
        self.worker.progress.connect(self.generation_progress)
        self.worker.finished.connect(self.accept_layers)
        self.worker.failed.connect(self.generation_failed)
        self.worker.done.connect(self.thread.quit)
        self.worker.done.connect(self.worker.deleteLater)
        self.thread.finished.connect(self.worker_finished)
        self.thread.finished.connect(self.thread.deleteLater)
        self.thread.start()

    @Slot(object)
    def accept_layers(self,document):
        self.progress_timer.stop()
        self.document=document
        self.project_dirty=True
        self.active_layer=-1
        self.show_flat.setChecked(True)
        self.refresh_layers()
        self.select_foreground()
        self.sidebar_tabs.setCurrentIndex(1)
        self.progress_bar.setValue(100)
        self.estimate_label.setText(f'{len(document.layers)} parts ready · review, then Auto Digitize')
        self.stats.setText(f'{len(document.layers)} editable parts · foreground selection defines the design\nReview colors and masks. Choose a part, rename it, or paint to correct it. Auto Digitize uses checked layers in list order.')
        self.invalidate()

    def refresh_layers(self):
        if self.document is not None:
            self.layer_panel.refresh(self.document,self.active_layer)
            self.render_layers()

    def render_layers(self,*args):
        if self.canvas.image is None:
            return
        flat=(self.document.render(self.canvas.image)
              if self.document is not None and self.show_flat.isChecked() else None)
        self.canvas.display_pixels(flat)
        # Flat colors are useful for judging likeness; do not tint them green.
        self.canvas.overlay.setVisible(not self.show_flat.isChecked() or self.active_layer>=0)

    def select_foreground(self):
        self.active_layer=-1
        if self.document is not None:
            self.canvas.overlay_color=(25,180,170)
            self.canvas.set_mask(self.document.foreground)
            self.layer_panel.refresh(self.document,-1)
            self.render_layers()
        self.tools.setCurrentText('Rectangle')
        self.width_changed()

    def select_layer(self,index):
        if self.document is None or not 0<=index<len(self.document.layers):
            return
        self.active_layer=index
        layer=self.document.layers[index]
        self.canvas.overlay_color=(60,155,215)
        self.canvas.set_mask(layer.mask)
        self.layer_panel.show_settings(self.document,index)
        self.render_layers()
        self.statusBar().showMessage(f'Editing {layer.name} · Brush/Polygon adds or subtracts pixels from this part')

    def pick_layer(self,x,y):
        if self.document is not None:
            for i,layer in enumerate(self.document.layers):
                if layer.mask[y,x]>0:
                    self.layer_panel.list.setCurrentRow(i)
                    self.sidebar_tabs.setCurrentIndex(1)
                    return

    def update_layer_mask(self):
        if self.document is None:
            return
        if 0<=self.active_layer<len(self.document.layers):
            self.document.replace_mask(self.active_layer,self.canvas.mask)
        else:
            self.document.foreground=self.canvas.mask.copy()
            for layer in self.document.layers:
                layer.mask &= self.document.foreground
            assigned=np.zeros_like(self.canvas.mask)
            for layer in self.document.layers:
                assigned|=layer.mask
            extra=(self.canvas.mask>0)&(assigned==0)
            if extra.any():
                pending=next((p for p in self.document.layers if p.name=='Added foreground'),None)
                if pending is None:
                    rgb=np.median(self.canvas.image[extra],axis=0).astype(np.uint8)
                    pending=ArtworkLayer('Added foreground','#'+bytes(rgb).hex(),np.zeros_like(self.canvas.mask))
                    self.document.layers.append(pending)
                pending.mask[extra]=255
        self.project_dirty=True
        self.render_layers()

    def edit_layer(self,index,field,value):
        if self.document is None or not 0<=index<len(self.document.layers):
            return
        self.checkpoint()
        layer=self.document.layers[index]
        if field=='item':
            layer.name=value[0].strip() or 'Unnamed part'; layer.enabled=value[1]
        else:
            setattr(layer,field,value)
        self.project_dirty=True
        self.render_layers()
        self.invalidate()

    def layer_action(self,action):
        if self.document is None:
            return
        index=self.active_layer
        if action in ('undo','redo'):
            stack=self.undo_layers if action=='undo' else self.redo_layers
            other=self.redo_layers if action=='undo' else self.undo_layers
            if stack:
                other.append((self.document.copy(),index))
                self.document,self.active_layer=stack.pop()
            else:
                return
        elif action=='new':
            if len(self.document.layers)>=128:
                QMessageBox.information(self,'Layer limit','Merge or delete parts before adding more.'); return
            self.checkpoint()
            self.document.layers.append(ArtworkLayer('New part','#302519',np.zeros_like(self.canvas.mask),protect_details=True))
            self.active_layer=len(self.document.layers)-1
        elif 0<=index<len(self.document.layers):
            layer=self.document.layers[index]
            if action=='color':
                color=QColorDialog.getColor(QColor(layer.color),self,'Choose thread color')
                if not color.isValid():
                    return
                self.checkpoint(); layer.color=color.name()
            elif action=='delete':
                self.checkpoint(); self.document.layers.pop(index)
                self.active_layer=min(index,len(self.document.layers)-1)
            elif action in ('up','down'):
                destination=index+(-1 if action=='up' else 1)
                if not 0<=destination<len(self.document.layers):
                    return
                self.checkpoint()
                self.document.layers[index],self.document.layers[destination]=self.document.layers[destination],layer
                self.active_layer=destination
            elif action=='merge':
                selected=sorted({self.layer_panel.list.row(item) for item in self.layer_panel.list.selectedItems()})
                if len(selected)<2:
                    self.statusBar().showMessage('Select several parts with Cmd/Ctrl, then Merge'); return
                self.checkpoint()
                merged=ArtworkLayer('Merged parts',layer.color,np.zeros_like(layer.mask),mode=layer.mode,
                                    angle=layer.angle,protect_details=any(self.document.layers[i].protect_details for i in selected))
                for i in selected:
                    merged.mask|=self.document.layers[i].mask
                for i in reversed(selected):
                    self.document.layers.pop(i)
                self.document.layers.insert(selected[0],merged)
                self.active_layer=selected[0]
        else:
            return
        self.project_dirty=True
        self.refresh_layers()
        if self.active_layer>=0:
            self.select_layer(self.active_layer)
        else:
            self.select_foreground()
        self.invalidate()

    def save_layer_project(self):
        if self.document is None:
            QMessageBox.information(self,'No layer project','Separate the artwork into layers first.'); return
        path,_=QFileDialog.getSaveFileName(self,'Save editable project','artwork.stitchforge','StitchForge (*.stitchforge)')
        if path:
            if not path.endswith('.stitchforge'):
                path+='.stitchforge'
            try:
                settings=self.settings() | {'maintain_aspect':self.aspect.isChecked()}
                save_project(path,self.canvas.image,self.canvas.alpha,self.document,settings)
                self.project_dirty=False
                self.statusBar().showMessage(f'Editable layers saved: {Path(path).name}')
            except Exception as error:
                QMessageBox.critical(self,'Could not save project',str(error))

    def confirm_replace_project(self):
        return not self.project_dirty or QMessageBox.question(self,'Unsaved layer edits',
            'Continue without saving these layer edits? Use Save Project to keep an editable copy.',
            QMessageBox.Yes|QMessageBox.No,QMessageBox.No)==QMessageBox.Yes

    def open_layer_project(self):
        path,_=QFileDialog.getOpenFileName(self,'Open editable project','','StitchForge (*.stitchforge)')
        if not path or not self.confirm_replace_project():
            return
        try:
            self.restore_project(path)
        except Exception as error:
            QMessageBox.critical(self,'Could not open project',str(error))

    def restore_project(self,path):
        image,alpha,document,settings=load_project(path)
        self.reset_layers()
        self.canvas.load_array(np.dstack((image,alpha)))
        self.aspect.setChecked(bool(settings.get('maintain_aspect',True)))
        for key,widget in [('width',self.width),('height',self.height),('colors',self.colors),
                           ('spacing',self.spacing),('length',self.length),('angle',self.angle),('min_area',self.minimum)]:
            if key in settings:
                widget.blockSignals(True)
                try:
                    widget.setValue(float(settings[key]) if key!='colors' else int(settings[key]))
                finally:
                    widget.blockSignals(False)
        self.mode.setCurrentText(settings.get('mode','Auto'))
        self.order.setCurrentIndex(1 if settings.get('reverse_colors',False) else 0)
        self.accept_layers(document)
        self.project_dirty=False
