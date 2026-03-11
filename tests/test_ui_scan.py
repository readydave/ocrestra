from __future__ import annotations

import os
import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import mock

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtGui import QCloseEvent
from PySide6.QtWidgets import QApplication

from ocr_app.models import TaskItem
from ocr_app.ui import MainWindow


class DummySettings:
    def __init__(self) -> None:
        self.values: dict[str, object] = {}

    def setValue(self, key: str, value: object) -> None:  # noqa: N802
        self.values[key] = value


class FakeCloseEvent:
    def __init__(self) -> None:
        self.ignored = False

    def ignore(self) -> None:
        self.ignored = True


class MainWindowScanTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self) -> None:
        patchers = [
            mock.patch.object(MainWindow, "_restore_queue_state_prompt", lambda self: None),
            mock.patch.object(MainWindow, "_check_runtime_dependencies", lambda self: None),
        ]
        self.addCleanup(mock.patch.stopall)
        for patcher in patchers:
            patcher.start()
        self.window = MainWindow(self.app)
        self.window.settings = DummySettings()

    def tearDown(self) -> None:
        self.window.poll_timer.stop()
        self.window.metrics_timer.stop()
        self.window.state_timer.stop()
        for task in self.window.tasks.values():
            task.status = "Canceled"
        self.window.close()

    def _symlink_or_skip(self, link_path: Path, target: Path) -> None:
        try:
            link_path.symlink_to(target)
        except OSError as exc:
            self.skipTest(f"symlink creation unavailable: {exc}")

    def _add_task_row(self, pdf_path: Path) -> TaskItem:
        self.window.add_paths([str(pdf_path)])
        task_id = next(reversed(self.window.tasks))
        return self.window.tasks[task_id]

    def test_expand_to_pdfs_skips_direct_symlink_inputs(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            pdf_path = root / "sample.pdf"
            pdf_path.write_bytes(b"%PDF-1.4\nsample\n")
            link_path = root / "linked.pdf"
            self._symlink_or_skip(link_path, pdf_path)

            discovered = self.window._expand_to_pdfs([str(link_path)])

            self.assertEqual(discovered, [])

    def test_expand_to_pdfs_dedupes_same_file_identity(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            pdf_path = root / "sample.pdf"
            pdf_path.write_bytes(b"%PDF-1.4\nsample\n")
            nested = root / "nested"
            nested.mkdir()
            hardlink_path = nested / "sample-hardlink.pdf"
            os.link(pdf_path, hardlink_path)

            discovered = self.window._expand_to_pdfs([str(pdf_path), str(root)])

            self.assertEqual(discovered, [pdf_path.absolute()])

    def test_secure_state_dir_rejects_symlink(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            target = root / "state-dir"
            target.mkdir()
            link_path = root / "state-link"
            self._symlink_or_skip(link_path, target)

            self.assertFalse(MainWindow._is_secure_state_dir(link_path))

    def test_responsive_table_widths_fit_available_space(self) -> None:
        for available in (640, 760, 980):
            widths = MainWindow._responsive_table_widths(available)
            self.assertLessEqual(sum(widths.values()), available)

    def test_auto_adjust_table_columns_enables_compact_mode_for_narrow_view(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            pdf_path = root / "sample.pdf"
            pdf_path.write_bytes(b"%PDF-1.4\nsample\n")
            task = self._add_task_row(pdf_path)
            self.window._set_log_button(task, enabled=True)

            with mock.patch.object(self.window.table.viewport(), "width", return_value=680):
                self.window._auto_adjust_table_columns()

            log_button = self.window.table.cellWidget(task.row, 4)
            action_button = self.window.table.cellWidget(task.row, 5)
            self.assertTrue(self.window._table_compact_mode)
            self.assertEqual(log_button.text(), "Log")
            self.assertEqual(action_button.text(), "Cancel")

    def test_close_event_preserves_unfinished_queue_when_requested(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            state_file = root / "queue_state.json"
            pdf_a = root / "a.pdf"
            pdf_b = root / "b.pdf"
            pdf_a.write_bytes(b"%PDF-1.4\na\n")
            pdf_b.write_bytes(b"%PDF-1.4\nb\n")

            with mock.patch.object(MainWindow, "_state_file_path", lambda _self: state_file):
                task_a = self._add_task_row(pdf_a)
                task_b = self._add_task_row(pdf_b)
                task_a.status = "Running"
                task_b.status = "Queued"

                with mock.patch.object(self.window, "_prompt_exit_queue_action", return_value="preserve"):
                    self.window.closeEvent(QCloseEvent())

            payload = json.loads(state_file.read_text(encoding="utf-8"))
            self.assertEqual(payload["queued_paths"], [str(pdf_a.absolute()), str(pdf_b.absolute())])
            self.assertEqual(task_a.status, "Canceled")
            self.assertEqual(task_b.status, "Canceled")

    def test_close_event_discards_unfinished_queue_when_requested(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            state_file = root / "queue_state.json"
            pdf_path = root / "running.pdf"
            pdf_path.write_bytes(b"%PDF-1.4\nrunning\n")

            with mock.patch.object(MainWindow, "_state_file_path", lambda _self: state_file):
                task = self._add_task_row(pdf_path)
                task.status = "Running"

                with mock.patch.object(self.window, "_prompt_exit_queue_action", return_value="discard"):
                    self.window.closeEvent(QCloseEvent())

            self.assertFalse(state_file.exists())
            self.assertEqual(task.status, "Canceled")

    def test_close_event_cancel_keeps_window_open_and_queue_unchanged(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            pdf_path = root / "running.pdf"
            pdf_path.write_bytes(b"%PDF-1.4\nrunning\n")

            task = self._add_task_row(pdf_path)
            task.status = "Running"
            event = FakeCloseEvent()

            with mock.patch.object(self.window, "_prompt_exit_queue_action", return_value="cancel"):
                self.window.closeEvent(event)

            self.assertTrue(event.ignored)
            self.assertEqual(task.status, "Running")


if __name__ == "__main__":
    unittest.main()
