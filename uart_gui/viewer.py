"""Offline analysis of JS CSV and legacy MATLAB recordings."""

from __future__ import annotations

import csv
from pathlib import Path

import numpy as np
import pyqtgraph as pg
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractItemView, QCheckBox, QDialog, QFileDialog, QHBoxLayout, QLabel,
    QListWidget, QListWidgetItem, QMessageBox, QPushButton, QSpinBox, QSplitter,
    QVBoxLayout, QWidget,
)

from .model import Recording, import_recording, smooth_values


COLORS = (
    "#0d9488", "#4f46e5", "#e18a24", "#e05c83", "#0284c7",
    "#8b5cf6", "#65a30d", "#d45032", "#0891b2", "#c026d3",
    "#64748b", "#b7791f", "#2f855a", "#6366f1", "#a85565", "#52525b",
)


class RecordingViewer(QDialog):
    """A resizable recording browser with selectable channels and moving means.

    ``load_file`` and ``export_smoothed`` also support callers which already
    have a path, without opening a native file dialog.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Recording analysis · JS")
        self.resize(1120, 720)
        self.setMinimumSize(760, 520)
        self.recording: Recording | None = None
        self.source: Path | None = None
        self._smoothed = np.empty((0, 0))

        root = QVBoxLayout(self)
        root.setContentsMargins(24, 22, 24, 18)
        root.setSpacing(16)
        header = QHBoxLayout()
        title = QLabel("Recording analysis")
        title.setStyleSheet("font-size: 24px; font-weight: 700; color: #162c40;")
        header.addWidget(title)
        header.addStretch()
        self.open_button = QPushButton("Open recording…")
        self.open_button.setObjectName("openRecording")
        self.open_button.clicked.connect(self.open_recording)
        header.addWidget(self.open_button)
        self.save_button = QPushButton("Export smoothed CSV…")
        self.save_button.setObjectName("exportSmoothed")
        self.save_button.setEnabled(False)
        self.save_button.clicked.connect(self.save_smoothed)
        header.addWidget(self.save_button)
        root.addLayout(header)

        self.file_label = QLabel("Open a CSV or MATLAB .mat recording to inspect its signals.")
        self.file_label.setStyleSheet("color: #64748b;")
        self.file_label.setTextFormat(Qt.TextFormat.PlainText)
        self.file_label.setWordWrap(True)
        root.addWidget(self.file_label)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        sidebar = QWidget()
        sidebar.setMaximumWidth(270)
        sidebar.setMinimumWidth(190)
        side = QVBoxLayout(sidebar)
        side.setContentsMargins(0, 0, 10, 0)
        caption = QLabel("CHANNELS")
        caption.setStyleSheet("font-weight: 700; color: #64748b; font-size: 11px;")
        side.addWidget(caption)
        hint = QLabel("Select one or more to compare.")
        hint.setStyleSheet("color: #64748b;")
        side.addWidget(hint)
        self.channels = QListWidget()
        self.channels.setObjectName("recordingChannels")
        self.channels.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.channels.itemSelectionChanged.connect(self.refresh_plot)
        side.addWidget(self.channels, 1)
        select_all = QPushButton("Select all")
        select_all.clicked.connect(self.channels.selectAll)
        side.addWidget(select_all)
        splitter.addWidget(sidebar)

        graph = QWidget()
        graph_layout = QVBoxLayout(graph)
        graph_layout.setContentsMargins(0, 0, 0, 0)
        options = QHBoxLayout()
        self.raw_checkbox = QCheckBox("Raw signal")
        self.raw_checkbox.setChecked(True)
        self.raw_checkbox.toggled.connect(self.refresh_plot)
        options.addWidget(self.raw_checkbox)
        self.smooth_checkbox = QCheckBox("Moving average")
        self.smooth_checkbox.toggled.connect(self.refresh_plot)
        options.addWidget(self.smooth_checkbox)
        options.addStretch()
        options.addWidget(QLabel("Window"))
        self.window_spin = QSpinBox()
        self.window_spin.setObjectName("smoothingWindow")
        self.window_spin.setRange(1, 100000)
        self.window_spin.setValue(51)
        self.window_spin.setSuffix(" samples")
        self.window_spin.valueChanged.connect(self._update_smoothing)
        options.addWidget(self.window_spin)
        graph_layout.addLayout(options)

        self.plot = pg.PlotWidget(background="#ffffff")
        self.plot.setObjectName("recordingPlot")
        self.plot.showGrid(x=True, y=True, alpha=0.15)
        self.plot.setLabel("bottom", "Time", units="s")
        self.plot.setLabel("left", "Value")
        for edge in ("left", "bottom"):
            self.plot.getAxis(edge).setPen("#94a3b8")
            self.plot.getAxis(edge).setTextPen("#64748b")
        self.legend = self.plot.addLegend(offset=(14, 12), labelTextColor="#334155")
        graph_layout.addWidget(self.plot, 1)
        splitter.addWidget(graph)
        splitter.setStretchFactor(1, 1)
        splitter.setSizes([210, 830])
        root.addWidget(splitter, 1)

        self.status_label = QLabel("Pan to explore · Scroll to zoom · Right-click for plot options")
        self.status_label.setStyleSheet("color: #64748b; font-size: 11px;")
        root.addWidget(self.status_label)

    def open_recording(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Open recording", "", "Recordings (*.csv *.mat);;All files (*)"
        )
        if path:
            try:
                self.load_file(path)
            except (OSError, ValueError, TypeError, IndexError) as exc:
                QMessageBox.warning(self, "Could not open recording", str(exc))

    def load_file(self, path):
        """Read a recording, replacing the displayed data only on success."""
        recording = import_recording(path)
        self.recording = recording
        self.source = Path(path)
        self.channels.blockSignals(True)
        self.channels.clear()
        for index, label in enumerate(recording.labels):
            item = QListWidgetItem(label)
            item.setData(Qt.ItemDataRole.UserRole, index)
            self.channels.addItem(item)
            item.setSelected(True)
        self.channels.blockSignals(False)
        self.file_label.setText(
            f"{self.source.name}  ·  {len(recording.times):,} samples  ·  "
            f"{recording.values.shape[1]} channels"
        )
        self.save_button.setEnabled(bool(recording.values.size))
        self._update_smoothing()
        self.plot.enableAutoRange()

    def _selected_columns(self):
        return sorted(
            item.data(Qt.ItemDataRole.UserRole) for item in self.channels.selectedItems()
        )

    def _update_smoothing(self, *_):
        if self.recording is not None:
            self._smoothed = smooth_values(self.recording.values, self.window_spin.value())
        self.refresh_plot()

    def refresh_plot(self, *_):
        self.plot.clear()
        self.legend.clear()
        if self.recording is None:
            return
        for column in self._selected_columns():
            color = COLORS[column % len(COLORS)]
            label = self.recording.labels[column]
            if self.raw_checkbox.isChecked():
                self.plot.plot(
                    self.recording.times, self.recording.values[:, column],
                    pen=pg.mkPen(color, width=1.5), name=label, connect="finite",
                )
            if self.smooth_checkbox.isChecked():
                self.plot.plot(
                    self.recording.times, self._smoothed[:, column],
                    pen=pg.mkPen(color, width=2.5, style=Qt.PenStyle.DashLine),
                    name=f"{label} · mean", connect="finite",
                )

    def save_smoothed(self):
        if self.recording is None:
            return
        if not self._selected_columns():
            QMessageBox.information(self, "Select channels", "Select at least one channel to export.")
            return
        suggestion = f"{self.source.stem if self.source else 'recording'}_smoothed.csv"
        path, _ = QFileDialog.getSaveFileName(self, "Export smoothed signals", suggestion, "CSV (*.csv)")
        if path:
            target = Path(path)
            if target.suffix.lower() != ".csv":
                target = Path(str(target) + ".csv")
            try:
                self.export_smoothed(target)
            except OSError as exc:
                QMessageBox.warning(self, "Could not export recording", str(exc))

    def export_smoothed(self, path):
        """Save selected smoothed signals in the same importable long CSV format."""
        if self.recording is None:
            raise ValueError("Open a recording first.")
        selected = self._selected_columns()
        if not selected:
            raise ValueError("Select at least one channel to export.")
        with Path(path).open("w", encoding="utf-8", newline="") as stream:
            writer = csv.writer(stream)
            writer.writerow(("time_s", "channel", "row", "column", "label", "value"))
            for column in selected:
                for timestamp, value in zip(self.recording.times, self._smoothed[:, column]):
                    if np.isfinite(value):
                        writer.writerow((
                            format(timestamp, ".12g"), column + 1, -1, -1,
                            self.recording.labels[column], format(value, ".12g"),
                        ))
        self.status_label.setText(f"Saved smoothed signals to {Path(path).name}")
