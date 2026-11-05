#!/usr/bin/env python3
"""Parse every S10-relevant shell script before GitHub publishes source.

This uses Bash's real parser, not grep heuristics. Submodule symlinks are
checked by the actual host-tool build, not treated as in-tree sources.
"""
from __future__ import annotations
import shutil
import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PATHS = [
    *ROOT.glob("*.sh"),
    *ROOT.glob("scripts/**/*.sh"),
    *ROOT.glob("target/beyond*/*.sh"),
    *ROOT.glob("target/beyond*/**/*.sh"),
    *ROOT.glob("platform/exynos9820/**/*.sh"),
    *ROOT.glob("unica/configs/*.sh"),
    *ROOT.glob("unica/patches/**/*.sh"),
]
CANDIDATES = sorted({p for p in PATHS if p.is_file() and not p.is_symlink()})


class ShellSyntaxTests(unittest.TestCase):
    def test_bash_available(self):
        self.assertIsNotNone(shutil.which("bash"), "CI requires a real Bash parser")

    def test_every_in_tree_s10_shell_script_parses(self):
        self.assertGreater(len(CANDIDATES), 30, "S10 Bash syntax scan found too few scripts")
        bad = []
        for path in CANDIDATES:
            process = subprocess.run(["bash", "-n", str(path)], capture_output=True, text=True)
            if process.returncode != 0:
                bad.append(f"{path.relative_to(ROOT)}: {process.stderr.strip()}")
        self.assertEqual(bad, [], "Invalid S10 source shell syntax; no release allowed")


if __name__ == "__main__":
    unittest.main()
