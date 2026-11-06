"""Aplikasi manajemen jastip makan siang — Streamlit, ramah mobile."""

import os
import sqlite3
from contextlib import closing
from datetime import date, timedelta

import pandas as pd
import streamlit as st

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "jastip.db")

DEFAULT_MENUS = [
    ("Nasi Ayam Geprek", 15000),
    ("Nasi Padang", 18000),
    ("Bakso", 15000),
    ("Mie Ayam", 15000),
    ("Nasi Goreng", 15000),
    ("Soto Ayam", 15000),
]

MOBILE_CSS = """
<style>
/* Sembunyikan chrome Streamlit */
[data-testid="stHeader"], [data-testid="stToolbar"], [data-testid="stDecoration"],
[data-testid="stStatusWidget"], #MainMenu, footer {display: none !important;}

/* Konten pas di layar HP */
[data-testid="stMainBlockContainer"], [data-testid="block-container"] {
    max-width: 640px !important;
    padding: 1rem 0.8rem 6rem 0.8rem !important;
}

/* Tab besar dan mudah disentuh */
.stTabs [data-baseweb="tab-list"] {gap: 4px;}
.stTabs [data-baseweb="tab"] {flex: 1 1 0; min-height: 3rem;}
.stTabs [data-baseweb="tab-highlight"] {border-radius: 12px;}
.stTabs [data-baseweb="tab-border"] {display: none;}

/* Tombol dan input ramah jempol */
.stButton > button {
    width: 100%; min-height: 48px; border-radius: 12px;
    font-size: 0.95rem; font-weight: 600;
}
input, select, textarea {font-size: 16px !important;}

[data-testid="stVerticalBlockBorderWrapper"] {border-radius: 14px;}
[data-testid="stExpander"] {border-radius: 12px;}

/* Kolom menumpuk di layar kecil */
@media (max-width: 640px) {
    [data-testid="stColumn"] {width: 100% !important; flex: 1 1 100% !important; min-width: 100% !important;}
}
</style>
"""


def get_conn():
    conn = sqlite3.connect(DB_PATH, timeout=10)
    conn.row_factory = sqlite3.Row
    return conn


def q(sql, params=(), *, fetch=False):
    with closing(get_conn()) as conn, conn:
        cur = conn.execute(sql, params)
        # dict agar aman dipakai sebagai nilai widget Streamlit (Row tidak bisa di-pickle)
        return [dict(r) for r in cur.fetchall()] if fetch else None


def init_db():
    with closing(get_conn()) as conn, conn:
        conn.execute(
            """CREATE TABLE IF NOT EXISTS orders (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                tanggal TEXT NOT NULL,
                pemesan TEXT NOT NULL,
                penjastip TEXT NOT NULL DEFAULT '',
                menu TEXT NOT NULL,
                harga INTEGER NOT NULL,
                qty INTEGER NOT NULL DEFAULT 1,
                status_bayar TEXT NOT NULL DEFAULT 'Belum',
                catatan TEXT NOT NULL DEFAULT '',
                created_at TEXT NOT NULL DEFAULT (datetime('now', 'localtime'))
            )"""
        )
        conn.execute(
            """CREATE TABLE IF NOT EXISTS menus (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                nama TEXT NOT NULL UNIQUE,
                harga INTEGER NOT NULL
            )"""
        )
        if conn.execute("SELECT COUNT(*) FROM menus").fetchone()[0] == 0:
            conn.executemany("INSERT INTO menus (nama, harga) VALUES (?, ?)", DEFAULT_MENUS)


def rupiah(n) -> str:
    return f"Rp {int(n):,}".replace(",", ".")


def periode_start(periode: str) -> str:
    today = date.today()
    mulai = {
        "Hari ini": today,
        "7 hari": today - timedelta(days=6),
        "30 hari": today - timedelta(days=29),
        "Semua": date(2000, 1, 1),
    }[periode]
    return mulai.isoformat()


def fetch_orders(periode: str, status: str = "Semua"):
    sql = "SELECT * FROM orders WHERE tanggal >= ?"
    params = [periode_start(periode)]
    if status != "Semua":
        sql += " AND status_bayar = ?"
        params.append(status)
    sql += " ORDER BY tanggal DESC, id DESC"
    return q(sql, params, fetch=True)


def ringkas(orders):
    total = sum(o["harga"] * o["qty"] for o in orders)
    belum = sum(o["harga"] * o["qty"] for o in orders if o["status_bayar"] == "Belum")
    return len(orders), total, belum


# ---------------------------------------------------------------- tab: Baru

def tab_pesanan_baru():
    st.subheader("Pesanan baru")
    menus = q("SELECT * FROM menus ORDER BY nama", fetch=True)
    names = [r["pemesan"] for r in q("SELECT DISTINCT pemesan FROM orders ORDER BY pemesan", fetch=True)]
    couriers = [
        r["penjastip"]
        for r in q("SELECT DISTINCT penjastip FROM orders WHERE penjastip != '' ORDER BY penjastip", fetch=True)
    ]

    sumber = st.radio(
        "Sumber menu",
        ("Dari menu favorit", "Ketik manual"),
        horizontal=True,
        label_visibility="collapsed",
    )

    if sumber == "Dari menu favorit":
        if menus:
            pilih = st.selectbox(
                "Menu", menus, format_func=lambda m: f"{m['nama']} — {rupiah(m['harga'])}"
            )
            menu_nama, harga = pilih["nama"], int(pilih["harga"])
        else:
            st.info("Belum ada menu favorit. Tambahkan dulu di tab Menu.")
            menu_nama = st.text_input("Nama menu")
            harga = st.number_input("Harga (Rp)", min_value=0, step=500, value=0)
    else:
        menu_nama = st.text_input("Nama menu")
        harga = st.number_input("Harga (Rp)", min_value=0, step=500, value=15000)

    qty = st.number_input("Jumlah porsi", min_value=1, step=1, value=1)
    st.markdown(f"Total: **{rupiah(harga * qty)}**")

    pilihan_pemesan = st.selectbox("Pemesan", names + ["Tambah nama baru..."], index=len(names))
    if pilihan_pemesan == "Tambah nama baru...":
        pemesan = st.text_input("Nama pemesan")
    else:
        pemesan = pilihan_pemesan

    pilihan_kurir = st.selectbox("Penjastip (opsional)", ["—"] + couriers + ["Tambah nama baru..."])
    if pilihan_kurir == "Tambah nama baru...":
        penjastip = st.text_input("Nama penjastip")
    elif pilihan_kurir == "—":
        penjastip = ""
    else:
        penjastip = pilihan_kurir

    tanggal = st.date_input("Tanggal", value=date.today(), format="DD/MM/YYYY")
    catatan = st.text_area("Catatan (opsional)", placeholder="cth: pedas, tanpa timun")

    siap = bool(menu_nama.strip()) and bool(pemesan and pemesan.strip()) and harga > 0
    if st.button("Simpan pesanan", type="primary", disabled=not siap):
        q(
            "INSERT INTO orders (tanggal, pemesan, penjastip, menu, harga, qty, catatan) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (tanggal.isoformat(), pemesan.strip(), penjastip.strip(), menu_nama.strip(), harga, qty, catatan.strip()),
        )
        st.success(f"Tersimpan: {pemesan.strip()} — {menu_nama.strip()} ×{qty} ({rupiah(harga * qty)})")


# ------------------------------------------------------------- tab: Daftar

def aksi_bayar(order_id: int, status: str):
    q("UPDATE orders SET status_bayar = ? WHERE id = ?", (status, order_id))
    st.rerun()


def aksi_hapus(order_id: int):
    q("DELETE FROM orders WHERE id = ?", (order_id,))
    st.rerun()


def tab_daftar():
    st.subheader("Daftar pesanan")
    c1, c2 = st.columns(2)
    periode = c1.selectbox("Periode", ["Hari ini", "7 hari", "Semua"])
    status = c2.selectbox("Status", ["Semua", "Belum", "Lunas"])

    orders = fetch_orders(periode, status)
    if not orders:
        st.info("Belum ada pesanan pada filter ini.")
        return

    n, total, belum = ringkas(orders)
    st.caption(f"{n} pesanan · {rupiah(total)} · belum lunas {rupiah(belum)}")

    if belum > 0:
        if st.button(f"Tandai semua lunas ({sum(1 for o in orders if o['status_bayar'] == 'Belum')} pesanan)"):
            q(
                "UPDATE orders SET status_bayar = 'Lunas' WHERE tanggal >= ? AND status_bayar = 'Belum'",
                (periode_start(periode),),
            )
            st.rerun()

    for o in orders:
        with st.container(border=True):
            badge = "LUNAS" if o["status_bayar"] == "Lunas" else "BELUM BAYAR"
            st.markdown(f"**{o['pemesan']}** · {o['menu']} ×{o['qty']}")
            st.caption(
                f"{badge} · {rupiah(o['harga'] * o['qty'])} · "
                f"penjastip: {o['penjastip'] or '—'} · {o['tanggal']}"
            )
            if o["catatan"]:
                st.caption(f"Catatan: {o['catatan']}")

            b1, b2 = st.columns(2)
            konfirm_key = f"konfirm_hapus_{o['id']}"
            label_hapus = "Yakin? Hapus" if st.session_state.get(konfirm_key) else "Hapus"
            if b1.button("Tandai lunas" if o["status_bayar"] == "Belum" else "Batalkan lunas", key=f"bayar_{o['id']}"):
                aksi_bayar(o["id"], "Lunas" if o["status_bayar"] == "Belum" else "Belum")
            if b2.button(label_hapus, key=f"hapus_{o['id']}", type="primary" if st.session_state.get(konfirm_key) else "secondary"):
                if st.session_state.get(konfirm_key):
                    aksi_hapus(o["id"])
                else:
                    st.session_state[konfirm_key] = True
                    st.rerun()
            if st.session_state.get(konfirm_key):
                st.caption("Klik sekali lagi untuk hapus permanen.")


# -------------------------------------------------------------- tab: Rekap

def tab_rekap():
    st.subheader("Rekap & tagihan")
    periode = st.selectbox("Periode", ["Hari ini", "7 hari", "30 hari", "Semua"])
    rows = fetch_orders(periode)
    if not rows:
        st.info("Belum ada data pada periode ini.")
        return

    df = pd.DataFrame([dict(o) for o in rows])
    df["total"] = df["harga"] * df["qty"]
    df["belum"] = df["total"].where(df["status_bayar"] == "Belum", 0)

    n, total, belum = ringkas(rows)
    st.markdown(
        f"**{n}** pesanan · **{rupiah(total)}**\n\n"
        f"Lunas **{rupiah(total - belum)}** · Belum lunas **{rupiah(belum)}**"
    )

    rekap_pemesan = (
        df.groupby("pemesan", as_index=False)
        .agg(pesanan=("id", "count"), total=("total", "sum"), belum_lunas=("belum", "sum"))
        .sort_values("total", ascending=False)
    )
    st.bar_chart(rekap_pemesan.set_index("pemesan")["total"], height=220)

    tampil = rekap_pemesan.copy()
    tampil["total"] = tampil["total"].map(rupiah)
    tampil["belum_lunas"] = tampil["belum_lunas"].map(rupiah)
    st.dataframe(tampil, width="stretch", hide_index=True)

    df_kurir = df.copy()
    df_kurir["penjastip"] = df_kurir["penjastip"].replace("", "—")
    rekap_kurir = (
        df_kurir.groupby("penjastip", as_index=False)
        .agg(pesanan=("id", "count"), total=("total", "sum"))
        .sort_values("total", ascending=False)
    )
    rekap_kurir["total"] = rekap_kurir["total"].map(rupiah)
    st.caption("Rekap per penjastip")
    st.dataframe(rekap_kurir, width="stretch", hide_index=True)

    csv = df.drop(columns=["belum"]).to_csv(index=False).encode("utf-8")
    st.download_button(
        "Unduh CSV",
        csv,
        file_name=f"jastip_{date.today().isoformat()}.csv",
        mime="text/csv",
        width="stretch",
    )


# --------------------------------------------------------------- tab: Menu

def tab_menu():
    st.subheader("Menu favorit")
    st.caption("Simpan menu langganan agar pesanan baru cukup dua ketukan.")

    with st.form("form_menu_baru", border=True):
        nama = st.text_input("Nama menu")
        harga = st.number_input("Harga (Rp)", min_value=0, step=500, value=15000)
        tambah = st.form_submit_button("Tambah menu", type="primary", width="stretch")
    if tambah and nama.strip() and harga > 0:
        try:
            q("INSERT INTO menus (nama, harga) VALUES (?, ?)", (nama.strip(), int(harga)))
            st.rerun()
        except sqlite3.IntegrityError:
            st.error("Menu dengan nama itu sudah ada.")

    menus = q("SELECT * FROM menus ORDER BY nama", fetch=True)
    for m in menus:
        with st.expander(f"{m['nama']} — {rupiah(m['harga'])}"):
            harga_baru = st.number_input(
                "Harga (Rp)", min_value=0, step=500, value=int(m["harga"]), key=f"menu_harga_{m['id']}"
            )
            c1, c2 = st.columns(2)
            konfirm_key = f"konfirm_menu_{m['id']}"
            if c1.button("Simpan harga", key=f"menu_simpan_{m['id']}"):
                q("UPDATE menus SET harga = ? WHERE id = ?", (int(harga_baru), m["id"]))
                st.rerun()
            if c2.button("Yakin? Hapus" if st.session_state.get(konfirm_key) else "Hapus", key=f"menu_hapus_{m['id']}"):
                if st.session_state.get(konfirm_key):
                    q("DELETE FROM menus WHERE id = ?", (m["id"],))
                    st.session_state.pop(konfirm_key, None)
                else:
                    st.session_state[konfirm_key] = True
                st.rerun()


# ------------------------------------------------------------------- main

st.set_page_config(page_title="Jastip Siang", page_icon=":bento:", layout="centered")
init_db()
st.markdown(MOBILE_CSS, unsafe_allow_html=True)

st.markdown("## Jastip Siang")
st.caption("Catat titipan makan siang tanpa ribet.")

t_baru, t_daftar, t_rekap, t_menu = st.tabs(["+ Baru", "Daftar", "Rekap", "Menu"])
with t_baru:
    tab_pesanan_baru()
with t_daftar:
    tab_daftar()
with t_rekap:
    tab_rekap()
with t_menu:
    tab_menu()

st.caption("Data tersimpan lokal di `jastip.db`.")
