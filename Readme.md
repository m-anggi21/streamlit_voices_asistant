# 🛒 Depo 78 — Web Voice Ordering System (Streamlit Version)

Sistem pemesanan **air minum & gas LPG** berbasis web dengan dukungan:

- 🎤 **Voice Input** (WebRTC + Whisper API)
- 🧠 **NLP CP12 Logic** (alias matching, brand/varian detection, size-group, multi-item order)
- 🔊 **Voice Output** (Edge-TTS)
- 🛍 **User Ordering Page**
- 🧺 **Keranjang belanja**
- 💵 **Checkout + Penyimpanan ke Database**
- 📦 **Admin Dashboard**
- 🔐 **User login & signup**
- 🗂 **Multi-page Streamlit UI**

Sistem ini merupakan hasil porting penuh dari versi CLI (`depo78_voice_assistant_CP12.py`)
ke **aplikasi web** tanpa mengubah logic NLP sama sekali.

---

# ✨ Fitur Utama

## 👤 1. Autentikasi User & Admin
- Signup khusus user
- Login untuk user & admin
- Session login persistent
- Role-based routing (user → order page, admin → dashboard)

---

## 🎙 2. Voice Ordering (STT Hybrid)
Sistem mendukung dua mode:

1. **WebRTC Recorder** (browser)
2. **Whisper API** (untuk hasil transkripsi yang akurat)

Input suara diproses → dikirim ke NLP engine → diubah menjadi item pesanan.

---

## 🧠 3. NLP CP12 Logic (Tanpa perubahan)
Semua logic asli CLI dipertahankan:

- Alias matching (strong, weak, direct, partial)
- Brand extraction & candidate scoring
- Variant & size-group detection
- Quantity detection
- Multi-item parsing ("dan", "terus", "lalu")
- Gas vs air category guessing
- Best-match product selection

NLP logic disimpan dalam:

