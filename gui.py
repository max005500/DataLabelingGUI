"""PyQt6 signal browser and interval editor for native KFall recordings."""

from __future__ import annotations

import numpy as np
from PyQt6 import QtCore, QtGui, QtWidgets
import pyqtgraph as pg

from kfall_labeler.editor import ACTIVITIES, ACTIVITY_CODES, UCI_CODE_OFFSET
from kfall_labeler.tasks import KFALL_REFERENCE_URL, KFALL_TASK_REFERENCE_VIDEOS

ACTIVITY_NAMES = {
    "WALKING": "Caminando", "WALKING_UPSTAIRS": "Subiendo escaleras",
    "WALKING_DOWNSTAIRS": "Bajando escaleras", "SITTING": "Sentado",
    "STANDING": "De pie", "LAYING": "Acostado",
    "ASCENDING": "Subiendo", "DESCENDING": "Bajando",
}
NAMES = {-1: "Sin etiqueta", 0: "Fall (protegida)", 1: "Dynamic (antigua)", 2: "Static (antigua)",
         3: "PostImpact (protegida)",
         **{UCI_CODE_OFFSET + k: ACTIVITY_NAMES[v] for k, v in ACTIVITIES.items()}}
COLORS = {-1: "#334155", 0: "#f43f5e", 1: "#64748b", 2: "#94a3b8", 3: "#fb923c",
          10: "#38bdf8", 11: "#818cf8", 12: "#c084fc", 13: "#34d399", 14: "#facc15", 15: "#2dd4bf",
          16: "#fb7185", 17: "#fbbf24"}
AXIS_COLORS = ("#f472b6", "#38bdf8", "#a3e635")
BG, PANEL, CARD, BORDER, TEXT, MUTED, ACCENT = (
    "#0b1120", "#111827", "#172033", "#263449", "#e5e7eb", "#94a3b8", "#8b5cf6")

STYLE = f"""
* {{ font-family: 'Inter', 'Segoe UI', 'Noto Sans', sans-serif; font-size: 10pt; color: {TEXT}; }}
QMainWindow, QWidget#root {{ background: {BG}; }}
QFrame#card {{ background: {PANEL}; border: 1px solid {BORDER}; border-radius: 14px; }}
QLabel#title {{ font-size: 17pt; font-weight: 700; }}
QLabel#subtitle, QLabel#hint, QLabel#status {{ color: {MUTED}; }}
QLabel#section {{ color: {MUTED}; font-size: 8pt; font-weight: 700; letter-spacing: 1px; }}
QLabel#heading {{ font-size: 14pt; font-weight: 700; }}
QLabel#badge {{ border-radius: 9px; padding: 3px 10px; font-weight: 700; }}
QComboBox, QDoubleSpinBox {{ background: {CARD}; border: 1px solid {BORDER}; border-radius: 8px;
    padding: 6px 10px; min-height: 20px; }}
QComboBox:hover, QDoubleSpinBox:hover {{ border-color: {ACCENT}; }}
QComboBox QAbstractItemView {{ background: {CARD}; selection-background-color: {ACCENT}; }}
QListWidget {{ background: transparent; border: none; outline: none; }}
QListWidget::item {{ background: {CARD}; border: 1px solid {BORDER}; border-radius: 9px;
    padding: 8px 10px; margin: 3px 0; }}
QListWidget::item:hover {{ border-color: #475569; }}
QListWidget::item:selected {{ background: #2e1065; border-color: {ACCENT}; color: white; }}
QPushButton {{ background: {CARD}; border: 1px solid {BORDER}; border-radius: 9px; padding: 8px 14px;
    font-weight: 600; }}
QPushButton:hover {{ border-color: {ACCENT}; background: #1e293b; }}
QPushButton:disabled {{ color: #475569; }}
QPushButton#primary {{ background: {ACCENT}; border-color: {ACCENT}; color: white; }}
QPushButton#primary:hover {{ background: #7c3aed; }}
QProgressBar {{ background: {CARD}; border: none; border-radius: 4px; height: 8px; }}
QProgressBar::chunk {{ background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #8b5cf6, stop:1 #22d3ee);
    border-radius: 4px; }}
QSplitter::handle {{ background: {BG}; width: 10px; }}
QScrollBar:vertical {{ background: transparent; width: 8px; }}
QScrollBar::handle:vertical {{ background: {BORDER}; border-radius: 4px; min-height: 30px; }}
QScrollBar::add-line, QScrollBar::sub-line {{ height: 0; }}
"""


def rgba(color, alpha):
    value = QtGui.QColor(color)
    return f"rgba({value.red()}, {value.green()}, {value.blue()}, {alpha})"


def card():
    frame = QtWidgets.QFrame()
    frame.setObjectName("card")
    return frame


def label(text, name=None):
    widget = QtWidgets.QLabel(text)
    if name:
        widget.setObjectName(name)
    return widget


class SelectionViewBox(pg.ViewBox):
    intervalSelected = QtCore.pyqtSignal(float, float)

    def mouseDragEvent(self, event, axis=None):
        if (event.button() == QtCore.Qt.MouseButton.LeftButton and axis is None
                and not event.modifiers() & QtCore.Qt.KeyboardModifier.ControlModifier):
            event.accept()
            start = self.mapToView(event.buttonDownPos()).x()
            stop = self.mapToView(event.pos()).x()
            self.intervalSelected.emit(start, stop)
        else:
            super().mouseDragEvent(event, axis=axis)


class LabelWindow(QtWidgets.QMainWindow):
    def __init__(self, source):
        super().__init__()
        self.source = source
        self.current = None
        self.selection = (0.0, 0.0)
        self.label_items = []
        self.syncing_selection = False
        self.last_filters = ("", False)
        self.setWindowTitle("KFall Labeler - UCI HAR")
        self.resize(1480, 900)
        self.setStyleSheet(STYLE)
        root = QtWidgets.QWidget()
        root.setObjectName("root")
        self.setCentralWidget(root)
        outer = QtWidgets.QVBoxLayout(root)
        outer.setContentsMargins(16, 14, 16, 14)
        outer.setSpacing(12)
        header = QtWidgets.QHBoxLayout()
        titles = QtWidgets.QVBoxLayout()
        titles.setSpacing(0)
        titles.addWidget(label("KFall Labeler", "title"))
        titles.addWidget(label("Etiquetado temporal con actividades UCI HAR", "subtitle"))
        header.addLayout(titles)
        header.addStretch()
        self.progress = label("", "subtitle")
        self.progress_bar = QtWidgets.QProgressBar()
        self.progress_bar.setTextVisible(False)
        self.progress_bar.setFixedWidth(220)
        stats = QtWidgets.QVBoxLayout()
        stats.addWidget(self.progress, alignment=QtCore.Qt.AlignmentFlag.AlignRight)
        stats.addWidget(self.progress_bar)
        header.addLayout(stats)
        legend_marks = label("<span style='color:#34d399'>●</span> UCI HAR   "
                             "<span style='color:#facc15'>◐</span> Dynamic/Static   "
                             "<span style='color:#64748b'>○</span> Pendiente", "hint")
        outer.addLayout(header)
        splitter = QtWidgets.QSplitter()
        outer.addWidget(splitter, 1)

        sidebar = card()
        side = QtWidgets.QVBoxLayout(sidebar)
        side.setContentsMargins(14, 14, 14, 14)
        side.addWidget(label("SUJETO", "section"))
        self.subject = QtWidgets.QComboBox()
        self.subject.addItem("Todos los sujetos", "")
        for subject in sorted({row["subject"] for row in source.catalog}):
            self.subject.addItem(subject, subject)
        side.addWidget(self.subject)
        side.addWidget(label("ESTADO", "section"))
        self.state_filter = QtWidgets.QComboBox()
        self.state_filter.addItem("Todas las grabaciones", False)
        self.state_filter.addItem("Solo sin etiquetar (UCI HAR)", True)
        side.addWidget(self.state_filter)
        side.addSpacing(6)
        self.count_label = label("", "section")
        side.addWidget(self.count_label)
        self.files = QtWidgets.QListWidget()
        self.files.setUniformItemSizes(True)
        self.files.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        side.addWidget(self.files, 1)
        side.addWidget(legend_marks)
        splitter.addWidget(sidebar)

        panel = QtWidgets.QWidget()
        body = QtWidgets.QVBoxLayout(panel)
        body.setContentsMargins(0, 0, 0, 0)
        body.setSpacing(12)
        top = card()
        top_layout = QtWidgets.QVBoxLayout(top)
        top_layout.setContentsMargins(16, 12, 16, 12)
        heading_row = QtWidgets.QHBoxLayout()
        self.heading = label("", "heading")
        self.heading.setSizePolicy(QtWidgets.QSizePolicy.Policy.Minimum, QtWidgets.QSizePolicy.Policy.Preferred)
        self.badge = label("", "badge")
        heading_row.addWidget(self.heading)
        heading_row.addWidget(self.badge, alignment=QtCore.Qt.AlignmentFlag.AlignVCenter)
        heading_row.addStretch()
        self.sensor = QtWidgets.QComboBox()
        self.sensor.addItem("Acelerometro", 0)
        self.sensor.addItem("Giroscopio", 3)
        heading_row.addWidget(self.sensor)
        reset = QtWidgets.QPushButton("Ver todo")
        reset.clicked.connect(self.reset_view)
        heading_row.addWidget(reset)
        focus = QtWidgets.QPushButton("Zoom ventana")
        focus.clicked.connect(self.focus_selection)
        heading_row.addWidget(focus)
        top_layout.addLayout(heading_row)
        self.task_description = label("", "subtitle")
        self.task_description.setWordWrap(True)
        top_layout.addWidget(self.task_description)
        hint = label("Arrastra sobre la senal para crear una ventana; mueve su interior o ajusta sus bordes  ·  "
                     "Rueda: zoom  ·  Ctrl+arrastre: mover vista  ·  1-8: etiquetar  ·  Supr: borrar", "hint")
        hint.setWordWrap(True)
        top_layout.addWidget(hint)
        activity_row = QtWidgets.QHBoxLayout()
        activity_row.addWidget(label("ACTIVIDAD", "section"))
        self.activity_title = label("Sin actividad seleccionada", "heading")
        self.activity_title.setStyleSheet("font-size: 11pt;")
        activity_row.addWidget(self.activity_title)
        activity_row.addStretch()
        self.reference_button = QtWidgets.QPushButton("Videos de referencia KFall")
        self.reference_button.setToolTip(
            "Abrir el video de la tarea si esta disponible; si no, abrir el sitio oficial de KFall")
        self.reference_button.clicked.connect(self.open_reference_video)
        activity_row.addWidget(self.reference_button)
        top_layout.addLayout(activity_row)
        body.addWidget(top)

        plot_card = card()
        plot_layout = QtWidgets.QVBoxLayout(plot_card)
        plot_layout.setContentsMargins(8, 8, 8, 8)
        self.graphics = pg.GraphicsLayoutWidget()
        self.graphics.setBackground(PANEL)
        self.plots = []
        self.curves = []
        self.regions = []
        for index in range(4):
            view = SelectionViewBox()
            view.setMouseMode(pg.ViewBox.PanMode)
            view.setMouseEnabled(x=True, y=False)
            view.intervalSelected.connect(self.select)
            plot = self.graphics.addPlot(row=index, col=0, viewBox=view)
            plot.setMenuEnabled(False)
            plot.hideButtons()
            plot.getAxis("left").setWidth(80)
            plot.getAxis("left").enableAutoSIPrefix(False)
            for name in ("left", "bottom"):
                plot.getAxis(name).setTextPen(MUTED)
                plot.getAxis(name).setPen(BORDER)
            plot.showGrid(x=True, y=index < 3, alpha=0.12)
            if self.plots:
                plot.setXLink(self.plots[0])
            if index < 3:
                plot.hideAxis("bottom")
                pen = pg.mkPen(AXIS_COLORS[index], width=1.6)
                self.curves.append(plot.plot(pen=pen, connect="finite"))
            else:
                plot.setLabel("left", "Etiquetas", color=MUTED)
                plot.getAxis("left").setTicks([])
                plot.setLabel("bottom", "Tiempo", units="s", color=MUTED)
                plot.setYRange(0, 1, padding=0)
                self.graphics.ci.layout.setRowMaximumHeight(index, 80)
            region = pg.LinearRegionItem(
                (0, 1), brush=pg.mkBrush(139, 92, 246, 45),
                hoverBrush=pg.mkBrush(139, 92, 246, 80),
                pen=pg.mkPen("#a78bfa", width=2), hoverPen=pg.mkPen("#ddd6fe", width=3))
            region.setZValue(20)
            region.setToolTip("Arrastra el interior para mover la ventana o los bordes para redimensionarla.")
            region.setCursor(QtCore.Qt.CursorShape.SizeAllCursor)
            for line in region.lines:
                line.setCursor(QtCore.Qt.CursorShape.SizeHorCursor)
            plot.addItem(region, ignoreBounds=True)
            region.sigRegionChanged.connect(self._region_changed)
            region.sigRegionChangeFinished.connect(self._region_finished)
            region.hide()
            self.regions.append(region)
            self.plots.append(plot)
        plot_layout.addWidget(self.graphics, 1)
        legend = QtWidgets.QHBoxLayout()
        legend.setSpacing(14)
        for axis, color in zip("XYZ", AXIS_COLORS):
            legend.addWidget(label(f"<span style='color:{color}'>━━</span> Eje {axis}", "hint"))
        legend.addStretch()
        for code in (0, 3, -1):
            legend.addWidget(label(f"<span style='color:{COLORS[code]}'>■</span> {NAMES[code]}", "hint"))
        plot_layout.addLayout(legend)
        body.addWidget(plot_card, 1)

        tools = card()
        tools_layout = QtWidgets.QVBoxLayout(tools)
        tools_layout.setContentsMargins(16, 12, 16, 12)
        window_row = QtWidgets.QHBoxLayout()
        window_row.addWidget(label("VENTANA", "section"))
        self.start = QtWidgets.QDoubleSpinBox()
        self.stop = QtWidgets.QDoubleSpinBox()
        for widget in (self.start, self.stop):
            widget.setDecimals(2)
            widget.setSingleStep(0.01)
            widget.setSuffix(" s")
            widget.setMinimumWidth(115)
        self.start.setPrefix("Inicio  ")
        self.stop.setPrefix("Fin  ")
        window_row.addWidget(self.start)
        window_row.addWidget(self.stop)
        self.width_label = label("", "hint")
        window_row.addWidget(self.width_label)
        whole = QtWidgets.QPushButton("Todo")
        whole.setToolTip("Seleccionar toda la grabacion")
        whole.clicked.connect(lambda: self.select(0, self.current.duration) if self.current else None)
        window_row.addWidget(whole)
        window_row.addStretch()
        clear = QtWidgets.QPushButton("Borrar")
        clear.clicked.connect(lambda: self.apply(-1))
        window_row.addWidget(clear)
        self.undo_button = QtWidgets.QPushButton("Deshacer")
        self.undo_button.clicked.connect(self.undo)
        window_row.addWidget(self.undo_button)
        tools_layout.addLayout(window_row)
        activities = QtWidgets.QGridLayout()
        activities.setSpacing(8)
        self.activity_buttons = {}
        for number, code in enumerate(ACTIVITY_CODES, start=1):
            color = COLORS[code]
            button = QtWidgets.QPushButton(f"{number}   {NAMES[code]}")
            button.setToolTip(f"{NAMES[code]} (tecla {number})")
            button.setMinimumHeight(40)
            button.setStyleSheet(
                f"QPushButton {{ background: {rgba(color, 30)}; border: 1px solid {rgba(color, 150)};"
                f" color: {color}; text-align: left; padding-left: 14px; }}"
                f"QPushButton:hover {{ background: {color}; color: {BG}; }}")
            button.clicked.connect(lambda checked=False, value=code: self.apply(value))
            QtGui.QShortcut(QtGui.QKeySequence(str(number)), self, activated=button.click)
            activities.addWidget(button, (number - 1) // 3, (number - 1) % 3)
            self.activity_buttons[code] = button
        actions = QtWidgets.QVBoxLayout()
        self.save_button = QtWidgets.QPushButton("Guardar revisada")
        self.save_button.setObjectName("primary")
        self.save_button.setMinimumHeight(40)
        self.save_button.clicked.connect(self.save)
        actions.addWidget(self.save_button)
        next_button = QtWidgets.QPushButton("Siguiente  ›")
        next_button.setMinimumHeight(40)
        next_button.clicked.connect(self.next_recording)
        actions.addWidget(next_button)
        activities.addLayout(actions, 0, 3, 3, 1)
        activities.setColumnStretch(3, 0)
        tools_layout.addLayout(activities)
        self.status = label("", "status")
        self.status.setWordWrap(True)
        tools_layout.addWidget(self.status)
        body.addWidget(tools)
        splitter.addWidget(panel)
        splitter.setSizes([320, 1140])
        QtGui.QShortcut(QtGui.QKeySequence.StandardKey.Delete, self, activated=lambda: self.apply(-1))
        QtGui.QShortcut(QtGui.QKeySequence.StandardKey.Undo, self, activated=self.undo)
        self.sensor.currentIndexChanged.connect(self.change_sensor)
        self.subject.currentIndexChanged.connect(self.refresh)
        self.state_filter.currentIndexChanged.connect(self.refresh)
        self.files.currentRowChanged.connect(self.change_recording)
        self.start.valueChanged.connect(self._numeric_selection)
        self.stop.valueChanged.connect(self._numeric_selection)
        shortcut = QtGui.QShortcut(QtGui.QKeySequence.StandardKey.Save, self)
        shortcut.activated.connect(self.save)
        self.refresh()

    def error(self, exc):
        QtWidgets.QMessageBox.critical(self, "No se pudo completar la operacion", str(exc))

    def open_reference_video(self):
        task_id = self.current.record["task_id"] if self.current is not None else None
        url = KFALL_TASK_REFERENCE_VIDEOS.get(task_id, KFALL_REFERENCE_URL)
        if not QtGui.QDesktopServices.openUrl(QtCore.QUrl(url)):
            self.error("No se pudo abrir la pagina oficial de referencias de KFall.")

    def confirm_leave(self):
        if self.current is None or not self.current.dirty:
            return True
        choice = QtWidgets.QMessageBox.question(
            self, "Cambios sin guardar", "Guardar los cambios antes de continuar?",
            QtWidgets.QMessageBox.StandardButton.Save | QtWidgets.QMessageBox.StandardButton.Discard
            | QtWidgets.QMessageBox.StandardButton.Cancel,
            QtWidgets.QMessageBox.StandardButton.Cancel)
        if choice == QtWidgets.QMessageBox.StandardButton.Save:
            return self.save(refresh=False)
        return choice == QtWidgets.QMessageBox.StandardButton.Discard

    def refresh(self):
        subject, pending = self.subject.currentData(), self.state_filter.currentData()
        rows = self.source.filtered(subject, pending)
        old_key = self.current.key if self.current else None
        keep = next((i for i, row in enumerate(rows) if row["key"] == old_key), None)
        if keep is None and not self.confirm_leave():
            self.subject.blockSignals(True)
            self.state_filter.blockSignals(True)
            self.subject.setCurrentIndex(self.subject.findData(self.last_filters[0]))
            self.state_filter.setCurrentIndex(self.state_filter.findData(self.last_filters[1]))
            self.subject.blockSignals(False)
            self.state_filter.blockSignals(False)
            return
        self.last_filters = (subject, pending)
        self.files.blockSignals(True)
        self.files.clear()
        marks = {"uci": ("●", "#34d399", "UCI HAR"), "legacy": ("◐", "#facc15", "Dynamic/Static"),
                 "pending": ("○", "#64748b", "pendiente")}
        for row in rows:
            icon, color, status = marks[self.source.status(row)]
            item = QtWidgets.QListWidgetItem(
                f"{icon}   {row['subject']}  ·  {row['code']}  ·  {row['trial']}\n{row['description']}")
            item.setForeground(QtGui.QColor(color))
            item.setToolTip(f"{row['key']}: {status}\n{row['description']}")
            item.setData(QtCore.Qt.ItemDataRole.UserRole, row)
            self.files.addItem(item)
        self.files.setCurrentRow(keep if keep is not None else 0 if rows else -1)
        self.files.blockSignals(False)
        reviewed = sum(self.source.reviewed(row) for row in self.source.catalog)
        total = len(self.source.catalog)
        self.progress.setText(f"{reviewed} / {total} grabaciones con UCI HAR")
        self.progress_bar.setMaximum(total)
        self.progress_bar.setValue(reviewed)
        self.count_label.setText(f"GRABACIONES  ·  {len(rows)}")
        if keep is None:
            # The leave prompt has already been handled above.
            self.current = None
            self.change_recording(self.files.currentRow())

    def change_recording(self, index):
        if not self.confirm_leave():
            self._restore_selection()
            return
        if index < 0:
            self.current = None
            self.heading.setText("No hay grabaciones con estos filtros")
            self.task_description.setText("")
            self.badge.setText("")
            self.badge.setStyleSheet("")
            self.activity_title.setText("Sin actividad seleccionada")
            for curve in self.curves:
                curve.clear()
            self._clear_labels()
            for region in self.regions:
                region.hide()
            self.status.setText("")
            self.save_button.setEnabled(False)
            self.undo_button.setEnabled(False)
            return
        row = self.files.item(index).data(QtCore.Qt.ItemDataRole.UserRole)
        try:
            item = self.source.load(row)
        except (OSError, ValueError, KeyError) as exc:
            self.error(exc)
            self._restore_selection()
            return
        self.current = item
        self.task_description.setText(f"{row['code']} · {row['description']}")
        self.save_button.setEnabled(True)
        for widget in (self.start, self.stop):
            widget.blockSignals(True)
            widget.setMaximum(item.duration)
            widget.blockSignals(False)
        self.selection = (0, min(1.0, item.duration))
        self.draw()
        self.select(*self.selection)

    def _restore_selection(self):
        self.files.blockSignals(True)
        for i in range(self.files.count()):
            if self.current and self.files.item(i).data(QtCore.Qt.ItemDataRole.UserRole)["key"] == self.current.key:
                self.files.setCurrentRow(i)
                break
        else:
            self.files.setCurrentRow(-1)
        self.files.blockSignals(False)

    def draw(self, preserve_view=False):
        if self.current is None:
            return
        item = self.current
        if not preserve_view:
            self.syncing_selection = True
            try:
                for plot, region in zip(self.plots, self.regions):
                    plot.setLimits(xMin=0, xMax=item.duration, minXRange=min(0.05, item.duration))
                    region.setBounds((0, item.duration))
                    region.show()
            finally:
                self.syncing_selection = False
            self.change_sensor()
            self.reset_view()
        self._clear_labels()
        boundaries = np.r_[0, np.flatnonzero(
            (np.diff(item.labels) != 0) | (np.diff(item.frames) != 1)) + 1, len(item.frames)]
        for start, stop in zip(boundaries[:-1], boundaries[1:]):
            label = int(item.labels[start])
            left = float(item.times[start])
            right = float(item.times[stop - 1] + 0.01)
            for index, plot in enumerate(self.plots):
                color = pg.mkColor(COLORS[label])
                color.setAlpha(200 if index == 3 else 30)
                band = pg.LinearRegionItem((left, right), movable=False, brush=pg.mkBrush(color),
                                           pen=pg.mkPen(None))
                band.setZValue(-10)
                band.setAcceptedMouseButtons(QtCore.Qt.MouseButton.NoButton)
                band.setAcceptHoverEvents(False)
                band.setToolTip(f"{NAMES[label]}: {left:.2f} - {right:.2f} s")
                plot.addItem(band, ignoreBounds=True)
                self.label_items.append((plot, band))
            if right - left > item.duration * 0.09:
                text = pg.TextItem(NAMES[label], color=BG, anchor=(0.5, 0.5))
                text.setPos((left + right) / 2, 0.5)
                self.plots[3].addItem(text, ignoreBounds=True)
                self.label_items.append((self.plots[3], text))
        self._sync_regions()
        self.update_status()

    def _clear_labels(self):
        for plot, item in self.label_items:
            plot.removeItem(item)
        self.label_items = []

    def change_sensor(self):
        if self.current is None:
            return
        first = self.sensor.currentData()
        unit = "g" if first == 0 else "deg/s"
        sensor = "Acc" if first == 0 else "Gyr"
        for channel, (plot, curve) in enumerate(zip(self.plots, self.curves)):
            curve.setData(self.current.times, self.current.signal[:, first + channel])
            plot.setLabel("left", f"{sensor} {'XYZ'[channel]}", units=unit, color="#cbd5e1")
            plot.enableAutoRange(axis=pg.ViewBox.YAxis)

    def reset_view(self):
        if self.current is not None:
            self.plots[0].setXRange(0, self.current.duration, padding=0)
            for plot in self.plots[:3]:
                plot.enableAutoRange(axis=pg.ViewBox.YAxis)

    def focus_selection(self):
        if self.current is not None and self.selection[1] > self.selection[0]:
            self.plots[0].setXRange(*self.selection, padding=0.1)

    def update_status(self):
        item = self.current
        state = self.source.status({"key": item.key})
        text, color = {"uci": ("UCI HAR", "#34d399"), "legacy": ("Antigua", "#facc15"),
                       "pending": ("Pendiente", "#94a3b8")}[state]
        if item.dirty:
            text, color = "Sin guardar", "#f472b6"
        self.heading.setText(f"{item.key}  ·  {item.duration:.2f} s")
        self.badge.setText(text)
        self.badge.setStyleSheet(f"background: {rgba(color, 45)}; color: {color};")
        legacy = f" | {item.legacy} muestras antiguas por reetiquetar" if item.legacy else ""
        self.status.setText(
            f"{item.unassigned} muestras sin etiqueta{legacy}  ·  Fall/PostImpact protegidas  ·  "
            f"Caminar/Subir/Bajar → Dynamic, Sentado/De pie/Acostado → Static  ·  {self.source.output.name}")
        self.status.setToolTip(str(self.source.output))
        self.undo_button.setEnabled(bool(item.history))
        self._update_activity_title()

    def _update_activity_title(self):
        if self.current is None:
            self.activity_title.setText("Sin actividad seleccionada")
            return
        start, stop = self.selection
        selected = self.current.labels[(self.current.times >= start) & (self.current.times < stop)]
        if not len(selected):
            title = "Sin actividad seleccionada"
        else:
            activities = np.unique(selected)
            title = NAMES[int(activities[0])] if len(activities) == 1 else "Varias actividades"
        self.activity_title.setText(title)

    def select(self, start, stop):
        if self.current is None:
            return
        start, stop = sorted((start, stop))
        start = max(0, min(round(start, 2), self.current.duration))
        stop = max(0, min(round(stop, 2), self.current.duration))
        self._set_selection(start, stop)

    def _set_selection(self, start, stop):
        self.selection = (start, stop)
        for widget, value in ((self.start, start), (self.stop, stop)):
            widget.blockSignals(True)
            widget.setValue(value)
            widget.blockSignals(False)
        self.width_label.setText(f"Δ {stop - start:.2f} s")
        self._sync_regions()
        self._update_activity_title()

    def _numeric_selection(self):
        if self.current is None:
            return
        self.select(self.start.value(), self.stop.value())

    def _sync_regions(self):
        self.syncing_selection = True
        try:
            for region in self.regions:
                region.setRegion(self.selection)
        finally:
            self.syncing_selection = False

    def _region_changed(self, region):
        if self.current is not None and not self.syncing_selection:
            self._set_selection(*region.getRegion())

    def _region_finished(self, region):
        if self.current is not None and not self.syncing_selection:
            self.select(*region.getRegion())

    def apply(self, label):
        if self.current is None:
            return
        try:
            self.current.apply(*self.selection, label)
        except ValueError as exc:
            self.error(exc)
            return
        self.draw(preserve_view=True)

    def undo(self):
        if self.current is not None:
            self.current.undo()
            self.draw(preserve_view=True)

    def save(self, checked=False, *, refresh=True):
        if self.current is None:
            return False
        if self.current.unassigned:
            choice = QtWidgets.QMessageBox.question(
                self, "Etiquetado parcial",
                "Quedan muestras sin etiqueta. Sus endpoints se excluiran del entrenamiento "
                "al usar este JSON. Guardar igualmente como revisada?",
                QtWidgets.QMessageBox.StandardButton.Yes | QtWidgets.QMessageBox.StandardButton.No,
                QtWidgets.QMessageBox.StandardButton.No)
            if choice != QtWidgets.QMessageBox.StandardButton.Yes:
                return False
        try:
            self.source.save(self.current)
        except (OSError, ValueError) as exc:
            self.error(exc)
            return False
        self.update_status()
        if refresh:
            self.refresh()
        return True

    def next_recording(self):
        index = self.files.currentRow()
        if index + 1 < self.files.count():
            self.files.setCurrentRow(index + 1)

    def closeEvent(self, event):
        if self.confirm_leave():
            event.accept()
        else:
            event.ignore()
