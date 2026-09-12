from pathlib import Path
from dataclasses import asdict,replace
from threading import Event
from time import monotonic
import numpy as np
from PySide6.QtWidgets import (QMainWindow,QWidget,QVBoxLayout,QHBoxLayout,QPushButton,
    QLabel,QFileDialog,QMessageBox,QSplitter,QComboBox,QCheckBox,QDoubleSpinBox,
    QSpinBox,QFormLayout,QGroupBox,QApplication,QProgressBar,QTabWidget,QScrollArea,
    QAbstractButton,QAbstractSpinBox,QListWidget,QSlider)
from PySide6.QtCore import QObject,Signal,Slot,QThread,Qt,QTimer
from embroidery_app.ui.image_canvas import ImageCanvas
from embroidery_app.ui.stitch_preview import StitchPreview
from embroidery_app.examples import proof_design
from embroidery_app.exporters.dst import export_dst
from embroidery_app.embroidery.engine import digitize
from embroidery_app.embroidery.validation import validate
from embroidery_app.embroidery.models import Command
from embroidery_app.embroidery.exceptions import DigitizeCancelled
from embroidery_app.ui.layer_panel import LayerPanel
from embroidery_app.ui.layer_workflow import LayerWorkflow
from embroidery_app.embroidery.profiles import PROFILES,get_profile


class Digitizer(QObject):
    finished=Signal(object,object)
    failed=Signal(str)
    progress=Signal(float,str)
    cancelled=Signal()
    done=Signal()

    def __init__(self,image,mask,settings,cancel_event):
        super().__init__()
        self.image,self.mask,self.settings,self.cancel_event=image,mask,settings,cancel_event

    @Slot()
    def run(self):
        try:
            design,metrics=digitize(self.image,self.mask,progress=lambda value,message:
                self.progress.emit(value*0.95,'Preparing stitch preview' if value>=1 else message),
                cancel_check=self.cancel_event.is_set,**self.settings)
            self.finished.emit(design,metrics)
        except DigitizeCancelled:
            self.cancelled.emit()
        except Exception as error:
            self.failed.emit(str(error))
        finally:
            self.done.emit()


class MainWindow(LayerWorkflow,QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Threadform • Local Embroidery")
        self.resize(1380,850)
        self.thread=None
        self.worker=None
        self.design=None
        self.dirty=False
        self.document=None
        self.active_layer=-1
        self.view_only_index=None
        self.undo_layers=[]; self.redo_layers=[]
        self.project_dirty=False
        self._progress_started_at=None
        self._progress_elapsed=0.0
        self.cancel_event=Event()
        self._last_fraction=0.0
        self._last_stage='Preparing artwork'
        self.progress_timer=QTimer(self)
        self.progress_timer.setInterval(250)
        self.progress_timer.timeout.connect(lambda:self.generation_progress(self._last_fraction,self._last_stage))
        self.setStyleSheet("""
            QMainWindow {background:#f1f3f2;}
            QWidget {color:#263c40;}
            QLabel {color:#263c40;}
            QPushButton {padding:7px 12px;border:1px solid #c8d2d0;border-radius:5px;background:#ffffff;color:#233e42;}
            QPushButton:hover {background:#e4efec;}
            QPushButton:disabled {color:#98a29f;}
            QGroupBox {font-weight:600;border:1px solid #d3dcd8;border-radius:6px;margin-top:12px;padding-top:14px;}
            QGroupBox::title {subcontrol-origin:margin;left:12px;}
            QComboBox,QSpinBox,QDoubleSpinBox {padding:5px;min-height:20px;}
            QComboBox,QSpinBox,QDoubleSpinBox,QListWidget {background:#fff;color:#263c40;}
            QTabWidget::pane {border:1px solid #d3dcd8;}
            QTabBar::tab {padding:8px;background:#e4ece8;color:#263c40;}
            QTabBar::tab:selected {background:#fff;}
            QScrollArea,QWidget#layer_page,QWidget#select_page,QWidget#stitch_page {background:#f1f3f2;}
        """)
        root=QWidget()
        self.setCentralWidget(root)
        layout=QVBoxLayout(root)
        title=QLabel("THREADFORM   /   Local embroidery studio")
        title.setStyleSheet("font-size:23px;font-weight:600;padding:14px 4px")
        layout.addWidget(title)
        bar=QHBoxLayout()
        layout.addLayout(bar)
        self.canvas=ImageCanvas()
        self.canvas.mask_changed.connect(self.mask_changed)
        self.canvas.edit_started.connect(self.checkpoint)
        self.canvas.layer_picked.connect(self.pick_layer)
        for label,callback in [("Open Image",self.open_image),("Fit",self.canvas.fit),
                               ("Reset view",self.canvas.reset),("Select all",self.canvas.select_all),
                               ("Clear",self.canvas.clear_selection),("Clean mask",self.canvas.clean),
                               ("Save mask",self.save_mask),("Open Project",self.open_layer_project),
                               ("Save Project",self.save_layer_project)]:
            self.button(bar,label,callback)
        self.proofs=QComboBox()
        self.proofs.addItems(["Load proof…","Square","Circle","Multicolor"])
        self.proofs.activated.connect(self.load_proof)
        bar.addWidget(self.proofs)
        content=QHBoxLayout()
        layout.addLayout(content,1)
        sidebar=QWidget()
        sidebar.setFixedWidth(315)
        side=QVBoxLayout(sidebar)
        content.addWidget(sidebar)
        self.sidebar_tabs=QTabWidget()
        side.addWidget(self.sidebar_tabs,1)
        selection_page=QWidget(); selection_page.setObjectName('select_page'); selection_layout=QVBoxLayout(selection_page)
        selection_scroll=QScrollArea(); selection_scroll.setWidgetResizable(True); selection_scroll.setWidget(selection_page)
        self.sidebar_tabs.addTab(selection_scroll,'Select')
        self.layer_panel=LayerPanel()
        self.layer_panel.setObjectName('layer_page')
        self.layer_panel.selected.connect(self.select_layer)
        self.layer_panel.changed.connect(self.edit_layer)
        self.layer_panel.action.connect(self.layer_action)
        layer_scroll=QScrollArea(); layer_scroll.setWidgetResizable(True); layer_scroll.setWidget(self.layer_panel)
        self.sidebar_tabs.addTab(layer_scroll,'Layers')
        settings_page=QWidget(); settings_page.setObjectName('stitch_page'); settings_layout=QVBoxLayout(settings_page)
        settings_scroll=QScrollArea(); settings_scroll.setWidgetResizable(True); settings_scroll.setWidget(settings_page)
        self.sidebar_tabs.addTab(settings_scroll,'Stitches')
        group=QGroupBox("1  Select artwork")
        form=QFormLayout(group)
        self.tools=QComboBox()
        self.tools.addItems(["Rectangle","Polygon","Brush","Color region","Pick layer","Pan"])
        self.tools.currentTextChanged.connect(self.canvas.set_tool)
        form.addRow("Tool",self.tools)
        self.subtract=QCheckBox("Subtract from selection")
        self.subtract.toggled.connect(lambda v:setattr(self.canvas,"subtract",v))
        form.addRow(self.subtract)
        brush=QSpinBox(); brush.setRange(2,150); brush.setValue(16)
        brush.valueChanged.connect(lambda v:setattr(self.canvas,"brush_size",v))
        form.addRow("Brush size (px)",brush)
        hint=QLabel("Polygon: click vertices, then right-click to finish. Scroll to zoom. Choose Pan to drag the canvas.")
        hint.setWordWrap(True)
        form.addRow(hint)
        selection_layout.addWidget(group)
        selection_layout.addWidget(self.segmentation_controls())
        selection_layout.addStretch()
        group=QGroupBox("Embroidery settings")
        form=QFormLayout(group)
        self.width=self.spin(0.1,300,80," mm")
        self.height=self.spin(0.1,300,60," mm")
        self.aspect=QCheckBox("Maintain selection aspect ratio"); self.aspect.setChecked(True)
        self.colors=QSpinBox(); self.colors.setRange(1,5); self.colors.setValue(4)
        # Palette count belongs to separation; edited layer colors are retained when digitizing.
        palette_form=QFormLayout()
        palette_form.addRow('Separation colors',self.colors)
        selection_layout.insertLayout(1,palette_form)
        self.spacing=self.spin(0.15,2,0.4," mm",0.05)
        self.length=self.spin(0.5,10,4," mm",0.5)
        self.angle=self.spin(0,179,25,"°",5)
        self.minimum=self.spin(0.01,50,0.3," mm²",0.1)
        self.mode=QComboBox(); self.mode.addItems(["Auto","Outline","Fill"])
        self.order=QComboBox(); self.order.addItems(["Palette order","Reverse palette"])
        self.order.setEnabled(False)
        self.fabric=QComboBox(); self.fabric.addItems([*PROFILES,'Legacy / no planning'])
        self.compensation=self.spin(0,2,0.2,' mm',0.05)
        self.underlap=self.spin(0,2,0.2,' mm',0.05)
        self.underlay_enabled=QCheckBox('Generate underlay'); self.underlay_enabled.setChecked(True)
        self.underlay_spacing=self.spin(0.15,10,2,' mm',0.1)
        self.stagger=QSpinBox(); self.stagger.setRange(1,16); self.stagger.setValue(4)
        self.auto_direction=QCheckBox('Plan direction per object'); self.auto_direction.setChecked(True)
        form.addRow('Fabric',self.fabric)
        form.addRow('Pull compensation',self.compensation)
        form.addRow('Underlap',self.underlap)
        form.addRow(self.underlay_enabled)
        form.addRow('Underlay spacing',self.underlay_spacing)
        form.addRow('Stagger cycle',self.stagger)
        form.addRow(self.auto_direction)
        self.fabric.currentTextChanged.connect(self.fabric_changed)
        for widget in [self.compensation,self.underlap,self.underlay_spacing,self.stagger]:
            widget.valueChanged.connect(self.invalidate)
        self.underlay_enabled.toggled.connect(self.invalidate)
        self.auto_direction.toggled.connect(self.invalidate)
        for name,widget in [("Width",self.width),("Height",self.height),("",self.aspect),
            ("Row spacing",self.spacing),("Max stitch length",self.length),
            ("Fill direction",self.angle),("Minimum region",self.minimum),("Strategy",self.mode),("Thread order",self.order)]:
            form.addRow(name,widget)
        self.width.valueChanged.connect(self.width_changed)
        self.height.valueChanged.connect(self.height_changed)
        self.aspect.toggled.connect(self.mask_changed)
        for widget in [self.colors,self.spacing,self.length,self.angle,self.minimum]:
            widget.valueChanged.connect(self.invalidate)
        for widget in [self.mode,self.order]:
            widget.currentTextChanged.connect(self.invalidate)
        settings_layout.addWidget(group)
        note=QLabel('Fabric values are starting points for test stitching. Checked layers sew in list order; part directions override automatic direction.')
        note.setWordWrap(True); settings_layout.addWidget(note); settings_layout.addStretch()
        self.generate_button=self.button(side,"Auto Digitize",self.generate)
        self.generate_button.setStyleSheet("background:#176e69;color:white;font-weight:600;padding:10px;")
        self.export_button=self.button(side,"Export DST",self.export)
        self.export_button.setEnabled(False)
        self.cancel_button=self.button(side,"Cancel",self.cancel_generation)
        self.cancel_button.setVisible(False)
        self.cancel_button.setStyleSheet("color:#9b3f30;")
        self.progress_bar=QProgressBar()
        self.progress_bar.setRange(0,100)
        self.progress_bar.setValue(0)
        self.progress_bar.setTextVisible(True)
        self.progress_bar.setFormat("%p%")
        side.addWidget(self.progress_bar)
        self.estimate_label=QLabel("Ready to digitize")
        self.estimate_label.setWordWrap(True)
        self.estimate_label.setStyleSheet("color:#52706d;font-size:11px;padding:2px 0 5px")
        side.addWidget(self.estimate_label)
        side.addStretch()
        workspace=QVBoxLayout()
        content.addLayout(workspace,1)
        labels=QHBoxLayout()
        labels.addWidget(QLabel("SOURCE  /  Selection overlay"))
        labels.addWidget(QLabel("STITCH PREVIEW  /  Millimeters"))
        workspace.addLayout(labels)
        self.preview=StitchPreview()
        split=QSplitter()
        split.addWidget(self.canvas); split.addWidget(self.preview)
        split.setSizes([500,500])
        workspace.addWidget(split,1)
        layers=QHBoxLayout()
        workspace.addLayout(layers)
        for key,label in [("stitches","Stitches"),("jumps","Jumps"),("polygons","Polygons"),("order","Object order")]:
            checkbox=QCheckBox(label); checkbox.setChecked(self.preview.layers[key])
            checkbox.toggled.connect(lambda value,k=key:self.layer(k,value))
            layers.addWidget(checkbox)
        debug=QHBoxLayout(); workspace.addLayout(debug)
        for key,label in [('underlay','Underlay'),('travel','Travel'),('trims','Trims'),('entries','Entry / exit'),('directions','Directions')]:
            checkbox=QCheckBox(label); checkbox.setChecked(self.preview.layers[key])
            checkbox.toggled.connect(lambda value,k=key:self.layer(k,value)); debug.addWidget(checkbox)
        playback=QHBoxLayout(); workspace.addLayout(playback)
        self.play_button=self.button(playback,'Play / Pause',self.preview.toggle_play)
        self.sequence_slider=QSlider(Qt.Horizontal); self.sequence_slider.setRange(0,1000); self.sequence_slider.setValue(1000)
        self.sequence_slider.valueChanged.connect(self.preview.scrub)
        self.preview.position_changed.connect(self.update_sequence_position)
        playback.addWidget(self.sequence_slider)
        self.stats=QLabel("Open a PNG or JPG, then select the artwork to embroider.")
        self.stats.setWordWrap(True)
        self.stats.setStyleSheet("padding:10px;background:#e4ece8;border-radius:6px")
        layout.addWidget(self.stats)
        self.statusBar().showMessage("Local processing · CPU only · No image upload")

    @Slot(object)
    def accept_layers(self, document):
        """Receive segmentation results as a registered MainWindow Qt slot.

        LayerWorkflow is a mixin rather than a QObject subclass.  Registering
        this forwarding slot on the actual QMainWindow is important: Qt then
        queues the result onto the GUI thread before it touches the source
        canvas and layer widgets.
        """
        LayerWorkflow.accept_layers(self, document)

    @staticmethod
    def button(layout,label,callback):
        button=QPushButton(label); button.clicked.connect(callback); layout.addWidget(button)
        return button

    def update_sequence_position(self,value):
        self.sequence_slider.blockSignals(True)
        self.sequence_slider.setValue(value)
        self.sequence_slider.blockSignals(False)

    @staticmethod
    def spin(low,high,value,suffix,step=1):
        widget=QDoubleSpinBox(); widget.setRange(low,high); widget.setValue(value)
        widget.setSuffix(suffix); widget.setSingleStep(step)
        return widget

    def ratio(self):
        mask=self.document.foreground if self.document is not None else self.canvas.mask
        if mask is not None and mask.any():
            ys,xs=np.nonzero(mask)
            return (xs.max()-xs.min()+1)/(ys.max()-ys.min()+1)
        return 4/3

    def width_changed(self,*args):
        if self.aspect.isChecked():
            self.height.blockSignals(True)
            self.height.setValue(self.width.value()/self.ratio())
            self.width.blockSignals(True)
            self.width.setValue(self.height.value()*self.ratio())
            self.width.blockSignals(False)
            self.height.blockSignals(False)
        self.invalidate()

    def height_changed(self,*args):
        if self.aspect.isChecked():
            self.width.blockSignals(True)
            self.width.setValue(self.height.value()*self.ratio())
            self.height.blockSignals(True)
            self.height.setValue(self.width.value()/self.ratio())
            self.height.blockSignals(False)
            self.width.blockSignals(False)
        self.invalidate()

    def mask_changed(self,*args):
        self.update_layer_mask()
        if hasattr(self,"width"):
            self.width_changed()

    def invalidate(self,*args):
        self.dirty=True
        if self.document is not None:
            self.project_dirty=True
        if hasattr(self,"export_button"):
            self.export_button.setEnabled(False)
        if self.design:
            self.statusBar().showMessage("Selection or settings changed. Auto Digitize to refresh the preview.")

    def layer(self,key,value):
        self.preview.layers[key]=value
        if self.design:
            self.preview.display(self.design)

    def load_proof(self,index):
        if index:
            self.accept_design(proof_design(self.proofs.itemText(index).lower()),{})

    def open_image(self):
        path,_=QFileDialog.getOpenFileName(self,"Open image","","Images (*.png *.jpg *.jpeg)")
        if path and self.confirm_replace_project():
            try:
                self.reset_layers()
                self.canvas.load(path)
                self.statusBar().showMessage(f"{Path(path).name} · select the region you want to embroider")
            except Exception as error:
                QMessageBox.critical(self,"Image could not be opened",str(error))

    def save_mask(self):
        path,_=QFileDialog.getSaveFileName(self,"Save mask","mask.png","PNG (*.png)")
        if path:
            try:
                self.canvas.export_mask(path)
            except Exception as error:
                QMessageBox.critical(self,"Mask export failed",str(error))

    def settings(self):
        return dict(width=self.width.value(),height=self.height.value(),colors=self.colors.value(),
                    spacing=self.spacing.value(),length=self.length.value(),angle=self.angle.value(),
                    min_area=self.minimum.value(),mode=self.mode.currentText(),reverse_colors=self.order.currentIndex()==1,
                    fabric=self.fabric_settings(),auto_direction=self.auto_direction.isChecked())

    def fabric_settings(self):
        if self.fabric.currentText()=='Legacy / no planning': return None
        profile=get_profile(self.fabric.currentText())
        return asdict(replace(profile,pull_compensation_mm=self.compensation.value(),
            underlap_mm=self.underlap.value(),underlay_spacing_mm=self.underlay_spacing.value(),
            stagger_period=self.stagger.value(),underlay_enabled=self.underlay_enabled.isChecked()))

    def fabric_changed(self,name):
        if name in PROFILES:
            profile=PROFILES[name]
            self.compensation.setValue(profile.pull_compensation_mm)
            self.underlap.setValue(profile.underlap_mm)
            self.underlay_spacing.setValue(profile.underlay_spacing_mm)
            self.stagger.setValue(profile.stagger_period)
            self.spacing.setValue(profile.suggested_row_spacing_mm)
            self.length.setValue(profile.suggested_stitch_length_mm)
        self.order.setEnabled(name=='Legacy / no planning')
        self.invalidate()

    def set_busy(self,busy):
        if busy:
            self._last_fraction=0.0
            self._last_stage='Preparing artwork'
            self.progress_timer.start()
            self._enabled_controls=[(widget,widget.isEnabled()) for widget in self.centralWidget().findChildren(QWidget)
                if isinstance(widget,(QAbstractButton,QAbstractSpinBox,QComboBox,QListWidget))]
            for widget,enabled in self._enabled_controls:
                widget.setEnabled(False)
            self.canvas.setEnabled(False)
            self.cancel_button.setEnabled(True)
            self.cancel_button.setVisible(True)
        else:
            self.progress_timer.stop()
            for widget,enabled in getattr(self,'_enabled_controls',[]):
                widget.setEnabled(enabled)
            self.canvas.setEnabled(True)
            self.cancel_button.setEnabled(False)
            self.cancel_button.setVisible(False)
            self.export_button.setEnabled(self.design is not None and not self.dirty and not validate(self.design)[0])
            if self.document is not None:
                self.layer_panel.show_settings(self.document,self.active_layer)

    def generate(self):
        if self.thread is not None:
            return
        mask=self.document.enabled_mask() if self.document is not None else self.canvas.mask
        if mask is None or not mask.any():
            QMessageBox.information(self,"Select artwork","Open an image and select a non-empty region first.")
            return
        self.set_busy(True)
        self.statusBar().showMessage("Generating geometry and stitches…")
        self._progress_started_at=monotonic()
        self._progress_elapsed=0.0
        self.progress_bar.setValue(0)
        self.estimate_label.setText("Preparing selected artwork · estimating remaining time…")
        self.thread=QThread(self)
        settings=self.settings()
        if self.document is not None:
            settings['layer_document']=self.document.copy()
        self.cancel_event=Event()
        self.worker=Digitizer(self.canvas.image.copy(),mask.copy(),settings,self.cancel_event)
        self.worker.moveToThread(self.thread)
        self.thread.started.connect(self.worker.run)
        # Digitizing is performed in a worker thread; all preview/UI mutations
        # must be delivered to the GUI thread.
        self.worker.finished.connect(self.accept_design, Qt.QueuedConnection)
        self.worker.progress.connect(self.generation_progress, Qt.QueuedConnection)
        self.worker.cancelled.connect(self.generation_cancelled, Qt.QueuedConnection)
        self.worker.failed.connect(self.generation_failed, Qt.QueuedConnection)
        self.worker.done.connect(self.thread.quit)
        self.worker.done.connect(self.worker.deleteLater)
        self.thread.finished.connect(self.worker_finished, Qt.QueuedConnection)
        self.thread.finished.connect(self.thread.deleteLater)
        self.thread.start()

    @Slot()
    def worker_finished(self):
        self.thread=None; self.worker=None
        self.set_busy(False)

    @Slot(str)
    def generation_failed(self,message):
        self.progress_timer.stop()
        self.statusBar().showMessage("Digitizing failed; adjust the selection or settings.")
        if self._progress_started_at is not None:
            self._progress_elapsed=monotonic()-self._progress_started_at
            self.estimate_label.setText(f"Failed after {self.format_duration(self._progress_elapsed)}")
        QMessageBox.critical(self,"Digitizing failed",message)

    def cancel_generation(self):
        if self.thread is None:
            return
        self.cancel_event.set()
        self.cancel_button.setEnabled(False)
        self.estimate_label.setText('Cancelling after the current fill row…')

    @Slot()
    def generation_cancelled(self):
        self.progress_timer.stop()
        self.statusBar().showMessage('Digitizing cancelled; the previous preview is unchanged.')
        self.estimate_label.setText(f"Cancelled after {self.format_duration(self._progress_elapsed)}")

    @staticmethod
    def format_duration(seconds):
        if seconds < 0.5:
            return "<1s"
        if seconds < 60:
            return f"{seconds:.1f}s"
        minutes, remainder=divmod(round(seconds),60)
        return f"{minutes}m {remainder:02d}s"

    @Slot(float,str)
    def generation_progress(self,fraction,message):
        fraction=max(0.0,min(1.0,float(fraction)))
        self._last_fraction=fraction
        self._last_stage=message
        self.progress_bar.setValue(round(fraction*100))
        if self._progress_started_at is None:
            self._progress_started_at=monotonic()
        elapsed=monotonic()-self._progress_started_at
        self._progress_elapsed=elapsed
        if fraction >= 1.0:
            self.estimate_label.setText(f"{message} · elapsed {self.format_duration(elapsed)}")
            return
        if fraction >= 0.05 and elapsed >= 0.1:
            remaining=max(0.0, elapsed*(1.0-fraction)/fraction)
            eta=f"~{self.format_duration(remaining)} remaining"
        else:
            eta="estimating remaining time…"
        self.estimate_label.setText(f"{message} · {self.format_duration(elapsed)} elapsed · {eta}")

    @Slot(object,object)
    def accept_design(self,design,metrics):
        self.design=design; self.dirty=False
        self.progress_timer.stop()
        self.preview.display(design)
        if self._progress_started_at is not None and metrics:
            self._progress_elapsed=monotonic()-self._progress_started_at
            self.progress_bar.setValue(100)
            self.estimate_label.setText(f"Digitizing complete · elapsed {self.format_duration(self._progress_elapsed)}")
        elif not metrics:
            self.progress_bar.setValue(100)
            self.estimate_label.setText("Preview loaded · ready to digitize")
        else:
            self.progress_bar.setValue(100)
            self.estimate_label.setText("Stitch preview ready")
        errors,warnings=validate(design,12.1 if not metrics else self.length.value())
        counts={c:sum(s.command==c for s in design.stitches) for c in Command}
        text=(f"{design.width_mm:g} × {design.height_mm:g} mm  ·  {counts[Command.STITCH]:,} stitches  ·  "
              f"{counts[Command.JUMP]:,} jumps  ·  {counts[Command.COLOR_CHANGE]} color changes  ·  {len(design.thread_colors)} threads")
        if metrics:
            text+=f"\nTravel: {metrics['before']['jump_distance_mm']:g} → {metrics['after']['jump_distance_mm']:g} mm · Palette: "+", ".join(design.thread_colors)
            if metrics.get('omitted_layers'):
                text+='\nFiltered out: '+', '.join(metrics['omitted_layers'])+' (reduce minimum area or enable Keep small details)'
            if metrics.get('phases'):
                phases=metrics['phases']
                text+=f"\nTop: {phases['TOP']:,} · Underlay: {phases['UNDERLAY']:,} · Hidden travel: {metrics['hidden_travel_mm']:g} mm · Trims: {metrics['counts']['TRIM']}"
        kinds={obj.stitch_type.value for obj in design.objects}
        if kinds:
            text+="\nStitch types: "+", ".join(sorted(kinds))
        if errors or warnings:
            messages=errors+warnings
            text+="\n"+"; ".join(messages[:3])
            if len(messages)>3: text+=f' · {len(messages)-3} more warnings (review before export)'
        self.stats.setText(text)
        self.export_button.setEnabled(not errors)
        self.statusBar().showMessage("Preview ready · Review stitches and jumps before exporting")

    def export(self):
        if self.design is None or self.dirty:
            return
        errors,warnings=validate(self.design)
        if errors:
            QMessageBox.critical(self,"Cannot export","\n".join(errors)); return
        if warnings and QMessageBox.warning(self,"Review warnings","\n".join(warnings)+"\n\nExport this design?",
                    QMessageBox.Yes|QMessageBox.No)!=QMessageBox.Yes:
            return
        path,_=QFileDialog.getSaveFileName(self,"Export DST","design.dst","DST (*.dst)")
        if path:
            if not path.lower().endswith(".dst"):
                path+=".dst"
            try:
                report=export_dst(self.design,path)
                QMessageBox.information(self,"DST verified",f"Saved {report['stitches']:,} stitches. Readback passed.\nThread order: "+", ".join(self.design.thread_colors))
            except Exception as error:
                QMessageBox.critical(self,"Export failed",str(error))

    def closeEvent(self,event):
        if self.thread is not None:
            self.statusBar().showMessage("Please wait for digitizing to finish before closing.")
            event.ignore()
        else:
            if self.confirm_replace_project():
                self.preview.timer.stop()
                event.accept()
            else:
                event.ignore()
