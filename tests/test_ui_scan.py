from __future__ import annotations

import os
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import mock

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

from ocr_app.ui import MainWindow


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

    def tearDown(self) -> None:
        self.window.poll_timer.stop()
        self.window.metrics_timer.stop()
        self.window.state_timer.stop()
        self.window.close()

    def _symlink_or_skip(self, link_path: Path, target: Path) -> None:
        try:
            link_path.symlink_to(target)
        except OSError as exc:
            self.skipTest(f"symlink creation unavailable: {exc}")

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


if __name__ == "__main__":
    unittest.main()
