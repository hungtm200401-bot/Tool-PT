import os
import tempfile
import unittest

from core.html_reporter import HTMLReporter
from core.runtime_metrics import RuntimeMetrics
from core.runtime_store import RuntimeStore
from core.single_instance import SingleInstanceLock


class RuntimeMetricsTests(unittest.TestCase):
    def test_snapshot_reports_bounded_samples_and_percentiles(self):
        metrics = RuntimeMetrics()
        for value in range(1, 21):
            metrics.record("telemetry", value / 1000)

        summary = metrics.snapshot()["telemetry"]

        self.assertEqual(summary["count"], 20)
        self.assertEqual(summary["window"], 20)
        self.assertGreater(summary["p95_ms"], summary["p50_ms"])

    def test_html_report_includes_runtime_performance(self):
        with tempfile.TemporaryDirectory(prefix="runtime_report_") as directory:
            store = RuntimeStore(os.path.join(directory, "runtime.sqlite3"))
            store.checkpoint("metrics:session-1", {
                "telemetry": {"count": 50, "window": 50, "p50_ms": 45.0, "p95_ms": 92.0}
            })
            output = os.path.join(directory, "dashboard.html")

            HTMLReporter(output_html=output, store=store).generate()

            with open(output, encoding="utf-8") as stream:
                report = stream.read()
            self.assertIn("Hiệu năng vận hành", report)
            self.assertIn("telemetry", report)
            self.assertIn("92.00 ms", report)


class SingleInstanceLockTests(unittest.TestCase):
    def test_lock_can_be_acquired_released_and_reacquired(self):
        with tempfile.TemporaryDirectory(prefix="tool_lock_") as directory:
            path = os.path.join(directory, "tool.lock")
            first = SingleInstanceLock(path)
            second = SingleInstanceLock(path)

            self.assertTrue(first.acquire())
            self.assertTrue(first.acquire())
            first.release()
            self.assertTrue(second.acquire())
            second.release()


if __name__ == "__main__":
    unittest.main()
