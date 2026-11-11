"""Command-worker regression checks using a controllable device driver."""
import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from queue import Empty, Queue
import threading
import time

import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication

from uart_gui.protocol import PlotSamples, Values
from uart_gui.session import RoutingComplete, Session
from uart_gui.transport import TransportError


def wait_until(condition, timeout=2):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if condition():
            return
        threading.Event().wait(.002)
    raise AssertionError("command worker did not reach the expected state")


class ControlledTransport:
    def __init__(self):
        self.events = Queue()
        self.sent = []
        self.connected = True
        self.on_send = None
        self.drain_started = threading.Event()
        self.drain_release = threading.Event()
        self.drain_release.set()
        self.cancelled_drains = 0

    def send(self, *command):
        self.sent.append((time.monotonic(), command))
        if self.on_send is not None:
            self.on_send(command)

    def wait_output(self, timeout=2, *, cancelled=None, progress=None):
        self.drain_started.set()
        deadline = time.monotonic() + timeout
        while True:
            if progress is not None:
                progress()
            if cancelled is not None and cancelled():
                self.cancelled_drains += 1
                return False
            if self.drain_release.wait(.002):
                return True
            if time.monotonic() >= deadline:
                raise TimeoutError("controlled output stall")

    def disconnect(self):
        self.connected = False
        self.drain_release.set()


@pytest.fixture(scope="module", autouse=True)
def application():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def session():
    result = Session()
    result.transport = ControlledTransport()
    result.connected = True
    yield result
    result.transport.drain_release.set()
    result.close()
    assert not result._thread.is_alive()


def queued_events(session):
    result = []
    while True:
        try:
            result.append(session.events.get_nowait())
        except Empty:
            return result


def test_route_has_no_numeric_batch_pauses_and_waits_for_output_before_fifo_boundary(session):
    transport = session.transport
    transport.drain_release.clear()
    finished = []
    session.routing_finished.connect(finished.append, Qt.ConnectionType.DirectConnection)
    commands = [(index, 13, index % 20) for index in range(50)]
    started = time.monotonic()
    revision = session.route(commands)
    # The old generic pacing took ~1.95 s before reaching this drain.
    assert transport.drain_started.wait(.8)
    assert time.monotonic() - started < .8
    assert [command for _, command in transport.sent] == commands
    assert not finished
    assert not any(isinstance(event, RoutingComplete) for event in queued_events(session))
    old_sample = PlotSamples(0, (1,), 10)
    transport.events.put(old_sample)
    wait_until(lambda: not session.events.empty())
    transport.drain_release.set()
    wait_until(lambda: finished == [revision])
    events = queued_events(session)
    assert events.index(old_sample) < events.index(RoutingComplete(revision))


def test_handshake_runs_before_pending_route_and_forwards_data_during_half_second_wait(session):
    transport = session.transport
    blocked = threading.Event()
    release = threading.Event()

    def on_send(command):
        if command[0] == 99:
            blocked.set()
            assert release.wait(1)

    transport.on_send = on_send
    session.send_many([(99, 6, 0)])
    assert blocked.wait(1)
    session.route([(6, 13, 0)])  # Priority3 is already pending.
    session.request_descriptions()  # Priority1 must overtake the route.
    release.set()
    wait_until(lambda: any(command[-1] == "D" for _, command in transport.sent))
    transport.events.put(Values(6, (3.5,)))
    wait_until(lambda: not session.events.empty())
    assert Values(6, (3.5,)) in queued_events(session)
    assert sum(command[-1] == "D" for _, command in transport.sent) == 1
    wait_until(lambda: len(transport.sent) == 4)
    first, second, route = transport.sent[1:]
    assert first[1] == second[1] == (0, 0, 0, "D")
    assert second[0] - first[0] >= .49
    assert route[1] == (6, 13, 0)
    assert route[0] >= second[0]


def test_stop_cancels_handshake_wait_and_stale_routing(session):
    transport = session.transport
    session.request_descriptions()
    session.route([(6, 13, 0)])
    wait_until(lambda: len(transport.sent) == 1)
    stop = [(0, 2, col) for col in range(3)]
    session.send_many(stop, urgent=True)
    wait_until(lambda: len(transport.sent) == 4, timeout=.4)
    # Wait beyond the original handshake deadline: the cancelled second D
    # and old routing job must not reappear after STOP.
    threading.Event().wait(.55)
    assert [command for _, command in transport.sent] == [(0, 0, 0, "D"), *stop]


def test_stop_cancels_pending_numeric_batch_after_current_write(session):
    transport = session.transport
    tenth = threading.Event()
    release = threading.Event()

    def on_send(command):
        if command == (9, 6, 0):
            tenth.set()
            assert release.wait(1)

    transport.on_send = on_send
    session.send_many([(index, 6, 0) for index in range(25)])
    assert tenth.wait(1)
    stop = [(0, 2, col) for col in range(3)]
    session.send_many(stop, urgent=True)
    release.set()
    wait_until(lambda: len(transport.sent) == 13)
    assert [command for _, command in transport.sent][-3:] == stop
    assert not any(command[1] == 6 and command[0] >= 10 for _, command in transport.sent)


def test_numeric_batch_retains_pause_between_groups_of_ten(session):
    session.send_many([(index, 6, 0) for index in range(11)])
    wait_until(lambda: len(session.transport.sent) == 11)
    times = [stamp for stamp, _ in session.transport.sent]
    assert times[10] - times[9] >= .29


def test_new_route_revision_cancels_output_wait_and_only_latest_boundary_survives(session):
    transport = session.transport
    transport.drain_release.clear()
    first = session.route([(1, 13, 0)])
    assert transport.drain_started.wait(1)
    second = session.route([(2, 13, 0)])
    wait_until(lambda: len(transport.sent) == 2)
    transport.drain_release.set()
    wait_until(lambda: session.events.qsize() >= 1)
    events = queued_events(session)
    assert RoutingComplete(first) not in events
    assert RoutingComplete(second) in events
    assert transport.cancelled_drains == 1


def test_boundary_and_errors_survive_queue_saturation_with_counted_loss(session):
    session.events = Queue(maxsize=2)
    session.events.put(Values(0, (1,)))
    session.events.put(Values(0, (2,)))
    revision = session.route([])
    wait_until(lambda: session.dropped_events == 1)
    assert queued_events(session) == [Values(0, (2,)), RoutingComplete(revision)]
    session.events.put(Values(0, (3,)))
    session.events.put(Values(0, (4,)))
    session.transport.events.put(TransportError("removed"))
    wait_until(lambda: not session.connected)
    assert queued_events(session) == [Values(0, (4,)), TransportError("removed")]
    assert session.dropped_events == 2


def test_routing_boundary_follows_entire_preexisting_transport_backlog(session):
    transport = session.transport
    backlog = [PlotSamples(0, (float(index),), index) for index in range(5001)]

    def output_drain_with_backlog(timeout=2, *, cancelled=None, progress=None):
        # Model a reader burst just as the OS transmit drain completes. This
        # backlog is larger than two ordinary 2,000-event forwarding turns.
        for event in backlog:
            transport.events.put(event)
        return True

    transport.wait_output = output_drain_with_backlog
    completed = threading.Event()
    session.routing_finished.connect(lambda revision: completed.set(), Qt.ConnectionType.DirectConnection)
    revision = session.route([(6, 13, 0)])
    assert completed.wait(1)
    events = queued_events(session)
    assert events[:len(backlog)] == backlog
    assert events[len(backlog)] == RoutingComplete(revision)
    assert session.dropped_events == 0


def test_initial_handshake_then_timing_write_precedes_route_and_default_numeric_jobs(session):
    transport = session.transport
    blocked = threading.Event()
    release = threading.Event()

    def on_send(command):
        if command == (99, 6, 0):
            blocked.set()
            assert release.wait(1)

    transport.on_send = on_send
    session.send_many([(99, 6, 0)])
    assert blocked.wait(1)
    # Enqueue lower priorities first, while the worker is held in a write.
    session.send_many([(12, 6, 0)])
    session.route([(7, 13, 0)])
    session.send_many([(100, 13, 20)], priority=2)
    session.request_descriptions()
    release.set()
    wait_until(lambda: len(transport.sent) == 6)
    assert [command for _, command in transport.sent] == [
        (99, 6, 0), (0, 0, 0, "D"), (0, 0, 0, "D"),
        (100, 13, 20), (7, 13, 0), (12, 6, 0),
    ]


def test_device_error_during_final_routing_backlog_does_not_publish_success_boundary(session):
    transport = session.transport

    def fail_as_output_drains(timeout=2, *, cancelled=None, progress=None):
        transport.events.put(TransportError("device removed at routing boundary"))
        transport.events.put(PlotSamples(0, (1,), 1))
        return True

    transport.wait_output = fail_as_output_drains
    session.route([(6, 13, 0)])
    wait_until(lambda: not session.connected)
    events = queued_events(session)
    assert any(isinstance(event, TransportError) for event in events)
    assert not any(isinstance(event, RoutingComplete) for event in events)
