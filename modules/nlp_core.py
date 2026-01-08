# modules/nlp_core.py

import re
import csv
import os
import io

# ================================================================
#                  GLOBAL CATALOG (untuk versi web)
# ================================================================
GLOBAL_CATALOG = {}

# ================================================================
#                        KONSTANTA UMUM
# ================================================================

def normalize(s):
    if s is None:
        return ""
    s = str(s).lower()
    s = re.sub(r"[^a-z0-9\s\.]", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s


NUM_WORDS = {
    "satu": 1, "sebuah": 1, "sebiji": 1,
    "dua": 2, "tiga": 3, "empat": 4, "lima": 5,
    "enam": 6, "tujuh": 7, "delapan": 8, "sembilan": 9, "sepuluh": 10,
    "sebelas": 11, "duabelas": 12, "dua belas": 12
}

STOPWORDS = {"saya", "mau", "ingin", "tolong", "dong", "ya", "deh", "aku", "pesan", "beli", "order", "punya", "nih"}

PACKAGING_WORDS = {"dus", "kardus", "karton", "kerdus", "box"}

GENERIC_VARIANT_WORDS = {
    "botol", "dus", "cup", "galon",
    "pack", "karton", "kardus", "kerdus", "box"
}

SIZE_GROUP = {
    "big": {
        "words": ["besar", "gede", "jumbo"],
        "patterns": ["1500", "1.5"],
    },
    "medium": {
        "words": ["sedang", "tanggung"],
        "patterns": ["600", "500"],
    },
    "small": {
        "words": ["mini", "kecil", "baby", "bebi"],
        "patterns": ["330", "350"],
    },
    "cup-only": {
        "words": ["cup", "gelas"],
        "patterns": ["cup", "240"],
    },
    "galon": {
        "words": ["galon"],
        "patterns": ["19", "galon"],
    }
}

# ================================================================
#      TAMBAHAN: MAPPING VARIANT (ANGKA) -> SIZE GROUP
# ================================================================
VARIANT_TO_SIZE_GROUP = {
    # botol besar
    "1500ml": "big",
    "1.5ml": "big",     # NOTE: di code kamu 1.5 dibentuk jadi "1.5ml"
    "1.5l": "big",

    # tanggung / sedang
    "600ml": "medium",
    "500ml": "medium",

    # kecil
    "330ml": "small",
    "350ml": "small",
    "400ml": "small",   # opsional: kalau kamu anggap masuk kecil

    # cup
    "240ml": "cup-only",

    # galon
    "19l": "galon",
}

def size_group_from_variant(variant: str):
    v = (variant or "").strip().lower()
    if not v:
        return None

    # exact
    if v in VARIANT_TO_SIZE_GROUP:
        return VARIANT_TO_SIZE_GROUP[v]

    # fallback: kalau varian mengandung angka tertentu
    # misal varian di katalog kadang "600 ml" / "600" / "600ml botol"
    for group, cfg in SIZE_GROUP.items():
        for p in cfg.get("patterns", []):
            if p and p in v:
                return group

    return None

# Build ALIAS_VARIANT_WORDS
ALIAS_VARIANT_WORDS = set()
for cfg in SIZE_GROUP.values():
    for w in cfg["words"]:
        ALIAS_VARIANT_WORDS.add(w)

ALIAS_VARIANT_WORDS |= {
    "gas", "kg", "kilo", "kilogram",
    "ml", "mililiter",
    "l", "liter", "ltr"
}

ALIAS_VARIANT_WORDS |= PACKAGING_WORDS

# Alias index global
ALIAS_INDEX = {}

CATALOG_VARIANT_NUMBERS = set()
# ================================================================
#                        VOICE PHRASE LOADER
# ================================================================

VOICE_PHRASES = {}
CURRENT_LANG = "id"
FALLBACK_LANG = "id"


def load_voice_phrases(path):
    if not os.path.exists(path):
        raise FileNotFoundError(f"[ERROR] file voice_phrases.csv tidak ditemukan: {path}")

    phrases = {}

    # FIX UTF-8 BOM: gunakan encoding utf-8-sig agar BOM otomatis dihapus
    with open(path, encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)

        # Normalisasi nama kolom → hilangkan spasi & BOM
        fieldnames_norm = [c.strip().lower() for c in reader.fieldnames]
        normalized_map = dict(zip(fieldnames_norm, reader.fieldnames))

        if "key" not in fieldnames_norm or "text" not in fieldnames_norm:
            raise KeyError(
                f"voice_phrases.csv wajib punya kolom ['key','text'].\n"
                f"Kolom ditemukan: {reader.fieldnames}"
            )

        lang_available = "lang" in fieldnames_norm

        for row in reader:
            key_raw = row[normalized_map["key"]]
            text_raw = row[normalized_map["text"]]

            key = key_raw.strip().lower()
            text = text_raw.strip()

            if lang_available:
                lang_raw = row[normalized_map["lang"]]
                lang = lang_raw.strip().lower()
            else:
                lang = "id"

            phrases[(key, lang)] = text

    return phrases


def init_voice_phrases_or_exit(path="voice_phrases.csv"):
    global VOICE_PHRASES
    VOICE_PHRASES = load_voice_phrases(path)
    return VOICE_PHRASES

def _lookup_phrase(key, lang):
    if (key, lang) in VOICE_PHRASES:
        return VOICE_PHRASES[(key, lang)], lang
    if (key, FALLBACK_LANG) in VOICE_PHRASES:
        return VOICE_PHRASES[(key, FALLBACK_LANG)], FALLBACK_LANG
    for (k, l), text in VOICE_PHRASES.items():
        if k == key:
            return text, l
    return None, None


def say_phrase(key, mode="text", lang=None, **kwargs):
    """
    Di Web: TTS ditangani di lapisan lain (tts_web).
    Di sini hanya mengembalikan teks final.
    """
    use_lang = (lang or CURRENT_LANG).lower()

    txt, resolved = _lookup_phrase(key, use_lang)
    if txt is None:
        return None

    try:
        txt_fmt = txt.format(**kwargs) if kwargs else txt
    except Exception:
        txt_fmt = txt

    return txt_fmt


# ================================================================
#                  LOADER KATALOG CSV + ALIAS INDEX
# ================================================================

def build_alias_index(catalog):
    global ALIAS_INDEX
    ALIAS_INDEX = {}

    for key, meta in catalog.items():
        for alias in meta.get("aliases", []):
            alias_norm = normalize(alias)
            if alias_norm:
                ALIAS_INDEX.setdefault(alias_norm, []).append(key)

    return ALIAS_INDEX


def load_catalog_from_csv(path):
    """
    Memuat katalog dari catalog_depo78_clean.csv dengan format khusus:

    - Header normal:
        kategori,varian,nama,harga,aliases,satuan,isi,brand
    - Setiap baris data DIBUNGKUS tanda kutip besar, misalnya:
        "galon,19l,Galon Aqua 19L,22000,""aqua galon 19l|galon aqua 19l|..."",galon,,aqua"

    Karena itu, kita perlu parsing 2x:
        1) csv.reader untuk melepas kutip luar → dapat 1 string
        2) csv.reader lagi untuk memecah menjadi 8 kolom sesuai header
    """

    # Lokasi file ini (modules/nlp_core.py)
    base_dir = os.path.dirname(os.path.abspath(__file__))

    # Root project = naik 1 folder dari /modules
    root_dir = os.path.abspath(os.path.join(base_dir, ".."))

    # Bangun path absolut final
    if os.path.isabs(path):
        abs_path = path
    else:
        abs_path = os.path.join(root_dir, path)

    if not os.path.exists(abs_path):
        raise FileNotFoundError(f"[ERROR] Katalog tidak ditemukan pada path: {abs_path}")

    catalog = {}

    with open(abs_path, encoding="utf-8") as f:
        # --- Baca header dan buang BOM ---
        header_line = f.readline().strip()
        header_line = header_line.lstrip("\ufeff")  # buang BOM kalau ada
        headers = [h.strip() for h in header_line.split(",")]
        # headers = ['kategori','varian','nama','harga','aliases','satuan','isi','brand']

        for raw_line in f:
            raw_line = raw_line.strip()
            if not raw_line:
                continue

            # 1) Lepas tanda kutip luar → dapat 1 field string panjang
            outer = next(csv.reader([raw_line]))
            if not outer:
                continue
            inner_line = outer[0]

            # 2) Pecah lagi string itu menjadi field-field sebenarnya
            cols = next(csv.reader([inner_line]))

            # Kalau jumlah kolom kurang dari header, pad dengan string kosong
            if len(cols) < len(headers):
                cols += [""] * (len(headers) - len(cols))

            row = dict(zip(headers, cols))

            # Gunakan 'nama' sebagai key (di file ini tidak ada kolom 'key')
            key = row.get("key") or row.get("id") or row.get("nama")
            if not key:
                continue

            # Aliases dipisah dengan '|'
            aliases = []
            if "aliases" in row and row["aliases"]:
                aliases = [a.strip() for a in row["aliases"].split("|")]

            # Harga → int aman
            harga_str = row.get("harga") or "0"
            try:
                harga = int(harga_str)
            except ValueError:
                harga = 0

            catalog[key] = {
                "kategori": (row.get("kategori") or "").strip().lower(),
                "varian": (row.get("varian") or "").strip().lower(),
                "nama": (row.get("nama") or "").strip(),
                "harga": harga,
                "brand": (row.get("brand") or "").strip().lower(),
                "aliases": aliases,
            }

    return catalog

# ================================================================
#                  NLP CORE — DETEKSI VARIAN, BRAND, ALIAS
# ================================================================

def detect_variant(tokens):
    joined = " ".join(tokens).replace(",", " ")

    # --- KG (3kg, 12kg, 3 kilo, dll)
    m = re.search(r"(\d+(?:\.\d+)?)\s*(kg|kilo|kilogram)\b", joined)
    if m:
        raw = m.group(1)
        if raw.endswith(".0"):
            raw = raw[:-2]
        return f"{raw}kg"

    # --- Liter (1.5l, 1l, 19l)
    m = re.search(r"(\d+(?:\.\d+)?)\s*(l|liter|ltr)\b", joined)
    if m:
        raw = m.group(1).replace(",", ".")
        return f"{raw}l"

    # --- ML (330ml, 600ml)
    m = re.search(r"(\d+)\s*(ml|mililiter)\b", joined)
    if m:
        return f"{m.group(1)}ml"

    # --- Galon (varian khusus air)
    if re.search(r"\b(galon|19l|19|isi ulang)\b", joined):
        return "19l"

    # --- 1.5 liter varian
    if re.search(r"\b(1,5ml|1.5ml|1/5ml|1,5|1.5|1/5)\b", joined):
        return "1.5ml"

    # --- 600ml
    if re.search(r"\b(600ml|600)\b", joined):
        return "600ml"

    # --- 500ml
    if re.search(r"\b(500ml|500)\b", joined):
        return "500ml"

    # --- 400ml
    if re.search(r"\b(400ml|400)\b", joined):
        return "400ml"

    # --- 330ml
    if re.search(r"\b(330ml|330)\b", joined):
        return "330ml"

    # --- 240ml
    if re.search(r"\b(240ml|240)\b", joined):
        return "240ml"

    return None


def detect_size_group(tokens):
    for group, cfg in SIZE_GROUP.items():
        if any(w in tokens for w in cfg["words"]):
            return group
    return None


def guess_variant_from_fragment(tokens):
    s = " ".join(tokens)

    if re.search(r"\b(gal|galon|19)\b", s):
        return "19l"

    if re.search(r"\b(bot|botol|1\.5|1,5|1/5)\b", s):
        return "1.5ml"

    if re.search(r"\b(bot|botol|600)\b", s):
        return "600ml"

    if re.search(r"\b(bot|botol|500)\b", s):
        return "500ml"

    if re.search(r"\b(bot|botol|400)\b", s):
        return "400ml"

    if re.search(r"\b(bot|botol|330)\b", s):
        return "330ml"

    if re.search(r"\b(cup|gelas|240)\b", s):
        return "240ml"

    return None


def guess_category(tokens):
    s = " ".join(tokens)
    if re.search(r"\b(gas|elpiji|lpg|bright|tabung|kg)\b", s):
        return "gas"
    if re.search(r"\b(air|galon|aqua|minerale|mineral|le|mineral|botol|dus|cup|gelas)\b", s):
        return "air"
    return None


def extract_brand_tokens(tokens):
    GENERIC_BRAND_WORDS = {"gas", "air"}
    out = []

    for t in tokens:
        if t in GENERIC_BRAND_WORDS:
            continue

        # exclude numbers / units
        if re.fullmatch(
            r"\d+|"
            r"\d+\.\d+|"
            r"\d+ml|"
            r"\d+\.\d+ml|"
            r"\d+l|"
            r"\d+\.\d+l|"
            r"kg|kilo|kilogram|liter|l|ltr|ml|mililiter|"
            r"galon|botol|dus|pack|karton|kardus|kerdus|pcs|buah|cup|gelas",
            t
        ):
            continue

        if len(t) > 30:
            continue

        out.append(t)

    return out


def find_brand_candidates(tokens, catalog):
    toks_norm = [normalize(t) for t in tokens]
    brand_tokens = extract_brand_tokens(toks_norm)
    if not brand_tokens:
        return []

    candidates = []
    seen = set()

    # 1) cocok dengan brand exact
    for bt in brand_tokens:
        for k, meta in catalog.items():
            b = (meta.get("brand") or "").strip().lower()
            if b == bt and k not in seen:
                seen.add(k)
                candidates.append(k)

    if candidates:
        return candidates

    # 2) cari pada nama + aliases
    for bt in brand_tokens:
        patt = re.compile(r"\b" + re.escape(bt) + r"\b")
        for k, meta in catalog.items():
            hay = " ".join([normalize(meta.get("nama", ""))] +
                           [normalize(a) for a in meta.get("aliases", [])])
            if patt.search(hay) and k not in seen:
                seen.add(k)
                candidates.append(k)

    return candidates


def alias_has_variant_info(alias_str):
    s = normalize(alias_str)
    if not s:
        return False

    if any(ch.isdigit() for ch in s):
        return True

    tokens = s.split()
    if any(tok in ALIAS_VARIANT_WORDS for tok in tokens):
        return True

    return False


def find_alias_candidates_from_text(text_norm):
    strong, weak = set(), set()

    for alias_norm, keys in ALIAS_INDEX.items():
        if alias_norm in text_norm:
            if alias_has_variant_info(alias_norm):
                strong.update(keys)
            else:
                weak.update(keys)

    return list(strong), list(weak)


def find_direct_alias_hits(text_norm):
    text_norm = normalize(text_norm)
    if not text_norm:
        return []

    exact = set()
    partial = set()

    for alias_norm, keys in ALIAS_INDEX.items():
        if text_norm == alias_norm:
            exact.update(keys)

    if exact:
        return list(exact)

    for alias_norm, keys in ALIAS_INDEX.items():
        if alias_norm in text_norm or text_norm in alias_norm:
            partial.update(keys)

    return list(partial)


def expand_quantity(tokens):
    UNIT_VARIAN = {"kg", "kilo", "kilogram", "l", "liter", "ltr", "ml", "mililiter"}
    QTY_UNITS = {"tabung", "galon", "botol", "dus", "karton",
                 "pack", "buah", "pcs", "pcs.", "cup", "gelas"}

    s = " ".join(tokens)

    # explicit "3 botol"
    m = re.search(r"\b(\d+)\s*(" + "|".join(QTY_UNITS) + r")\b", s)
    if m:
        try:
            return max(1, int(m.group(1)))
        except Exception:
            pass

    # strip variant-number combos
    s_wo = re.sub(r"\b\d+(?:\.\d+)?\s*(kg|kilo|kilogram|l|liter|ltr|ml|mililiter)\b", " ", s)
    s_wo = re.sub(r"\s+", " ", s_wo).strip()
    toks = s_wo.split()

    for i, t in enumerate(toks):
        if t.isdigit():
            n = int(t)
            nxt = toks[i + 1] if i + 1 < len(toks) else ""
            if nxt in UNIT_VARIAN:
                continue
            return n

    m2 = re.search(r"\b(\d+)\b", s_wo)
    if m2:
        return max(1, int(m2.group(1)))

    return 1

def detect_explicit_qty(tokens, variant=None, variant_numbers=None):
    """
    Return: (qty:int|None, has_explicit:bool)

    RULE:
    - Angka varian (600/330/240 dst), dengan atau tanpa 'ml', HARUS dianggap VARIAN, bukan qty.
    - qty hanya diambil jika eksplisit dan bukan varian.
    """
    UNIT_VARIAN = {"kg", "kilo", "kilogram", "l", "liter", "ltr", "ml", "mililiter"}
    QTY_UNITS = {"tabung", "galon", "botol", "dus", "karton", "pack", "buah", "pcs", "pcs.", "cup", "gelas"}

    # angka varian dari katalog (prioritas dataset)
    var_nums = set(variant_numbers or set())
    # fallback hard safety (kalau belum kebangun)
    if not var_nums:
        var_nums |= {"1500", "600", "500", "400", "350", "330", "240", "19", "1.5"}

    s = " ".join(tokens)

    # 1) pola eksplisit qty dengan satuan qty: "3 botol", "2 dus", dst
    m = re.search(r"\b(\d+)\s*(" + "|".join(QTY_UNITS) + r")\b", s)
    if m:
        n = int(m.group(1))
        return (max(1, n), True)

    # normalisasi varian yang sudah terdeteksi
    v = (variant or "").strip().lower()  # contoh: "600ml", "3kg", "1.5ml", "19l"

    # buang pola varian yang pakai unit (600ml, 3kg, 1.5l, dst)
    s_wo = re.sub(r"\b\d+(?:\.\d+)?\s*(kg|kilo|kilogram|l|liter|ltr|ml|mililiter)\b", " ", s)
    s_wo = re.sub(r"\s+", " ", s_wo).strip()

    parts = s_wo.split()

    # 2) angka digit: ambil sebagai qty HANYA jika bukan varian
    for t in parts:
        # skip decimal untuk qty (qty harus integer)
        if re.fullmatch(r"\d+\.\d+", t):
            # kalau decimal ini varian (mis 1.5) -> abaikan (bukan qty)
            continue

        if t.isdigit():
            # ✅ jika angka ini termasuk varian dari katalog -> bukan qty
            if t in var_nums:
                continue

            # ✅ jika varian sudah terdeteksi dan angka ini bagian dari varian -> bukan qty
            # contoh v="600ml" dan t="600"
            if v and (t in v):
                continue

            return (max(1, int(t)), True)

    # 3) kata angka: "dua", "tiga", dst (ini boleh jadi qty)
    # tapi jika user bilang "dua liter" itu varian (skip)
    for i, t in enumerate(tokens):
        if t in NUM_WORDS:
            nxt = tokens[i + 1] if i + 1 < len(tokens) else ""
            if nxt in UNIT_VARIAN:
                continue
            return (max(1, int(NUM_WORDS[t])), True)

    # tidak ada qty eksplisit
    return (None, False)

def select_best_candidate(candidates, variant, category, tokens, catalog):
    if not candidates:
        return None

    # exact varian match
    exacts = []
    for k in candidates:
        meta = catalog[k]
        if variant and meta.get("varian") == variant and (not category or meta.get("kategori") == category):
            exacts.append(k)

    if len(exacts) == 1:
        return exacts[0]
    if len(exacts) > 1:
        candidates = exacts

    token_set = set(tokens)
    scored = []

    for k in candidates:
        meta = catalog[k]
        hay = " ".join([normalize(meta.get("nama", ""))] +
                       [normalize(a) for a in meta.get("aliases", [])])
        score = sum(1 for t in token_set if t in hay)

        name_first = normalize(meta.get("nama", "")).split()[0]
        if name_first in token_set:
            score += 2

        scored.append((score, k))

    scored.sort(key=lambda x: (-x[0], x[1]))

    return scored[0][1] if scored and scored[0][0] > 0 else candidates[0]

def find_all_keys_for_varian(category, varian, catalog):
    """
    Ambil semua produk dengan varian tertentu.
    Jika pakai kategori tapi tidak ketemu, fallback abaikan kategori.
    """
    results = []
    for k, meta in catalog.items():
        if (meta.get("varian") or "").lower() == (varian or "").lower() and (not category or meta.get("kategori") == category):
            results.append(k)

    if not results and category:
        for k, meta in catalog.items():
            if (meta.get("varian") or "").lower() == (varian or "").lower():
                results.append(k)
    return results


def find_products_by_size_group(size_group, catalog):
    patterns = SIZE_GROUP[size_group]["patterns"]
    results = []
    for k, meta in catalog.items():
        varian = (meta.get("varian") or "").lower()
        if any(p in varian for p in patterns):
            results.append(k)
    return results

# ================================================================
#           NLP CORE — PARSER UTAMA (MULTI-ITEM ORDER)
# ================================================================

def parse_orders_verbose(text, catalog):
    """
    Porting LOGIC PRIORITAS CP12 (CLI) ke WEB.

    Output per-chunk:
    - Jika sudah jelas: chosen_item terisi
    - Jika ambigu / perlu tanya: chosen_item None + need_action terisi

    need_action.type:
      - "choose_item"             -> tampilkan list produk untuk dipilih user
      - "choose_brand_then_item"  -> user pilih brand dulu, lalu pilih produk (dengan filter tertentu)
    """

    def _uniq(seq):
        return list(dict.fromkeys(seq))

    def _as_options(keys):
        opts = []
        for k in keys:
            if k not in catalog:
                continue
            m = catalog[k]
            opts.append({
                "key": k,
                "label": f"{m.get('nama')} (Rp {m.get('harga',0):,})",
                "nama": m.get("nama"),
                "harga": m.get("harga", 0),
                "brand": (m.get("brand") or "").lower(),
                "kategori": (m.get("kategori") or "").lower(),
                "varian": (m.get("varian") or "").lower(),
            })
        return opts

    def _keys_by_brand(brand_value):
        b = (brand_value or "").lower().strip()
        if not b:
            return []
        return [k for k, m in catalog.items() if (m.get("brand") or "").lower().strip() == b]

    def _filter_no_galon(keys):
        out = []
        for k in keys:
            m = catalog.get(k, {})
            kat = (m.get("kategori") or "").lower()
            var = (m.get("varian") or "").lower()
            nama = normalize(m.get("nama") or "")
            # buang galon/19l
            if "galon" in kat or var == "19l" or "19l" in var or "galon" in nama:
                continue
            out.append(k)
        return out

    def _filter_botol_only(keys):
        out = []
        for k in keys:
            m = catalog.get(k, {})
            kat = (m.get("kategori") or "").lower()
            nama = normalize(m.get("nama") or "")
            if kat == "botol" or "botol" in nama:
                out.append(k)
        return out

    def _filter_botol_or_cup(keys):
        out = []
        for k in keys:
            m = catalog.get(k, {})
            kat = (m.get("kategori") or "").lower()
            var = (m.get("varian") or "").lower()
            nama = normalize(m.get("nama") or "")

            # ✅ kandidat air kemasan (non-galon):
            # - kategori botol/cup
            # - atau nama mengandung botol/cup/gelas
            # - atau varian berisi ukuran ml (mis: 600ml, 1500ml, 330ml) yang umumnya botol/cup
            is_pack = (
                kat in {"botol", "cup"}
                or ("botol" in nama)
                or ("cup" in nama)
                or ("gelas" in nama)
                or ("ml" in var)
                or ("ml" in nama)
            )

            if is_pack:
                out.append(k)
        return out

    def _all_brands():
        s = set()
        for m in catalog.values():
            b = (m.get("brand") or "").strip().lower()
            if b:
                s.add(b)
        return sorted(s)

    def _brands_from_keys(keys):
        s = set()
        for k in keys:
            b = (catalog.get(k, {}).get("brand") or "").strip().lower()
            if b:
                s.add(b)
        return sorted(s)

    text_norm = normalize(text)
    if not text_norm:
        return []

    # split chunk mirip CP12: "dan", koma, lalu, terus
    tokens_all = text_norm.split()
    chunks, cur = [], []
    for t in tokens_all:
        if t in {"dan", ",", "terus", "lalu"}:
            if cur:
                chunks.append(cur)
                cur = []
        else:
            cur.append(t)
    if cur:
        chunks.append(cur)
    if not chunks:
        chunks = [tokens_all]

    results = []

    ALL_BRANDS = set(_all_brands())

    for chunk_tokens in chunks:
        if not chunk_tokens:
            continue

        # buang stopword (mirip CP12)
        tokens = [w for w in chunk_tokens if w and w not in STOPWORDS]
        token_set = set(tokens)
        s_chunk = " ".join(tokens)

        variant = detect_variant(tokens) or guess_variant_from_fragment(tokens)
        size_group = detect_size_group(tokens)
        category = guess_category(tokens)
        qty, has_explicit_qty = detect_explicit_qty(
            tokens,
            variant=variant,
            variant_numbers=CATALOG_VARIANT_NUMBERS
        )


        # ✅ SAMAKAN LOGIKA: kalau user bilang "air 600/330/240/1.5/19"
        # dan tidak menyebut kata "tanggung/cup/kecil/galon", kita tetap isi size_group.
        if (not size_group) and variant:
            # umumnya untuk air kemasan
            sg_from_var = size_group_from_variant(variant)
            if sg_from_var:
                size_group = sg_from_var

        # brand candidates (produk-produk yang match brand token)
        brand_keys = find_brand_candidates(tokens, catalog)
        brand_keys = [k for k in brand_keys if k in catalog]
        brands_hit = _brands_from_keys(brand_keys)

        explicit_brand = brands_hit[0] if len(brands_hit) == 1 else None

        # alias strong/weak
        strongs, weaks = find_alias_candidates_from_text(s_chunk)


        # alias strong/weak
        strongs, weaks = find_alias_candidates_from_text(s_chunk)
        strongs = [k for k in strongs if k in catalog]
        weaks = [k for k in weaks if k in catalog]

        # direct alias
        direct = find_direct_alias_hits(s_chunk)
        direct = [k for k in direct if k in catalog]

        # flags
        has_packaging = any(t in PACKAGING_WORDS for t in token_set)
        has_botol = ("botol" in token_set)
        has_gas_hint = any(t in {"gas", "elpiji", "lpg", "bright"} for t in token_set) or (category == "gas")

        # sebelum blok: if direct:  (LOGIC 0)
        # paksa packaging lebih prioritas daripada direct alias kalau brand belum jelas
        if has_packaging and (not explicit_brand):
            direct = []   # matikan direct alias supaya jatuh ke LOGIC packaging

        # -----------------------------
        # LOGIC 0 — DIRECT ALIAS (PRIORITAS TERTINGGI, TAPI HARUS SPESIFIK)
        # -----------------------------
        if direct:
            # DIRECT ALIAS hanya boleh jalan kalau chunk "spesifik"
            # (misal ada angka/varian/gas/galon/botol/cup/packaging)
            has_digit = any(t.isdigit() for t in tokens)
            has_packaging = any(t in PACKAGING_WORDS for t in token_set)
            has_container = any(t in {"galon", "botol", "cup", "gelas"} for t in token_set)
            has_gas_hint = any(t in {"gas", "elpiji", "lpg", "bright"} for t in token_set) or (category == "gas")
            # variant sudah kamu deteksi dari detect_variant()/guess_variant
            has_specific = bool(variant) or has_digit or has_packaging or has_container or has_gas_hint

            # Kalau tidak spesifik (contoh: "aqua tanggung", "aqua sedang", "aqua") → jangan pakai direct alias
            if not has_specific:
                direct = []  # force skip ke logic berikutnya
            else:
                direct = list(dict.fromkeys([k for k in direct if k in catalog]))

                if len(direct) == 1:
                    chosen = direct[0]
                    results.append({
                        "text": text,
                        "chunk": s_chunk,
                        "kategori": category,
                        "variant": variant,
                        "size_group": size_group,
                        "qty": qty,
                        "has_explicit_qty": has_explicit_qty,
                        "candidates_all": direct,
                        "chosen_key": chosen,
                        "chosen_item": catalog[chosen],
                        "need_action": None,
                        "logic": "L0_DIRECT_ALIAS_SINGLE",
                    })
                    continue

                if len(direct) > 1:
                    results.append({
                        "text": text,
                        "chunk": s_chunk,
                        "kategori": category,
                        "variant": variant,
                        "size_group": size_group,
                        "qty": qty,
                        "has_explicit_qty": has_explicit_qty,
                        "candidates_all": direct,
                        "chosen_key": None,
                        "chosen_item": None,
                        "need_action": {
                            "type": "choose_item",
                            "title": "Saya menemukan beberapa produk yang cocok. Pilih salah satu:",
                            "options": direct,
                        },
                        "logic": "L0_DIRECT_ALIAS_MULTI",
                    })
                    continue

        # -----------------------------
        # LOGIC 1 — GAS
        # -----------------------------
        if has_gas_hint:
            gas_keys = [k for k, m in catalog.items() if (m.get("kategori") or "").lower() == "gas"]
            gas_keys = _uniq(gas_keys)

            if len(gas_keys) == 1:
                chosen = gas_keys[0]
                results.append({
                    "text": text,
                    "chunk": " ".join(chunk_tokens),
                    "kategori": "gas",
                    "variant": variant,
                    "size_group": size_group,
                    "qty": qty,
                    "has_explicit_qty": has_explicit_qty,
                    "candidates_all": gas_keys,
                    "chosen_key": chosen,
                    "chosen_item": catalog.get(chosen),
                    "need_action": None,
                    "logic": "L1_GAS_SINGLE",
                })
                continue

            results.append({
                "text": text,
                "chunk": " ".join(chunk_tokens),
                "kategori": "gas",
                "variant": variant,
                "size_group": size_group,
                "qty": qty,
                "has_explicit_qty": has_explicit_qty,
                "candidates_all": gas_keys,
                "chosen_key": None,
                "chosen_item": None,
                "need_action": {
                    "type": "choose_item",
                    "title": "Mau gas yang mana?",
                    "options": _as_options(gas_keys),
                },
                "logic": "L1_GAS_MULTI",
            })
            continue

        # -----------------------------
        # LOGIC 2 — SIZE GROUP (CP12 + AUTO PICK jika brand jelas)
        # -----------------------------
        if size_group:
            patterns = SIZE_GROUP[size_group]["patterns"]  # contoh medium: ["600","500"]

            # tentukan brand_name jika brand terdeteksi
            brand_name = None
            if brand_keys:
                brand_name = (catalog[brand_keys[0]].get("brand") or "").strip().lower()

            sg_keys = []
            for k, meta in catalog.items():
                # kalau brand diketahui → filter per brand
                if brand_name:
                    b = (meta.get("brand") or "").strip().lower()
                    if b != brand_name:
                        continue

                var = (meta.get("varian") or "").strip().lower()
                nama = normalize(meta.get("nama") or "")

                if any(p in var for p in patterns) or any(p in nama for p in patterns):
                    sg_keys.append(k)

            sg_keys = list(dict.fromkeys(sg_keys))

            if sg_keys:
                # ✅ AUTO PICK jika brand jelas:
                # pilih berdasarkan urutan patterns (misal ["600","500"] → cari 600 dulu)
                if brand_name:
                    picked = None
                    for ptn in patterns:
                        for k in sg_keys:
                            meta = catalog.get(k, {})
                            var = (meta.get("varian") or "").lower()
                            nama = normalize(meta.get("nama") or "")
                            if (ptn in var) or (ptn in nama):
                                picked = k
                                break
                        if picked:
                            break

                    if picked:
                        results.append({
                            "text": text,
                            "chunk": s_chunk,
                            "kategori": category,
                            "variant": variant,
                            "size_group": size_group,
                            "qty": qty,
                            "has_explicit_qty": has_explicit_qty,
                            "candidates_all": sg_keys,
                            "chosen_key": picked,
                            "chosen_item": catalog[picked],
                            "need_action": None,
                            "logic": "L2_SIZE_GROUP_AUTO_PICK",
                        })
                        continue
                    # kalau gagal auto-pick (harusnya jarang), fallback ke choose_item

                # kalau brand tidak jelas → baru minta pilih
                if len(sg_keys) == 1:
                    chosen = sg_keys[0]
                    results.append({
                        "text": text,
                        "chunk": s_chunk,
                        "kategori": category,
                        "variant": variant,
                        "size_group": size_group,
                        "qty": qty,
                        "has_explicit_qty": has_explicit_qty,
                        "candidates_all": sg_keys,
                        "chosen_key": chosen,
                        "chosen_item": catalog[chosen],
                        "need_action": None,
                        "logic": "L2_SIZE_GROUP_SINGLE"
                    })
                else:
                    results.append({
                        "text": text,
                        "chunk": s_chunk,
                        "kategori": category,
                        "variant": variant,
                        "size_group": size_group,
                        "qty": qty,
                        "has_explicit_qty": has_explicit_qty,
                        "candidates_all": sg_keys,
                        "chosen_key": None,
                        "chosen_item": None,
                        "need_action": {
                            "type": "choose_item",
                            "title": f"Anda menyebut ukuran '{size_group}'. Pilih produk yang Anda maksud:",
                            "options": sg_keys,
                        },
                        "logic": "L2_SIZE_GROUP_MULTI"
                    })
                continue

        # -----------------------------
        # LOGIC 3 — VARIAN SAJA
        # -----------------------------
        # kondisi: varian ada, tapi brand tidak jelas
        if variant and not explicit_brand and not brands_hit:
            var_keys = find_all_keys_for_varian(category, variant, catalog)
            var_keys = [k for k in var_keys if k in catalog]
            var_keys = _uniq(var_keys)

            # kalau varian ketemu banyak brand -> pilih brand dulu (CLI-like)
            brands_var = _brands_from_keys(var_keys)
            if len(brands_var) > 1:
                results.append({
                    "text": text,
                    "chunk": " ".join(chunk_tokens),
                    "kategori": category,
                    "variant": variant,
                    "size_group": size_group,
                    "qty": qty,
                    "has_explicit_qty": has_explicit_qty,
                    "candidates_all": var_keys,
                    "chosen_key": None,
                    "chosen_item": None,
                    "need_action": {
                        "type": "choose_brand_then_item",
                        "title": f"Varian '{variant}' ada di beberapa brand. Pilih brand dulu:",
                        "brand_options": brands_var,
                        "filter": {
                            "mode": "varian_only",
                            "variant": variant,
                            "category": category,
                        },
                    },
                    "logic": "L3_VARIAN_ONLY_BRAND_FIRST",
                })
                continue

            if len(var_keys) == 1:
                chosen = var_keys[0]
                results.append({
                    "text": text,
                    "chunk": " ".join(chunk_tokens),
                    "kategori": category,
                    "variant": variant,
                    "size_group": size_group,
                    "qty": qty,
                    "has_explicit_qty": has_explicit_qty,
                    "candidates_all": var_keys,
                    "chosen_key": chosen,
                    "chosen_item": catalog.get(chosen),
                    "need_action": None,
                    "logic": "L3_VARIAN_ONLY_SINGLE",
                })
                continue

            results.append({
                "text": text,
                "chunk": " ".join(chunk_tokens),
                "kategori": category,
                "variant": variant,
                "size_group": size_group,
                "qty": qty,
                "has_explicit_qty": has_explicit_qty,
                "candidates_all": var_keys,
                "chosen_key": None,
                "chosen_item": None,
                "need_action": {
                    "type": "choose_item",
                    "title": f"Pilih produk untuk varian '{variant}':",
                    "options": _as_options(var_keys),
                },
                "logic": "L3_VARIAN_ONLY_MULTI",
            })
            continue

        # -----------------------------
        # LOGIC 4 — BOTOL / PACKAGING
        # -----------------------------
        # A) "botol" -> 2 tahap: pilih brand lalu varian botol (tanpa cup/galon)
        if has_botol:
            if explicit_brand:
                keys = _keys_by_brand(explicit_brand)
                keys = _filter_botol_only(keys)
                keys = _uniq(keys)

                if len(keys) == 1:
                    chosen = keys[0]
                    results.append({
                        "text": text,
                        "chunk": " ".join(chunk_tokens),
                        "kategori": category,
                        "variant": variant,
                        "size_group": size_group,
                        "qty": qty,
                        "has_explicit_qty": has_explicit_qty,
                        "candidates_all": keys,
                        "chosen_key": chosen,
                        "chosen_item": catalog.get(chosen),
                        "need_action": None,
                        "logic": "L4_BOTOL_SINGLE",
                    })
                    continue

                results.append({
                    "text": text,
                    "chunk": " ".join(chunk_tokens),
                    "kategori": category,
                    "variant": variant,
                    "size_group": size_group,
                    "qty": qty,
                    "has_explicit_qty": has_explicit_qty,
                    "candidates_all": keys,
                    "chosen_key": None,
                    "chosen_item": None,
                    "need_action": {
                        "type": "choose_item",
                        "title": f"Pilih varian botol untuk brand '{explicit_brand}':",
                        "options": _as_options(keys),
                    },
                    "logic": "L4_BOTOL_MULTI",
                })
                continue

            # brand belum jelas -> pilih brand dulu (yang punya botol)
            brand_list = []
            for b in _all_brands():
                keys_b = _filter_botol_only(_keys_by_brand(b))
                if keys_b:
                    brand_list.append(b)

            results.append({
                "text": text,
                "chunk": " ".join(chunk_tokens),
                "kategori": category,
                "variant": variant,
                "size_group": size_group,
                "qty": qty,
                "has_explicit_qty": has_explicit_qty,
                "candidates_all": [],
                "chosen_key": None,
                "chosen_item": None,
                "need_action": {
                    "type": "choose_brand_then_item",
                    "title": "Anda mau brand botol yang mana?",
                    "brand_options": brand_list,
                    "filter": {"mode": "botol_only"},
                },
                "logic": "L4_BOTOL_BRAND_FIRST",
            })
            continue

        # B) PACKAGING WORDS: dus/kardus/box -> brand tsb, varian botol & cup, TANPA GALON
        if has_packaging:
            if explicit_brand:
                keys = _keys_by_brand(explicit_brand)
                keys = _filter_botol_or_cup(keys)
                keys = _filter_no_galon(keys)
                keys = _uniq(keys)

                results.append({
                    "text": text,
                    "chunk": " ".join(chunk_tokens),
                    "kategori": category,
                    "variant": variant,
                    "size_group": size_group,
                    "qty": qty,
                    "has_explicit_qty": has_explicit_qty,
                    "candidates_all": keys,
                    "chosen_key": None,
                    "chosen_item": None,
                    "need_action": {
                        "type": "choose_item",
                        "title": f"Anda menyebut kemasan dus/kardus. Pilih varian botol/cup untuk brand '{explicit_brand}' (tanpa galon):",
                        "options": _as_options(keys),
                    },
                    "logic": "L4_PACKAGING_BRAND_KNOWN",
                })
                continue

            # brand belum ada -> pilih brand dulu
            brand_list = []
            for b in _all_brands():
                keys_b = _filter_no_galon(_filter_botol_or_cup(_keys_by_brand(b)))
                if keys_b:
                    brand_list.append(b)
                    
            # fallback kalau filter terlalu ketat / data kategori tidak konsisten
            if not brand_list:
                for b in _all_brands():
                    keys_b = _filter_no_galon(_keys_by_brand(b))  # tanpa botol_or_cup
                    if keys_b:
                        brand_list.append(b)

            results.append({
                "text": text,
                "chunk": " ".join(chunk_tokens),
                "kategori": category,
                "variant": variant,
                "size_group": size_group,
                "qty": qty,
                "has_explicit_qty": has_explicit_qty,
                "candidates_all": [],
                "chosen_key": None,
                "chosen_item": None,
                "need_action": {
                    "type": "choose_brand_then_item",
                    "title": "Kemasan dus/kardus/box untuk brand apa?",
                    "brand_options": brand_list,
                    "filter": {"mode": "packaging_no_galon"},
                },
                "logic": "L4_PACKAGING_BRAND_FIRST",
            })
            continue

        # -----------------------------
        # LOGIC 4C — "AIR MINERAL" GENERIC -> PILIH BRAND DULU
        # (perlakuan sama seperti dus/kardus: brand -> varian -> qty)
        # -----------------------------
        is_air_mineral = ("air" in token_set and "mineral" in token_set)

        if is_air_mineral and (not explicit_brand) and (not variant) and (not size_group):
            # definisi "produk air": kategori botol/cup/galon (bukan gas)
            def _is_air_product(meta):
                kat = (meta.get("kategori") or "").lower()
                nama = normalize(meta.get("nama") or "")
                return (kat in {"botol", "cup", "galon"}) or ("galon" in nama) or ("botol" in nama) or ("cup" in nama) or ("gelas" in nama)

            # ambil brand yang punya produk air
            brand_list = []
            for b in _all_brands():
                keys_b = _keys_by_brand(b)
                keys_b = [k for k in keys_b if _is_air_product(catalog.get(k, {}))]
                if keys_b:
                    brand_list.append(b)

            results.append({
                "text": text,
                "chunk": " ".join(chunk_tokens),
                "kategori": "air",
                "variant": variant,
                "size_group": size_group,
                "qty": qty,
                "has_explicit_qty": has_explicit_qty,
                "candidates_all": [],
                "chosen_key": None,
                "chosen_item": None,
                "need_action": {
                    "type": "choose_brand_then_item",
                    "title": "Anda mau **brand air mineral** yang mana?",
                    "brand_options": brand_list,
                    "filter": {"mode": "air_all"},   # mode baru utk UI
                },
                "logic": "L4C_AIR_MINERAL_BRAND_FIRST",
            })
            continue

        # -----------------------------
        # LOGIC 5 — BRAND ONLY
        # -----------------------------
        if explicit_brand and not variant and not size_group:
            keys = _keys_by_brand(explicit_brand)
            keys = _uniq(keys)

            # CLI: brand-only tidak auto pilih
            results.append({
                "text": text,
                "chunk": " ".join(chunk_tokens),
                "kategori": category,
                "variant": variant,
                "size_group": size_group,
                "qty": qty,
                "has_explicit_qty": has_explicit_qty,
                "candidates_all": keys,
                "chosen_key": None,
                "chosen_item": None,
                "need_action": {
                    "type": "choose_item",
                    "title": f"Anda menyebut brand '{explicit_brand}'. Pilih varian/produk yang Anda maksud:",
                    "options": _as_options(keys),
                },
                "logic": "L5_BRAND_ONLY",
            })
            continue

        # Jika token brand ambigu (lebih dari 1 brand ketemu)
        if len(brands_hit) > 1 and not variant and not size_group:
            results.append({
                "text": text,
                "chunk": " ".join(chunk_tokens),
                "kategori": category,
                "variant": variant,
                "size_group": size_group,
                "qty": qty,
                "has_explicit_qty": has_explicit_qty,
                "candidates_all": [],
                "chosen_key": None,
                "chosen_item": None,
                "need_action": {
                    "type": "choose_brand_then_item",
                    "title": "Saya menemukan beberapa kemungkinan brand. Pilih brand dulu:",
                    "brand_options": brands_hit,
                    "filter": {"mode": "brand_only"},
                },
                "logic": "L5_BRAND_AMBIGUOUS",
            })
            continue

        # -----------------------------
        # LOGIC 6 — ALIAS UMUM (WEAK)
        # -----------------------------
        if weaks:
            keys = _uniq(weaks)
            results.append({
                "text": text,
                "chunk": " ".join(chunk_tokens),
                "kategori": category,
                "variant": variant,
                "size_group": size_group,
                "qty": qty,
                "has_explicit_qty": has_explicit_qty,
                "candidates_all": keys,
                "chosen_key": None,
                "chosen_item": None,
                "need_action": {
                    "type": "choose_item",
                    "title": "Maksud Anda yang mana?",
                    "options": _as_options(keys),
                },
                "logic": "L6_ALIAS_UMUM",
            })
            continue

        # -----------------------------
        # LOGIC 7 — KATEGORI
        # -----------------------------
        if category:
            keys = [k for k, m in catalog.items() if (m.get("kategori") or "").lower() == category]
            keys = _uniq(keys)
            results.append({
                "text": text,
                "chunk": " ".join(chunk_tokens),
                "kategori": category,
                "variant": variant,
                "size_group": size_group,
                "qty": qty,
                "has_explicit_qty": has_explicit_qty,
                "candidates_all": keys,
                "chosen_key": None,
                "chosen_item": None,
                "need_action": {
                    "type": "choose_item",
                    "title": f"Anda menyebut kategori '{category}'. Pilih produk:",
                    "options": _as_options(keys),
                },
                "logic": "L7_KATEGORI",
            })
            continue

        # -----------------------------
        # FALLBACK: strong alias (kalau ada) / atau pool kosong
        # -----------------------------
        if strongs:
            keys = _uniq(strongs)
            results.append({
                "text": text,
                "chunk": " ".join(chunk_tokens),
                "kategori": category,
                "variant": variant,
                "size_group": size_group,
                "qty": qty,
                "has_explicit_qty": has_explicit_qty,
                "candidates_all": keys,
                "chosen_key": None,
                "chosen_item": None,
                "need_action": {
                    "type": "choose_item",
                    "title": "Saya menemukan beberapa kemungkinan. Pilih salah satu:",
                    "options": _as_options(keys),
                },
                "logic": "FALLBACK_STRONG_ALIAS",
            })
            continue

        results.append({
            "text": text,
            "chunk": " ".join(chunk_tokens),
            "kategori": category,
            "variant": variant,
            "size_group": size_group,
            "qty": qty,
            "has_explicit_qty": has_explicit_qty,
            "candidates_all": [],
            "chosen_key": None,
            "chosen_item": None,
            "need_action": None,
            "logic": "NO_MATCH",
        })

    return results

# ================================================================
#               TOP-LEVEL NLP CALL (DIPAKAI order_engine)
# ================================================================

def main(user_data, text):
    """
    Wrapper utama untuk versi WEB.

    - Menggunakan GLOBAL_CATALOG yang di-set oleh register_catalog()
    - Mengembalikan list hasil parse_orders_verbose (CP12 original).
    """
    global GLOBAL_CATALOG

    if not GLOBAL_CATALOG:
        raise RuntimeError(
            "GLOBAL_CATALOG kosong. Pastikan init_nlp() sudah memanggil register_catalog()."
        )

    return parse_orders_verbose(text, GLOBAL_CATALOG)

def build_variant_numbers_from_catalog(catalog):
    """
    Ambil angka-angka yang dianggap VARIAN dari field meta['varian'] katalog.
    Contoh:
      "600ml" -> "600"
      "1.5l"  -> "1.5"
      "19l"   -> "19"
    """
    nums = set()

    for _, meta in (catalog or {}).items():
        v = (meta.get("varian") or "").strip().lower()
        if not v:
            continue

        # ambil angka (integer/decimal) dari string varian
        found = re.findall(r"\d+(?:\.\d+)?", v)
        for x in found:
            x = x.strip()
            if not x:
                continue
            # normalisasi "1.0" -> "1"
            if x.endswith(".0"):
                x = x[:-2]
            nums.add(x)

    # tambahkan juga angka varian umum (air) biar aman walau katalog tidak konsisten
    nums |= {"1500", "600", "500", "400", "350", "330", "240", "19", "1.5"}

    return nums

def register_catalog(catalog):
    """
    Dipanggil sekali dari order_engine.init_nlp().
    Menyimpan catalog ke global + membangun ALIAS_INDEX + VARIANT NUMBERS.
    """
    global GLOBAL_CATALOG, CATALOG_VARIANT_NUMBERS
    GLOBAL_CATALOG = catalog
    build_alias_index(catalog)

    # ✅ penting: angka varian dari dataset/katalog
    CATALOG_VARIANT_NUMBERS = build_variant_numbers_from_catalog(catalog)
