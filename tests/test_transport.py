import os
from queue import Empty
import select
import struct
import threading
import time

import pytest

from uart_gui.protocol import Description, PlotSamples, Values, encode_command
from uart_gui.transport import DemoTransport, SerialTransport, TransportError


def take_until(transport, event_type, timeout=2):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            event = transport.events.get(timeout=max(0.01, deadline - time.monotonic()))
        except Empty:
            break
        if isinstance(event, event_type):
            return event
    raise AssertionError(f"did not receive {event_type.__name__}")


def test_disconnected_transport_rejects_writes_and_disconnect_is_idempotent():
    transport = SerialTransport()
    with pytest.raises(ConnectionError):
        transport.send(1, 2, 0)
    transport.disconnect()
    transport.disconnect()
    assert not transport.connected


@pytest.mark.skipif(not hasattr(os, "openpty"), reason="POSIX pseudoterminal integration test")
def test_real_pyserial_pseudoterminal_send_receive_and_disconnect():
    master, slave = os.openpty()
    transport = SerialTransport()
    try:
        transport.connect(os.ttyname(slave))
        assert transport.connected
        transport.send(3.25, 6, 7)
        assert select.select([master], [], [], 1)[0]
        assert os.read(master, 100) == encode_command(3.25, 6, 7)
        # Deliberately fragment an incoming device packet across reads.
        packet = b"stx\x00\x07\x02\x01\x00\x00\x00" + struct.pack("<2f", 2.5, -3)
        os.write(master, packet[:5])
        os.write(master, packet[5:])
        assert take_until(transport, Values) == Values(7, (2.5, -3.0))
        assert transport.bytes_sent == 11
        assert transport.bytes_received == len(packet)
        transport.disconnect()
        assert not transport.connected
    finally:
        transport.disconnect()
        os.close(master)
        os.close(slave)


@pytest.mark.skipif(not hasattr(os, "openpty"), reason="POSIX pseudoterminal integration test")
def test_device_removal_reports_error_and_can_reconnect():
    master, slave = os.openpty()
    transport = SerialTransport()
    try:
        transport.connect(os.ttyname(slave))
        os.close(master)
        master = None
        error = take_until(transport, TransportError)
        assert error.fatal and "Serial receive failed" in error.message
        assert not transport.connected
        transport.connect("loop://")
        assert transport.connected
    finally:
        transport.disconnect()
        if master is not None:
            os.close(master)
        os.close(slave)


def test_demo_echoes_edits_descriptions_and_only_subscribed_plot_channels():
    demo = DemoTransport()
    try:
        demo.connect()
        demo._clear_events()
        demo.send(12.5, 6, 2)
        assert take_until(demo, Values).values[2] == 12.5
        demo.send(0, 0, 0, "D")
        description = take_until(demo, Description)
        assert description.text.startswith("Simulated ")
        demo.send(6, 13, 0)
        demo.send(2, 13, 1)
        plot = take_until(demo, PlotSamples)
        assert plot.channel == 0 and len(plot.values) == 5
        assert min(plot.values) > 10
        demo.send(255, 13, 0)
        demo.send(255, 13, 1)
        demo.disconnect()
        assert not demo.connected
    finally:
        demo.disconnect()


def test_queue_overflow_is_counted_and_error_remains_visible():
    transport = SerialTransport(queue_size=1)
    transport._publish(Values(0, (1,)))
    transport._publish(Values(0, (2,)))
    transport._publish(TransportError("removed"))
    assert transport.dropped_events == 2
    assert transport.events.get_nowait() == TransportError("removed")


class ControlledSerialOutput:
    """Model an OS output queue whose drain can stall independently of writes."""
    def __init__(self):
        self.is_open = True
        self.entered_flush = threading.Event()
        self.release_flush = threading.Event()
        self.writes = []
        self.failure = None
        self.flush_calls = 0

    def flush(self):
        self.flush_calls += 1
        self.entered_flush.set()
        self.release_flush.wait()
        if self.failure is not None:
            raise self.failure

    def write(self, packet):
        self.writes.append(packet)
        return len(packet)

    def close(self):
        self.is_open = False
        self.release_flush.set()


def test_output_drain_waits_for_driver_and_leaves_writes_and_progress_unblocked():
    transport = SerialTransport()
    connection = ControlledSerialOutput()
    transport._serial = connection
    result = []
    progress = []
    worker = threading.Thread(target=lambda: result.append(transport.wait_output(progress=lambda: progress.append(True))))
    try:
        worker.start()
        assert connection.entered_flush.wait(1)
        assert worker.is_alive() and not result
        transport.send(1, 2, 0)
        assert connection.writes == [encode_command(1, 2, 0)]
        connection.release_flush.set()
        worker.join(1)
        assert result == [True] and progress
    finally:
        transport.disconnect()
        worker.join(1)


def test_stalled_output_drain_is_cancellable_without_closing_port_needed_for_stop():
    transport = SerialTransport()
    connection = ControlledSerialOutput()
    transport._serial = connection
    cancelled = threading.Event()
    result = []
    worker = threading.Thread(target=lambda: result.append(transport.wait_output(cancelled=cancelled.is_set)))
    try:
        worker.start()
        assert connection.entered_flush.wait(1)
        cancelled.set()
        worker.join(.5)
        assert result == [False]
        assert transport.connected
        transport.send(0, 2, 0)
        assert connection.writes == [encode_command(0, 2, 0)]
    finally:
        transport.disconnect()
        worker.join(1)


def test_stalled_output_drain_has_bounded_timeout_and_driver_errors_propagate():
    transport = SerialTransport()
    connection = ControlledSerialOutput()
    transport._serial = connection
    try:
        started = time.monotonic()
        with pytest.raises(TimeoutError, match="did not drain"):
            transport.wait_output(timeout=.05)
        assert time.monotonic() - started < .5
        connection.failure = OSError("driver removed")
        connection.release_flush.set()
        with pytest.raises(ConnectionError, match="driver removed"):
            transport.wait_output()
    finally:
        transport.disconnect()


def test_replacing_cancelled_route_does_not_accumulate_stalled_flush_helpers():
    transport = SerialTransport()
    connection = ControlledSerialOutput()
    transport._serial = connection
    cancel_first = threading.Event()
    results = []
    first = threading.Thread(target=lambda: results.append(transport.wait_output(cancelled=cancel_first.is_set)))
    progressed = threading.Event()
    second = threading.Thread(target=lambda: results.append(transport.wait_output(progress=progressed.set)))
    try:
        first.start()
        assert connection.entered_flush.wait(1)
        cancel_first.set()
        first.join(.5)
        assert results == [False]
        transport.send(4, 13, 0)  # New transaction queued after the first drain.
        second.start()
        assert progressed.wait(1)
        assert connection.flush_calls == 1  # Wait for existing OS call first.
        connection.release_flush.set()
        second.join(1)
        assert results == [False, True]
        assert connection.flush_calls == 2  # Fresh drain covers the new bytes.
    finally:
        transport.disconnect()
        first.join(1)
        if second.ident is not None:
            second.join(1)
