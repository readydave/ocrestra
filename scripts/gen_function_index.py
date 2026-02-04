#!/usr/bin/env python3
from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DOC_PATH = ROOT / "docs" / "FUNCTION_INDEX.md"

MODULES = [
    Path("ocr_gui.py"),
    Path("ocr_app/__main__.py"),
    Path("ocr_app/config.py"),
    Path("ocr_app/models.py"),
    Path("ocr_app/job_runner.py"),
    Path("ocr_app/themes.py"),
    Path("ocr_app/ui.py"),
]


def parse_module(rel_path: Path) -> tuple[list[str], dict[str, list[str]]]:
    src_path = ROOT / rel_path
    tree = ast.parse(src_path.read_text(encoding="utf-8"))
    functions: list[str] = []
    methods: dict[str, list[str]] = {}

    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            functions.append(node.name)
        elif isinstance(node, ast.ClassDef):
            class_methods: list[str] = []
            for child in node.body:
                if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    class_methods.append(child.name)
            methods[node.name] = class_methods
    return functions, methods


def main() -> int:
    lines: list[str] = []
    lines.append("# Function Index")
    lines.append("")
    lines.append("Auto-generated index of modules, functions, and class methods.")
    lines.append("")
    lines.append("Regenerate with:")
    lines.append("")
    lines.append("```bash")
    lines.append("python scripts/gen_function_index.py")
    lines.append("```")
    lines.append("")

    for module in MODULES:
        functions, methods = parse_module(module)
        lines.append(f"## `{module.as_posix()}`")
        lines.append("")

        if functions:
            lines.append("### Module functions")
            lines.append("")
            for name in functions:
                lines.append(f"- `{name}`")
            lines.append("")

        if methods:
            lines.append("### Classes")
            lines.append("")
            for class_name, class_methods in methods.items():
                lines.append(f"- `{class_name}`")
                if class_methods:
                    for method in class_methods:
                        lines.append(f"  - `{method}`")
                else:
                    lines.append("  - *(no methods)*")
            lines.append("")

    DOC_PATH.parent.mkdir(parents=True, exist_ok=True)
    DOC_PATH.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")
    print(f"Wrote {DOC_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
