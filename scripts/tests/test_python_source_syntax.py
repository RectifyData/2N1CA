#!/usr/bin/env python3
"""Parse all first-party Python source before publishing an S10 prerelease."""
import ast
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PYTHON_FILES = sorted({
    *ROOT.glob("scripts/**/*.py"),
    *ROOT.glob("*.py"),
    *ROOT.glob("unica/**/*.py"),
    *ROOT.glob("platform/exynos9820/**/*.py"),
})


class PythonSyntaxAudit(unittest.TestCase):
    def test_all_first_party_python_parses(self):
        files = [p for p in PYTHON_FILES if p.is_file() and not p.is_symlink()]
        self.assertGreater(len(files), 15, "Missing Python source from repository scan")
        errors = []
        for path in files:
            try:
                ast.parse(path.read_bytes(), filename=str(path))
            except (SyntaxError, UnicodeError) as exc:
                errors.append(f"{path.relative_to(ROOT)}: {exc}")
        self.assertEqual(errors, [], "Invalid Python source; prerelease must fail")


if __name__ == "__main__":
    unittest.main()
