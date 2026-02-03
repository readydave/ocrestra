from __future__ import annotations

import multiprocessing as mp

from .ui import run_app


def main() -> int:
    try:
        mp.set_start_method("spawn")
    except RuntimeError:
        pass
    return run_app()


if __name__ == "__main__":
    raise SystemExit(main())
