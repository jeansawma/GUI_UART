"""Threaded serial I/O and a clearly separate, hardware-free simulator."""

from __future__ import annotations

from dataclasses import dataclass
import math
from queue import Empty, Full, Queue
import threading
import time
from typing import Callable

from .protocol import Description, Event, PlotSamples, ScopeSamples, StreamDecoder, Values, encode_command


@dataclass(frozen=True)
class TransportError:
    message: str
    fatal: bool = True


def available_ports() -> list[tuple[str, str]]:
    """Return device names and readable descriptions without opening devices."""
    from serial.tools import list_ports

    return [(port.device, port.description) for port in list_ports.comports()]


class SerialTransport:
    """A worker reads bytes; consumers drain ``events`` on their GUI thread.

    Queue limits prevent an unattended GUI from consuming unlimited memory.
    ``dropped_events`` reports saturation rather than pretending all data was
    retained. Reconnection starts a new decoder and clears stale queued data.
    """

    def __init__(self, serial_factory: Callable | None = None, queue_size: int = 20_000) -> None:
        self.events: Queue[Event | TransportError] = Queue(maxsize=queue_size)
        self.dropped_events = 0
        self.bytes_received = 0
        self.bytes_sent = 0
        self.decoder = StreamDecoder()
        self._factory = serial_factory
        self._serial = None
        self._thread: threading.Thread | None = None
        self._stop = threading.Event()
        self._write_lock = threading.Lock()
        self._output_drain = None

    @property
    def connected(self) -> bool:
        return self._serial is not None and self._serial.is_open and not self._stop.is_set()

    def _publish(self, event: Event | TransportError) -> None:
        try:
            self.events.put_nowait(event)
        except Full:
            self.dropped_events += 1
            # Preserve fatal errors so the user can see why acquisition ended.
            if isinstance(event, TransportError):
                try:
                    self.events.get_nowait()
                except Empty:
                    pass
                try:
                    self.events.put_nowait(event)
                except Full:
                    pass

    def _clear_events(self) -> None:
        while True:
            try:
                self.events.get_nowait()
            except Empty:
                return

    def connect(self, port: str, baudrate: int = 115_200) -> None:
        if not port:
            raise ValueError("select a serial port")
        if baudrate <= 0:
            raise ValueError("baud rate must be positive")
        self.disconnect()
        self._clear_events()
        self.decoder.reset()
        self.dropped_events = self.bytes_received = self.bytes_sent = 0
        if self._factory is None:
            import serial

            factory = serial.serial_for_url
        else:
            factory = self._factory
        connection = factory(port, baudrate=baudrate, timeout=0.1, write_timeout=1.0)
        self._serial = connection
        self._stop.clear()
        self._thread = threading.Thread(target=self._read_loop, args=(connection,), daemon=True, name="uart-reader")
        self._thread.start()

    def disconnect(self) -> None:
        self._stop.set()
        connection = self._serial
        if connection is not None:
            try:
                cancel_read = getattr(connection, "cancel_read", None)
                if cancel_read is not None:
                    cancel_read()
            except OSError:
                pass
        if self._thread is not None and self._thread is not threading.current_thread():
            self._thread.join(timeout=1.0)
        with self._write_lock:
            if connection is not None and connection.is_open:
                connection.close()
            self._serial = None
        self._thread = None

    def send(self, value: float, row: int, column: int, command: int | str = 0) -> None:
        packet = encode_command(value, row, column, command)
        with self._write_lock:
            if not self.connected:
                raise ConnectionError("serial port is not connected")
            try:
                sent = self._serial.write(packet)
                if sent != len(packet):
                    raise OSError(f"incomplete serial write ({sent}/{len(packet)} bytes)")
                self.bytes_sent += sent
            except OSError as exc:
                self._publish(TransportError(f"Serial write failed: {exc}"))
                self._stop.set()
                raise ConnectionError(f"Serial write failed: {exc}") from exc

    def wait_output(self, timeout: float = 2.0, *, cancelled=None, progress=None) -> bool:
        """Wait for driver-confirmed transmission without blocking the reader.

        ``write`` can return while bytes remain in the OS transmit queue. Use
        this boundary after a routing transaction before attributing samples
        to its new signals. It is not an acknowledgement from the firmware.

        Some drivers can block indefinitely in flush/tcdrain, so that OS call
        runs in a daemon helper. The calling command worker remains bounded
        and cancellable, and can keep forwarding received events. Cancellation
        does not retract bytes already queued: subsequent STOP commands follow
        them on the wire. A timeout must be followed by disconnecting the port.
        """
        if not math.isfinite(timeout) or timeout <= 0:
            raise ValueError("output timeout must be positive and finite")
        if cancelled is not None and cancelled():
            return False
        if not self.connected:
            raise ConnectionError("serial port is not connected")
        connection = self._serial
        deadline = time.monotonic() + timeout

        def await_drain(completed, errors):
            while True:
                if progress is not None:
                    progress()
                if cancelled is not None and cancelled():
                    return False
                if self._stop.is_set() or self._serial is not connection:
                    return False
                if completed.is_set():
                    if errors:
                        raise ConnectionError(f"Serial output drain failed: {errors[0]}") from errors[0]
                    return True
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise TimeoutError("Serial output did not drain within the timeout; disconnecting the port is required")
                completed.wait(min(.01, remaining))

        # A cancelled route may leave its OS drain in progress. Finish that
        # helper before starting the drain for this transaction, limiting the
        # device to one helper even during repeated routing changes. A fresh
        # drain is still required for bytes queued after the earlier call.
        if self._output_drain is not None:
            previous_connection, previous_completed, previous_errors = self._output_drain
            if previous_connection is connection and not previous_completed.is_set():
                if not await_drain(previous_completed, previous_errors):
                    return False

        completed = threading.Event()
        errors: list[Exception] = []

        def flush():
            try:
                connection.flush()
            except Exception as exc:
                errors.append(exc)
            finally:
                completed.set()

        self._output_drain = (connection, completed, errors)
        threading.Thread(target=flush, name="uart-output-drain", daemon=True).start()
        return await_drain(completed, errors)

    def _read_loop(self, connection) -> None:
        try:
            while not self._stop.is_set():
                data = connection.read(max(1, min(connection.in_waiting, 8192)))
                if data:
                    self.bytes_received += len(data)
                    for event in self.decoder.feed(data):
                        self._publish(event)
        except (OSError, ValueError) as exc:
            if not self._stop.is_set():
                self._stop.set()
                self._publish(TransportError(f"Serial receive failed: {exc}"))
        finally:
            if self._stop.is_set() and connection.is_open:
                connection.close()


class DemoTransport(SerialTransport):
    """Deterministic simulated telemetry; never opens or writes a serial port."""

    def __init__(self, queue_size: int = 20_000) -> None:
        super().__init__(queue_size=queue_size)
        self._demo_connected = False
        self._values: dict[int, list[float]] = {}
        self._subscriptions = [[255, 255] for _ in range(15)]
        self._demo_lock = threading.RLock()
        self._tick = 0

    @property
    def connected(self) -> bool:
        return self._demo_connected and not self._stop.is_set()

    def connect(self, port: str = "Demo", baudrate: int = 115_200) -> None:
        self.disconnect()
        self._clear_events()
        self._stop.clear()
        self._demo_connected = True
        self._values = {row: [round((row + 1) * (col + 1) / 10, 3) for col in range(25)] for row in range(15)}
        self._values[0][2] = 0.0001
        self._values[0][1] = 0.0  # INIT_Gui's ERROR status; no simulated fault
        self._subscriptions = [[255, 255] for _ in range(15)]
        self._tick = 0
        self.dropped_events = self.bytes_received = self.bytes_sent = 0
        for row, values in self._values.items():
            self._publish(Values(row, tuple(values)))
        # The supplied application receives scope blocks but contains no
        # command to request one. Synthetic blocks are supplied locally only.
        for channel in range(16):
            values = tuple(math.sin(index / 30 + channel) for index in range(500))
            self._publish(ScopeSamples(channel, values))
        self._thread = threading.Thread(target=self._demo_loop, daemon=True, name="uart-demo")
        self._thread.start()

    def disconnect(self) -> None:
        self._demo_connected = False
        super().disconnect()

    def wait_output(self, timeout: float = 2.0, *, cancelled=None, progress=None) -> bool:
        if progress is not None:
            progress()
        return self.connected and not (cancelled is not None and cancelled())

    def send(self, value: float, row: int, column: int, command: int | str = 0) -> None:
        packet = encode_command(value, row, column, command)
        if not self.connected:
            raise ConnectionError("demo is not connected")
        self.bytes_sent += len(packet)
        cmd = ord(command) if isinstance(command, str) else command
        if cmd == ord("D"):
            from .catalog import FIELD_BY_ADDRESS

            for field in FIELD_BY_ADDRESS.values():
                self._publish(Description(field.row, field.column, f"Simulated {field.label}"))
            return
        with self._demo_lock:
            if row == 13 and column < 20:
                self._subscriptions[column // 2][column % 2] = int(value)
            elif row == 14 and column < 10:
                self._subscriptions[10 + column // 2][column % 2] = int(value)
            if row in self._values and column < 25:
                self._values[row][column] = float(value)
                self._publish(Values(row, tuple(self._values[row])))

    def _demo_loop(self) -> None:
        while not self._stop.wait(0.05):
            phase = self._tick * 0.0001
            with self._demo_lock:
                for column in range(24):
                    if column != 2:
                        self._values[0][column] = math.sin(phase * 2 + column * 0.4) * (column + 1)
                self._values[0][1] = 0.0
                self._publish(Values(0, tuple(self._values[0])))
                subscriptions = [tuple(pair) for pair in self._subscriptions]
                snapshot = {row: tuple(values) for row, values in self._values.items()}
            for channel, (row, column) in enumerate(subscriptions):
                if row not in snapshot or not 0 <= column < len(snapshot[row]):
                    continue
                baseline = snapshot[row][column]
                values = tuple(baseline + (1 + channel * 0.15) * math.sin(2 * math.pi * (phase + index * 0.01) + channel * 0.6)
                               + 0.07 * math.sin(phase * 29 + index) for index in range(5))
                self._publish(PlotSamples(channel, values, self._tick))
                self.bytes_received += 34
            self._tick += 500
