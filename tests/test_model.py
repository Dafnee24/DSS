import copy
import io
import json
import unittest
import zipfile

import numpy as np

from engine import ModelError, calculate_dm, calculate_project, rank_descending, validate_project
from workbook_io import (SOURCE, compare_cached_workbook, export_bundle, import_json,
                         import_workbook, scenario_json)


class ModelTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.project = import_workbook()
        cls.result = calculate_project(cls.project)

    def test_all_numeric_blocks_against_excel_cache(self):
        checks = compare_cached_workbook(self.project, self.result)
        self.assertEqual(len(checks), 4924)
        failures = checks[checks.Status != "Sesuai"]
        self.assertTrue(failures.empty, failures.to_string())
        self.assertLess(checks.Selisih.max(), 1e-12)

    def test_hand_computed_two_criterion_example(self):
        # Both MEREC effects are ln(1+ln2) - ln(1+ln2/2), hence equal weights.
        # S_AAI=.5, S_AI=1; MARCOS utility is 6/7 and 3/7.
        result = calculate_dm([[1, 4], [2, 2]], ["Cost", "Benefit"])
        np.testing.assert_allclose(result["weights"], [.5, .5], atol=1e-15)
        np.testing.assert_allclose(result["utility"], [6 / 7, 3 / 7], atol=1e-15)
        np.testing.assert_array_equal(result["rank"], [1, 2])

    def test_rank_ties_use_excel_competition_ranking(self):
        np.testing.assert_array_equal(rank_descending([.8, .8, .5, .7]), [1, 1, 4, 3])

    def test_changing_one_dm_does_not_change_other_dm_results(self):
        changed = copy.deepcopy(self.project)
        changed["decision_makers"][0]["ratings"][0][7] = "CL"
        result = calculate_project(changed)
        for dm in ["DM2", "DM3"]:
            np.testing.assert_array_equal(result["dms"][dm]["utility"], self.result["dms"][dm]["utility"])
        self.assertFalse(np.allclose(result["dms"]["DM1"]["weights"], self.result["dms"]["DM1"]["weights"]))
        self.assertFalse(np.allclose(result["combined"], self.result["combined"]))

    def test_lambda_only_dm1_gives_dm1_result(self):
        changed = copy.deepcopy(self.project)
        for dm, weight in zip(changed["decision_makers"], [1, 0, 0]):
            dm["weight"] = weight
        result = calculate_project(changed)
        np.testing.assert_array_equal(result["combined"], self.result["dms"]["DM1"]["utility"])
        np.testing.assert_array_equal(result["rank"], self.result["dms"]["DM1"]["rank"])
        self.assertEqual(changed["alternatives"][np.argmax(result["combined"])], "Al14")

    def test_weights_are_not_silently_normalized(self):
        changed = copy.deepcopy(self.project)
        for dm in changed["decision_makers"]:
            dm["weight"] *= 2
        result = calculate_project(changed)
        np.testing.assert_allclose(result["combined"], 2 * self.result["combined"], atol=1e-15)
        np.testing.assert_array_equal(result["rank"], self.result["rank"])

    def test_cost_benefit_direction(self):
        result = calculate_dm([[1, 4], [2, 2]], ["Benefit", "Cost"])
        np.testing.assert_array_equal(result["rank"], [2, 1])

    def test_constant_criterion_receives_zero_weight(self):
        result = calculate_dm([[1, 5], [2, 5]], ["Cost", "Benefit"])
        np.testing.assert_allclose(result["weights"], [1, 0], atol=1e-15)

    def test_identical_alternatives_fail_without_fabricated_weights(self):
        with self.assertRaisesRegex(ModelError, "ΣE = 0"):
            calculate_dm([[5, 6], [5, 6]], ["Cost", "Benefit"])

    def test_invalid_values_are_rejected(self):
        for value in [0, -1, float("nan"), float("inf")]:
            changed = copy.deepcopy(self.project)
            changed["scale"][0]["value"] = value
            with self.subTest(value=value), self.assertRaises(ModelError):
                validate_project(changed)
        for code in ["???", None, ""]:
            changed = copy.deepcopy(self.project)
            changed["decision_makers"][0]["ratings"][0][0] = code
            with self.subTest(code=code), self.assertRaises(ModelError):
                validate_project(changed)

    def test_json_roundtrip_preserves_exact_results(self):
        restored = import_json(scenario_json(self.project))
        np.testing.assert_array_equal(calculate_project(restored)["combined"], self.result["combined"])
        for data in [b"broken", b"{}", b"null"]:
            with self.subTest(data=data), self.assertRaises(ModelError):
                import_json(data)

    def test_excel_bytes_import_and_bad_archive(self):
        self.assertEqual(import_workbook(SOURCE.read_bytes()), self.project)
        with self.assertRaises(ModelError):
            import_workbook(b"not an xlsx")

    def test_export_bundle_is_complete_and_restorable(self):
        with zipfile.ZipFile(io.BytesIO(export_bundle(self.project, self.result))) as archive:
            self.assertEqual(len(archive.namelist()), 37)
            restored = import_json(archive.read("skenario.json"))
            self.assertEqual(restored, self.project)
            self.assertIn("f(K) gabungan", archive.read("ranking.csv").decode("utf-8-sig"))
            for dm in ["DM1", "DM2", "DM3"]:
                self.assertEqual(len([n for n in archive.namelist() if n.startswith(dm + "/")]), 11)


if __name__ == "__main__":
    unittest.main()
