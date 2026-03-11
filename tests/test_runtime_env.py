from __future__ import annotations

import os
import sys
import types
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest import mock

from ocr_app.runtime_env import repair_ssl_cert_env


class RepairSslCertEnvTests(unittest.TestCase):
    def test_repairs_env_with_certifi_when_default_paths_are_missing(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            bundle = root / "cacert.pem"
            bundle.write_text("dummy cert bundle", encoding="utf-8")
            verify_paths = SimpleNamespace(
                cafile=str(root / "missing-cert.pem"),
                capath=str(root / "missing-certs"),
            )
            fake_certifi = types.SimpleNamespace(where=lambda: str(bundle))

            with mock.patch.dict(os.environ, {}, clear=True):
                with mock.patch("ocr_app.runtime_env.ssl.get_default_verify_paths", return_value=verify_paths):
                    with mock.patch.dict(sys.modules, {"certifi": fake_certifi}):
                        repaired = repair_ssl_cert_env()
                        self.assertEqual(repaired, str(bundle))
                        self.assertEqual(os.environ["SSL_CERT_FILE"], str(bundle))
                        self.assertEqual(os.environ["REQUESTS_CA_BUNDLE"], str(bundle))

    def test_skips_repair_when_default_cafile_exists(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            cafile = root / "system-ca.pem"
            cafile.write_text("system cert bundle", encoding="utf-8")
            verify_paths = SimpleNamespace(cafile=str(cafile), capath=str(root / "missing-certs"))

            with mock.patch.dict(os.environ, {}, clear=True):
                with mock.patch("ocr_app.runtime_env.ssl.get_default_verify_paths", return_value=verify_paths):
                    repaired = repair_ssl_cert_env()

            self.assertIsNone(repaired)
            self.assertNotIn("SSL_CERT_FILE", os.environ)
            self.assertNotIn("REQUESTS_CA_BUNDLE", os.environ)

    def test_respects_existing_env_override(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            custom_bundle = root / "custom.pem"
            custom_bundle.write_text("custom cert bundle", encoding="utf-8")
            verify_paths = SimpleNamespace(
                cafile=str(root / "missing-cert.pem"),
                capath=str(root / "missing-certs"),
            )

            with mock.patch.dict(os.environ, {"SSL_CERT_FILE": str(custom_bundle)}, clear=True):
                with mock.patch("ocr_app.runtime_env.ssl.get_default_verify_paths", return_value=verify_paths):
                    repaired = repair_ssl_cert_env()
                    self.assertIsNone(repaired)
                    self.assertEqual(os.environ["SSL_CERT_FILE"], str(custom_bundle))
                    self.assertNotIn("REQUESTS_CA_BUNDLE", os.environ)


if __name__ == "__main__":
    unittest.main()
