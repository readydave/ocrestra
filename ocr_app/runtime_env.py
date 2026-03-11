from __future__ import annotations

import os
import ssl
from pathlib import Path


def _default_ca_bundle_available() -> bool:
    verify_paths = ssl.get_default_verify_paths()
    cafile = verify_paths.cafile
    capath = verify_paths.capath
    if cafile and Path(cafile).is_file():
        return True
    if capath and Path(capath).is_dir():
        return True
    return False


def repair_ssl_cert_env() -> str | None:
    # Respect explicit user or system overrides.
    if os.environ.get("SSL_CERT_FILE") or os.environ.get("SSL_CERT_DIR") or os.environ.get("REQUESTS_CA_BUNDLE"):
        return None
    if _default_ca_bundle_available():
        return None
    try:
        import certifi
    except Exception:
        return None
    bundle_path = Path(certifi.where())
    if not bundle_path.is_file():
        return None
    bundle_text = str(bundle_path)
    os.environ["SSL_CERT_FILE"] = bundle_text
    os.environ.setdefault("REQUESTS_CA_BUNDLE", bundle_text)
    return bundle_text
