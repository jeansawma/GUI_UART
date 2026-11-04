"""Exercise the actual desktop workflow with its asynchronous demo device."""
import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import time
import numpy as np
import pytest
from PySide6.QtWidgets import QApplication, QFileDialog

from uart_gui.app import MainWindow
from uart_gui.model import import_recording
from uart_gui.style import STYLESHEET


@pytest.fixture(scope="module")
def application():
    app = QApplication.instance() or QApplication([])
    app.setStyleSheet(STYLESHEET)
    return app


def wait_until(application, condition, timeout=6):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        application.processEvents()
        if condition():
            return
        time.sleep(.01)
    raise AssertionError("GUI condition did not become true before timeout")


@pytest.fixture
def window(application):
    widget = MainWindow(demo=True)
    widget.show()
    wait_until(application, lambda: widget.session.connected and widget._routing_pending is None and len(widget.model.descriptions) == 142)
    wait_until(application, lambda: len(widget.model.history_data(0)[0]) > 0)
    yield widget
    widget.close()
    application.processEvents()


def test_demo_has_live_fields_plots_scopes_search_and_pause(window, application):
    assert len(window.model.scope) == 16
    assert len(window._curves) == 3
    assert window.device_error.text() == "Device error: 0"
    assert np.isfinite(window.model.vplot).any()
    window.search.setText("Variable 04")
    assert sum(not window.table.isRowHidden(r) for r in range(24)) == 1
    window.search.clear()
    window.toggle_pause()
    count = window._events_count
    wait_until(application, lambda: window._events_count > count)
    assert window._paused  # pausing rendering must not pause acquisition
    window.toggle_pause()
    window.reset_acquisition()
    assert not window.model.scope
    assert len(window.model.history_data(0)[0]) == 0


def test_edits_are_validated_echoed_and_preserved_across_panels(window, application):
    window.navigation.setCurrentRow(1)
    address = (6, 0)
    window._editors[address].setText("nan")
    calls = []
    real_send = window.send_commands
    window.send_commands = lambda *args, **kwargs: calls.append(args)
    window.write_all()
    assert not calls  # no partial batch when any edit is invalid
    assert window._editors[address].property("invalid") is True
    window._editors[address].setText("12.75")
    window.write_all()
    assert len(calls) == 1
    assert len(calls[0][0]) == 18
    assert calls[0][0][0] == (12.75, 6, 0)
    window.send_commands = real_send
    window._editors[address].setText("12.75")
    window.write_field(address)
    wait_until(application, lambda: window.model.values[address] == 12.75)
    window.navigation.setCurrentRow(2)
    window.navigation.setCurrentRow(1)
    assert window._editors[address].text() == "12.75"
    assert window.table.isColumnHidden(0)
    window.use_live()
    assert window._editors[address].text() == "12.75"


def test_plot_limit_stop_resync_and_disconnect(window, application):
    for field in window.section.fields:
        if field.address not in window.model.slots and sum(s is not None for s in window.model.slots) < 15:
            window.select_signal(field.address, True)
    assert sum(s is not None for s in window.model.slots) == 15
    extra = next(field.address for field in window.section.fields if field.address not in window.model.slots)
    window.select_signal(extra, True)
    assert extra not in window.model.slots
    # A STOP during a routing update must be followed by the final route mapping.
    window.stop_device()
    wait_until(application, lambda: window._routing_pending is None)
    for col in range(3):
        assert window.session.transport._values[2][col] == 0
    for channel, address in enumerate(window.model.slots):
        row = 13 if channel < 10 else 14
        col = 2 * (channel if channel < 10 else channel - 10)
        assert tuple(window.session.transport._values[row][col:col + 2]) == address
    window.toggle_connection()
    wait_until(application, lambda: not window.session.connected and window.connect_button.text() == "Connect")
    assert not window.stop_button.isEnabled()


def test_export_actions_roundtrip_real_acquisition(window, application, monkeypatch, tmp_path):
    acquisition = tmp_path / "acquisition.mat"
    monkeypatch.setattr(QFileDialog, "getSaveFileName", lambda *args: (str(acquisition), "MATLAB acquisition (*.mat)"))
    window.export_recording()
    recording = import_recording(acquisition)
    assert len(recording.times) > 0
    assert np.isfinite(recording.values[:, 0]).any()
    scopes = tmp_path / "scopes.mat"
    monkeypatch.setattr(QFileDialog, "getSaveFileName", lambda *args: (str(scopes), "MATLAB scope data (*.mat)"))
    window.export_scopes()
    assert import_recording(scopes).values.shape == (500, 16)
