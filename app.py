"""Role-based Streamlit interface for the Excel-matched MEREC–MARCOS model."""
from __future__ import annotations

import copy
from html import escape
from pathlib import Path

import numpy as np
import pandas as pd
import plotly.express as px
import streamlit as st

from engine import ModelError, calculate_project, calculation_tables, ranking_frame, weight_frame
from project_ops import (add_alternative, add_criterion, delete_alternative,
                         delete_criterion, delete_dm, edit_criterion, group_data,
                         rename_alternative, rename_dm)
from store import (AccessError, ConflictError, add_dm_with_account,
                   admin_exists, admin_reset_password, authenticate, change_password,
                   confirm_own_ratings, create_dm_account, current_user, initialize,
                   list_dm_accounts, load_for_user, post_message, save_admin_project,
                   save_decision, save_dm_ratings, setup_admin)
from workbook_io import (SOURCE, csv_bytes, export_bundle, import_json,
                         import_workbook, scenario_json)

ROOT = Path(__file__).resolve().parent
st.set_page_config(page_title="DSS Pemasok · MEREC–MARCOS", page_icon="◈", layout="wide")
st.html("<style>" + (ROOT / "assets" / "style.css").read_text(encoding="utf-8") + "</style>")
initialize(seed_demo=True)


def header(title, description):
    st.html('<div class="eyebrow">DSS PEMASOK / MEREC–MARCOS</div>')
    st.title(title)
    st.html(f'<div class="subtitle">{escape(description)}</div>')


def table(frame, index=False, number_format="%.4f", height="auto"):
    configs = {column: st.column_config.NumberColumn(format=number_format)
               for column in frame.columns if pd.api.types.is_float_dtype(frame[column])}
    st.dataframe(frame, hide_index=not index, column_config=configs,
                 width="stretch", height=height)


def chart_style(fig, height=340):
    fig.update_layout(height=height, margin=dict(l=8, r=18, t=12, b=18),
                      font=dict(family="Arial", color="#516573", size=12),
                      paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                      showlegend=False, xaxis=dict(gridcolor="#edf1f3", zeroline=False),
                      yaxis=dict(gridcolor="#edf1f3", zeroline=False))
    return fig


def handle_error(exc):
    st.error(str(exc))


def commit_admin(candidate, message):
    save_admin_project(user["username"], candidate, revision)
    st.session_state.flash = message
    st.rerun()


def login_screen():
    if not admin_exists():
        header("Siapkan akun admin", "Langkah pertama: buat akun yang mengelola proyek dan melihat hasil seluruh DM.")
        with st.form("setup_admin"):
            username = st.text_input("Nama pengguna admin", value="admin")
            password = st.text_input("Kata sandi admin (minimal 10 karakter)", type="password")
            confirm = st.text_input("Ulangi kata sandi", type="password")
            submitted = st.form_submit_button("Buat akun admin", type="primary")
        if submitted:
            if password != confirm:
                st.error("Kedua kata sandi tidak sama.")
            else:
                try:
                    st.session_state.auth_username = setup_admin(username, password)
                    st.rerun()
                except (ModelError, AccessError) as exc:
                    handle_error(exc)
        st.stop()
    header("Masuk ke DSS Pemasok", "Masuk sebagai admin atau DM. Setiap DM hanya dapat mengubah penilaiannya sendiri.")
    with st.form("login"):
        username = st.text_input("Nama pengguna")
        password = st.text_input("Kata sandi", type="password")
        submitted = st.form_submit_button("Masuk", type="primary")
    if submitted:
        try:
            account = authenticate(username, password)
            st.session_state.auth_username = account["username"]
            st.rerun()
        except (ModelError, AccessError) as exc:
            handle_error(exc)
    st.caption("Akun demo admin dan DM1–DM3 tersedia pada instalasi baru. Akun tambahan dikelola admin; data tersimpan pada komputer yang menjalankan Streamlit.")
    st.stop()


if not st.session_state.get("auth_username"):
    login_screen()

try:
    user = current_user(st.session_state.auth_username)
    project, revision = load_for_user(user["username"])
except AccessError:
    st.session_state.pop("auth_username", None)
    login_screen()

is_admin = user["role"] == "admin"
pages = ["Hasil grup", "Kelola proyek", "Rincian perhitungan"] if is_admin else ["Penilaian saya"]
with st.sidebar:
    st.html('<div class="brand"><div class="brand-icon">◈</div><div><div class="brand-name">DSS Pemasok</div><div class="brand-sub">MEREC → MARCOS</div></div></div>')
    st.caption(f"MASUK SEBAGAI {'ADMIN' if is_admin else user['dm_id']}")
    st.markdown(f"**{user['username']}**")
    page = st.radio("Navigasi", pages, label_visibility="collapsed",
                    key=f"page_{user['role']}")
    st.divider()
    with st.expander("Ganti kata sandi"):
        with st.form("change_password"):
            old_password = st.text_input("Kata sandi lama", type="password")
            new_password = st.text_input("Kata sandi baru", type="password")
            change = st.form_submit_button("Simpan kata sandi")
        if change:
            try:
                change_password(user["username"], old_password, new_password)
                st.success("Kata sandi diperbarui.")
            except (ModelError, AccessError) as exc:
                handle_error(exc)
    if st.button("Keluar", width="stretch"):
        st.session_state.pop("auth_username", None)
        st.rerun()

if "flash" in st.session_state:
    st.toast(st.session_state.pop("flash"), icon="✅")

result = None
calculation_error = None
try:
    result = calculate_project(project)
except ModelError as exc:
    calculation_error = str(exc)


def require_result():
    if result is None:
        st.error(calculation_error)
        st.stop()


def dm_page():
    dm = project["decision_makers"][0]
    dm_id = dm["id"]
    header("Penilaian saya", f"{dm['name']} ({dm_id}) · ubah Linguistic Term lalu simpan.")
    confirmed = bool(group_data(project)["confirmed"].get(dm_id))
    st.info("Alur Anda: pilih kode bahasa pada tabel → klik Simpan penilaian → lihat hasil DM Anda. Admin akan melihat hasil gabungan secara otomatis. Anda tidak dapat membuka atau mengubah penilaian DM lain.")
    st.caption(f"Status: {'Selesai dikonfirmasi' if confirmed else 'Belum dikonfirmasi'} · Bobot DM: {dm['weight']:.0%}")
    codes = [item["code"] for item in project["scale"]]
    frame = pd.DataFrame(dm["ratings"], columns=[c["id"] for c in project["criteria"]])
    frame.insert(0, "Alternatif", project["alternatives"])
    with st.form(f"ratings_{dm_id}_{revision}"):
        config = {c["id"]: st.column_config.SelectboxColumn(
            c["id"], options=codes, required=True, width="small",
            help=f"{c['name']} ({c['kind']})") for c in project["criteria"]}
        edited = st.data_editor(frame, hide_index=True, disabled=["Alternatif"],
                                column_config=config, width="stretch", height=550,
                                key=f"ratings_editor_{dm_id}_{revision}")
        st.caption("Klik dua kali pada sel untuk memilih kode. Setiap perubahan harus disimpan.")
        saved = st.form_submit_button("Simpan penilaian saya", type="primary")
    if saved:
        try:
            save_dm_ratings(user["username"], edited.iloc[:, 1:].values.tolist())
            st.session_state.flash = "Penilaian Anda disimpan. Hasil admin ikut diperbarui."
            st.rerun()
        except (ModelError, AccessError) as exc:
            handle_error(exc)
    if st.button("Konfirmasi penilaian selesai", disabled=confirmed):
        try:
            confirm_own_ratings(user["username"])
            st.session_state.flash = "Status penilaian Anda menjadi selesai."
            st.rerun()
        except AccessError as exc:
            handle_error(exc)
    with st.expander("Arti kode dan kriteria"):
        a, b = st.columns([1, 2])
        with a:
            table(pd.DataFrame(project["scale"]).rename(columns={"code": "Kode", "label": "Arti", "value": "Angka"}))
        with b:
            table(pd.DataFrame(project["criteria"]).rename(columns={"id": "Kode", "name": "Kriteria", "kind": "Jenis"}))
    if result is not None:
        own = result["dms"][dm_id]
        with st.expander("Lihat hasil perhitungan saya", expanded=False):
            own_frame = pd.DataFrame({"Alternatif": project["alternatives"],
                                      "Skor MARCOS": own["utility"],
                                      "Ranking": own["rank"]}).sort_values("Ranking", kind="stable")
            table(own_frame)
            st.caption("Bobot kriteria dihitung oleh MEREC dari penilaian Anda. Skor dan ranking di atas hanya untuk DM Anda.")
    else:
        st.error(calculation_error)
    with st.expander("Kirim catatan kepada admin"):
        with st.form("dm_note"):
            note = st.text_area("Catatan", placeholder="Contoh: Saya sudah memeriksa nilai C8")
            send = st.form_submit_button("Kirim")
        if send:
            try:
                post_message(user["username"], note)
                st.success("Catatan tersimpan untuk admin.")
            except (ModelError, AccessError) as exc:
                handle_error(exc)


def group_results_page():
    header("Hasil grup", "Admin melihat hasil seluruh DM dan ranking akhir dari penilaian terbaru.")
    st.info("Alur: admin menyiapkan data dan akun → tiap DM masuk dan mengisi Linguistic Term sendiri → skor MEREC–MARCOS dihitung per DM → skor digabung sesuai bobot DM → admin meninjau ranking akhir.")
    require_result()
    group = group_data(project)
    ranking = ranking_frame(project, result).sort_values("Ranking akhir", kind="stable")
    winner = ranking.iloc[0]
    dm_ids = [dm["id"] for dm in project["decision_makers"]]
    confirmed = sum(bool(group["confirmed"].get(dm_id)) for dm_id in dm_ids)
    a, b, c = st.columns(3)
    a.metric("Peringkat pertama", winner["Alternatif"])
    b.metric("Skor gabungan", f"{winner['f(K) gabungan']:.4f}")
    c.metric("DM selesai", f"{confirmed} / {len(dm_ids)}")
    total_weight = sum(dm["weight"] for dm in project["decision_makers"])
    if not np.isclose(total_weight, 1, atol=1e-10):
        st.warning(f"Total bobot DM {total_weight:.2%}. Seperti Excel, bobot dipakai apa adanya tanpa normalisasi otomatis.")
    rank_tab, comparison_tab, activity_tab = st.tabs(["Ranking akhir", "Perbandingan DM", "Status & catatan"])
    with rank_tab:
        shown = ranking.head(min(10, len(ranking)))
        fig = px.bar(shown, x="f(K) gabungan", y="Alternatif", orientation="h",
                     color_discrete_sequence=["#16846c"], text="f(K) gabungan")
        fig.update_traces(texttemplate="%{x:.4f}", textposition="outside",
                          hovertemplate="%{y}<br>Skor: %{x:.4f}<extra></extra>")
        fig.update_yaxes(autorange="reversed", title=None)
        fig.update_xaxes(title="Skor gabungan", range=[0, max(shown["f(K) gabungan"]) * 1.18])
        st.plotly_chart(chart_style(fig, max(300, len(shown) * 30 + 80)), width="stretch",
                        config={"displayModeBar": False})
        table(ranking)
        st.caption("Gabungan = jumlah (skor MARCOS tiap DM × bobot DM). Skor terbesar mendapat ranking 1. Data awal sesuai Rekap!H27:I40.")
        st.download_button("Unduh ranking CSV", csv_bytes(ranking_frame(project, result)),
                           "ranking_pemasok.csv", "text/csv")
    with comparison_tab:
        scores = ranking[[f"f(K) {dm_id}" for dm_id in dm_ids] + ["f(K) gabungan"]]
        fig = px.imshow(scores.to_numpy(), x=dm_ids + ["Gabungan"],
                        y=ranking["Alternatif"].tolist(), text_auto=".4f", aspect="auto",
                        color_continuous_scale=["#f0f7f4", "#9bcbb8", "#126650"])
        fig.update_traces(xgap=4, ygap=4, hovertemplate="%{y} · %{x}<br>Skor: %{z:.4f}<extra></extra>")
        fig = chart_style(fig, max(400, len(ranking) * 28 + 70))
        fig.update_layout(coloraxis_showscale=False)
        st.plotly_chart(fig, width="stretch", config={"displayModeBar": False})
        st.subheader("Bobot kriteria MEREC")
        table(weight_frame(project, result))
    with activity_tab:
        accounts = {item["dm_id"]: item for item in list_dm_accounts(user["username"])}
        table(pd.DataFrame([{"DM": dm["id"], "Nama": dm["name"],
                            "Akun": accounts.get(dm["id"], {}).get("username", "Belum ada"),
                            "Status": "Selesai" if group["confirmed"].get(dm["id"]) else "Belum dikonfirmasi"}
                            for dm in project["decision_makers"]]))
        st.subheader("Catatan DM")
        if group["discussion"]:
            for item in reversed(group["discussion"]):
                st.markdown(f"**{escape(item['author'])}** · {escape(item['time'])}: {escape(item['message'])}")
        else:
            st.caption("Belum ada catatan.")
        st.subheader("Riwayat keputusan")
        with st.form("record_decision"):
            note = st.text_input("Nama atau alasan keputusan", placeholder="Contoh: Hasil rapat final")
            recorded = st.form_submit_button("Catat hasil saat ini")
        if recorded:
            try:
                save_decision(user["username"], note)
                st.session_state.flash = "Ranking dan bobot disimpan dalam riwayat."
                st.rerun()
            except (ModelError, AccessError) as exc:
                handle_error(exc)
        for item in reversed(group["history"]):
            with st.expander(f"{item['time']} · {item['note']}"):
                st.caption("Bobot saat dicatat: " + ", ".join(f"{key} {value:.0%}" for key, value in item["weights"].items()))
                table(pd.DataFrame(item["ranking"]).rename(columns={
                    "alternative": "Alternatif", "score": "Skor gabungan", "rank": "Ranking"}))


STAGE_HELP = [
    "DM memilih kode linguistik untuk setiap pemasok dan kriteria.",
    "Kode diubah menjadi angka crisp memakai skala Excel.",
    "MEREC: Cost = nilai ÷ maksimum kolom; Benefit = minimum kolom ÷ nilai.",
    "MEREC: ambil ABS(LN(normalisasi)), jumlahkan per pemasok, lalu LN(1 + jumlah/n).",
    "MEREC: keluarkan kontribusi satu kriteria; penyebut tetap n.",
    "MEREC: hitung selisih absolut antara performa lengkap dan tanpa kriteria.",
    "MEREC: jumlahkan selisih per kriteria, lalu bagi dengan total untuk mendapat bobot.",
    "MARCOS: bentuk kondisi terburuk (AAI) dan terbaik (AI).",
    "MARCOS: Cost = nilai AI ÷ nilai; Benefit = nilai ÷ AI.",
    "MARCOS: kalikan hasil normalisasi dengan bobot MEREC DM yang sama, lalu jumlahkan.",
    "MARCOS: bandingkan jumlah dengan AAI/AI, hitung f(K), lalu urutkan dari terbesar.",
]


def calculations_page():
    header("Rincian perhitungan", "Admin dapat menelusuri satu DM dan satu tahap tanpa tabel yang berulang.")
    require_result()
    dm_id = st.selectbox("Lihat perhitungan DM", [dm["id"] for dm in project["decision_makers"]])
    stages = calculation_tables(project, result, dm_id)
    stage = st.selectbox("Tahap", range(len(stages)),
                         format_func=lambda i: stages[i][0])
    title, address, frame = stages[stage]
    st.subheader(title)
    st.info(STAGE_HELP[stage])
    st.caption(f"Padanan data awal Excel: {dm_id}!{address}" if address != "struktur dinamis"
               else "Struktur berubah; rumus sama, tetapi alamat sel Excel awal tidak berlaku.")
    table(frame, index=True, number_format="%.0f" if stage in {1, 7} else "%.4f")
    st.download_button("Unduh tabel tahap ini", csv_bytes(frame, index=True),
                       f"{dm_id}_tahap_{stage + 1}.csv", "text/csv")
    with st.expander("Rumus kunci Excel"):
        st.code("MEREC: E_j = Σ_i ABS(S'_ij - S_i); w_j = E_j / Σ_j E_j\n"
                "MARCOS: v_ij = normalisasi_ij × w_j; S_i = Σ_j v_ij\n"
                "Gabungan awal: Rekap!H27 = B27*$B$4 + D27*$B$5 + F27*$B$6\n"
                "Ranking awal: Rekap!I27 = RANK(H27,$H$27:$H$40,0)", language=None)


def manage_page():
    header("Kelola proyek", "Admin menyiapkan data, akun DM, bobot, dan berkas. DM hanya mengisi penilaiannya sendiri.")
    alternatives_tab, criteria_tab, users_tab, settings_tab, files_tab = st.tabs(
        ["1 · Alternatif", "2 · Kriteria", "3 · Akun DM", "4 · Bobot & skala", "5 · Berkas"])
    with alternatives_tab:
        table(pd.DataFrame({"Alternatif": project["alternatives"]}))
        with st.form("add_alternative"):
            name = st.text_input("Nama alternatif baru")
            add = st.form_submit_button("Tambah alternatif", type="primary")
        if add:
            try:
                commit_admin(add_alternative(project, name), "Alternatif ditambahkan.")
            except (ModelError, AccessError, ConflictError) as exc:
                handle_error(exc)
        st.caption("Alternatif baru mendapat kode A sebagai nilai awal pada semua DM. Tiap DM dapat mengubahnya setelah masuk.")
        old = st.selectbox("Pilih alternatif", project["alternatives"], key="alt_edit")
        with st.form(f"rename_alt_{old}"):
            renamed = st.text_input("Nama pengganti", value=old)
            rename = st.form_submit_button("Ubah nama")
        if rename:
            try:
                commit_admin(rename_alternative(project, old, renamed), "Nama alternatif diperbarui.")
            except (ModelError, AccessError, ConflictError) as exc:
                handle_error(exc)
        with st.form("delete_alt"):
            doomed = st.selectbox("Alternatif untuk dihapus", project["alternatives"])
            remove = st.form_submit_button("Hapus alternatif")
        if remove:
            try:
                commit_admin(delete_alternative(project, doomed), "Alternatif dihapus.")
            except (ModelError, AccessError, ConflictError) as exc:
                handle_error(exc)
    with criteria_tab:
        table(pd.DataFrame(project["criteria"]).rename(columns={"id": "Kode", "name": "Kriteria", "kind": "Jenis"}))
        with st.form("add_criterion"):
            name = st.text_input("Nama kriteria baru")
            kind = st.selectbox("Jenis", ["Benefit", "Cost"])
            add = st.form_submit_button("Tambah kriteria", type="primary")
        if add:
            try:
                commit_admin(add_criterion(project, name, kind), "Kriteria ditambahkan.")
            except (ModelError, AccessError, ConflictError) as exc:
                handle_error(exc)
        st.caption("Kriteria baru mendapat kode berikutnya dan nilai awal A. Jumlah kriteria n pada rumus MEREC ikut berubah.")
        criterion_id = st.selectbox("Pilih kriteria", [c["id"] for c in project["criteria"]], key="criterion_edit")
        selected = next(c for c in project["criteria"] if c["id"] == criterion_id)
        with st.form(f"edit_criterion_{criterion_id}"):
            renamed = st.text_input("Nama pengganti", value=selected["name"])
            kind = st.selectbox("Jenis pengganti", ["Benefit", "Cost"],
                                index=0 if selected["kind"] == "Benefit" else 1)
            edit = st.form_submit_button("Ubah kriteria")
        if edit:
            try:
                commit_admin(edit_criterion(project, criterion_id, renamed, kind), "Kriteria diperbarui.")
            except (ModelError, AccessError, ConflictError) as exc:
                handle_error(exc)
        with st.form("delete_criterion"):
            doomed = st.selectbox("Kriteria untuk dihapus", [c["id"] for c in project["criteria"]])
            remove = st.form_submit_button("Hapus kriteria")
        if remove:
            try:
                commit_admin(delete_criterion(project, doomed), "Kriteria dihapus.")
            except (ModelError, AccessError, ConflictError) as exc:
                handle_error(exc)
    with users_tab:
        accounts = {item["dm_id"]: item for item in list_dm_accounts(user["username"])}
        table(pd.DataFrame([{"DM": dm["id"], "Nama": dm["name"],
                            "Akun": accounts.get(dm["id"], {}).get("username", "Belum ada akun"),
                            "Bobot (%)": dm["weight"] * 100}
                            for dm in project["decision_makers"]]))
        missing = [dm["id"] for dm in project["decision_makers"] if dm["id"] not in accounts]
        if missing:
            st.subheader("Buat akun untuk DM yang ada")
            with st.form("create_account"):
                dm_id = st.selectbox("DM", missing)
                username = st.text_input("Nama pengguna DM")
                password = st.text_input("Kata sandi awal (minimal 10 karakter)", type="password")
                created = st.form_submit_button("Buat akun", type="primary")
            if created:
                try:
                    create_dm_account(user["username"], dm_id, username, password)
                    st.session_state.flash = f"Akun {dm_id} dibuat. Berikan nama pengguna dan kata sandinya kepada DM tersebut."
                    st.rerun()
                except (ModelError, AccessError) as exc:
                    handle_error(exc)
        st.subheader("Tambah DM baru beserta akunnya")
        with st.form("add_dm"):
            name = st.text_input("Nama DM baru")
            username = st.text_input("Nama pengguna baru")
            password = st.text_input("Kata sandi awal", type="password")
            added = st.form_submit_button("Tambah DM dan akun")
        if added:
            try:
                dm_id = add_dm_with_account(user["username"], name, username, password)
                st.session_state.flash = f"{dm_id} dan akunnya dibuat. Bobot awal 0%; atur pada tab Bobot & skala."
                st.rerun()
            except (ModelError, AccessError) as exc:
                handle_error(exc)
        dm_id = st.selectbox("DM yang dikelola", [dm["id"] for dm in project["decision_makers"]], key="manage_dm")
        selected = next(dm for dm in project["decision_makers"] if dm["id"] == dm_id)
        with st.form(f"rename_dm_{dm_id}"):
            name = st.text_input("Nama pengganti DM", value=selected["name"])
            renamed = st.form_submit_button("Ubah nama DM")
        if renamed:
            try:
                commit_admin(rename_dm(project, dm_id, name), "Nama DM diperbarui.")
            except (ModelError, AccessError, ConflictError) as exc:
                handle_error(exc)
        if dm_id in accounts:
            with st.form(f"reset_password_{dm_id}"):
                new_password = st.text_input("Kata sandi awal baru", type="password")
                reset = st.form_submit_button("Reset kata sandi DM")
            if reset:
                try:
                    admin_reset_password(user["username"], dm_id, new_password)
                    st.success("Kata sandi DM direset.")
                except (ModelError, AccessError) as exc:
                    handle_error(exc)
        with st.form("delete_dm"):
            doomed = st.selectbox("DM untuk dihapus", [dm["id"] for dm in project["decision_makers"]])
            remove = st.form_submit_button("Hapus DM beserta akunnya")
        if remove:
            try:
                commit_admin(delete_dm(project, doomed), "DM dan akunnya dihapus.")
            except (ModelError, AccessError, ConflictError) as exc:
                handle_error(exc)
    with settings_tab:
        st.subheader("Bobot pengambil keputusan")
        st.caption("Masukkan persen. Pada data awal Excel: DM1 40%, DM2 25%, DM3 35%. Bobot dipakai apa adanya.")
        with st.form("weights"):
            values = {}
            for dm in project["decision_makers"]:
                values[dm["id"]] = st.number_input(f"Bobot {dm['id']} (%)", min_value=0.0,
                                                     value=float(dm["weight"] * 100),
                                                     step=1.0, format="%.2f")
            saved = st.form_submit_button("Simpan bobot", type="primary")
        if saved:
            candidate = copy.deepcopy(project)
            for dm in candidate["decision_makers"]:
                dm["weight"] = values[dm["id"]] / 100
            try:
                commit_admin(candidate, "Bobot DM disimpan; ranking gabungan dihitung ulang.")
            except (ModelError, AccessError, ConflictError) as exc:
                handle_error(exc)
        st.subheader("Skala linguistik")
        st.caption("Nilai crisp harus positif agar LN dan pembagian terdefinisi.")
        with st.form(f"scale_{revision}"):
            scale = st.data_editor(pd.DataFrame(project["scale"]).rename(columns={
                "code": "Kode", "label": "Arti", "value": "Nilai"}),
                hide_index=True, disabled=["Kode", "Arti"], width="stretch",
                column_config={"Nilai": st.column_config.NumberColumn(required=True)},
                key=f"scale_editor_{revision}")
            saved = st.form_submit_button("Simpan skala")
        if saved:
            candidate = copy.deepcopy(project)
            for i, value in enumerate(scale["Nilai"]):
                candidate["scale"][i]["value"] = value
            group_data(candidate)["confirmed"] = {}
            try:
                commit_admin(candidate, "Skala disimpan; seluruh hasil dihitung ulang.")
            except (ModelError, AccessError, ConflictError) as exc:
                handle_error(exc)
    with files_tab:
        st.caption("XLSX hanya untuk struktur awal 14 × 12 × 3. JSON menyimpan struktur dinamis, penilaian, status, catatan, dan riwayat.")
        st.download_button("Unduh proyek JSON", scenario_json(project),
                           "skenario_dss.json", "application/json")
        if result is not None:
            st.download_button("Unduh semua hasil ZIP", export_bundle(project, result),
                               "hasil_merec_marcos.zip", "application/zip")
        st.download_button("Unduh Excel acuan", SOURCE.read_bytes(), SOURCE.name,
                           "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
        uploaded = st.file_uploader("Impor XLSX atau JSON", type=["xlsx", "json"])
        if uploaded is not None and st.button("Impor data"):
            try:
                candidate = import_workbook(uploaded.getvalue()) if uploaded.name.lower().endswith(".xlsx") else import_json(uploaded.getvalue())
                commit_admin(candidate, "Data proyek diimpor.")
            except (ModelError, AccessError, ConflictError) as exc:
                handle_error(exc)
        with st.expander("Pulihkan input Excel awal"):
            st.caption("Mengganti input bersama. Unduh JSON terlebih dahulu jika ingin menyimpan keadaan sekarang.")
            if st.button("Pulihkan data awal"):
                try:
                    commit_admin(import_workbook(), "Data awal Excel dipulihkan.")
                except (ModelError, AccessError, ConflictError) as exc:
                    handle_error(exc)
        st.caption("Jurnal menyediakan kasus pemasok; metode prototipe MEREC–MARCOS mengikuti workbook. Jurnal: https://doi.org/10.3390/su151813973")


if is_admin:
    {"Hasil grup": group_results_page,
     "Kelola proyek": manage_page,
     "Rincian perhitungan": calculations_page}[page]()
else:
    dm_page()
st.html('<div class="footer-note">DSS Pemasok · MEREC–MARCOS &nbsp; / &nbsp; Rumus data awal mengikuti DSS PROJECT.xlsx</div>')
