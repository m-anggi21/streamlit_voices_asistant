# pages/4_Admin_Dashboard.py
import os
import streamlit as st
from datetime import datetime
from streamlit_autorefresh import st_autorefresh

from modules.logout import do_logout
from modules.admin_api import (
    get_all_orders, get_order_items,
    update_order_status, delete_order
)

# ✅ Streamlit command pertama
st.set_page_config(page_title="Admin Panel", page_icon="📦", layout="wide")


# ============================
# LOAD CSS
# ============================
def load_css(path="assets/styles.css"):
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    css_path = os.path.join(base_dir, path)
    if os.path.exists(css_path):
        with open(css_path, "r", encoding="utf-8") as f:
            st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)

load_css()
st.markdown('<div class="page-admin-dashboard">', unsafe_allow_html=True)
st.markdown('</div>', unsafe_allow_html=True)


# ============================
# PROTEKSI LOGIN + ROLE ADMIN
# ============================
auth = st.session_state.get("auth") or {}
if not auth.get("is_logged_in"):
    # ✅ langsung lempar ke halaman login (tanpa pesan error)
    st.switch_page("pages/1_Login.py")
    st.stop()

user = auth.get("user") or {}
if user.get("role") != "admin":
    st.error("Halaman ini hanya untuk admin.")
    st.stop()


# ============================
# HEADER + LOGOUT
# ============================
col_title, col_logout = st.columns([6, 1])
with col_title:
    st.title("📦 Dashboard Admin Depo 78")
with col_logout:
    if st.button("🚪 Logout"):
        do_logout("app.py")
        st.switch_page("pages/1_Login.py")
        st.stop()

st.divider()

# ============================
# REALTIME AUTO-REFRESH
# ============================
st_autorefresh(interval=3000, key="admin_autorefresh")


# ============================
# HELPER: PARSE DATETIME
# ============================
def _parse_dt(val):
    if not val:
        return datetime.min
    if isinstance(val, datetime):
        return val
    s = str(val).strip()

    for fmt in (
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%d %H:%M",
        "%Y-%m-%dT%H:%M:%S",
        "%Y-%m-%dT%H:%M:%S.%f",
        "%d-%m-%Y %H:%M:%S",
        "%d-%m-%Y %H:%M",
    ):
        try:
            return datetime.strptime(s, fmt)
        except Exception:
            pass

    # fallback buang timezone sederhana
    try:
        if "+" in s:
            return _parse_dt(s.split("+", 1)[0].strip())
    except Exception:
        pass

    return datetime.min


def _order_number(order: dict):
    na = order.get("nomor_antrian")
    try:
        if na is not None and str(na).strip() != "":
            return int(str(na).strip())
    except Exception:
        pass
    try:
        return int(order.get("orders_id") or 0)
    except Exception:
        return 0


def _customer_name(order: dict):
    return (order.get("nama_lengkap") or order.get("nama") or "").strip().lower()


def format_jam(created_at):
    dt = _parse_dt(created_at)
    if dt == datetime.min:
        return "-"
    return dt.strftime("%H:%M")


# ============================
# AMBIL DATA ORDERS
# ============================
orders_all = get_all_orders() or []


# ============================
# DETEKSI ORDER BARU (BADGE AUTO-HIDE 5 DETIK)
# - pertama kali buka: anggap semua sudah terlihat => tidak tampil badge
# ============================
current_ids = set([o.get("orders_id") for o in orders_all if o.get("orders_id")])

if "admin_seen_orders" not in st.session_state:
    st.session_state.admin_seen_orders = current_ids
    new_ids = set()
else:
    new_ids = current_ids - st.session_state.admin_seen_orders

if new_ids:
    st.markdown(
        f"""
        <div class="depo-badge-top" id="depo-admin-badge">
          <span class="depo-badge-dot"></span>
          <span>Order baru masuk: {len(new_ids)}</span>
        </div>

        <script>
        (function() {{
          const badge = window.parent.document.getElementById("depo-admin-badge");
          if (!badge) return;
          setTimeout(() => {{
            badge.classList.add("hide");
          }}, 5000);
        }})();
        </script>
        """,
        unsafe_allow_html=True
    )

st.session_state.admin_seen_orders = current_ids


# ============================
# FILTER TANGGAL (KALENDER)
# default: hari ini, bisa pilih tanggal sebelumnya
# ============================

today = datetime.now().date()
f1, f2, f3 = st.columns([2.2, 2.0, 7])

with f1:
    filter_date = st.date_input(
        "Tanggal:",
        value=st.session_state.get("admin_filter_date", today),
        key="admin_filter_date",
    )

with f2:
    show_all_dates = st.checkbox("Tampilkan semua", value=False, key="admin_show_all_dates")

with f3:
    if show_all_dates:
        st.caption("Mode: Semua tanggal (tanpa filter).")
    else:
        st.caption(f"Mode: Menampilkan pesanan tanggal {filter_date.strftime('%d/%m/%Y')}.")


# terapkan filter tanggal
if show_all_dates:
    orders = orders_all
else:
    orders = []
    for o in orders_all:
        dt = _parse_dt(o.get("created_at"))
        if dt != datetime.min and dt.date() == filter_date:
            orders.append(o)


# ============================
# UI SORT CONTROL
# ============================
c1, c2, c3 = st.columns([2.2, 1.6, 6])

with c1:
    sort_by = st.selectbox(
        "Urutkan berdasarkan:",
        ["Waktu Pemesanan", "Nama Customer", "Nomor Order"],
        key="admin_sort_by"
    )

with c2:
    sort_dir = st.selectbox(
        "Arah:",
        ["Terbaru → Terlama", "Terlama → Terbaru"] if sort_by == "Waktu Pemesanan"
        else ["A → Z", "Z → A"] if sort_by == "Nama Customer"
        else ["Kecil → Besar", "Besar → Kecil"],
        key="admin_sort_dir"
    )

if sort_by == "Waktu Pemesanan":
    reverse = (sort_dir == "Terbaru → Terlama")
    orders = sorted(orders, key=lambda o: _parse_dt(o.get("created_at")), reverse=reverse)
elif sort_by == "Nama Customer":
    reverse = (sort_dir == "Z → A")
    orders = sorted(orders, key=_customer_name, reverse=reverse)
else:
    reverse = (sort_dir == "Besar → Kecil")
    orders = sorted(orders, key=_order_number, reverse=reverse)

with c3:
    st.caption(f"Menampilkan {len(orders)} pesanan (sudah diurutkan).")


# ============================
# RENDER ORDERS
# ============================
STATUS_LIST = ["menunggu", "diproses", "dikirim", "selesai"]

STATUS_EMOJI = {
    "menunggu": "⏳",
    "diproses": "⚙️",
    "dikirim": "🚚",
    "selesai": "✅",
}

for order in orders:
    order_id = order.get("orders_id")

    nama = order.get("nama_lengkap") or order.get("nama") or "-"
    nomor_antrian = order.get("nomor_antrian") or "-"
    order_label = f"Dep78-{nomor_antrian}" if nomor_antrian != "-" else f"#{order_id}"

    status_now = (order.get("status") or "menunggu").strip().lower()
    if status_now not in STATUS_LIST:
        status_now = "menunggu"

    status_badge = f"{STATUS_EMOJI.get(status_now,'')} {status_now}"
    jam_order = format_jam(order.get("created_at"))

    # ✅ STATUS tampil di judul expander (dekat panah dropdown)
    exp_title = f"🧾 Order {order_label} — {nama} • {jam_order}  |  {status_badge}"

    with st.expander(exp_title, expanded=False):
        st.write(
            f"**Alamat:** Cluster {order.get('cluster','-')}, "
            f"Blok {order.get('blok','-')}, No {order.get('no_rumah','-')}"
        )
        st.write(f"**Nomor Antrian:** {nomor_antrian}")
        st.write(f"**Status:** {status_now}")
        st.write(f"**Waktu:** {order.get('created_at','-')}")

        metode_bayar = order.get("metode_pembayaran") or "-"
        st.write(f"**Metode Pembayaran:** {metode_bayar}")

        st.markdown("### 🧾 Item Pesanan", unsafe_allow_html=True)

        items = get_order_items(order_id) or []
        if not items:
            st.caption("Tidak ada item.")
        else:
            for it in items:
                st.markdown(
                    f"""
                    <div class="admin-item-row">
                        <div class="admin-item-name">
                            • {int(it.get('qty', 0))}× {it.get('nama_item','-')}
                        </div>
                        <div class="admin-item-price">
                            Rp {int(it.get('total_harga', 0)):,}
                        </div>
                    </div>
                    """,
                    unsafe_allow_html=True
                )

        st.markdown(
            f"""
            <div class="admin-total">
                <div>Total</div>
                <div>Rp {int(order.get('total_harga', 0)):,}</div>
            </div>
            """,
            unsafe_allow_html=True
        )

        st.divider()

        new_status = st.selectbox(
            "Ubah Status:",
            STATUS_LIST,
            index=STATUS_LIST.index(status_now),
            key=f"status-{order_id}"
        )

        col1, col2 = st.columns(2)
        with col1:
            if st.button("Update Status", key=f"u-{order_id}", use_container_width=True):
                update_order_status(order_id, new_status)
                st.success("Status berhasil diperbarui.")
                st.rerun()

        with col2:
            if st.button("❌ Hapus Pesanan", key=f"d-{order_id}", use_container_width=True):
                ok, err = delete_order(order_id)
                if ok:
                    st.warning("Pesanan dihapus.")
                    st.rerun()
                else:
                    st.error(f"Gagal hapus pesanan: {err}")
