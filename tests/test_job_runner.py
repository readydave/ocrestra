from __future__ import annotations

import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import mock

from ocr_app.job_runner import OCRCommandError, _install_output_pdf, _run_ocr_command


class InstallOutputPdfTests(unittest.TestCase):
    def _symlink_or_skip(self, link_path: Path, target: Path) -> None:
        try:
            link_path.symlink_to(target)
        except OSError as exc:
            self.skipTest(f"symlink creation unavailable: {exc}")

    def test_install_output_pdf_copies_staged_contents(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            staged_output = root / "staged.pdf"
            staged_output.write_bytes(b"%PDF-1.4\nstaged\n")

            output_pdf = root / "OCR_Output" / "final.pdf"
            _install_output_pdf(staged_output, output_pdf)

            self.assertTrue(output_pdf.exists())
            self.assertEqual(output_pdf.read_bytes(), b"%PDF-1.4\nstaged\n")

    def test_install_output_pdf_rejects_symlink_destination(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            staged_output = root / "staged.pdf"
            staged_output.write_bytes(b"%PDF-1.4\nstaged\n")

            target = root / "existing.pdf"
            target.write_bytes(b"existing\n")
            output_dir = root / "OCR_Output"
            output_dir.mkdir()
            output_pdf = output_dir / "final.pdf"
            self._symlink_or_skip(output_pdf, target)

            with self.assertRaises(PermissionError):
                _install_output_pdf(staged_output, output_pdf)

    def test_install_output_pdf_rejects_symlink_parent_directory(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            staged_output = root / "staged.pdf"
            staged_output.write_bytes(b"%PDF-1.4\nstaged\n")

            real_dir = root / "real-output"
            real_dir.mkdir()
            linked_dir = root / "OCR_Output"
            self._symlink_or_skip(linked_dir, real_dir)
            output_pdf = linked_dir / "final.pdf"

            with self.assertRaises(PermissionError):
                _install_output_pdf(staged_output, output_pdf)


class OCRCommandTests(unittest.TestCase):
    def test_run_ocr_command_raises_for_silent_easyocr_cert_failure(self) -> None:
        class FakeProc:
            def __init__(self, lines: list[str]) -> None:
                self.stdout = iter(lines)

            def wait(self) -> int:
                return 0

        lines = [
            "Downloading detection model, please wait.\n",
            "Traceback (most recent call last):\n",
            "  File \"/tmp/easyocr.py\", line 1, in <module>\n",
            "urllib.error.URLError: <urlopen error [SSL: CERTIFICATE_VERIFY_FAILED] certificate verify failed>\n",
            "  File \"/tmp/plugin.py\", line 1, in <module>\n",
            "ocrmypdf_easyocr\n",
        ]
        with mock.patch("ocr_app.job_runner.subprocess.Popen", return_value=FakeProc(lines)):
            with self.assertRaises(OCRCommandError) as ctx:
                _run_ocr_command(["ocrmypdf"])

        self.assertIn("EasyOCR GPU backend could not download its model files", str(ctx.exception))

    def test_run_ocr_command_accepts_clean_success_output(self) -> None:
        class FakeProc:
            def __init__(self, lines: list[str]) -> None:
                self.stdout = iter(lines)

            def wait(self) -> int:
                return 0

        lines = [
            "Start processing\n",
            "Postprocessing...\n",
            "Output file is a PDF\n",
        ]
        with mock.patch("ocr_app.job_runner.subprocess.Popen", return_value=FakeProc(lines)):
            _run_ocr_command(["ocrmypdf"])

    def test_run_ocr_command_throttles_progress_lines_by_percent_bucket(self) -> None:
        class FakeProc:
            def __init__(self, lines: list[str]) -> None:
                self.stdout = iter(lines)

            def wait(self) -> int:
                return 0

        lines = [
            "Progress: [97-a] 97.0% Complete\n",
            "Progress: [97-b] 97.4% Complete\n",
            "Progress: [98-a] 98.0% Complete\n",
            "Progress: [98-b] 98.8% Complete\n",
            "Progress: [99-a] 99.0% Complete\n",
            "Progress: [100] 100.0% Complete\n",
        ]
        fake_logger = mock.Mock()
        with mock.patch("ocr_app.job_runner.subprocess.Popen", return_value=FakeProc(lines)):
            with mock.patch("ocr_app.job_runner.logging.getLogger", return_value=fake_logger):
                _run_ocr_command(["ocrmypdf"])

        logged_messages = [call.args[1] for call in fake_logger.info.call_args_list]
        self.assertEqual(
            logged_messages,
            [
                "Progress: [97-a] 97.0% Complete",
                "Progress: [98-a] 98.0% Complete",
                "Progress: [99-a] 99.0% Complete",
                "Progress: [100] 100.0% Complete",
            ],
        )


if __name__ == "__main__":
    unittest.main()
