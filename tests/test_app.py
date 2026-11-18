import os
import tempfile
import unittest
from pathlib import Path

from streamlit.testing.v1 import AppTest

from engine import calculate_project
from store import create_dm_account, load_for_user, setup_admin

APP = str(Path(__file__).resolve().parents[1] / "app.py")


def button(app, label):
    return next(item for item in app.button if item.label == label)


class AppTests(unittest.TestCase):
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

    def login(self, username, password):
        app = AppTest.from_file(APP, default_timeout=30).run()
        self.assertEqual(len(app.exception), 0)
        app.text_input[0].set_value(username)
        app.text_input[1].set_value(password)
        button(app, "Masuk").click().run()
        self.assertEqual(len(app.exception), 0)
        return app

    def test_admin_and_dm_have_different_navigation(self):
        admin = self.login("admin", "admin-secret-123")
        self.assertEqual(admin.radio(key="page_admin").value, "Hasil grup")
        admin.radio(key="page_admin").set_value("Kelola proyek").run()
        self.assertEqual(len(admin.exception), 0)
        admin.radio(key="page_admin").set_value("Rincian perhitungan").run()
        self.assertEqual(len(admin.exception), 0)
        dm = self.login("dm1", "dm1-secret-123")
        self.assertEqual([item.value for item in dm.radio], ["Penilaian saya"])
        self.assertFalse(any("Hasil grup" in item.label for item in dm.button))

    def test_each_dm_changes_only_own_linguistic_terms_and_admin_sees_result(self):
        admin = self.login("admin", "admin-secret-123")
        baseline, _ = load_for_user("admin")
        baseline_result = calculate_project(baseline)
        dm1 = self.login("dm1", "dm1-secret-123")
        dm1.session_state["ratings_editor_DM1_0"] = {
            "edited_rows": {0: {"C8": "CL"}}, "added_rows": [], "deleted_rows": []}
        button(dm1, "Simpan penilaian saya").click().run()
        self.assertEqual(len(dm1.exception), 0)
        current, _ = load_for_user("admin")
        self.assertEqual(current["decision_makers"][0]["ratings"][0][7], "CL")
        self.assertEqual(current["decision_makers"][1]["ratings"],
                         baseline["decision_makers"][1]["ratings"])
        self.assertFalse((calculate_project(current)["combined"] == baseline_result["combined"]).all())
        dm2 = self.login("dm2", "dm2-secret-123")
        dm2.session_state["ratings_editor_DM2_1"] = {
            "edited_rows": {0: {"C8": "VH"}}, "added_rows": [], "deleted_rows": []}
        button(dm2, "Simpan penilaian saya").click().run()
        self.assertEqual(len(dm2.exception), 0)
        latest, _ = load_for_user("admin")
        self.assertEqual(latest["decision_makers"][0]["ratings"][0][7], "CL")
        self.assertEqual(latest["decision_makers"][1]["ratings"][0][7], "VH")
        admin.run()
        self.assertEqual(len(admin.exception), 0)
        ranking = admin.dataframe[0].value
        self.assertIn("f(K) DM1", ranking.columns)
        self.assertIn("f(K) DM2", ranking.columns)

    def test_admin_can_create_account_and_dm_can_confirm_own_status(self):
        admin = self.login("admin", "admin-secret-123")
        admin.radio(key="page_admin").set_value("Kelola proyek").run()
        self.assertEqual(len(admin.exception), 0)
        # Initial DM3 has no account until admin creates one.
        self.assertIn("Belum ada akun", admin.dataframe[2].value["Akun"].tolist())
        dm = self.login("dm1", "dm1-secret-123")
        button(dm, "Konfirmasi penilaian selesai").click().run()
        self.assertEqual(len(dm.exception), 0)
        project, _ = load_for_user("admin")
        self.assertTrue(project["group"]["confirmed"]["DM1"])
        admin.radio(key="page_admin").set_value("Hasil grup").run()
        self.assertEqual(len(admin.exception), 0)
        self.assertTrue(any("1 / 3" in item.value for item in admin.metric))


if __name__ == "__main__":
    unittest.main()
