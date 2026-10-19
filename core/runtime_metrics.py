"""Bounded timing samples for real sessions; no synthetic performance claims."""

import collections
import contextlib
import threading
import time


class RuntimeMetrics:
    def __init__(self):
        self._samples = collections.defaultdict(lambda: collections.deque(maxlen=512))
        self._counts = collections.Counter()
        self._lock = threading.Lock()

    @contextlib.contextmanager
    def measure(self, name):
        started = time.monotonic()
        try:
            yield
        finally:
            self.record(name, time.monotonic()-started)

    def record(self, name, seconds):
        with self._lock:
            self._samples[name].append(seconds)
            self._counts[name] += 1

    def snapshot(self):
        with self._lock:
            result = {}
            for name, values in self._samples.items():
                ordered = sorted(values)
                result[name] = {"count": self._counts[name], "window": len(ordered),
                                "p50_ms": round(ordered[int((len(ordered)-1)*0.5)]*1000, 2),
                                "p95_ms": round(ordered[int((len(ordered)-1)*0.95)]*1000, 2)}
            return result
