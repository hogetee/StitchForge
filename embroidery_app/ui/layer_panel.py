from PySide6.QtCore import Signal, Qt
from PySide6.QtGui import QColor, QIcon, QPixmap
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QListWidget, QListWidgetItem, QComboBox, QCheckBox, QDoubleSpinBox, QFormLayout,
    QAbstractItemView)


class LayerPanel(QWidget):
    selected = Signal(int)
    changed = Signal(int, str, object)
    action = Signal(str)

    def __init__(self):
        super().__init__()
        layout = QVBoxLayout(self)
        hint = QLabel("Each row is an editable object part with a proposed thread color. Check = include in DST; click a row to edit its mask. Use the view buttons to inspect one part or all parts.")
        hint.setWordWrap(True)
        layout.addWidget(hint)
        self.list = QListWidget()
        self.list.setMinimumHeight(150)
        self.list.setSelectionMode(QAbstractItemView.ExtendedSelection)
        layout.addWidget(QLabel('Objects / proposed thread colors'))
        layout.addWidget(self.list, 1)
        self.list.currentRowChanged.connect(self.selected.emit)
        self.list.itemChanged.connect(self.item_changed)
        for row in [[('Up','up'),('Down','down'),('Color','color')],
                    [('New part','new'),('Delete','delete'),('Merge','merge')],
                    [('Undo','undo'),('Redo','redo')],
                    [('Show selected','solo'),('Show all','all')],
                    [('Group by color','group_colors')]]:
            bar = QHBoxLayout()
            for label, action in row:
                button = QPushButton(label)
                button.clicked.connect(lambda checked=False,a=action:self.action.emit(a))
                bar.addWidget(button)
            layout.addLayout(bar)
        form = QFormLayout()
        self.mode = QComboBox(); self.mode.addItems(['Auto','Outline','Fill'])
        from embroidery_app.embroidery.sequence import ROLES
        self.role=QComboBox(); self.role.addItems(list(ROLES))
        form.addRow('Sewing role',self.role)
        self.role.currentTextChanged.connect(lambda v:self.changed.emit(self.list.currentRow(),'role',v))
        self.angle = QDoubleSpinBox(); self.angle.setRange(-1,179); self.angle.setValue(-1)
        self.angle.setSpecialValueText('Auto / global'); self.angle.setSuffix('°')
        self.details = QCheckBox('Keep small details')
        form.addRow('Part strategy', self.mode)
        form.addRow('Part direction', self.angle)
        form.addRow(self.details)
        layout.addLayout(form)
        self.mode.currentTextChanged.connect(lambda v:self.changed.emit(self.list.currentRow(),'mode',v))
        self.angle.valueChanged.connect(lambda v:self.changed.emit(self.list.currentRow(),'angle',None if v < 0 else v))
        self.details.toggled.connect(lambda v:self.changed.emit(self.list.currentRow(),'protect_details',v))
        self.count = QLabel('No layers yet. Use Separate into layers.')
        self.count.setWordWrap(True)
        layout.addWidget(self.count)
        self._refreshing = False

    def refresh(self, document, current=-1):
        self._refreshing = True
        self.list.blockSignals(True)
        self.list.clear()
        for layer in document.layers:
            item = QListWidgetItem(layer.name)
            item.setData(Qt.UserRole, layer.id)
            item.setFlags(item.flags() | Qt.ItemIsUserCheckable | Qt.ItemIsEditable)
            item.setCheckState(Qt.Checked if layer.enabled else Qt.Unchecked)
            swatch = QPixmap(16,16); swatch.fill(QColor(layer.color))
            item.setIcon(QIcon(swatch))
            item.setToolTip(f"{layer.color} · {int((layer.mask > 0).sum()):,} pixels")
            self.list.addItem(item)
        self.list.setCurrentRow(current)
        self.list.blockSignals(False)
        self.show_settings(document, current)
        self.count.setText(f"{len(document.layers)} parts · {len({p.color for p in document.layers if p.enabled})} thread colors\nCheckbox controls DST inclusion. Select a row, then Show selected to inspect it.")
        self._refreshing = False

    def show_settings(self, document, index):
        valid = 0 <= index < len(document.layers)
        for widget in [self.mode,self.angle,self.details,self.role]:
            widget.blockSignals(True); widget.setEnabled(valid)
        if valid:
            layer = document.layers[index]
            self.mode.setCurrentText(layer.mode)
            self.angle.setValue(-1 if layer.angle is None else layer.angle)
            self.details.setChecked(layer.protect_details)
            self.role.setCurrentText(layer.role)
        for widget in [self.mode,self.angle,self.details,self.role]:
            widget.blockSignals(False)

    def item_changed(self, item):
        if not self._refreshing:
            self.changed.emit(self.list.row(item), 'item', (item.text(),item.checkState() == Qt.Checked))
