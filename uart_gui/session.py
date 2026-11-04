"""Keep connection and paced command writes off the GUI thread."""
from __future__ import annotations

import itertools
from queue import Empty, PriorityQueue, Queue
import threading
import time

from PySide6.QtCore import QObject, Signal

from .protocol import encode_command
from .transport import DemoTransport, SerialTransport, TransportError


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

    def send_many(self, commands, *, urgent=False, label=""):
        # Validate every edit before queueing any writes.
        commands = tuple(tuple(command) for command in commands)
        for command in commands:
            encode_command(*command)
        if not self.connected:
            raise ConnectionError("Connect a device or start demo mode first.")
        if urgent:
            self._generation += 1  # cancel pending batch/routing commands
        self._enqueue("send", (commands, label), 0 if urgent else 5)

    def route(self, commands):
        commands = tuple(tuple(command) for command in commands)
        for command in commands:
            encode_command(*command)
        if not self.connected:
            raise ConnectionError("Connect a device before routing signals.")
        self._routing_revision += 1
        self._enqueue("route", (commands, self._routing_revision), priority=3)
        return self._routing_revision

    def _drain(self):
        if self.transport is None:
            return
        for _ in range(2000):
            try:
                event = self.transport.events.get_nowait()
            except Empty:
                break
            if not self.events.full():
                self.events.put_nowait(event)
            else:
                self.dropped_events += 1
                if isinstance(event, TransportError):
                    try:
                        self.events.get_nowait()
                    except Empty:
                        pass
                    self.events.put_nowait(event)
            if isinstance(event, TransportError) and event.fatal:
                self.connected = False
                self.state_changed.emit(False, "Disconnected")

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
                    _, _, generation, operation, args = self._jobs.get(timeout=.03)
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
                    elif operation in ("send", "route"):
                        commands, detail = args
                        if operation == "route" and detail != self._routing_revision:
                            continue
                        for index, command in enumerate(commands):
                            if generation != self._generation or self._closed.is_set():
                                break
                            if operation == "route" and detail != self._routing_revision:
                                break
                            self.transport.send(*command)
                            self._drain()
                            # Preserve the firmware pacing in MATLAB's ENTER ALL.
                            time.sleep(.3 if (index + 1) % 10 == 0 else .01)
                        else:
                            self._drain()
                            if operation == "route":
                                self.routing_finished.emit(detail)
                            elif detail:
                                self.message.emit(detail + " sent (device acknowledgement not available)")
                except Exception as exc:
                    self.message.emit(str(exc))
                    if not self.events.full():
                        self.events.put_nowait(TransportError(str(exc)))
                    self._disconnect()
        finally:
            self._disconnect()

    def close(self):
        self._generation += 1
        self._closed.set()
        self._thread.join(timeout=2.5)
