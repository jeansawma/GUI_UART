"""UART Studio desktop workspace. Run with ``python -m uart_gui --demo``."""
from __future__ import annotations

import argparse
from datetime import datetime
import math
from pathlib import Path
from queue import Empty
import sys

import numpy as np
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QAction, QColor, QFont
from PySide6.QtWidgets import (
    QApplication, QCheckBox, QComboBox, QFileDialog, QFrame, QHBoxLayout,
    QHeaderView, QLabel, QLineEdit, QListWidget, QMainWindow, QMessageBox,
    QPlainTextEdit, QPushButton, QSplitter, QTableWidget, QTableWidgetItem,
    QTabWidget, QVBoxLayout, QWidget,
)
import pyqtgraph as pg

from .catalog import FIELD_BY_ADDRESS, SECTIONS, START_COMMANDS, STOP_COMMANDS
from .model import AcquisitionModel
from .protocol import Description, PlotSamples, Values, encode_command
from .session import Session
from .style import COLORS, STYLESHEET
from .transport import TransportError, available_ports


def label(text, name=None):
    widget = QLabel(text)
    if name:
        widget.setObjectName(name)
    return widget


def button(text, callback, name=None):
    widget = QPushButton(text)
    if name:
        widget.setObjectName(name)
    widget.clicked.connect(callback)
    return widget


def card():
    widget = QFrame()
    widget.setObjectName("card")
    return widget


class MainWindow(QMainWindow):
    def __init__(self, *, demo=False):
        super().__init__()
        self.setWindowTitle("UART Studio · Device workspace")
        self.resize(1440, 920)
        self.setMinimumSize(1140, 720)
        self.model = AcquisitionModel()
        self.session = Session(self)
        self.session.state_changed.connect(self._state_changed)
        self.session.message.connect(self.log)
        self.session.routing_finished.connect(self._routing_finished)
        self._pending_connection = False
        self._paused = False
        self._events_count = 0
        self._routing_pending = None
        self._editors = {}
        self._field_rows = {}
        self._checkboxes = {}
        self._live_items = {}
        self._name_items = {}
        self._write_buttons = []
        self._curves = {}
        self._curve_labels = {}
        self._scope_curves = {}
        self._scope_data = {}
        self._build()
        self.refresh_ports()
        self._state_changed(False, "Disconnected")
        self._build_table(0)
        self._refresh_timer = QTimer(self)
        self._refresh_timer.timeout.connect(self._refresh)
        self._refresh_timer.start(150)
        self._receive_timer = QTimer(self)
        self._receive_timer.timeout.connect(self._receive)
        self._receive_timer.start(30)
        self.log("Workspace ready. Connect a serial device or explore with Demo mode.")
        if demo:
            QTimer.singleShot(0, self.start_demo)

    def _build(self):
        root = QWidget()
        self.setCentralWidget(root)
        outer = QHBoxLayout(root)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)
        sidebar = QFrame()
        sidebar.setObjectName("sidebar")
        sidebar.setFixedWidth(178)
        side = QVBoxLayout(sidebar)
        side.setContentsMargins(16, 28, 16, 24)
        side.addWidget(label("◉ UART", "brand"))
        side.addWidget(label("S T U D I O    /    1.0", "brandSub"))
        side.addSpacing(38)
        side.addWidget(label("DEVICE WORKSPACE", "sideLabel"))
        self.navigation = QListWidget()
        self.navigation.setObjectName("navigation")
        self.navigation.addItems([section.title for section in SECTIONS])
        self.navigation.setCurrentRow(0)
        self.navigation.currentRowChanged.connect(self._build_table)
        side.addWidget(self.navigation)
        side.addWidget(label("RECORDINGS", "sideLabel"))
        viewer_button = button("Open recording…", self.open_recording)
        viewer_button.setStyleSheet("background: #203d4b; color: #cbe1e8; border: 1px solid #355461;")
        side.addWidget(viewer_button)
        side.addSpacing(20)
        note = label("Serial control\nLive acquisition\nOffline analysis", "sideNote")
        note.setStyleSheet("line-height: 150%;")
        side.addWidget(note)
        outer.addWidget(sidebar)

        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setContentsMargins(26, 22, 26, 16)
        layout.setSpacing(16)
        header = QHBoxLayout()
        titles = QVBoxLayout()
        titles.setSpacing(3)
        titles.addWidget(label("DEVICE WORKSPACE", "eyebrow"))
        titles.addWidget(label("Measure. Tune. Understand.", "title"))
        self.tagline = label("Your signals and device controls, in one place.", "muted")
        titles.addWidget(self.tagline)
        header.addLayout(titles)
        header.addStretch()
        self.status_pill = label("● Disconnected", "pill")
        status_labels = QVBoxLayout()
        status_labels.addWidget(self.status_pill)
        self.device_error = label("Device error: —", "muted")
        self.device_error.setAlignment(Qt.AlignmentFlag.AlignRight)
        status_labels.addWidget(self.device_error)
        status_labels.addStretch()
        header.addLayout(status_labels)
        layout.addLayout(header)

        connection = card()
        connection_row = QHBoxLayout(connection)
        connection_row.setContentsMargins(16, 12, 16, 12)
        connection_row.addWidget(label("SERIAL PORT", "eyebrow"))
        self.port = QComboBox()
        self.port.setObjectName("port")
        self.port.setEditable(True)
        self.port.setMinimumWidth(170)
        self.port.setToolTip("Select a local port or type its device path.")
        connection_row.addWidget(self.port, 1)
        self.refresh_button = button("↻", self.refresh_ports)
        self.refresh_button.setToolTip("Refresh serial ports")
        connection_row.addWidget(self.refresh_button)
        self.baud = QComboBox()
        self.baud.addItems(["9600", "19200", "38400", "57600", "115200", "230400", "460800", "921600"])
        self.baud.setEditable(True)
        self.baud.setCurrentText("115200")
        self.baud.setMaximumWidth(110)
        self.baud.setToolTip("Baud rate · 8 data bits, no parity, 1 stop bit")
        connection_row.addWidget(self.baud)
        self.connect_button = button("Connect", self.toggle_connection, "primary")
        self.connect_button.setObjectName("primary")
        connection_row.addWidget(self.connect_button)
        self.demo_button = button("Demo mode", self.start_demo)
        connection_row.addWidget(self.demo_button)
        layout.addWidget(connection)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setChildrenCollapsible(False)
        controls = card()
        controls.setMinimumWidth(480)
        control_layout = QVBoxLayout(controls)
        control_layout.setContentsMargins(14, 16, 14, 12)
        control_layout.setSpacing(10)
        table_heading = QHBoxLayout()
        self.section_title = label("Variables", "cardTitle")
        table_heading.addWidget(self.section_title)
        table_heading.addStretch()
        self.fields_count = label("24 signals", "muted")
        table_heading.addWidget(self.fields_count)
        control_layout.addLayout(table_heading)
        self.search = QLineEdit()
        self.search.setObjectName("search")
        self.search.setPlaceholderText("Search signals…")
        self.search.textChanged.connect(self._filter)
        control_layout.addWidget(self.search)
        self.table = QTableWidget()
        self.table.setObjectName("signals")
        self.table.setAlternatingRowColors(True)
        self.table.setShowGrid(False)
        self.table.verticalHeader().hide()
        self.table.setSelectionMode(QTableWidget.SelectionMode.NoSelection)
        self.table.verticalHeader().setDefaultSectionSize(44)
        control_layout.addWidget(self.table, 1)
        actions = QHBoxLayout()
        self.description_button = button("Refresh names", self.refresh_descriptions)
        actions.addWidget(self.description_button)
        actions.addStretch()
        self.live_button = button("Use live", self.use_live)
        self.write_all_button = button("Write all", self.write_all, "primary")
        actions.addWidget(self.live_button)
        actions.addWidget(self.write_all_button)
        control_layout.addLayout(actions)
        self.edit_hint = label("Select a signal to add it to the live plot.", "muted")
        self.edit_hint.setWordWrap(True)
        control_layout.addWidget(self.edit_hint)
        splitter.addWidget(controls)

        acquisition = card()
        acquisition.setMinimumWidth(360)
        plot_layout = QVBoxLayout(acquisition)
        plot_layout.setContentsMargins(16, 16, 16, 12)
        plot_layout.setSpacing(8)
        plot_heading = QHBoxLayout()
        plot_heading.addWidget(label("Live acquisition", "cardTitle"))
        plot_heading.addStretch()
        self.channel_count = label("0 / 15 channels", "muted")
        plot_heading.addWidget(self.channel_count)
        plot_layout.addLayout(plot_heading)
        self.plot_note = label("20 s sweep  ·  10 ms display step  ·  Drag to zoom", "muted")
        plot_layout.addWidget(self.plot_note)
        self.plot_tabs = QTabWidget()
        self.plot = self._new_plot("Time", "s")
        self.plot.setXRange(0, self.model.window, padding=0)
        self.plot.setLabel("left", "Value")
        self.plot.addLegend(offset=(12, 10), labelTextColor="#587482", brush=pg.mkBrush(255, 255, 255, 220), pen=None)
        self.plot_tabs.addTab(self.plot, "Signals")
        self.scope_plot = self._new_plot("Time", "s")
        self.scope_plot.setLabel("left", "Value")
        self.scope_plot.addLegend(offset=(12, 10), labelTextColor="#587482", brush=pg.mkBrush(255, 255, 255, 220), pen=None)
        self.plot_tabs.addTab(self.scope_plot, "Scopes")
        plot_layout.addWidget(self.plot_tabs, 1)
        self.empty_hint = label("Select signals on the left to start plotting.", "muted")
        self.empty_hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        plot_layout.addWidget(self.empty_hint)
        plot_actions = QHBoxLayout()
        self.pause_button = button("Pause plot", self.toggle_pause)
        plot_actions.addWidget(self.pause_button)
        plot_actions.addWidget(button("Reset", self.reset_acquisition))
        plot_actions.addStretch()
        plot_actions.addWidget(button("Export…", self.export_recording))
        plot_layout.addLayout(plot_actions)
        splitter.addWidget(acquisition)
        splitter.setSizes([510, 660])
        splitter.setStretchFactor(0, 4)
        splitter.setStretchFactor(1, 5)
        layout.addWidget(splitter, 1)

        commands = card()
        command_row = QHBoxLayout(commands)
        command_row.setContentsMargins(16, 12, 16, 12)
        command_row.addWidget(label("DEVICE COMMANDS", "eyebrow"))
        command_row.addStretch()
        self.start_buttons = []
        for caption, command in START_COMMANDS.items():
            start_button = button(caption, lambda checked=False, cmd=command, text=caption: self.send_commands([cmd], text))
            start_button.setToolTip("Send the original " + caption + " device command")
            self.start_buttons.append(start_button)
            command_row.addWidget(start_button)
        self.stop_button = button("■  STOP ALL", self.stop_device, "stop")
        self.stop_button.setToolTip("Send zero to W, I and Identification; cancels queued writes. Not a hardware emergency stop.")
        command_row.addWidget(self.stop_button)
        layout.addWidget(commands)

        self.log_box = QPlainTextEdit()
        self.log_box.setObjectName("activity")
        self.log_box.setReadOnly(True)
        self.log_box.setMaximumHeight(72)
        self.log_box.setMaximumBlockCount(300)
        layout.addWidget(self.log_box)
        outer.addWidget(content, 1)
        self.statusBar().showMessage("Disconnected · No device data")
        menu = self.menuBar().addMenu("File")
        for caption, callback in [("Open recording…", self.open_recording), ("Export acquisition…", self.export_recording), ("Export scopes…", self.export_scopes), ("Close", self.close)]:
            action = QAction(caption, self)
            action.triggered.connect(callback)
            menu.addAction(action)
        help_menu = self.menuBar().addMenu("Help")
        help_action = QAction("About UART Studio", self)
        help_action.triggered.connect(lambda: QMessageBox.information(self, "UART Studio", "Python successor to the MATLAB GUIDE UART tools.\n\n15 plot channels · 142 device fields · MAT/CSV recordings\n\nDevice names arrive from firmware. Demo mode uses simulated data.\nPhysical firmware compatibility requires testing on your device.\n\nSee README.md and docs/MIGRATION.md for setup and protocol details."))
        help_menu.addAction(help_action)

    @staticmethod
    def _new_plot(axis, units):
        plot = pg.PlotWidget(background="white")
        plot.setLabel("bottom", axis, units)
        plot.showGrid(x=True, y=True, alpha=.12)
        plot.setMouseEnabled(x=True, y=True)
        for name in ["left", "bottom"]:
            plot.getAxis(name).setPen(pg.mkPen("#d9e3e8"))
            plot.getAxis(name).setTextPen(pg.mkPen("#78909c"))
        plot.setMenuEnabled(False)
        return plot

    @property
    def section(self):
        return SECTIONS[max(0, self.navigation.currentRow())]

    def _build_table(self, index):
        if not hasattr(self, "table"):
            return
        # Retain unsent edits when navigating between panels.
        previous = getattr(self, "_drafts", {})
        for address, editor in self._editors.items():
            previous[address] = editor.text()
        self._drafts = previous
        self._editors.clear()
        self._field_rows.clear()
        self._checkboxes.clear()
        self._live_items.clear()
        self._name_items.clear()
        self._write_buttons.clear()
        section = SECTIONS[index]
        self.section_title.setText(section.title)
        editable = any(field.editable for field in section.fields)
        self.table.clear()
        self.table.setColumnCount(5 if editable else 3)
        self.table.setHorizontalHeaderLabels(["PLOT", "SIGNAL", "LIVE VALUE", "NEW VALUE", ""] if editable else ["PLOT", "SIGNAL", "LIVE VALUE"])
        self.table.setColumnHidden(0, not any(field.plottable for field in section.fields))
        self.table.setRowCount(len(section.fields))
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Fixed)
        header.resizeSection(0, 46)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Fixed)
        header.resizeSection(2, 95)
        if editable:
            header.setSectionResizeMode(3, QHeaderView.ResizeMode.Fixed)
            header.resizeSection(3, 100)
            header.setSectionResizeMode(4, QHeaderView.ResizeMode.Fixed)
            header.resizeSection(4, 64)
        for row, field in enumerate(section.fields):
            address = field.address
            self._field_rows[address] = row
            if field.plottable:
                checkbox = QCheckBox()
                checkbox.setChecked(address in self.model.slots)
                checkbox.setToolTip("Add to live plot (up to 15 signals)")
                checkbox.toggled.connect(lambda enabled, addr=address: self.select_signal(addr, enabled))
                wrapper = QWidget()
                centered = QHBoxLayout(wrapper)
                centered.setContentsMargins(14, 0, 0, 0)
                centered.addWidget(checkbox)
                self.table.setCellWidget(row, 0, wrapper)
                self._checkboxes[address] = checkbox
            name = QTableWidgetItem(self.field_label(address))
            name.setToolTip(f"Firmware address: row {field.row}, column {field.column} (zero-based)")
            name.setFlags(Qt.ItemFlag.ItemIsEnabled)
            self.table.setItem(row, 1, name)
            self._name_items[address] = name
            live = QTableWidgetItem("—")
            live.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            live.setForeground(QColor("#227b84"))
            live.setFont(QFont("monospace", 10))
            live.setFlags(Qt.ItemFlag.ItemIsEnabled)
            self.table.setItem(row, 2, live)
            self._live_items[address] = live
            if editable:
                editor = QLineEdit(previous.get(address, ""))
                editor.setPlaceholderText("Set value")
                editor.setToolTip("Finite float32 number. Press Enter or Write to send.")
                editor.textEdited.connect(lambda text, edit=editor: self._edited(edit, text))
                editor.returnPressed.connect(lambda addr=address: self.write_field(addr))
                self.table.setCellWidget(row, 3, editor)
                self._editors[address] = editor
                write = button("Write", lambda checked=False, addr=address: self.write_field(addr), "write")
                write.setEnabled(self.session.connected)
                self.table.setCellWidget(row, 4, write)
                self._write_buttons.append(write)
        self.live_button.setVisible(editable)
        self.write_all_button.setVisible(editable)
        self.write_all_button.setEnabled(self.session.connected)
        self.live_button.setEnabled(self.session.connected)
        self.edit_hint.setText("Changes send only when you press Write. Write all uses your edits or current live values." if editable else "Select a signal to add it to the live plot. Up to 15 channels can be viewed together.")
        self._refresh_fields()
        self._filter()

    @staticmethod
    def _edited(editor, text):
        editor.setProperty("invalid", False)
        editor.setProperty("dirty", bool(text))
        editor.style().unpolish(editor)
        editor.style().polish(editor)

    def field_label(self, address):
        return self.model.descriptions.get(address) or (FIELD_BY_ADDRESS[address].label if address in FIELD_BY_ADDRESS else f"R{address[0]} C{address[1]}")

    def _filter(self):
        query = self.search.text().strip().casefold()
        shown = 0
        for address, row in self._field_rows.items():
            visible = query in (self.field_label(address) + f" {address[0]},{address[1]}").casefold()
            self.table.setRowHidden(row, not visible)
            shown += int(visible)
        self.fields_count.setText(f"{shown} / {len(self._field_rows)} signals")

    def refresh_ports(self):
        current = self.port.currentText()
        self.port.clear()
        try:
            for device, description in available_ports():
                self.port.addItem(device)
                self.port.setItemData(self.port.count() - 1, description, Qt.ItemDataRole.ToolTipRole)
        except Exception as exc:
            self.log(f"Port scan: {exc}")
        if current:
            self.port.setCurrentText(current)
        self.port.lineEdit().setPlaceholderText("Select or type a port")

    def toggle_connection(self):
        if self.session.connected or self._pending_connection:
            self.session.disconnect_device()
            self._pending_connection = False
            self.connect_button.setEnabled(False)
            return
        port = self.port.currentText().strip()
        if not port:
            self.notify("Select a serial port, or use Demo mode to explore without hardware.")
            return
        try:
            baudrate = int(self.baud.currentText())
            if baudrate <= 0:
                raise ValueError
        except ValueError:
            self.notify("Enter a positive integer baud rate.")
            return
        self._connect(port, baudrate, False)

    def start_demo(self):
        if not self._pending_connection:
            self._connect("Demo", 115200, True)

    def _connect(self, port, baudrate, demo):
        self.model.clear()
        self.model.values.clear()
        self.model.descriptions.clear()
        self.model.sample_period = .0001
        self._clear_session_events()
        self._pending_connection = True
        self._routing_pending = None
        self.connect_button.setEnabled(False)
        self.demo_button.setEnabled(False)
        self.status_pill.setText("● Connecting…")
        self.session.connect_device(port, baudrate, demo)

    def _clear_session_events(self):
        while True:
            try:
                self.session.events.get_nowait()
            except Empty:
                break

    def _state_changed(self, connected, description):
        self._pending_connection = False
        self.connect_button.setEnabled(True)
        self.connect_button.setText("Disconnect" if connected else "Connect")
        self.demo_button.setEnabled(not connected)
        self.port.setEnabled(not connected)
        self.baud.setEnabled(not connected)
        self.refresh_button.setEnabled(not connected)
        self.description_button.setEnabled(connected)
        self.write_all_button.setEnabled(connected)
        self.live_button.setEnabled(connected)
        for widget in self.start_buttons + self._write_buttons + [self.stop_button]:
            widget.setEnabled(connected)
        self.status_pill.setText("● " + ("Demo mode" if connected and self.session.demo else "Connected" if connected else "Disconnected"))
        self.status_pill.setStyleSheet("background: #def2ed; color: #157d70;" if connected else "")
        self.log(description)
        if connected:
            # Demo starts with three signals; connecting hardware never starts W/I/Ident.
            if self.session.demo and all(slot is None for slot in self.model.slots):
                for address in [(0, 0), (0, 3), (7, 0)]:
                    self.model.select_signal(*address)
                self._build_table(self.navigation.currentRow())
            self.refresh_descriptions()
            if any(slot is not None for slot in self.model.slots):
                self._route_signals()
        else:
            self._routing_pending = None
        self._refresh_fields()

    def refresh_descriptions(self):
        # Match two requests separated by .5 seconds without blocking the GUI.
        self.send_commands([(0, 0, 0, "D")], "Description request")
        generation = self.session._generation
        QTimer.singleShot(500, lambda: self.send_commands([(0, 0, 0, "D")]) if self.session.connected and self.session._generation == generation else None)

    def send_commands(self, commands, caption="", *, urgent=False):
        try:
            self.session.send_many(commands, urgent=urgent, label=caption)
            return True
        except (ValueError, ConnectionError) as exc:
            self.notify(str(exc))
            return False

    def _editor_value(self, address):
        editor = self._editors[address]
        try:
            value = float(editor.text()) if editor.text().strip() else self.model.values[address]
            encode_command(value, *address)
        except (ValueError, KeyError, OverflowError):
            editor.setProperty("invalid", True)
            editor.style().unpolish(editor)
            editor.style().polish(editor)
            editor.setFocus()
            raise ValueError(f"{self.field_label(address)}: enter a finite float32 value.") from None
        return value

    def write_field(self, address):
        try:
            value = self._editor_value(address)
        except ValueError as exc:
            self.notify(str(exc))
            return
        self.send_commands([(value, *address)], self.field_label(address))

    def write_all(self):
        try:
            commands = [(self._editor_value(field.address), *field.address) for field in self.section.fields if field.editable]
        except ValueError as exc:
            self.notify(str(exc) + " No values were sent.")
            return
        self.send_commands(commands, self.section.title + " batch")

    def use_live(self):
        for address, editor in self._editors.items():
            if address in self.model.values:
                editor.setText(format(self.model.values[address], ".8g"))
                self._edited(editor, "")

    def stop_device(self):
        if self.send_commands(STOP_COMMANDS, "STOP ALL", urgent=True):
            if self._routing_pending is not None or any(slot is not None for slot in self.model.slots):
                self._route_signals()

    def _route_signals(self):
        self._routing_pending = self.session.route(self.model.mapping_commands())
        self.empty_hint.setText("Updating signal routing…")
        self.empty_hint.setVisible(True)

    def _routing_finished(self, revision):
        if revision != self._routing_pending:
            return
        # Discard samples received while mappings were in transition.
        self._receive(drop_plots=True)
        self._routing_pending = None
        self.empty_hint.setText("Select signals on the left to start plotting.")
        self.log("Signal routing sent. Device acknowledgement is not available.")

    def select_signal(self, address, enabled):
        try:
            self.model.select_signal(*address, enabled)
        except ValueError as exc:
            checkbox = self._checkboxes.get(address)
            if checkbox:
                checkbox.blockSignals(True)
                checkbox.setChecked(not enabled)
                checkbox.blockSignals(False)
            self.notify(str(exc))
            return
        if self.session.connected:
            self._route_signals()
        self._refresh_plot()

    def _receive(self, *, drop_plots=False):
        if self._pending_connection:
            return
        changed_names = False
        for _ in range(20000 if drop_plots else 1500):
            try:
                event = self.session.events.get_nowait()
            except Empty:
                break
            if isinstance(event, TransportError):
                self.log("Connection error: " + event.message)
                self.statusBar().showMessage(event.message)
                continue
            if isinstance(event, PlotSamples) and (drop_plots or self._routing_pending is not None):
                continue
            self._events_count += 1
            self.model.handle(event)
            changed_names |= isinstance(event, Description)
            if isinstance(event, Values) and event.row == 0 and len(event.values) > 2:
                sample_period = event.values[2]
                if math.isfinite(sample_period) and sample_period > 0 and not math.isclose(sample_period, self.model.sample_period, rel_tol=1e-6):
                    divider = math.floor(self.model.step / sample_period)
                    if divider >= 1:
                        self.model.sample_period = sample_period
                        self.send_commands([(divider, 13, 20)], "Display sample divider")
                    else:
                        self.log("Device sample period exceeds the 10 ms display step; divider unchanged.")
        if changed_names:
            self._filter()

    def _refresh_fields(self):
        error = self.model.values.get((0, 1))
        self.device_error.setText("Device error: " + (format(error, ".7g") if error is not None else "—"))
        self.device_error.setStyleSheet("color: #b64238; font-weight: 600;" if error else "")
        for address, item in self._live_items.items():
            value = self.model.values.get(address)
            item.setText(format(value, ".7g") if value is not None else "—")
            self._name_items[address].setText(self.field_label(address))
        # Edits are intentionally not overwritten by incoming telemetry.

    def _refresh_plot(self):
        selected = {index: address for index, address in enumerate(self.model.slots) if address is not None}
        for channel in list(self._curves):
            if channel not in selected or self._curve_labels[channel] != self.field_label(selected[channel]):
                self.plot.removeItem(self._curves.pop(channel))
                self._curve_labels.pop(channel, None)
        for channel, address in selected.items():
            caption = self.field_label(address)
            if channel not in self._curves:
                self._curves[channel] = self.plot.plot([], [], pen=pg.mkPen(COLORS[channel], width=1.8), name=caption)
                self._curve_labels[channel] = caption
            times, values = self.model.plot_data(channel)
            self._curves[channel].setData(times, values, connect="finite")
        for channel in list(self._scope_curves):
            if channel not in self.model.scope:
                self.scope_plot.removeItem(self._scope_curves.pop(channel))
                self._scope_data.pop(channel, None)
        for channel, values in self.model.scope.items():
            if channel not in self._scope_curves:
                self._scope_curves[channel] = self.scope_plot.plot([], [], pen=pg.mkPen(COLORS[channel % 15], width=1.4), name=f"Scope {channel + 1}")
            if self._scope_data.get(channel) is not values:
                self._scope_curves[channel].setData(np.arange(len(values)) * self.model.sample_period, values, connect="finite")
                self._scope_data[channel] = values
        self.channel_count.setText(f"{len(selected)} / 15 channels")
        self.empty_hint.setVisible((not selected or self._routing_pending is not None) and self.plot_tabs.currentIndex() == 0)
        self.plot_tabs.setTabText(1, f"Scopes ({len(self.model.scope)})" if self.model.scope else "Scopes")

    def _refresh(self):
        self._refresh_fields()
        if not self._paused:
            self._refresh_plot()
        transport = self.session.transport
        if transport is not None:
            dropped = transport.dropped_events + self.session.dropped_events
            self.statusBar().showMessage(f"{'SIMULATED DATA' if self.session.demo else 'Serial'}  ·  RX {transport.bytes_received:,} B  ·  TX {transport.bytes_sent:,} B  ·  {self._events_count:,} events  ·  dropped {dropped:,}  ·  Ts {self.model.sample_period:g} s")

    def toggle_pause(self):
        self._paused = not self._paused
        self.pause_button.setText("Resume plot" if self._paused else "Pause plot")
        self.log("Plot paused; acquisition continues." if self._paused else "Plot resumed.")

    def reset_acquisition(self):
        self.model.clear()
        self._refresh_plot()
        self.log("Acquisition buffers reset. Device values and signal selection retained.")

    def export_recording(self):
        path, chosen = QFileDialog.getSaveFileName(self, "Export acquisition", "acquisition.mat", "MATLAB acquisition (*.mat);;CSV history (*.csv)")
        if not path:
            return
        if not Path(path).suffix:
            path += ".csv" if "CSV" in chosen else ".mat"
        try:
            if Path(path).suffix.lower() == ".csv":
                self.model.export_csv(path)
            else:
                self.model.export_mat(path)
            self.log("Acquisition exported to " + path)
        except Exception as exc:
            self.notify("Export failed: " + str(exc))

    def export_scopes(self):
        if not self.model.scope:
            self.notify("No scope data received yet. Scope blocks are sent by the device.")
            return
        path, _ = QFileDialog.getSaveFileName(self, "Export scopes", "scopefile.mat", "MATLAB scope data (*.mat)")
        if path:
            if not Path(path).suffix:
                path += ".mat"
            try:
                self.model.export_scopes_mat(path)
                self.log("Scopes exported to " + path)
            except Exception as exc:
                self.notify("Scope export failed: " + str(exc))

    def open_recording(self):
        from .viewer import RecordingViewer
        viewer = RecordingViewer(self)
        viewer.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        viewer.show()
        # Keep a Python reference while a nonmodal viewer is open.
        if not hasattr(self, "_viewers"):
            self._viewers = []
        self._viewers.append(viewer)
        viewer.destroyed.connect(lambda: self._viewers.remove(viewer) if viewer in self._viewers else None)

    def log(self, message):
        if hasattr(self, "log_box"):
            self.log_box.appendPlainText(f"{datetime.now().strftime('%H:%M:%S')}  {message}")

    def notify(self, message):
        self.log(message)
        self.statusBar().showMessage(message, 10000)
        # Nonmodal validation feedback: do not interrupt acquisition or typing.
        self.edit_hint.setText(message)

    def closeEvent(self, event):
        self._refresh_timer.stop()
        self._receive_timer.stop()
        self.session.close()
        event.accept()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if hasattr(self, "log_box"):
            # Give signal tables room on shorter laptop displays. Activity is
            # still retained; the status bar carries the latest feedback.
            self.log_box.setVisible(self.height() >= 800)
            self.tagline.setVisible(self.height() >= 800)


def main(argv=None):
    parser = argparse.ArgumentParser(description="UART Studio desktop control and acquisition")
    parser.add_argument("--demo", action="store_true", help="Start with simulated telemetry; no serial port is opened")
    args = parser.parse_args(argv)
    application = QApplication.instance() or QApplication(sys.argv[:1])
    application.setApplicationName("UART Studio")
    application.setStyle("Fusion")
    application.setStyleSheet(STYLESHEET)
    application.setFont(QFont("Inter", 10))
    pg.setConfigOptions(antialias=True)
    window = MainWindow(demo=args.demo)
    window.show()
    return application.exec()


if __name__ == "__main__":
    raise SystemExit(main())
