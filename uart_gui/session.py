"""Keep connection and paced command writes off the GUI thread."""
from __future__ import annotations

import itertools
from dataclasses import dataclass
from queue import Empty, Full, PriorityQueue, Queue
import threading
import time

from PySide6.QtCore import QObject, Signal

from .protocol import encode_command
from .transport import DemoTransport, SerialTransport, TransportError


@dataclass(frozen=True)
class RoutingComplete:
    """FIFO boundary: preceding samples belong to the previous routing."""

    revision: int


class Session(QObject):
    state_changed = Signal(bool, str)
    message = Signal(str)
    routing_finished = Signal(int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.events = Queue(maxsize=20000)
        self.transport = None
        self.connected = False
        self.demo = False
        self.dropped_events = 0
        self._generation = 0
        self._routing_revision = 0
        self._counter = itertools.count()
        self._jobs = PriorityQueue()
        self._closed = threading.Event()
        self._thread = threading.Thread(target=self._run, name="uart-commands", daemon=True)
        self._thread.start()

    def _enqueue(self, operation, args=(), priority=5):
        self._jobs.put((priority, next(self._counter), self._generation, operation, args))

    def connect_device(self, port, baudrate, demo=False):
        self._generation += 1
        self._enqueue("connect", (port, baudrate, demo), 0)

    def disconnect_device(self):
        self._generation += 1
        self._enqueue("disconnect", priority=0)

    def send_many(self, commands, *, urgent=False, label="", priority=5):
        # Validate every edit before queueing any writes.
        commands = tuple(tuple(command) for command in commands)
        for command in commands:
            encode_command(*command)
        if not self.connected:
            raise ConnectionError("Connect a device or start demo mode first.")
        if urgent:
            self._generation += 1  # cancel pending batch/routing commands
        self._enqueue("send", (commands, label), 0 if urgent else priority)

    def route(self, commands):
        commands = tuple(tuple(command) for command in commands)
        for command in commands:
            encode_command(*command)
        if not self.connected:
            raise ConnectionError("Connect a device before routing signals.")
        self._routing_revision += 1
        self._enqueue("route", (commands, self._routing_revision), priority=3)
        return self._routing_revision

    def request_descriptions(self):
        """Queue MATLAB's D / 500 ms / D handshake ahead of plot routing."""
        if not self.connected:
            raise ConnectionError("Connect a device before requesting descriptions.")
        self._enqueue("descriptions", priority=1)

    def _active(self, generation, routing_revision=None):
        return (generation == self._generation and not self._closed.is_set()
                and self.connected
                and (routing_revision is None or routing_revision == self._routing_revision))

    def _wait(self, duration, generation):
        """Pace only the operations that need it, while forwarding telemetry."""
        deadline = time.monotonic() + duration
        while self._active(generation):
            self._drain()
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                return self._active(generation)
            self._closed.wait(min(.01, remaining))
        return False

    def _wait_output(self, generation, routing_revision=None):
        return self.transport.wait_output(
            timeout=2.0,
            cancelled=lambda: not self._active(generation, routing_revision),
            progress=self._drain,
        )

    def _drain(self, limit=2000, *, cancelled=None):
        if self.transport is None:
            return
        for _ in range(limit):
            if cancelled is not None and cancelled():
                break
            try:
                event = self.transport.events.get_nowait()
            except Empty:
                break
            self._publish(event, required=isinstance(event, TransportError))
            if isinstance(event, TransportError) and event.fatal:
                self.connected = False
                self.state_changed.emit(False, "Disconnected")

    def _publish(self, event, *, required=False):
        try:
            self.events.put_nowait(event)
        except Full:
            if not required:
                self.dropped_events += 1
                return
            # Preserve ordered routing boundaries and errors. Replacing the
            # oldest event preserves FIFO ordering among all retained events,
            # counts that loss, and never blocks shutdown on a full GUI queue.
            while True:
                try:
                    self.events.get_nowait()
                    self.dropped_events += 1
                except Empty:
                    pass
                try:
                    self.events.put_nowait(event)
                    return
                except Full:
                    continue

    def _disconnect(self, announce=True):
        self.connected = False
        if self.transport is not None:
            self.transport.disconnect()
        if announce:
            self.state_changed.emit(False, "Disconnected")

    def _run(self):
        try:
            while not self._closed.is_set():
                self._drain()
                try:
                    _, _, generation, operation, args = self._jobs.get(timeout=.01)
                except Empty:
                    continue
                if generation != self._generation:
                    continue
                try:
                    if operation == "connect":
                        self._disconnect(announce=False)
                        while True:
                            try:
                                self.events.get_nowait()
                            except Empty:
                                break
                        self.demo = bool(args[2])
                        self.dropped_events = 0
                        self.transport = DemoTransport() if self.demo else SerialTransport()
                        self.transport.connect(args[0], args[1])
                        if generation != self._generation:
                            self._disconnect()
                            continue
                        self.connected = True
                        self.state_changed.emit(True, "Demo · simulated device" if self.demo else args[0])
                    elif operation == "disconnect":
                        self._disconnect()
                    elif operation == "descriptions":
                        if not self._active(generation):
                            continue
                        self.transport.send(0, 0, 0, "D")
                        if not self._wait_output(generation):
                            continue
                        if not self._wait(.5, generation):
                            continue
                        self.transport.send(0, 0, 0, "D")
                        if self._wait_output(generation):
                            self.message.emit("Description requests sent (device acknowledgement not available)")
                    elif operation in ("send", "route"):
                        commands, detail = args
                        if operation == "route" and detail != self._routing_revision:
                            continue
                        for index, command in enumerate(commands):
                            if not self._active(generation):
                                break
                            if operation == "route" and detail != self._routing_revision:
                                break
                            self.transport.send(*command)
                            self._drain()
                            # Plot_Fill_UART has no pauses. Retain the existing
                            # ENTER ALL batch pacing for numeric writes only.
                            if operation == "send" and (index + 1) % 10 == 0 and index + 1 < len(commands):
                                if not self._wait(.3, generation):
                                    break
                        else:
                            self._drain()
                            if operation == "route":
                                if self._wait_output(generation, detail) and self._active(generation, detail):
                                    # Preserve the boundary even when the reader
                                    # has more than a normal turn's 2,000 events.
                                    # Snapshot the FIFO length so an ongoing
                                    # producer cannot extend this drain forever.
                                    pending = self.transport.events.qsize()
                                    self._drain(pending, cancelled=lambda: not self._active(generation, detail))
                                    if self._active(generation, detail):
                                        self._publish(RoutingComplete(detail), required=True)
                                        self.routing_finished.emit(detail)
                            elif detail:
                                self.message.emit(detail + " sent (device acknowledgement not available)")
                except Exception as exc:
                    self.message.emit(str(exc))
                    self._publish(TransportError(str(exc)), required=True)
                    self._disconnect()
        finally:
            self._disconnect()

    def close(self):
        self._generation += 1
        self._closed.set()
        self._thread.join(timeout=2.5)
