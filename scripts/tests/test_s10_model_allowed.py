#!/usr/bin/env python3
"""Exercise actual S10 model allowlist with generated strings and raw arrays."""
import subprocess
import unittest
from pathlib import Path
SCRIPT = Path(__file__).resolve().parents[1] / "lib/s10_model_allowed.sh"

class ModelAllowedTests(unittest.TestCase):
    def allowed(self, assignment, model):
        code = 'source "$1"; ' + assignment + '; S10_MODEL_ALLOWED "$2"'
        result = subprocess.run(["bash", "-c", code, "--", str(SCRIPT), model],
                                capture_output=True, text=True, check=False)
        return result.returncode == 0

    def test_generated_list_accepts_all_configured_regions(self):
        setting = 'TARGET_ASSERT_MODEL="SM-G975F:SM-G975N"'
        self.assertTrue(self.allowed(setting, "SM-G975F"))
        self.assertTrue(self.allowed(setting, "SM-G975N"))
        self.assertFalse(self.allowed(setting, "SM-G973F"))

    def test_raw_array_accepts_second_entry(self):
        setting = 'TARGET_ASSERT_MODEL=("SM-G975F" "SM-G975N")'
        self.assertTrue(self.allowed(setting, "SM-G975N"))
        self.assertFalse(self.allowed(setting, "SM-G970F"))

    def test_invalid_models_rejected(self):
        self.assertFalse(self.allowed('TARGET_ASSERT_MODEL=""', "SM-G975N"))
        self.assertFalse(self.allowed('TARGET_ASSERT_MODEL="SM-G975F"', "SM-G975F;reboot"))

if __name__ == "__main__":
    unittest.main()
