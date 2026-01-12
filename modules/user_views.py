# modules/user_views.py
import streamlit as st
from typing import List, Dict, Any, Optional


# =========================
# DB HELPERS
# =========================
def fetch_user_orders(
    get_db_func,
    users_id: int,
    only_active: bool = False,
    active_exclude_statuses: Optional[List[str]] = None,
) -> List[Dict[str, Any]]:
    """
    Ambil order milik user.
    - only_active=True  -> order yang belum selesai/batal
    - only_active=False -> semua order

    get_db_func: function yang mengembalikan koneksi DB (mis: get_db)
    """
    if active_exclude_statuses is None:
        # sesuaikan dengan status yang kamu pakai di DB
        active_exclude_statuses = ["selesai", "dibatalkan"]

    db = get_db_func()
    cur = db.cursor(dictionary=True)

    if only_active:
        placeholders = ",".join(["%s"] * len(active_exclude_statuses))
        sql = f"""
            SELECT orders_id, nomor_antrian, status, created_at, total_harga, metode_pembayaran
            FROM orders
            WHERE users_id=%s AND status NOT IN ({placeholders})
            ORDER BY created_at DESC
        """
        cur.execute(sql, (users_id, *active_exclude_statuses))
    else:
        cur.execute(
            """
            SELECT orders_id, nomor_antrian, status, created_at, total_harga, metode_pembayaran
            FROM orders
            WHERE users_id=%s
            ORDER BY created_at DESC
            """,
            (users_id,),
        )

    rows = cur.fetchall()
    cur.close()
    db.close()
    return rows


def fetch_order_items(get_order_items_func, orders_id: int) -> List[Dict[str, Any]]:
    """
    get_order_items_func: function yang menerima orders_id dan mengembalikan list item
    (mis: modules.admin_api.get_order_items)
    """
    try:
        return get_order_items_func(orders_id) or []
    except Exception:
        return []

def render_top_nav(default_nav="Order", key_prefix="user_order"):
    nav_key = f"{key_prefix}_nav"

    options = ["Beranda", "Order", "History"]
    icons = {"Beranda": "🏠", "Order": "🛒", "History": "🧾"}
    # pastikan value valid
    if nav_key not in st.session_state:
        st.session_state[nav_key] = default_nav
    if st.session_state[nav_key] not in options:
        st.session_state[nav_key] = default_nav

    def _fmt(x: str) -> str:
        return f"{icons.get(x, '•')} {x}"

    st.markdown('<div class="top-nav-wrap">', unsafe_allow_html=True)
    picked = st.radio(
        "Navigasi",
        options=options,
        key=nav_key,
        horizontal=True,
        label_visibility="collapsed",
        format_func=_fmt,
    )
    st.markdown("</div>", unsafe_allow_html=True)
    st.write("---")
    return picked

# =========================
# UI: BERANDA
# =========================
def render_beranda(
    user: Dict[str, Any],
    get_db_func,
    get_order_items_func,
    active_exclude_statuses: Optional[List[str]] = None,
):
    st.subheader("🏠 Beranda")
    st.caption("Ringkasan pesanan aktif (belum selesai).")

    active_orders = fetch_user_orders(
        get_db_func=get_db_func,
        users_id=int(user["users_id"]),
        only_active=True,
        active_exclude_statuses=active_exclude_statuses,
    )

    if not active_orders:
        st.info("Tidak ada pesanan aktif saat ini.")
        return

    st.markdown('<div class="beranda-active-cards">', unsafe_allow_html=True)

    for o in active_orders:
        orders_id = int(o.get("orders_id") or 0)

        created = o.get("created_at")
        try:
            created_str = created.strftime("%d/%m/%Y %H:%M")
        except Exception:
            created_str = str(created) if created else "-"

        nomor = o.get("nomor_antrian") or "-"
        status = (o.get("status") or "-").strip()
        total = int(o.get("total_harga") or 0)

        # badge status (simple mapping)
        st_lower = status.lower()
        if "menunggu" in st_lower:
            badge_cls = "badge-wait"
        elif "proses" in st_lower or "diproses" in st_lower:
            badge_cls = "badge-proc"
        elif "antar" in st_lower or "dikirim" in st_lower:
            badge_cls = "badge-ship"
        elif "selesai" in st_lower:
            badge_cls = "badge-done"
        elif "batal" in st_lower:
            badge_cls = "badge-cancel"
        else:
            badge_cls = "badge-default"

        # ===== CARD RINGKAS =====
        st.markdown(
            f"""
            <div class="order-mini-card">
              <div class="omc-top">
                <div class="omc-queue">🧾 <span>{nomor}</span></div>
                <div class="omc-badge {badge_cls}">{status}</div>
              </div>

              <div class="omc-mid">
                <div class="omc-date">🗓️ {created_str}</div>
                <div class="omc-total">Rp {total:,}</div>
              </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        # ===== DROPDOWN DETAIL (EXPANDER) =====
        with st.expander("▾ Lihat detail", expanded=False):
            st.markdown(
                f"""
                <div class="order-mini-detail">
                  <div><b>Nomor Antrian:</b> <code>{nomor}</code></div>
                  <div><b>Tanggal:</b> {created_str}</div>
                  <div><b>Status:</b> <b>{status}</b></div>
                  <div><b>Total:</b> Rp {total:,}</div>
                </div>
                """,
                unsafe_allow_html=True,
            )

            items = fetch_order_items(get_order_items_func, orders_id)
            st.markdown("<div class='order-mini-items-title'><b>📦 Item</b></div>", unsafe_allow_html=True)

            if not items:
                st.write("Tidak ada item.")
            else:
                for it in items:
                    qty = int(it.get("qty") or 0)
                    nama = it.get("nama_item") or "-"
                    sub = int(it.get("total_harga") or 0)
                    st.markdown(
                        f"<div class='order-mini-item-row'><span>{qty}× {nama}</span><span>Rp {sub:,}</span></div>",
                        unsafe_allow_html=True,
                    )

        st.markdown("<div class='order-mini-gap'></div>", unsafe_allow_html=True)

    st.markdown("</div>", unsafe_allow_html=True)

# =========================
# UI: HISTORY
# =========================
def render_history(
    user: Dict[str, Any],
    get_db_func,
    get_order_items_func,
):
    st.subheader("🧾 History Pesanan")
    st.caption("Seluruh riwayat order user (selesai & dibatalkan termasuk bila ada).")

    all_orders = fetch_user_orders(
        get_db_func=get_db_func,
        users_id=int(user["users_id"]),
        only_active=False,
    )

    if not all_orders:
        st.info("Belum ada riwayat pesanan.")
        return

    for o in all_orders:
        created = o.get("created_at")
        try:
            created_str = created.strftime("%d/%m/%Y %H:%M")
        except Exception:
            created_str = str(created) if created else "-"

        st.markdown(
            f"""
**Nomor Antrian:** `{o.get('nomor_antrian','-')}`  
**Tanggal Pesanan:** {created_str}  
**Status:** **{o.get('status','-')}**  
**Metode:** `{o.get('metode_pembayaran') or '-'}`  
**Total:** Rp {int(o.get('total_harga') or 0):,}
""".strip()
        )

        with st.expander("📦 Detail item"):
            items = fetch_order_items(get_order_items_func, int(o["orders_id"]))
            if not items:
                st.write("Tidak ada item.")
            else:
                for it in items:
                    st.write(
                        f"• {it.get('qty',0)}× {it.get('nama_item','-')} = Rp {int(it.get('total_harga') or 0):,}"
                    )

        st.write("---")
        
def render_user_header_bar(user: dict, do_logout_func, key_prefix: str = "user_header"):
    st.write("---")
    u = user or {}

    nama = u.get("nama") or u.get("username") or "User"
    alamat = f"{u.get('cluster','-')} , {u.get('blok','-')} / {u.get('no_rumah','-')}"

    st.markdown('<div class="user-header-box">', unsafe_allow_html=True)

    colL, colR = st.columns([8, 3])

    with colL:
        st.markdown(
            f"""
            <div class="user-header-left">
                <div class="user-name">👤 {nama}</div>
                <div class="user-address">📍 {alamat}</div>
            </div>
            """,
            unsafe_allow_html=True
        )

    with colR:
        st.button(
            "🚪 Logout",
            key=f"{key_prefix}_logout",
            use_container_width=True,
            on_click=lambda: do_logout_func("app.py"),
        )

    st.markdown("</div>", unsafe_allow_html=True)
    st.write("---")
