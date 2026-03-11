from __future__ import annotations

import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from ocr_app.job_runner import _install_output_pdf


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


if __name__ == "__main__":
    unittest.main()
