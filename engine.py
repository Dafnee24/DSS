"""MEREC–MARCOS formulas from DSS PROJECT.xlsx, with variable matrix dimensions.

No intermediate rounding, DM-weight normalization, or alternate aggregation.
Excel locations refer to the original 14-alternative, 12-criterion template.
"""
from __future__ import annotations

import numpy as np
import pandas as pd


class ModelError(ValueError):
    """An input or calculation does not have a defined result."""


def rank_descending(values):
    """Excel RANK(number, range, 0): equal values share the minimum rank."""
    values = np.asarray(values, dtype=float)
    return 1 + (values[None, :] > values[:, None]).sum(axis=1)


def validate_project(project):
    try:
        if project["version"] != 1:
            raise ModelError("Versi skenario tidak didukung.")
        criteria, scale = project["criteria"], project["scale"]
        alternatives, dms = project["alternatives"], project["decision_makers"]
        if len(criteria) < 1 or len(alternatives) < 2 or len(dms) < 1:
            raise ModelError("Diperlukan sedikitnya 2 alternatif, 1 kriteria, dan 1 DM.")
        if [c["id"] for c in criteria] != [f"C{i}" for i in range(1, len(criteria) + 1)]:
            raise ModelError("Kode kriteria harus berurutan C1, C2, dan seterusnya.")
        if len({a.strip().casefold() for a in alternatives if isinstance(a, str)}) != len(alternatives) or any(
            not isinstance(a, str) or not a.strip() or a.strip().upper() in {"AAI", "AI"}
            for a in alternatives
        ):
            raise ModelError("Nama alternatif harus terisi, unik, dan bukan AAI/AI.")
        if any(c["kind"] not in {"Cost", "Benefit"} for c in criteria):
            raise ModelError("Jenis kriteria harus Cost atau Benefit.")
        if any(not isinstance(c["name"], str) or not c["name"].strip() for c in criteria):
            raise ModelError("Nama kriteria tidak boleh kosong.")
        if len({c["name"].strip().casefold() for c in criteria}) != len(criteria):
            raise ModelError("Nama kriteria harus unik.")
        codes = [s["code"] for s in scale]
        if codes != ["CL", "VL", "L", "BA", "A", "AA", "H", "VH", "CH"]:
            raise ModelError("Skala harus memuat CL, VL, L, BA, A, AA, H, VH, CH secara berurutan.")
        numbers = np.array([s["value"] for s in scale], dtype=float)
        if not np.isfinite(numbers).all() or (numbers <= 0).any():
            raise ModelError("Semua nilai crisp harus berupa angka positif agar LN dan pembagian terdefinisi.")
        ids = [dm["id"] for dm in dms]
        if len(set(ids)) != len(ids) or any(
            not isinstance(dm_id, str) or not dm_id.startswith("DM") or not dm_id[2:].isdigit()
            for dm_id in ids
        ):
            raise ModelError("Kode DM harus unik, misalnya DM1 atau DM4.")
        weights = np.array([dm["weight"] for dm in dms], dtype=float)
        if not np.isfinite(weights).all() or (weights < 0).any() or weights.sum() <= 0:
            raise ModelError("Bobot DM harus nonnegatif dan setidaknya satu bobot lebih dari nol.")
        for dm in dms:
            if not isinstance(dm["name"], str) or not dm["name"].strip():
                raise ModelError("Nama pengambil keputusan tidak boleh kosong.")
            ratings = np.asarray(dm["ratings"], dtype=object)
            if ratings.shape != (len(alternatives), len(criteria)):
                raise ModelError(f"Matriks {dm['id']} harus berukuran {len(alternatives)} × {len(criteria)}.")
            for i, j in np.ndindex(ratings.shape):
                if ratings[i, j] not in codes:
                    raise ModelError(f"{dm['id']} / {alternatives[i]} / C{j + 1}: kode penilaian kosong atau di luar skala.")
    except (KeyError, TypeError, ValueError, OverflowError) as exc:
        if isinstance(exc, ModelError):
            raise
        raise ModelError("Struktur data tidak valid. Gunakan Excel asli atau JSON hasil ekspor aplikasi.") from exc


def calculate_dm(crisp, kinds):
    x = np.asarray(crisp, dtype=float)
    if x.ndim != 2 or min(x.shape) == 0 or len(kinds) != x.shape[1]:
        raise ModelError("Dimensi matriks dan jenis kriteria tidak sesuai.")
    if not np.isfinite(x).all() or (x <= 0).any():
        raise ModelError("Matriks crisp harus berisi angka positif dan berhingga.")
    if any(k not in {"Cost", "Benefit"} for k in kinds):
        raise ModelError("Jenis kriteria tidak dikenal.")
    cost = np.array([k == "Cost" for k in kinds])
    lo, hi = x.min(axis=0), x.max(axis=0)
    # Blocks 3–6: B41:M54, B58:O71, B75:M88, B92:N107.
    with np.errstate(divide="raise", invalid="raise", over="raise", under="ignore"):
        try:
            norm = np.where(cost, x / hi, lo / x)
            logs = np.abs(np.log(norm))
            log_sum = logs.sum(axis=1)
            n = x.shape[1]  # The original n remains the denominator after removal.
            performance = np.log(1 + log_sum / n)
            removed = np.log(1 + (log_sum[:, None] - logs) / n)
            deviations = np.abs(removed - performance[:, None])
            effects = deviations.sum(axis=0)
            if effects.sum() == 0:
                raise ModelError("ΣE = 0: semua alternatif identik pada setiap kriteria. Bobot MEREC tidak terdefinisi, sama seperti pembagian nol di Excel.")
            weights = effects / effects.sum()
            # Blocks 7–9: B112:M127, B131:M146, B150:N165.
            ideal = np.where(cost, lo, hi)
            anti_ideal = np.where(cost, hi, lo)
            extended = np.vstack([anti_ideal, x, ideal])
            marcos_norm = np.where(cost, ideal / extended, extended / ideal)
            weighted = marcos_norm * weights
            totals = weighted.sum(axis=1)
            # Block 10: B169:H182. Keep the workbook's exact formula structure.
            k_minus = totals[1:-1] / totals[0]
            k_plus = totals[1:-1] / totals[-1]
            f_minus = k_plus / (k_minus + k_plus)
            f_plus = k_minus / (k_minus + k_plus)
            utility = (k_minus + k_plus) / (1 + (1 - f_plus) / f_plus + (1 - f_minus) / f_minus)
        except FloatingPointError as exc:
            raise ModelError("Nilai masukan menghasilkan logaritma atau pembagian yang tidak terdefinisi.") from exc
    return dict(crisp=x, merec_norm=norm, logs=logs, log_sum=log_sum,
                performance=performance, removed=removed, deviations=deviations,
                effects=effects, weights=weights, extended=extended,
                marcos_norm=marcos_norm, weighted=weighted, totals=totals,
                k_minus=k_minus, k_plus=k_plus, f_minus=f_minus, f_plus=f_plus,
                utility=utility, rank=rank_descending(utility))


def calculate_project(project):
    validate_project(project)
    scale = {s["code"]: float(s["value"]) for s in project["scale"]}
    kinds = [c["kind"] for c in project["criteria"]]
    results = {}
    for dm in project["decision_makers"]:
        crisp = [[scale[code] for code in row] for row in dm["ratings"]]
        try:
            results[dm["id"]] = calculate_dm(crisp, kinds)
        except ModelError as exc:
            raise ModelError(f"{dm['id']}: {exc}") from exc
    # Rekap multiplies raw lambda values. Do NOT normalize them implicitly.
    lambdas = [float(dm["weight"]) for dm in project["decision_makers"]]
    combined = sum(results[dm["id"]]["utility"] * weight
                   for dm, weight in zip(project["decision_makers"], lambdas))
    combined_weights = sum(results[dm["id"]]["weights"] * weight
                           for dm, weight in zip(project["decision_makers"], lambdas))
    return dict(dms=results, combined=combined, rank=rank_descending(combined),
                combined_weights=combined_weights)


def ranking_frame(project, result):
    frame = pd.DataFrame({"Alternatif": project["alternatives"]})
    for dm in project["decision_makers"]:
        r = result["dms"][dm["id"]]
        frame[f"f(K) {dm['id']}"] = r["utility"]
        frame[f"Rank {dm['id']}"] = r["rank"]
    frame["f(K) gabungan"] = result["combined"]
    frame["Ranking akhir"] = result["rank"]
    return frame


def weight_frame(project, result):
    frame = pd.DataFrame({"Kriteria": [c["id"] for c in project["criteria"]]})
    for dm in project["decision_makers"]:
        frame[f"w {dm['id']}"] = result["dms"][dm["id"]]["weights"]
    frame["Rata-rata terbobot λ"] = result["combined_weights"]
    frame["Ranking"] = rank_descending(result["combined_weights"])
    return frame


def calculation_tables(project, result, dm_id):
    """Display/export all ten workbook blocks in their original order."""
    r = result["dms"][dm_id]
    dm = next(d for d in project["decision_makers"] if d["id"] == dm_id)
    alts = project["alternatives"]
    cols = [c["id"] for c in project["criteria"]]
    def matrix(values, labels=None):
        frame = pd.DataFrame(values, index=labels if labels is not None else alts, columns=cols)
        frame.index.name = "Alternatif"
        return frame
    logs = matrix(r["logs"])
    logs["Σ |ln n|"] = r["log_sum"]
    logs["S_i"] = r["performance"]
    deviations = matrix(r["deviations"])
    effects = pd.DataFrame([r["effects"], r["weights"]], index=["E_j", "w_j"], columns=cols)
    effects["Jumlah"] = [r["effects"].sum(), r["weights"].sum()]
    ext_labels = ["AAI", *alts, "AI"]
    weighted = matrix(r["weighted"], ext_labels)
    weighted["S_i"] = r["totals"]
    final = pd.DataFrame({"S_i": r["totals"][1:-1], "K⁻": r["k_minus"],
                          "K⁺": r["k_plus"], "f(K⁻)": r["f_minus"],
                          "f(K⁺)": r["f_plus"], "f(K)": r["utility"],
                          "Ranking": r["rank"]}, index=alts)
    final.index.name = "Alternatif"
    tables = [
        ("1. Input linguistik", "A7:M20", matrix(dm["ratings"])),
        ("2. Matriks crisp", "A24:M37", matrix(r["crisp"])),
        ("3. Normalisasi MEREC", "A41:M54", matrix(r["merec_norm"])),
        ("4. Logaritma dan S_i", "A58:O71", logs),
        ("5. S'_ij tanpa kriteria j", "A75:M88", matrix(r["removed"])),
        ("6a. Deviasi absolut", "A92:M105", deviations),
        ("6b. E_j dan bobot MEREC", "A106:N107", effects),
        ("7. Matriks diperluas", "A112:M127", matrix(r["extended"], ext_labels)),
        ("8. Normalisasi MARCOS", "A131:M146", matrix(r["marcos_norm"], ext_labels)),
        ("9. Matriks terbobot dan S_i", "A150:N165", weighted),
        ("10. Utilitas dan ranking", "A169:H182", final),
    ]
    if len(alts) != 14 or len(cols) != 12 or len(project["decision_makers"]) != 3:
        return [(title, "struktur dinamis", frame) for title, _, frame in tables]
    return tables
