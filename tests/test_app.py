"""Exercise the actual desktop workflow with its asynchronous demo device."""
import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import time
import numpy as np
import pytest
from PySide6.QtWidgets import QApplication, QFileDialog

from uart_gui.app import MainWindow
from uart_gui.model import import_recording
from uart_gui.protocol import PlotSamples, ScopeSamples
from uart_gui.session import RoutingComplete
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


@pytest.fixture
def idle_window(application):
    widget = MainWindow()
    yield widget
    widget.close()
    application.processEvents()


def test_receive_budget_yields_without_losing_recorded_samples(idle_window):
    widget = idle_window
    widget.model.select_signal(0, 0)
    for index in range(300):
        widget.session.events.put(PlotSamples(0, (float(index),), index * 100))
    widget.RECEIVE_BUDGET_SECONDS = 0  # Always yield after the first event.
    widget._receive()
    assert widget.session.events.qsize() == 299
    assert widget._events_count == 1
    widget.RECEIVE_BUDGET_SECONDS = 1
    widget._receive()
    assert widget.session.events.qsize() == 43  # 256-event count bound.
    widget._receive()
    assert widget.session.events.empty()
    assert widget._events_count == 300
    times, values = widget.model.history_data(0)
    np.testing.assert_allclose(times, np.arange(300) * .01)
    np.testing.assert_array_equal(values, np.arange(300))


def test_routing_boundary_is_ordered_even_across_multiple_gui_turns(idle_window):
    widget = idle_window
    widget.model.select_signal(0, 0)
    widget._routing_pending = 42
    widget.RECEIVE_MAX_EVENTS = 1
    widget.session.events.put(PlotSamples(0, (111.0,), 0))
    widget.session.events.put(RoutingComplete(42))
    widget.session.events.put(PlotSamples(0, (222.0,), 100))
    widget._receive()
    assert widget._routing_pending == 42
    assert widget._routing_discarded == 1
    assert len(widget.model.history_data(0)[0]) == 0
    widget._receive()
    assert widget._routing_pending is None
    assert len(widget.model.history_data(0)[0]) == 0
    widget._receive()
    np.testing.assert_allclose(widget.model.history_data(0)[1], [222])


def test_unchanged_curves_are_not_redrawn(idle_window, monkeypatch):
    widget = idle_window
    widget.model.select_signal(0, 0)
    widget.model.handle(PlotSamples(0, (1.0,), 0))
    widget._refresh_plot()
    curve = widget._curves[0]
    assert curve.opts["antialias"] is False
    assert curve.opts["pen"].widthF() == 1
    changes = []
    original = curve.setData

    def capture(*args, **kwargs):
        changes.append(args)
        return original(*args, **kwargs)

    monkeypatch.setattr(curve, "setData", capture)
    for _ in range(10):
        widget._refresh()
    assert changes == []
    widget.model.handle(PlotSamples(0, (2.0,), 100))
    widget._refresh()
    assert len(changes) == 1
    widget._refresh()
    assert len(changes) == 1


def test_initial_divider_is_sent_for_default_clock_and_after_stop(idle_window, monkeypatch):
    widget = idle_window
    widget.session.connected = True
    writes = []

    def send(commands, caption="", **kwargs):
        writes.extend(commands)
        return True

    monkeypatch.setattr(widget, "send_commands", send)
    widget._sync_sample_timing(.0001)
    widget._sync_sample_timing(.0001)
    assert writes == [(100, 13, 20)]
    widget.model.values[0, 2] = .0001
    widget.stop_device()
    assert writes[-4:] == [(0, 2, 0), (0, 2, 1), (0, 2, 2), (100, 13, 20)]


def test_device_clock_change_resets_history_and_preserves_raw_scopes(idle_window, monkeypatch):
    widget = idle_window
    widget.model.select_signal(0, 0)
    widget.model.handle(PlotSamples(0, (1.0,), 0))
    widget.model.handle(ScopeSamples(0, (1.0, 2.0)))
    scope = widget.model.scope[0]
    widget.session.connected = True
    writes = []
    monkeypatch.setattr(widget, "send_commands", lambda commands, caption="", **kwargs: writes.extend(commands) or True)
    widget._sync_sample_timing(.00005)
    assert widget.model.sample_period == .00005
    assert len(widget.model.history_data(0)[0]) == 0
    assert widget.model.scope[0] is scope
    assert writes == [(200, 13, 20)]
    for invalid in (0, -1, float("nan"), float("inf"), 1e-300):
        widget._sync_sample_timing(invalid)
    assert writes == [(200, 13, 20)]


def test_display_rate_changes_do_not_change_acquisition_clock(idle_window):
    widget = idle_window
    assert widget.windowTitle().startswith("JS")
    assert widget._refresh_timer.interval() == 50
    widget.refresh_rate.setCurrentIndex(0)  # Original MATLAB display cadence.
    assert widget._refresh_timer.interval() == 200
    assert widget.model.sample_period == .0001
    assert widget.model.step == .01
