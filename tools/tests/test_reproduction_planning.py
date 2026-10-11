"""Structural tests only: no scientific jobs, imports of torch, or installations."""
import contextlib
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import reproduce
import reproduce_tables


class ReproductionPlanningTests(unittest.TestCase):
    def test_default_plan_cannot_launch_process_or_create_work(self):
        with tempfile.TemporaryDirectory() as temporary:
            work = Path(temporary) / "new-campaign"
            with patch.object(sys, "argv", ["reproduce.py", "--work-root", str(work)]), \
                    patch.object(reproduce.subprocess, "run", side_effect=AssertionError("Process launched")), \
                    contextlib.redirect_stdout(io.StringIO()) as output:
                reproduce.main()
            plan = json.loads(output.getvalue())
            self.assertEqual(plan["status"], "PLAN_ONLY")
            self.assertFalse(work.exists())
            self.assertEqual(len(plan["commands"]["train"]), 30)
            self.assertEqual(len(plan["commands"]["evaluate"]), 50)

    def test_preparation_preserves_all_scientific_config_fields(self):
        with tempfile.TemporaryDirectory() as temporary:
            work = Path(temporary) / "campaign"
            reproduce.prepare(work)
            for rep, seed, original in reproduce.records():
                path = reproduce.config_path(work, rep, seed)
                adapted = json.loads(path.read_text())
                for key in original.keys() - {"index_path", "output_root"}:
                    self.assertEqual(original[key], adapted[key])
                self.assertTrue(Path(adapted["output_root"]).is_relative_to(work))
            reproduce.prepare(work)  # exact-repeat is safe
            path = reproduce.config_path(work, "shape_cwt", 1729)
            config = json.loads(path.read_text())
            config["seed"] = 123
            path.write_text(json.dumps(config))
            with self.assertRaises(ValueError):
                reproduce.prepare(work)
            self.assertEqual(json.loads(path.read_text())["seed"], 123)

    def test_original_or_unowned_results_cannot_be_output_roots(self):
        for path in (reproduce.ROOT, reproduce.ROOT / "local", reproduce.ROOT.parent, Path(reproduce.ROOT.anchor)):
            with self.assertRaises(ValueError):
                reproduce.validate_work(path)
        with tempfile.TemporaryDirectory() as temporary:
            work = Path(temporary)
            preserved = work / "existing-result.txt"
            preserved.write_text("preserve")
            with self.assertRaises(ValueError):
                reproduce.prepare(work)
            self.assertEqual(preserved.read_text(), "preserve")

    def test_analysis_adaptation_changes_only_the_destination_assignment(self):
        for name in reproduce_tables.ANALYSIS_SCRIPTS:
            original = (reproduce.ROOT / "analysis/final/scripts" / name).read_text(encoding="utf-8")
            adapted = reproduce_tables.adapted_source(name)
            restored = adapted.replace("ROOT = Path(__file__).resolve().parents[1]", reproduce_tables.HISTORICAL_ROOT)
            self.assertEqual(original, restored)

    def test_matlab_argument_quoting_and_new_calibration_paths(self):
        self.assertEqual(reproduce.matlab_text("D:/O'Brien/work"), "'D:/O''Brien/work'")
        work = Path("D:/reproduction")
        command = reproduce.commands("calibrate", work, "python", "matlab")[0]
        self.assertIn("calibrate", command)
        self.assertIn(str(work / "AI/e4/calibration.json"), command)
        self.assertNotIn("metadata/AI/e4/production_e4_calibration.json", " ".join(command))


if __name__ == "__main__":
    unittest.main()
