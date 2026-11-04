import os
from queue import Empty
import select
import struct
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
