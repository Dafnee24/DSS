"""Read only the workbook inputs; use cached formulas solely for comparison."""
from __future__ import annotations

import io
import json
import numbers
import warnings
import zipfile
from pathlib import Path

import numpy as np
import openpyxl
import pandas as pd

from engine import ModelError, calculation_tables, ranking_frame, validate_project, weight_frame

ROOT = Path(__file__).resolve().parent
SOURCE = ROOT / "data" / "DSS PROJECT.xlsx"


def open_workbook(source, data_only=False):
    if isinstance(source, bytes):
        if len(source) > 10 * 1024 * 1024:
            raise ModelError("Ukuran file maksimal 10 MB.")
        source = io.BytesIO(source)
    try:
        with zipfile.ZipFile(source) as archive:
            if sum(info.file_size for info in archive.infolist()) > 50 * 1024 * 1024:
                raise ModelError("Isi workbook terlalu besar (maksimal 50 MB setelah ekstraksi).")
        if hasattr(source, "seek"):
            source.seek(0)
        with warnings.catch_warnings():
            warnings.filterwarnings("ignore", message="Data Validation extension is not supported.*")
            return openpyxl.load_workbook(source, data_only=data_only, read_only=True)
    except (zipfile.BadZipFile, KeyError, OSError, ValueError) as exc:
        if isinstance(exc, ModelError):
            raise
        raise ModelError("File Excel tidak dapat dibaca. Gunakan berkas .xlsx dengan struktur template.") from exc


def import_workbook(source=SOURCE):
    w = open_workbook(source)
    try:
        if not {"Skala", "DM1", "DM2", "DM3", "Rekap"}.issubset(w.sheetnames):
            raise ModelError("Sheet Skala, DM1, DM2, DM3, dan Rekap harus tersedia.")
        # Materialize small bounded grids once (read_only cell access otherwise reparses XML).
        scale_rows = list(w["Skala"].iter_rows(min_row=4, max_row=15, max_col=7, values_only=True))
        recap_rows = list(w["Rekap"].iter_rows(min_row=4, max_row=6, max_col=2, values_only=True))
        project = {"version": 1, "source": "DSS PROJECT.xlsx", "scale": [], "criteria": [],
                   "alternatives": [], "decision_makers": []}
        for row in scale_rows[:9]:
            project["scale"].append(dict(code=row[0], label=row[1], value=row[2]))
        for row in scale_rows:
            project["criteria"].append(dict(id=row[4], name=row[5], kind=row[6]))
        for index, dm_id in enumerate(["DM1", "DM2", "DM3"]):
            rows = list(w[dm_id].iter_rows(min_row=1, max_row=20, max_col=13, values_only=True))
            if list(rows[5][1:13]) != [c["id"] for c in project["criteria"]]:
                raise ModelError(f"Header C1–C12 pada {dm_id}!B6:M6 tidak sesuai template.")
            alternatives = [row[0] for row in rows[6:20]]
            if index == 0:
                project["alternatives"] = alternatives
            elif project["alternatives"] != alternatives:
                raise ModelError(f"Urutan alternatif pada {dm_id}!A7:A20 berbeda dari DM1.")
            project["decision_makers"].append(dict(
                id=dm_id, name=str(rows[0][0]).split(" – ", 1)[-1],
                weight=recap_rows[index][1], ratings=[list(row[1:13]) for row in rows[6:20]]))
        validate_project(project)
        return project
    finally:
        w.close()


def import_json(data):
    try:
        project = json.loads(data)
        validate_project(project)
        return project
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise ModelError("JSON tidak valid. Gunakan skenario yang diekspor dari aplikasi.") from exc


def scenario_json(project):
    return json.dumps(project, indent=2, ensure_ascii=False, allow_nan=False)


def csv_bytes(frame, index=False):
    # Escape text that spreadsheet software could otherwise treat as formulas.
    safe = frame.copy()
    def escape(value):
        return "'" + value if isinstance(value, str) and value.startswith(("=", "+", "-", "@", "\t", "\r")) else value
    for col in safe.columns:
        if not pd.api.types.is_numeric_dtype(safe[col]):
            safe[col] = safe[col].map(escape)
    safe.index = safe.index.map(escape)
    return safe.to_csv(index=index, float_format="%.17g").encode("utf-8-sig")


def export_bundle(project, result):
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("skenario.json", scenario_json(project))
        archive.writestr("ranking.csv", csv_bytes(ranking_frame(project, result)))
        archive.writestr("bobot_merec.csv", csv_bytes(weight_frame(project, result)))
        for dm in project["decision_makers"]:
            for i, (title, address, frame) in enumerate(calculation_tables(project, result, dm["id"]), 1):
                archive.writestr(f"{dm['id']}/{i:02d}_{address.replace(':', '-')}.csv", csv_bytes(frame, index=True))
        archive.writestr("PETUNJUK.txt", "Hasil dihitung mengikuti DSS PROJECT.xlsx.\n"
                         "Setiap CSV DM memakai urutan baris sumber, dengan alamat blok Excel pada nama file.\n"
                         "CSV menyimpan 17 digit signifikan, tanpa pembulatan perantara.\n"
                         "Bobot DM dipakai apa adanya (tidak dinormalisasi otomatis).\n"
                         "Impor skenario.json untuk memulihkan input.\n")
    return output.getvalue()


def compare_cached_workbook(project, result, source=SOURCE):
    """Compare every numeric calculation cell, not just the final winner.

    Formula caches are a reference snapshot; this function does not evaluate Excel.
    """
    w = open_workbook(source, data_only=True)
    checks = []
    try:
        for dm in project["decision_makers"]:
            grid = list(w[dm["id"]].iter_rows(max_row=182, max_col=16, values_only=True))
            r = result["dms"][dm["id"]]
            ranges = [
                ("Crisp", 24, 2, r["crisp"]), ("Normalisasi MEREC", 41, 2, r["merec_norm"]),
                ("Log dan S_i", 58, 2, np.column_stack([r["logs"], r["log_sum"], r["performance"]])),
                ("S'_ij", 75, 2, r["removed"]), ("Deviasi", 92, 2, r["deviations"]),
                ("E_j dan w_j", 106, 2, np.column_stack([np.vstack([r["effects"], r["weights"]]),
                    [r["effects"].sum(), r["weights"].sum()]])),
                ("Matriks diperluas", 112, 2, r["extended"]),
                ("Normalisasi MARCOS", 131, 2, r["marcos_norm"]),
                ("Matriks terbobot", 150, 2, np.column_stack([r["weighted"], r["totals"]])),
                ("Utilitas dan ranking", 169, 2, np.column_stack([r["totals"][1:-1], r["k_minus"],
                    r["k_plus"], r["f_minus"], r["f_plus"], r["utility"], r["rank"]])),
            ]
            for label, row, col, array in ranges:
                for i, j in np.ndindex(array.shape):
                    checks.append(_comparison(dm["id"], label, row + i, col + j,
                                              grid[row + i - 1][col + j - 1], array[i, j],
                                              exact=(label == "Utilitas dan ranking" and j == 6)))
        grid = list(w["Rekap"].iter_rows(max_row=40, max_col=9, values_only=True))
        for frame, start_row, rank_columns in [
            (weight_frame(project, result).iloc[:, 1:], 11, [4]),
            (ranking_frame(project, result).iloc[:, 1:], 27, [1, 3, 5, 7]),
        ]:
            values = frame.to_numpy()
            for i, j in np.ndindex(values.shape):
                checks.append(_comparison("Rekap", "Rekap kelompok", start_row + i, 2 + j,
                                          grid[start_row + i - 1][1 + j], values[i, j], exact=j in rank_columns))
        return pd.DataFrame(checks)
    finally:
        w.close()


def _comparison(sheet, block, row, column, cached, actual, exact=False):
    valid = isinstance(cached, numbers.Real) and np.isfinite(cached)
    delta = abs(float(cached) - float(actual)) if valid else np.nan
    matched = valid and (delta == 0 if exact else delta <= 1e-12)
    return {"Sheet": sheet, "Blok": block, "Sel": f"{openpyxl.utils.get_column_letter(column)}{row}",
            "Excel": cached if valid else None, "Prototipe": actual, "Selisih": delta,
            "Status": "Sesuai" if matched else ("Berbeda" if valid else "Cache tidak tersedia")}
