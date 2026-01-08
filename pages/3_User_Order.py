# pages/3_User_Order.py
import streamlit as st
import os

st.set_page_config(
    page_title="Order - Depo 78",
    page_icon="🛒",
    layout="wide"   # ⬅️ WAJIB
)
from modules.listen_web import listen_web
from modules.tts_web import speak, tts_reset_queue, tts_flush
from modules.order_engine import init_nlp, process_command
from modules.db import get_db
from modules.admin_api import get_order_items  # biarkan saja
from modules.nlp_core import say_phrase
from modules.logout import do_logout
from modules.user_views import (
    render_beranda,
    render_history,
    render_user_header_bar,
    render_top_nav,   # kalau kamu pakai top nav
)

# ===============================
# FORCE LOGOUT REDIRECT (AMAN)
# ===============================
if st.session_state.get("_force_logout"):
    st.session_state.clear()
    st.switch_page("pages/1_Login.py")

# ============================================================
#   AUTENTIKASI
# ============================================================
if "auth" not in st.session_state or not st.session_state.auth["is_logged_in"]:
    st.error("Anda harus login terlebih dahulu.")
    st.stop()

user = st.session_state.auth["user"]
if user["role"] != "user":
    st.error("Hanya user yang dapat melakukan pemesanan.")
    st.stop()
render_user_header_bar(user, do_logout, key_prefix="user_header")

# ============================================================
#   PROTEKSI LOGIN (WAJIB)
# ============================================================
if "auth" not in st.session_state or not st.session_state.auth.get("is_logged_in"):
    st.error("Anda harus login terlebih dahulu.")
    st.stop()

def load_css(path="assets/styles.css"):
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    css_path = os.path.join(base_dir, path)
    with open(css_path, "r", encoding="utf-8") as f:
        st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)

load_css()

st.markdown('<div class="page-user-order-marker" style="display:none"></div>', unsafe_allow_html=True)

# setelah load_css()
st.markdown("""
<style>
/* default: no extra class */
</style>
""", unsafe_allow_html=True)

nav = render_top_nav(
    default_nav="Order",
    key_prefix="user_order",
)

# ============================================================
#   ROUTING KONTEN (content area berubah, sidebar tetap)
# ============================================================
if nav == "Beranda":
    render_beranda(user, get_db, get_order_items)
    tts_flush(show_controls=True)
    st.stop()

if nav == "History":
    render_history(user, get_db, get_order_items)
    tts_flush(show_controls=True)
    st.stop()

# kalau nav == "Order" -> lanjutkan kode order yang panjang di bawah

# ============================================================
#   HEADER
# ============================================================
st.title(f"🛒 Halo, {user['nama']} — Silakan Pesan")

# ============================================================
#   INISIALISASI NLP
# ============================================================
init_nlp()
st.session_state.setdefault("welcome_tts_done", False)

if not st.session_state.get("welcome_tts_done"):
    tts_text = say_phrase(
        "welcome_user",
        lang="id",
        nama=user["nama"]   # ← parameter masuk ke {nama}
    )

    if not tts_text:
        raise KeyError("Phrase key 'welcome_user' tidak ditemukan / kosong di voice_phrases.csv")

    tts_reset_queue()
    speak(tts_text, lang="id")
    st.session_state.welcome_tts_done = True

# ============================================================
#   PLACEHOLDER UI (biar bisa dihapus tanpa rerun manual)
# ============================================================
voice_status_box = st.empty()   # kotak hijau status voice (Audio diterima, dst)
said_box = st.empty()           # kotak "Anda mengatakan..."
system_box = st.empty()         # opsional: status sistem

# ============================================================
#   SESSION KERANJANG
# ============================================================
st.session_state.setdefault("cart", [])
st.session_state.setdefault("voice_ui_open", False)
st.session_state.setdefault("voice_text", "")
st.session_state.setdefault("pending_action", None)
st.session_state.setdefault("pending_qty", None)
st.session_state.setdefault("has_explicit_qty", False)
st.session_state.setdefault("pending_variant", None)
st.session_state.setdefault("pending_choice", None)
st.session_state.setdefault("last_command_text", "")
st.session_state.setdefault("pause_voice", False)  # ✅ TAMBAH
st.session_state.setdefault("skip_next_process", False)
st.session_state.setdefault("just_cleared_cart", False)
st.session_state.setdefault("clear_boxes_once", False)
st.session_state.setdefault("skip_listen_once", False)
st.session_state.setdefault("checkout_ready", False)
st.session_state.setdefault("cart_locked", False)
st.session_state.setdefault("payment_in_progress", False)
st.session_state.setdefault("order_submitted", False)
st.session_state.setdefault("submitted_order", None)
st.session_state.setdefault("success_tts_done", False)
st.session_state.setdefault("checkout_tts_done", False)
st.session_state.setdefault("payment_method", None)   # "COD" | "TRANSFER" | "QRIS"
st.session_state.setdefault("confirm_payment", False)
st.session_state.setdefault("cart", [])
st.session_state.setdefault("last_view", "cart")  # "cart" | "checkout"

# ✅ AUTO-PAUSE: voice hanya dipause saat ada UI konfirmasi (pending)
st.session_state.pause_voice = bool(st.session_state.get("pending_choice")) or bool(st.session_state.get("pending_action"))

# ============================================================
#   GUARD VIEW BERDASARKAN last_view
#   (agar refresh tetap di kondisi terakhir)
# ============================================================
if st.session_state.get("last_view") == "checkout" and not st.session_state.get("order_submitted"):
    st.session_state.checkout_ready = True

if st.session_state.get("last_view") == "cart":
    st.session_state.checkout_ready = False

# ✅ GUARD GLOBAL: saat checkout/cart terkunci, hentikan voice & proses perintah
if st.session_state.get("checkout_ready") or st.session_state.get("cart_locked") or st.session_state.get("payment_in_progress"):
    st.session_state.voice_ui_open = False
    st.session_state.voice_text = ""
    st.session_state.pause_voice = True
    st.session_state.skip_listen_once = True
    st.session_state.skip_next_process = True

def clear_pending():
    st.session_state.pending_choice = None
    st.session_state.pending_action = None
    st.session_state.pending_qty = 1
    st.session_state.pending_variant = None
    st.session_state.last_command_text = ""
    st.session_state.voice_text = ""
    st.session_state.pause_voice = False  # ✅ pastikan langsung bisa rekam

def checkout_callback():
    st.session_state.checkout_ready = True
    st.session_state.last_view = "checkout"
    st.session_state.cart_locked = True

    # ✅ MATIKAN VOICE total agar tidak retrieving audio saat rerun
    st.session_state.pause_voice = True
    st.session_state.voice_ui_open = False
    st.session_state.voice_text = ""

    # ✅ cegah listen & proses NLP pada 1x run berikutnya
    st.session_state.skip_next_process = True
    st.session_state.skip_listen_once = True
    st.session_state.setdefault("skip_listen_once", False)
    st.session_state.setdefault("checkout_tts_done", False)

def back_to_cart_callback():
    st.session_state.checkout_ready = False
    st.session_state.last_view = "cart"
    st.session_state.cart_locked = False
    st.session_state.checkout_tts_done = False
    st.session_state.payment_in_progress = False
    # hidupkan lagi voice kalau user balik
    st.session_state.pause_voice = False

def pay_now_callback():
    # masuk tahap pilih metode pembayaran (bukan langsung insert DB)
    st.session_state.payment_in_progress = True
    st.session_state.payment_method = None

# ============================================================
#   GUARD: jika order sudah dibayar -> jangan proses ulang apa pun saat rerun
# ============================================================
if st.session_state.get("order_submitted") and st.session_state.get("submitted_order"):
    so = st.session_state.submitted_order
    st.write("---")
    st.subheader("✅ Pembayaran Berhasil")
    st.success("Pesanan Anda sudah diproses. Walau aplikasi rerun, order tidak akan dibuat ulang.")
    if so.get("nomor_antrian"):
        st.info(f"Nomor Antrian: **{so['nomor_antrian']}**")
    if so.get("order_id"):
        st.caption(f"Order ID: {so['order_id']}")
    st.write("### Ringkasan Pesanan")
    for it in (so.get("items") or []):
        st.write(f"• {it['qty']}× {it['nama_item']} = Rp {it['total']:,}")
    st.write(f"### Total Pembayaran: Rp {int(so.get('total', 0)):,}")
    if not st.session_state.get("success_tts_done"):
        tts_paid = say_phrase("payment_received", lang="id")
        if not tts_paid:
            raise KeyError("Phrase key 'payment_received' tidak ditemukan / kosong di voice_phrases.csv")
        speak(tts_paid, lang="id")

        st.session_state.success_tts_done = True
    if st.button("🆕 Mulai Transaksi Baru", key="btn_new_tx"):
        st.session_state.cart = []
        st.session_state.checkout_ready = False
        st.session_state.cart_locked = False
        st.session_state.payment_in_progress = False
        st.session_state.order_submitted = False
        st.session_state.submitted_order = None
        st.session_state.success_tts_done = False
        st.session_state.checkout_tts_done = False
        clear_pending()
        st.session_state.voice_ui_open = False
        st.session_state.voice_text = ""
        st.rerun()
    tts_flush(show_controls=True)
    st.stop()
# ============================================================
#   CHECKOUT VIEW (FULL PAGE)
#   (muncul HANYA setelah klik "✔ Selesai & Bayar" di keranjangst.session_state.setdefault("checkout_ready", False))
# ============================================================
# ============================================================
#   CHECKOUT VIEW (FULL PAGE) - SATU BLOK SAJA
# ============================================================
if st.session_state.get("checkout_ready") and not st.session_state.get("order_submitted"):
    st.write("---")
    st.subheader("💳 Selesaikan Pemesanan")

    st.success("Berikut ringkasan pesanan Anda:")
    total = sum(int(i["total"]) for i in st.session_state.cart)

    for item in st.session_state.cart:
        st.write(f"• {item['qty']}× {item['nama_item']} = Rp {item['total']:,}")

    st.write(f"### Total Pembayaran: Rp {total:,}")

    if not st.session_state.get("checkout_tts_done"):
        tts_summary = say_phrase("order_summary", lang="id")
        if tts_summary:
            speak(tts_summary, lang="id")
        st.session_state.checkout_tts_done = True

    col1, col2 = st.columns(2)

    with col1:
        if st.button(
            "💵 Bayar Sekarang",
            key="btn_pay_now",
            use_container_width=True,
            disabled=bool(st.session_state.get("payment_in_progress"))
                    or bool(st.session_state.get("order_submitted")),
        ):
            st.session_state.payment_in_progress = True
            st.session_state.payment_method = None
            st.session_state.confirm_payment = False
            st.rerun()

    with col2:
        st.button(
            "⬅ Kembali ke Keranjang",
            key="btn_back_to_cart",
            on_click=back_to_cart_callback,
            use_container_width=True,
            disabled=bool(st.session_state.get("payment_in_progress")),
        )

    # ============================================================
    #   PILIH METODE PEMBAYARAN (muncul setelah klik Bayar Sekarang)
    # ============================================================
    if st.session_state.get("payment_in_progress") and (not st.session_state.get("order_submitted")):
        st.write("---")
        st.subheader("🧾 Pilih Metode Pembayaran")

        method = st.radio(
            "Metode Pembayaran:",
            ["COD (Tunai)", "Transfer", "QRIS"],
            horizontal=True,
            key="payment_method_radio",
        )

        if method == "COD (Tunai)":
            st.session_state.payment_method = "COD"
            st.info("Pembayaran ketika barang sudah sampai dan siapkan uang pas.")
        elif method == "Transfer":
            st.session_state.payment_method = "TRANSFER"
            st.info("Silakan transfer ke rekening berikut:")
            st.code("BCA 1234567890 a.n. DEPO 78")  # ganti rekening kamu
        else:
            st.session_state.payment_method = "QRIS"
            st.info("Silakan scan QRIS berikut untuk melakukan pembayaran:")

            import os
            base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            qris_path = os.path.join(base_dir, "assets", "qris.png")  # pastikan nama file sama

            if os.path.exists(qris_path):
                col_l, col_c, col_r = st.columns([1, 2, 1])
                with col_c:
                    st.image(qris_path, caption="QRIS Depo 78", width=260)
            else:
                st.warning("File QRIS belum ditemukan. Pastikan ada di assets/qris.png")

        colp1, colp2 = st.columns(2)

        with colp1:
            if st.button("✅ Konfirmasi Pembayaran", key="btn_confirm_payment", use_container_width=True):
                st.session_state.confirm_payment = True
                st.rerun()

        with colp2:
            if st.button("⬅ Ubah / Batal", key="btn_cancel_payment_method", use_container_width=True):
                st.session_state.payment_in_progress = False
                st.session_state.payment_method = None
                st.session_state.confirm_payment = False
                st.rerun()

        # ============================================================
        #   INSERT DB setelah konfirmasi (masih di dalam checkout)
        # ============================================================
        if st.session_state.get("confirm_payment") and (not st.session_state.get("order_submitted")):
            if not st.session_state.get("payment_method"):
                st.error("Silakan pilih metode pembayaran terlebih dahulu.")
            else:
                try:
                    from datetime import datetime

                    db = get_db()
                    cursor = db.cursor()

                    # 1) queue_numbers -> queue_id
                    tgl = datetime.now().strftime("%d%m%y")
                    cursor.execute(
                        "INSERT INTO queue_numbers (tanggal, created_at) VALUES (%s, NOW())",
                        (tgl,)
                    )
                    queue_id = cursor.lastrowid
                    nomor_antrian = f"{tgl}-{queue_id:03d}"

                    # 2) insert orders
                    cursor.execute(
                        """
                        INSERT INTO orders (
                            users_id, nama, cluster, blok, no_rumah,
                            nomor_antrian, total_harga, metode_pembayaran,
                            status, created_at, queue_id
                        )
                        VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,NOW(),%s)
                        """,
                        (
                            user["users_id"],
                            user["nama"],
                            user["cluster"],
                            user["blok"],
                            user["no_rumah"],
                            nomor_antrian,
                            float(total),
                            st.session_state.get("payment_method"),  # ✅ simpan metode
                            "menunggu",
                            int(queue_id),
                        )
                    )
                    orders_id = cursor.lastrowid  # ✅ PK orders yang benar

                    # 3) insert order_items
                    for it in st.session_state.cart:
                        cursor.execute(
                            """
                            INSERT INTO order_items (orders_id, nama_item, qty, harga_satuan, total_harga)
                            VALUES (%s,%s,%s,%s,%s)
                            """,
                            (
                                int(orders_id),
                                it["nama_item"],
                                int(it["qty"]),
                                float(it["harga_satuan"]),
                                float(it["total"]),
                            )
                        )

                    db.commit()
                    cursor.close()
                    db.close()

                    # sukses
                    st.session_state.submitted_order = {
                        "orders_id": orders_id,
                        "nomor_antrian": nomor_antrian,
                        "total": total,
                        "metode": st.session_state.get("payment_method"),
                        "items": list(st.session_state.cart),
                    }

                    st.session_state.order_submitted = True
                    st.session_state.last_view = "success"

                    # reset flags
                    st.session_state.confirm_payment = False
                    st.session_state.payment_in_progress = False

                    # kosongkan cart
                    st.session_state.cart = []
                    st.session_state.checkout_ready = False
                    st.session_state.cart_locked = True

                    st.success("Pesanan berhasil disimpan!")
                    st.info(f"Nomor antrian Anda: **{nomor_antrian}**")
                    st.balloons()
                    st.rerun()

                except Exception as e:
                    st.session_state.confirm_payment = False
                    st.error(f"Gagal menyimpan pesanan: {e}")

    # ✅ INI HARUS SELALU DI AKHIR BLOK CHECKOUT
    tts_flush(show_controls=True)
    st.stop()

# ============================================================
#   INPUT MODE (Dropdown / List) - default Voice
# ============================================================
st.session_state.setdefault("input_mode", "Voice")

st.markdown("<div class='mode-label'>Mode Input:</div>", unsafe_allow_html=True)

mode = st.selectbox(
    label="Pilih mode input",   # ✅ label tidak boleh kosong
    options=["Voice", "Text"],
    index=0 if st.session_state.input_mode == "Voice" else 1,
    key="input_mode_select",
    label_visibility="collapsed"  # ✅ label disembunyikan tapi tetap ada
)

st.session_state.input_mode = mode

text = ""
trigger = False

if mode == "Text":
    text = st.text_input("Ketikkan perintah:")
    trigger = st.button("Proses")
else:
    # Voice mode: langsung buka recorder (tanpa tombol rekam)
    system_box.info("Silakan bicara. Rekaman otomatis siap digunakan.")

    # ✅ auto-open
    st.session_state.voice_ui_open = True

    stt_text = ""  # biar aman dari NameError

    if st.session_state.voice_ui_open:

        if st.session_state.get("pause_voice"):
            voice_status_box.info("Selesaikan pilihan yang muncul di bawah, lalu Anda bisa rekam lagi.")
        else:
            # ✅ kalau baru clear cart, cukup turunkan flag-nya
            if st.session_state.get("just_cleared_cart"):
                st.session_state.just_cleared_cart = False

            # ✅ recorder tetap tampil, tapi boleh skip proses STT 1x
            skip_now = bool(st.session_state.get("skip_listen_once", False))

            # ✅ tampilkan UI recorder
            stt_text = listen_web(show_ui=True, skip_process=skip_now)

            # ✅ reset skip flag setelah 1x run
            if skip_now:
                st.session_state.skip_listen_once = False

            if stt_text:
                st.session_state.voice_text = stt_text

            if st.session_state.voice_text:
                text = st.session_state.voice_text
                trigger = True
                st.session_state.voice_text = ""

# ============================================================
#   HELPER: add to cart
# ============================================================
def _add_item_to_cart(chosen_item: dict, qty: int):
    nama_item = chosen_item["nama"]
    harga = chosen_item["harga"]
    total = qty * harga

    st.session_state.cart.append({
        "nama_item": nama_item,
        "qty": qty,
        "harga_satuan": harga,
        "total": total
    })

    st.success(f"Menambahkan: **{qty}× {nama_item}** (Rp {total:,})")

    # ✅ suara item_added harus tetap dipanggil (key saja)
    tts_text = say_phrase("item_added", lang="id", name=nama_item, qty=qty)

    # ❌ DILARANG: fallback text hardcode di kode
    # if not tts_text:
    #     tts_text = f"Item {nama_item} sejumlah {qty} berhasil ditambahkan ke keranjang."

    # ✅ STRICT: kalau phrase kosong / key tidak ada -> anggap error (supaya ketahuan & wajib ditambah di CSV)
    if not tts_text:
        raise KeyError("Phrase key 'item_added' tidak ditemukan / kosong di voice_phrases.csv")

    speak(tts_text, lang="id")

# ============================================================
#   ASK QTY UI (WAJIB jika qty belum disebut)
# ============================================================
pa = st.session_state.pending_action
if pa and pa.get("type") == "ask_qty":
    st.warning(pa.get("title") or "Berapa jumlahnya?")

    qty = st.number_input("Jumlah:", min_value=1, step=1)

    if st.button("✅ Tambahkan ke Keranjang"):
        tts_reset_queue()
        _add_item_to_cart(pa["chosen_item"], int(qty))
        clear_pending()
        st.rerun()

    tts_flush(show_controls=True)
    st.stop()

# ============================================================
#   DISAMBIGUATION UI (kalau ada pending_action)
# ============================================================
pa = st.session_state.pending_action
if pa:
    st.warning(pa.get("title") or "Perlu pilihan Anda:")

    has_explicit = st.session_state.pending_choice.get("has_explicit_qty", False)
    qty = st.session_state.pending_choice.get("qty")

    if not has_explicit:
        qty = st.number_input("Jumlah:", min_value=1, step=1)

    if pa["type"] == "choose_item":
        options_keys = pa.get("options") or []
        # tampilkan nama produk
        catalog = st.session_state.get("catalog", {})
        labels = []
        for k in options_keys:
            meta = catalog.get(k, {})
            labels.append(f"{meta.get('nama','(unknown)')} — Rp {int(meta.get('harga',0)):,}")

        picked = st.selectbox("Pilih produk:", list(range(len(options_keys))), format_func=lambda i: labels[i] if i < len(labels) else str(i))

        if st.button("✅ Tambahkan"):
            catalog = st.session_state.get("catalog", {})
            chosen_key = options_keys[picked]
            chosen_item = catalog[chosen_key]
            tts_reset_queue()
            _add_item_to_cart(chosen_item, int(qty))
            st.session_state.pending_action = None
            st.session_state.pending_qty = 1
            st.rerun()

    elif pa["type"] == "choose_brand_then_item":
        # tahap 1: pilih brand
        brand_list = pa.get("brand_options") or []
        variant = pa.get("variant")
        brand = st.selectbox("Pilih brand:", brand_list)

        if st.button("➡ Lanjut pilih produk"):
            # bangun options item berdasarkan brand + variant
            catalog = st.session_state.get("catalog", {})
            opts = []
            for k, meta in catalog.items():
                if (meta.get("brand") or "").strip().lower() == (brand or "").strip().lower() and (meta.get("varian") or "").strip().lower() == (variant or "").strip().lower():
                    opts.append(k)

            st.session_state.pending_action = {
                "type": "choose_item",
                "title": f"Pilih produk brand **{brand}** varian **{variant}**:",
                "options": opts
            }
            st.session_state.pending_qty = int(qty)
            st.rerun()

    # penting: jangan lanjut proses normal kalau sedang disambiguation
    tts_flush(show_controls=True)
    st.stop()

# ✅ Guard: kalau barusan ada aksi UI (clear cart / batal), jangan proses NLP 1x
if st.session_state.get("skip_next_process"):
    st.session_state.skip_next_process = False
    trigger = False
    text = ""

# ============================================================
#   PROSES INPUT USER (normal)
# ============================================================
if trigger and text:
    # ✅ tampilkan satu kali saja
    # said_box.success(f"Anda mengatakan: {text}")

    # ✅ Jika user memberi perintah baru, pending lama harus di-override otomatis
    if text.strip().lower() != st.session_state.get("last_command_text", "").strip().lower():
        clear_pending()
        st.session_state.last_command_text = text

    parsed = process_command(user, text)

    if not parsed:
        st.error("Saya tidak memahami pesanan Anda.")
    else:
        for p in parsed:
            chosen = p.get("chosen_item")
            need = p.get("need_action")

            # ✅ kalau butuh pilihan (brand / item), jangan break
            #    langsung rerun supaya UI pilihan muncul sekarang juga
            if (not chosen) and need:
                st.session_state.pending_choice = {
                    "need": need,
                    "qty": p.get("qty"),  # bisa None
                    "has_explicit_qty": p.get("has_explicit_qty", False),
                    "chunk": p.get("chunk", text),
                    "meta": p.get("meta", {}),
                }

                # ✅ penting untuk mode voice: hentikan listening agar tidak ketimpa audio berikutnya
                st.session_state.pause_voice = True

                st.rerun()

            if chosen:
                qty = p.get("qty")
                if qty is None:
                    # tahan → wajib tanya qty
                    st.session_state.pending_action = {
                        "type": "ask_qty",
                        "title": "Berapa jumlah yang ingin Anda pesan?",
                        "chosen_item": chosen,
                    }
                    st.session_state.pause_voice = True  # ✅ konsisten: stop listening saat menunggu jawaban
                    st.rerun()   # ✅ PENTING: supaya UI ask_qty langsung muncul sekarang juga
                else:
                    _add_item_to_cart(chosen, int(qty))

# ============================================================
#   PENDING CHOICE (FLOW CLI) - BRAND -> VARIANT -> QTY
# ============================================================
pc = st.session_state.get("pending_choice")
if pc:
    need = pc["need"] or {}
    need_type = need.get("type")
    catalog = st.session_state.get("catalog", {})

    # ambil info qty
    has_explicit_qty = bool(pc.get("has_explicit_qty", False))
    qty_from_text = pc.get("qty")  # bisa None

    st.write("---")
    st.subheader("🔎 Perlu Konfirmasi Pilihan")
    st.info(need.get("title") or "Pilih salah satu:")

    def _set_pending_need(next_need: dict, keep_qty=True):
        """helper untuk lanjut ke tahap berikutnya"""
        st.session_state.pending_choice = {
            "need": next_need,
            "qty": qty_from_text if keep_qty else None,
            "has_explicit_qty": has_explicit_qty,
            "chunk": pc.get("chunk", ""),
            "meta": pc.get("meta", {}),
        }

    def _finalize_add(chosen_item: dict):
        """kalau qty belum disebut -> tanya qty dulu, kalau sudah -> add"""
        if (qty_from_text is None) or (not has_explicit_qty):
            # wajib tanya qty jika qty tidak eksplisit dari user
            st.session_state.pending_action = {
                "type": "ask_qty",
                "title": "Berapa jumlah yang ingin Anda pesan?",
                "chosen_item": chosen_item,
            }
            st.session_state.pending_choice = None
            st.rerun()
        else:
            _add_item_to_cart(chosen_item, int(qty_from_text))
            clear_pending()
            st.rerun()

    # -----------------------------
    # 1A) HANDLER: choose_brand_then_item (dari NLP)
    # -----------------------------
    if need_type == "choose_brand_then_item":
        brand_list = need.get("brand_options") or []
        flt = need.get("filter") or {}
        mode_f = flt.get("mode")

        if not brand_list:
            # ✅ fallback: ambil semua brand dari catalog (biar tidak dead-end)
            s = set()
            for _, meta in catalog.items():
                b = (meta.get("brand") or "").strip().lower()
                if b:
                    s.add(b)
            brand_list = sorted(list(s))

            if not brand_list:
                st.error("Tidak ada opsi brand yang bisa dipilih.")
                clear_pending()
                st.rerun()

        brand = st.selectbox("Pilih brand:", brand_list, key="pc_brand_then_item")

        col1, col2 = st.columns(2)
        with col1:
            if st.button("➡ Lanjut", key="pc_brand_then_item_next"):
                # ambil semua produk dari brand terpilih
                keys = [
                    k for k, meta in catalog.items()
                    if (meta.get("brand") or "").strip().lower()
                       == (brand or "").strip().lower()
                ]

                # ==== APPLY FILTER MODE dari NLP ====
                if mode_f == "varian_only":
                    variant = (flt.get("variant") or "").strip().lower()
                    category = (flt.get("category") or "").strip().lower()
                    keys = [
                        k for k in keys
                        if (catalog[k].get("varian") or "").strip().lower() == variant
                        and (not category or (catalog[k].get("kategori") or "").strip().lower() == category)
                    ]

                elif mode_f == "botol_only":
                    def _is_botol(m):
                        kat = (m.get("kategori") or "").lower()
                        nama = (m.get("nama") or "").lower()
                        return (kat == "botol") or ("botol" in nama)
                    keys = [k for k in keys if _is_botol(catalog.get(k, {}))]

                elif mode_f == "packaging_no_galon":
                    def _is_botol_or_cup(m):
                        kat = (m.get("kategori") or "").lower()
                        nama = (m.get("nama") or "").lower()
                        return (kat in {"botol", "cup"}) or ("botol" in nama) or ("cup" in nama) or ("gelas" in nama)

                    def _is_not_galon(m):
                        kat = (m.get("kategori") or "").lower()
                        var = (m.get("varian") or "").lower()
                        nama = (m.get("nama") or "").lower()
                        return ("galon" not in kat) and (var != "19l") and ("19l" not in var) and ("galon" not in nama)

                    keys = [k for k in keys if _is_botol_or_cup(catalog.get(k, {})) and _is_not_galon(catalog.get(k, {}))]

                elif mode_f == "air_all":
                    # khusus "air mineral": tampilkan semua produk air (botol/cup/galon)
                    def _is_air(m):
                        kat = (m.get("kategori") or "").lower()
                        nama = (m.get("nama") or "").lower()
                        return (
                            kat in {"botol", "cup", "galon"}
                            or "botol" in nama
                            or "cup" in nama
                            or "gelas" in nama
                            or "galon" in nama
                        )
                    keys = [k for k in keys if _is_air(catalog.get(k, {}))]

                elif mode_f == "brand_only":
                    pass  # cukup by brand saja

                if not keys:
                    st.warning(f"Tidak ada produk yang cocok untuk brand '{brand}'.")
                    st.stop()

                # lanjut ke tahap pilih produk/varian
                _set_pending_need({
                    "type": "choose_item",
                    "title": f"Pilih varian/produk untuk brand **{brand}**:",
                    "brand": brand,
                    "options": keys,
                })
                st.rerun()

        with col2:
            if st.button("❌ Batal", key="pc_brand_then_item_cancel"):
                clear_pending()
                st.rerun()

        tts_flush(show_controls=True)
        st.stop()

    # -----------------------------
    # 1) PILIH BRAND DULU
    # need contoh:
    # {type:"choose_brand", brand_options:[...], variant_options:[...], size_group:"medium", packaging:"dus"}
    # -----------------------------
    if need_type == "choose_brand":
        brand_list = need.get("brand_options") or need.get("options") or []
        if not brand_list:
            st.error("Tidak ada opsi brand yang bisa dipilih.")
            clear_pending()
            st.rerun()

        brand = st.selectbox("Pilih brand:", brand_list, key="pc_brand")

        col1, col2 = st.columns(2)
        with col1:
            if st.button("➡ Lanjut", key="pc_brand_next"):
                # kalau engine sudah menyiapkan variant_options, pakai itu
                variant_list = need.get("variant_options") or []

                # fallback: kalau tidak ada variant_options, coba ambil dari catalog berdasarkan brand
                if not variant_list:
                    s = set()
                    for _, meta in catalog.items():
                        if (meta.get("brand", "") or "").strip().lower() == (brand or "").strip().lower():
                            v = (meta.get("varian") or "").strip()
                            if v:
                                s.add(v)
                    variant_list = sorted(list(s))

                # kalau tetap kosong, berarti langsung ke choose_item
                if variant_list:
                    _set_pending_need({
                        "type": "choose_variant",
                        "title": f"Brand **{brand}**. Pilih varian dulu:",
                        "brand": brand,
                        "variant_options": variant_list,
                    })
                else:
                    # langsung ke item (brand saja)
                    opts = []
                    for k, meta in catalog.items():
                        if (meta.get("brand", "") or "").strip().lower() == (brand or "").strip().lower():
                            opts.append(k)
                    _set_pending_need({
                        "type": "choose_item",
                        "title": f"Pilih produk untuk brand **{brand}**:",
                        "brand": brand,
                        "options": opts,
                    })

                st.rerun()

        with col2:
            if st.button("❌ Batal", key="pc_brand_cancel"):
                clear_pending()
                st.rerun()

        tts_flush(show_controls=True)
        st.stop()

    # -----------------------------
    # 2) PILIH VARIANT
    # need contoh:
    # {type:"choose_variant", brand:"aqua", variant_options:[...]}
    # -----------------------------
    if need_type == "choose_variant":
        brand = need.get("brand")
        variant_list = need.get("variant_options") or need.get("options") or []
        if not variant_list:
            st.error("Tidak ada opsi varian yang bisa dipilih.")
            clear_pending()
            st.rerun()

        variant = st.selectbox("Pilih varian:", variant_list, key="pc_variant")

        col1, col2 = st.columns(2)
        with col1:
            if st.button("➡ Lanjut pilih produk", key="pc_variant_next"):
                opts = []
                for k, meta in catalog.items():
                    ok_brand = True
                    if brand:
                        ok_brand = (meta.get("brand", "") or "").strip().lower() == (brand or "").strip().lower()
                    ok_var = (meta.get("varian", "") or "").strip().lower() == (variant or "").strip().lower()
                    if ok_brand and ok_var:
                        opts.append(k)

                _set_pending_need({
                    "type": "choose_item",
                    "title": f"Pilih produk **{brand or ''} {variant}**:",
                    "brand": brand,
                    "variant": variant,
                    "options": opts,
                })
                st.rerun()

        with col2:
            if st.button("❌ Batal", key="pc_variant_cancel"):
                clear_pending()
                st.rerun()

        tts_flush(show_controls=True)
        st.stop()

    # -----------------------------
    # 3) PILIH ITEM (produk final)
    # mendukung:
    # - options = list[str] (catalog keys)
    # - options = list[dict] ({label,nama,harga})
    # -----------------------------
    if need_type == "choose_item":
        options = need.get("options") or []
        if not options:
            st.error("Tidak ada opsi produk yang bisa dipilih.")
            clear_pending()
            st.rerun()

        is_key_list = isinstance(options[0], str)

        if is_key_list:
            option_keys = options
            labels = []
            for k in option_keys:
                m = catalog.get(k, {})
                labels.append(f"{m.get('nama','(unknown)')} — Rp {int(m.get('harga',0)):,}")

            idx = st.selectbox(
                "Pilih produk:",
                list(range(len(option_keys))),
                format_func=lambda i: labels[i],
                key="pc_choose_item_keylist"
            )

            col1, col2 = st.columns(2)
            with col1:
                if st.button("✅ Pilih", key="pc_add_choose_item"):
                    chosen_key = option_keys[idx]
                    chosen = catalog.get(chosen_key)
                    if not chosen:
                        st.error("Produk tidak ditemukan di catalog.")
                    else:
                        _finalize_add(chosen)

            with col2:
                if st.button("❌ Batal", key="pc_cancel_keylist"):
                    clear_pending()
                    st.rerun()

        else:
            labels = [o.get("label") or o.get("nama") or str(o) for o in options]
            idx = st.selectbox(
                "Pilih produk:",
                list(range(len(labels))),
                format_func=lambda i: labels[i],
                key="pc_choose_item_dict"
            )

            col1, col2 = st.columns(2)
            with col1:
                if st.button("✅ Pilih", key="pc_add_choose_item_dict"):
                    picked = options[idx]
                    chosen_item = {
                        "nama": picked.get("nama"),
                        "harga": int(picked.get("harga", 0)),
                    }
                    _finalize_add(chosen_item)

            with col2:
                if st.button("❌ Batal", key="pc_cancel_dict"):
                    clear_pending()
                    st.rerun()

        tts_flush(show_controls=True)
        st.stop()

    # fallback kalau type belum di-handle
    st.warning(f"need_action type '{need_type}' belum didukung UI.")
    tts_flush(show_controls=True)
    st.stop()

def clear_cart_callback():
    tts_reset_queue()

    # kosongkan cart + state penting
    st.session_state.cart = []
    st.session_state.voice_ui_open = False
    st.session_state.voice_text = ""
    st.session_state.last_command_text = ""
    st.session_state.pending_choice = None
    st.session_state.pending_action = None

    # reset STT/VAD state
    for k in [
        "stt_last_hash", "stt_last_text",
        "vf_buf", "vf_last_voice", "vf_done",
        "vf_last_voice_ts", "vf_processing", "vf_level",
    ]:
        st.session_state.pop(k, None)

    # flag supaya 1x run berikutnya tidak listen & tidak proses NLP
    st.session_state.just_cleared_cart = True
    st.session_state.skip_next_process = True
    st.session_state.skip_listen_once = True

    # flag untuk mengosongkan box UI pada run berikutnya
    st.session_state.clear_boxes_once = True

# ============================================================
#   TAMPILKAN CART
# ============================================================
st.write("---")
st.subheader("🧺 Keranjang Pesanan")

has_cart = len(st.session_state.cart) > 0

def clear_cart_full():
    """Bersihkan keranjang + reset state (versi lengkap sesuai kode kamu)."""
    tts_reset_queue()

    # kosongkan cart + state penting
    st.session_state.cart = []
    st.session_state.voice_ui_open = False
    st.session_state.voice_text = ""
    st.session_state.last_command_text = ""
    st.session_state.pending_choice = None
    st.session_state.pending_action = None

    # reset STT/VAD state
    for k in [
        "stt_last_hash", "stt_last_text",
        "vf_buf", "vf_last_voice", "vf_done",
        "vf_last_voice_ts", "vf_processing", "vf_level",
    ]:
        st.session_state.pop(k, None)

    # flag supaya 1x run berikutnya tidak listen & tidak proses NLP
    st.session_state.skip_next_process = True
    st.session_state.skip_listen_once = True

    # hilangkan box UI yang sudah terlanjur tampil
    voice_status_box.empty()
    said_box.empty()
    system_box.empty()

    # optional flag yang kamu pakai
    if st.session_state.get("clear_boxes_once"):
        voice_status_box.empty()
        said_box.empty()
        system_box.empty()
        st.session_state.clear_boxes_once = False

    # TTS clear_cart (sekali)
    tts_clear = say_phrase("clear_cart", lang="id")
    if tts_clear:
        speak(tts_clear, lang="id")

    # pesan sukses (akan tampil setelah rerun natural streamlit)
    st.session_state["cart_cleared_msg"] = True


if not has_cart:
    # tampilkan pesan sukses bila baru clear
    if st.session_state.pop("cart_cleared_msg", False):
        st.success("Keranjang dikosongkan.")
    st.info("Keranjang masih kosong.")
else:
    total_all = 0
    for i, item in enumerate(st.session_state.cart):
        st.write(f"**{i+1}. {item['nama_item']}** — {item['qty']}×  (Rp {item['total']:,})")
        total_all += item["total"]

    st.write(f"### 💰 Total: Rp {total_all:,}")

    # ✅ tombol sejajar: Bersihkan + Selesai & Bayar
    col1, col2 = st.columns(2)

    with col1:
        st.button(
            "🗑 Bersihkan Keranjang",
            key="btn_clear_cart",
            on_click=clear_cart_full,   # ✅ pakai callback lengkap
            use_container_width=True
        )

    with col2:
        st.button(
            "✔ Selesai & Bayar",
            key="btn_checkout",
            on_click=checkout_callback,  # ✅ aktifkan checkout view
            disabled=bool(st.session_state.get("checkout_ready"))
                    or bool(st.session_state.get("cart_locked"))
                    or bool(st.session_state.get("order_submitted"))
                    or bool(st.session_state.get("payment_in_progress")),
            use_container_width=True
        )

# ============================================================
#   PENTING: flush TTS hanya sekali di akhir file
# ============================================================
tts_flush(show_controls=True)
