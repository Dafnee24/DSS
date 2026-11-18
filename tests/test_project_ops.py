import unittest

import numpy as np

from engine import ModelError, calculate_project
from project_ops import (add_alternative, add_criterion, add_dm, add_message,
                         confirm_dm, delete_alternative, delete_criterion, delete_dm,
                         edit_criterion, group_data, record_decision,
                         rename_alternative, rename_dm)
from workbook_io import import_json, import_workbook, scenario_json


class ProjectOperationsTests(unittest.TestCase):
    def setUp(self):
        self.original = import_workbook()

    def test_alternatives_can_be_added_renamed_and_removed(self):
        project = add_alternative(self.original, "Pemasok 15")
        self.assertEqual(len(project["alternatives"]), 15)
        self.assertEqual(project["decision_makers"][0]["ratings"][-1], ["A"] * 12)
        self.assertEqual(len(calculate_project(project)["combined"]), 15)
        project = rename_alternative(project, "Pemasok 15", "Pemasok Baru")
        self.assertEqual(project["alternatives"][-1], "Pemasok Baru")
        project = delete_alternative(project, "Pemasok Baru")
        self.assertEqual(project["alternatives"], self.original["alternatives"])
        self.assertEqual(project["decision_makers"][0]["ratings"],
                         self.original["decision_makers"][0]["ratings"])
        with self.assertRaises(ModelError):
            add_alternative(self.original, "Al1")
        with self.assertRaises(ModelError):
            add_alternative(self.original, "")

    def test_criteria_can_be_added_edited_and_removed(self):
        project = add_criterion(self.original, "Ketepatan waktu", "Benefit")
        result = calculate_project(project)
        self.assertEqual(len(project["criteria"]), 13)
        self.assertEqual(result["dms"]["DM1"]["weights"][-1], 0)
        # MEREC divides by n=13 after insertion, so existing weights may change
        # even though the newly added constant criterion itself has zero weight.
        self.assertFalse(np.allclose(result["combined"], calculate_project(self.original)["combined"]))
        project = edit_criterion(project, "C13", "Ketepatan pengiriman", "Cost")
        self.assertEqual(project["criteria"][-1]["kind"], "Cost")
        project = delete_criterion(project, "C13")
        self.assertEqual(project["criteria"], self.original["criteria"])
        project = delete_criterion(project, "C2")
        self.assertEqual(project["criteria"][1]["id"], "C2")
        self.assertEqual(len(project["decision_makers"][0]["ratings"][0]), 11)
        self.assertEqual(len(calculate_project(project)["dms"]["DM1"]["weights"]), 11)
        with self.assertRaises(ModelError):
            add_criterion(self.original, "", "Benefit")
        with self.assertRaises(ModelError):
            add_criterion(self.original, "Baru", "Invalid")

    def test_many_dm_have_independent_ratings_and_weights(self):
        project, dm_id = add_dm(self.original, "Penilai 4")
        self.assertEqual(dm_id, "DM4")
        self.assertEqual(project["decision_makers"][-1]["weight"], 0)
        self.assertEqual(project["decision_makers"][-1]["ratings"],
                         self.original["decision_makers"][0]["ratings"])
        project["decision_makers"][-1]["ratings"][0][0] = "CL"
        self.assertNotEqual(project["decision_makers"][-1]["ratings"],
                            project["decision_makers"][0]["ratings"])
        project["decision_makers"][-1]["weight"] = .1
        result = calculate_project(project)
        self.assertEqual(len(result["dms"]), 4)
        self.assertFalse(np.allclose(result["combined"], calculate_project(self.original)["combined"]))
        project = rename_dm(project, dm_id, "Penilai Keempat")
        self.assertEqual(project["decision_makers"][-1]["name"], "Penilai Keempat")
        project = delete_dm(project, dm_id)
        self.assertEqual(len(project["decision_makers"]), 3)

    def test_group_records_roundtrip_and_confirmations_reset_on_structure_change(self):
        project = confirm_dm(self.original, "DM1")
        self.assertTrue(group_data(project)["confirmed"]["DM1"])
        project = add_message(project, "DM2", "Periksa C8 untuk Al1")
        project = record_decision(project, calculate_project(project), "Rapat final")
        self.assertEqual(project["group"]["history"][0]["ranking"][0]["alternative"], "Al1")
        restored = import_json(scenario_json(project))
        self.assertEqual(restored["group"], project["group"])
        project = add_alternative(restored, "Baru")
        self.assertEqual(project["group"]["confirmed"], {})
        self.assertEqual(len(project["group"]["discussion"]), 1)
        self.assertEqual(len(project["group"]["history"]), 1)
        with self.assertRaises(ModelError):
            add_message(project, "DM1", " ")
        with self.assertRaises(ModelError):
            record_decision(project, calculate_project(project), " ")


if __name__ == "__main__":
    unittest.main()
