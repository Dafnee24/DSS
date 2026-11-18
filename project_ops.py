"""Changes to project structure and lightweight group records.

All changes work on copies; callers validate and commit the result atomically.
"""
from __future__ import annotations

import copy
from datetime import datetime

from engine import ModelError, validate_project


def group_data(project):
    group = project.setdefault("group", {})
    group.setdefault("confirmed", {})
    group.setdefault("discussion", [])
    group.setdefault("history", [])
    return group


def _ready(project):
    candidate = copy.deepcopy(project)
    group_data(candidate)
    return candidate


def _finish(candidate, reset_all=False, reset_dm=None):
    group = group_data(candidate)
    if reset_all:
        group["confirmed"] = {}
    elif reset_dm:
        group["confirmed"].pop(reset_dm, None)
    validate_project(candidate)
    return candidate


def add_alternative(project, name, default_code="A"):
    candidate = _ready(project)
    candidate["alternatives"].append(name.strip())
    for dm in candidate["decision_makers"]:
        dm["ratings"].append([default_code] * len(candidate["criteria"]))
    return _finish(candidate, reset_all=True)


def rename_alternative(project, old_name, new_name):
    candidate = _ready(project)
    candidate["alternatives"][candidate["alternatives"].index(old_name)] = new_name.strip()
    return _finish(candidate, reset_all=True)


def delete_alternative(project, name):
    candidate = _ready(project)
    if len(candidate["alternatives"]) <= 2:
        raise ModelError("Minimal dua alternatif harus tetap ada.")
    index = candidate["alternatives"].index(name)
    candidate["alternatives"].pop(index)
    for dm in candidate["decision_makers"]:
        dm["ratings"].pop(index)
    return _finish(candidate, reset_all=True)


def add_criterion(project, name, kind, default_code="A"):
    candidate = _ready(project)
    candidate["criteria"].append({"id": f"C{len(candidate['criteria']) + 1}",
                                   "name": name.strip(), "kind": kind})
    for dm in candidate["decision_makers"]:
        for row in dm["ratings"]:
            row.append(default_code)
    return _finish(candidate, reset_all=True)


def edit_criterion(project, criterion_id, name, kind):
    candidate = _ready(project)
    criterion = next(c for c in candidate["criteria"] if c["id"] == criterion_id)
    criterion["name"] = name.strip()
    criterion["kind"] = kind
    return _finish(candidate, reset_all=True)


def delete_criterion(project, criterion_id):
    candidate = _ready(project)
    if len(candidate["criteria"]) <= 1:
        raise ModelError("Minimal satu kriteria harus tetap ada.")
    index = [c["id"] for c in candidate["criteria"]].index(criterion_id)
    candidate["criteria"].pop(index)
    for i, criterion in enumerate(candidate["criteria"], 1):
        criterion["id"] = f"C{i}"
    for dm in candidate["decision_makers"]:
        for row in dm["ratings"]:
            row.pop(index)
    return _finish(candidate, reset_all=True)


def add_dm(project, name, weight=0.0):
    candidate = _ready(project)
    used = {dm["id"] for dm in candidate["decision_makers"]}
    number = 1
    while f"DM{number}" in used:
        number += 1
    dm_id = f"DM{number}"
    candidate["decision_makers"].append({
        "id": dm_id, "name": name.strip(), "weight": weight,
        "ratings": copy.deepcopy(candidate["decision_makers"][0]["ratings"]),
    })
    return _finish(candidate), dm_id


def rename_dm(project, dm_id, name):
    candidate = _ready(project)
    next(dm for dm in candidate["decision_makers"] if dm["id"] == dm_id)["name"] = name.strip()
    return _finish(candidate)


def delete_dm(project, dm_id):
    candidate = _ready(project)
    if len(candidate["decision_makers"]) <= 1:
        raise ModelError("Minimal satu DM harus tetap ada.")
    candidate["decision_makers"] = [dm for dm in candidate["decision_makers"] if dm["id"] != dm_id]
    group_data(candidate)["confirmed"].pop(dm_id, None)
    return _finish(candidate)


def confirm_dm(project, dm_id, confirmed=True):
    candidate = _ready(project)
    if dm_id not in {dm["id"] for dm in candidate["decision_makers"]}:
        raise ModelError("DM tidak ditemukan.")
    group_data(candidate)["confirmed"][dm_id] = bool(confirmed)
    return _finish(candidate)


def add_message(project, author, message):
    candidate = _ready(project)
    content = message.strip()
    if not content:
        raise ModelError("Pesan diskusi tidak boleh kosong.")
    if author not in {dm["id"] for dm in candidate["decision_makers"]}:
        raise ModelError("Pilih DM yang tersedia sebagai penulis.")
    group_data(candidate)["discussion"].append({
        "time": datetime.now().astimezone().isoformat(timespec="seconds"),
        "author": author, "message": content,
    })
    return _finish(candidate)


def record_decision(project, result, note):
    candidate = _ready(project)
    text = note.strip()
    if not text:
        raise ModelError("Catatan keputusan tidak boleh kosong.")
    order = sorted(range(len(candidate["alternatives"])),
                   key=lambda i: (-result["combined"][i], i))
    group_data(candidate)["history"].append({
        "time": datetime.now().astimezone().isoformat(timespec="seconds"),
        "note": text,
        "weights": {dm["id"]: dm["weight"] for dm in candidate["decision_makers"]},
        "ranking": [{"alternative": candidate["alternatives"][i],
                     "score": float(result["combined"][i]), "rank": int(result["rank"][i])}
                    for i in order],
    })
    return _finish(candidate)
