# modules/user_views.py
import streamlit as st
from typing import List, Dict, Any, Optional
from pathlib import Path
from datetime import datetime
import html as _html
import re

from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm

# =========================
# STRUK (PDF) HELPERS
# =========================

def _fmt_dt(dt_val) -> str:
    try:
        return dt_val.strftime("%d/%m/%Y %H:%M")
    except Exception:
        return str(dt_val) if dt_val else "-"


def _rupiah(n: int) -> str:
    try:
        return f"Rp {int(n):,}"
    except Exception:
        return "Rp 0"


def _build_invoice_context(user: dict, order: dict, items: list) -> dict:
    u = user or {}
    o = order or {}

    nama = u.get("nama") or u.get("username") or "User"
    addr = f"{u.get('cluster','-')} , {u.get('blok','-')} / {u.get('no_rumah','-')}"
    created_str = _fmt_dt(o.get("created_at"))

    rows = []
    subtotal_sum = 0
    for it in (items or []):
        qty = int(it.get("qty") or 0)
        nama_item = str(it.get("nama_item") or "-")
        sub = int(it.get("total_harga") or 0)
        subtotal_sum += sub
        rows.append({"qty": qty, "name": nama_item, "subtotal": sub})

    total = int(o.get("total_harga") or subtotal_sum or 0)

    return {
        "SHOP_NAME": "Toko Depo78",
        "ORDER_ID": str(o.get("orders_id") or ""),
        "ORDER_NO": str(o.get("nomor_antrian") or "-"),
        "ORDER_DATE": created_str,
        "STATUS": str(o.get("status") or "-"),
        "PAYMENT_METHOD": str(o.get("metode_pembayaran") or "-"),
        "CUSTOMER_NAME": nama,
        "CUSTOMER_ADDR": addr,
        "TOTAL_INT": total,
        "TOTAL": _rupiah(total),
        "ITEMS": rows,
    }


def _paper_spec(paper: str, item_count: int):
    """Thermal paper only: return (page_size, width_pt, height_pt, is_dynamic_height)."""
    paper = (paper or "").lower().strip()

    # Default: 80mm
    if "58" in paper:
        width = 58 * mm
    else:
        width = 80 * mm

    # Dynamic height: base + per-item lines
    base_h = 95 * mm
    per_item = 8 * mm
    height = base_h + max(0, item_count) * per_item
    return ((width, height), width, height, True)


def _render_invoice_pdf(ctx: dict, paper: str) -> bytes:
    items = ctx.get("ITEMS", []) or []
    page_size, w, h, dynamic = _paper_spec(paper, len(items))

    from io import BytesIO
    buff = BytesIO()
    c = canvas.Canvas(buff, pagesize=page_size)

    # Margins
    left = 6 * mm
    right = w - 6 * mm
    y = h - 8 * mm

    # Thermal: choose value indent based on width
    # 58mm: smaller indent, 80mm: larger indent
    value_left = left + (18 * mm if w <= (65 * mm) else 24 * mm)

    # Line heights (bigger spacing to avoid overlap)
    lh8 = 11   # font 8
    lh9 = 12   # font 9
    lh10 = 14  # font 10
    lh14 = 18  # font 14

    def hr(thick=0.6, gap_before=6, gap_after=10):
        """Horizontal separator with extra spacing so it won't touch text."""
        nonlocal y
        y -= gap_before
        c.setLineWidth(thick)
        c.line(left, y, right, y)
        y -= gap_after

    def draw_kv_left(label: str, value: str, size=9):
        """Left-aligned label + left-aligned value with wrapping."""
        nonlocal y
        c.setFont("Helvetica-Bold", size)
        c.drawString(left, y, f"{label}:")
        c.setFont("Helvetica", size)

        max_w = right - value_left
        value = "" if value is None else str(value)

        # wrap value
        words = value.split()
        lines = []
        cur = ""
        for wword in words:
            test = (cur + " " + wword).strip()
            if c.stringWidth(test, "Helvetica", size) <= max_w:
                cur = test
            else:
                if cur:
                    lines.append(cur)
                cur = wword
        if cur:
            lines.append(cur)
        if not lines:
            lines = ["-"]

        # first line at current y, subsequent lines below
        c.drawString(value_left, y, lines[0])
        y -= (lh9 if size == 9 else lh10)

        for ln in lines[1:]:
            c.drawString(value_left, y, ln)
            y -= (lh9 if size == 9 else lh10)

    # ===== Header (centered) =====
    c.setFont("Helvetica-Bold", 14)
    c.drawCentredString(w / 2, y, ctx.get("SHOP_NAME", "TOKO"))
    y -= lh14

    c.setFont("Helvetica", 9)
    c.drawCentredString(w / 2, y, "STRUK PEMESANAN")
    y -= lh9

    hr(thick=0.9, gap_before=6, gap_after=10)

    # ===== Order meta (left aligned like your previous) =====
    draw_kv_left("No Antrian", ctx.get("ORDER_NO", "-"), size=9)
    draw_kv_left("Tanggal", ctx.get("ORDER_DATE", "-"), size=9)
    draw_kv_left("Status", ctx.get("STATUS", "-"), size=9)
    draw_kv_left("Metode", ctx.get("PAYMENT_METHOD", "-"), size=9)

    hr(thick=0.6, gap_before=4, gap_after=10)

    # ===== Customer =====
    c.setFont("Helvetica-Bold", 10)
    c.drawString(left, y, "Pelanggan")
    y -= lh10

    draw_kv_left("Nama", ctx.get("CUSTOMER_NAME", "-"), size=9)
    draw_kv_left("Alamat", ctx.get("CUSTOMER_ADDR", "-"), size=9)

    hr(thick=0.6, gap_before=4, gap_after=10)

    # ===== Items header =====
    c.setFont("Helvetica-Bold", 9)
    qty_x = left
    item_x = left + (12 * mm if w <= (65 * mm) else 16 * mm)
    sub_x = right

    c.drawString(qty_x, y, "QTY")
    c.drawString(item_x, y, "ITEM")
    c.drawRightString(sub_x, y, "SUBTOTAL")
    y -= lh9

    hr(thick=0.4, gap_before=2, gap_after=8)

    # ===== Items rows =====
    c.setFont("Helvetica", 9)
    name_max = right - (item_x + 24 * mm)  # leave space for subtotal

    for it in items:
        qty = str(it.get("qty", 0))
        name = str(it.get("name", "-"))
        sub = _rupiah(int(it.get("subtotal", 0)))

        c.drawString(qty_x, y, f"{qty}x")

        # wrap item name max 2 lines
        words = name.split()
        l1 = ""
        l2 = ""
        for wword in words:
            test = (l1 + " " + wword).strip()
            if c.stringWidth(test, "Helvetica", 9) <= name_max:
                l1 = test
            else:
                l2 = (l2 + " " + wword).strip()

        c.drawString(item_x, y, l1 if l1 else name[:24])
        c.drawRightString(sub_x, y, sub)
        y -= lh9

        if l2:
            c.drawString(item_x, y, l2)
            y -= lh9

    hr(thick=0.9, gap_before=4, gap_after=12)

    # ===== Total =====
    c.setFont("Helvetica-Bold", 11)
    c.drawString(left, y, "TOTAL")
    c.drawRightString(right, y, ctx.get("TOTAL", "Rp 0"))
    y -= 18

    c.setFont("Helvetica", 8)
    c.drawString(left, y, "Terima kasih. Simpan struk ini sebagai bukti pemesanan.")
    y -= lh8

    c.showPage()
    c.save()
    return buff.getvalue()


def get_paper_choice_ui(page_key: str) -> str:
    """Deprecated: ukuran kertas diset default."""
    return "Thermal 80mm"

def build_struk_pdf_bytes(user: dict, order: dict, items: list, paper_choice: str) -> bytes:
    """
    Generate PDF struk (bytes) untuk dipakai download maupun print.
    """
    ctx = _build_invoice_context(user, order, items)
    return _render_invoice_pdf(ctx, paper_choice)

def render_struk_pdf_download_button(user: dict, order: dict, items: list, key_prefix: str, paper_choice: str):
    """Tombol download PDF per pesanan."""
    ctx = _build_invoice_context(user, order, items)

    base_name = f"struk_{ctx.get('ORDER_NO','order')}_{ctx.get('ORDER_ID','')}"
    base_name = re.sub(r"[^A-Za-z0-9_\-]", "_", base_name).strip("_") or "struk"

    pdf_bytes = build_struk_pdf_bytes(user, order, items, paper_choice)
    st.download_button(
        "⬇️ Download Struk (PDF)",
        data=pdf_bytes,
        file_name=f"{base_name}.pdf",
        mime="application/pdf",
        key=f"{key_prefix}_pdf",
        use_container_width=True,
    )


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

            # Tombol download struk per pesanan
            render_struk_pdf_download_button(user, o, items, key_prefix=f"beranda_inv_{orders_id}", paper_choice="Thermal 80mm")

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

        items = fetch_order_items(get_order_items_func, int(o["orders_id"]))

        # Tombol download struk per pesanan
        render_struk_pdf_download_button(user, o, items, key_prefix=f"history_inv_{int(o.get('orders_id') or 0)}", paper_choice="Thermal 80mm")

        with st.expander("📦 Detail item"):
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
