import copy
import os
import tempfile
import unittest
from pathlib import Path

from engine import ModelError, calculate_project
from store import (AccessError, ConflictError, add_dm_with_account,
                   admin_reset_password, authenticate, change_password,
                   create_dm_account, load_for_user, save_admin_project,
                   save_dm_ratings, setup_admin)


class StoreTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.previous_path = os.environ.get("DSS_DB_PATH")
        os.environ["DSS_DB_PATH"] = str(Path(self.temp.name) / "dss.sqlite3")
        setup_admin("admin", "admin-secret-123")
        create_dm_account("admin", "DM1", "dm1", "dm1-secret-123")
        create_dm_account("admin", "DM2", "dm2", "dm2-secret-123")

    def tearDown(self):
        if self.previous_path is None:
            os.environ.pop("DSS_DB_PATH", None)
        else:
            os.environ["DSS_DB_PATH"] = self.previous_path
        self.temp.cleanup()

    def test_dm_view_contains_only_assigned_dm_and_cannot_write_admin_data(self):
        admin_project, revision = load_for_user("admin")
        dm_project, _ = load_for_user("dm1")
        self.assertEqual([dm["id"] for dm in dm_project["decision_makers"]], ["DM1"])
        self.assertEqual(dm_project["group"]["discussion"], [])
        self.assertEqual(dm_project["group"]["history"], [])
        with self.assertRaises(AccessError):
            save_admin_project("dm1", admin_project, revision)
        with self.assertRaises(AccessError):
            save_dm_ratings("admin", admin_project["decision_makers"][0]["ratings"])

    def test_separate_dm_saves_merge_and_admin_sees_latest(self):
        initial, _ = load_for_user("admin")
        dm1_matrix = copy.deepcopy(initial["decision_makers"][0]["ratings"])
        dm2_matrix = copy.deepcopy(initial["decision_makers"][1]["ratings"])
        dm1_matrix[0][7] = "CL"
        dm2_matrix[0][7] = "VH"
        save_dm_ratings("dm1", dm1_matrix)
        save_dm_ratings("dm2", dm2_matrix)
        latest, revision = load_for_user("admin")
        self.assertEqual(revision, 2)
        self.assertEqual(latest["decision_makers"][0]["ratings"][0][7], "CL")
        self.assertEqual(latest["decision_makers"][1]["ratings"][0][7], "VH")
        self.assertEqual(latest["decision_makers"][2]["ratings"], initial["decision_makers"][2]["ratings"])
        self.assertNotEqual(calculate_project(latest)["combined"][0],
                            calculate_project(initial)["combined"][0])

    def test_stale_admin_edit_is_rejected_without_overwriting_dm(self):
        candidate, revision = load_for_user("admin")
        matrix = copy.deepcopy(candidate["decision_makers"][0]["ratings"])
        matrix[0][7] = "CL"
        save_dm_ratings("dm1", matrix)
        with self.assertRaises(ConflictError):
            save_admin_project("admin", candidate, revision)
        latest, _ = load_for_user("admin")
        self.assertEqual(latest["decision_makers"][0]["ratings"][0][7], "CL")

    def test_login_password_change_and_admin_reset(self):
        self.assertEqual(authenticate("DM1", "dm1-secret-123")["dm_id"], "DM1")
        with self.assertRaises(AccessError):
            authenticate("dm1", "wrong-password")
        change_password("dm1", "dm1-secret-123", "new-dm1-secret")
        with self.assertRaises(AccessError):
            authenticate("dm1", "dm1-secret-123")
        self.assertEqual(authenticate("dm1", "new-dm1-secret")["role"], "dm")
        with self.assertRaises(AccessError):
            admin_reset_password("dm1", "DM2", "another-secret")
        admin_reset_password("admin", "DM1", "reset-dm1-secret")
        self.assertEqual(authenticate("dm1", "reset-dm1-secret")["role"], "dm")
        with self.assertRaises(ModelError):
            create_dm_account("admin", "DM2", "other", "short")

    def test_new_dm_and_account_are_created_together(self):
        dm_id = add_dm_with_account("admin", "Penilai 4", "dm4", "dm4-secret-123")
        self.assertEqual(dm_id, "DM4")
        self.assertEqual(authenticate("dm4", "dm4-secret-123")["dm_id"], "DM4")
        project, _ = load_for_user("admin")
        self.assertEqual(len(project["decision_makers"]), 4)
        self.assertEqual(project["decision_makers"][-1]["weight"], 0)
        with self.assertRaises(ModelError):
            add_dm_with_account("admin", "Penilai 5", "dm4", "other-secret-123")
        project, _ = load_for_user("admin")
        self.assertEqual(len(project["decision_makers"]), 4)


if __name__ == "__main__":
    unittest.main()
