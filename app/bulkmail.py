"""Toplu mail: Excel/CSV listesi okuma, kişiselleştirme ve gönderim yardımcıları.

- Excel (.xlsx) yalnızca standart kütüphaneyle okunur (zipfile + XML); ek
  bağımlılık gerekmez. .csv için stdlib csv kullanılır (Türkçe dosyalar için
  utf-8-sig → cp1254 → latin-1 sırasıyla kodlama denenir).
- Şablonlarda {sütun} yer tutucuları satır verisiyle değiştirilir.
- Gönderim, hesabın kendi SMTP'si üzerinden tek bağlantı açılarak yapılır;
  her mail için yeniden bağlanmak yavaştır ve sunucular tarafından
  hız sınırı/spam olarak değerlendirilebilir.
"""
import csv
import io
import re
import tempfile
import zipfile
from xml.etree import ElementTree as ET

_NS = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
_EMAIL_RE = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")
_PLACEHOLDER_RE = re.compile(r"\{\s*([^}]+?)\s*\}")

MAX_ROWS = 5000          # tek listede işlenecek en fazla satır
PREVIEW_ROWS = 5


def is_email(value) -> bool:
    return bool(value) and bool(_EMAIL_RE.match(str(value).strip()))


def render_template(template: str, row: dict) -> str:
    """'Merhaba {isim}' → satırdaki değerle doldurur; bilinmeyen alan boş kalır."""
    if not template:
        return ""
    def sub(m: re.Match) -> str:
        val = row.get(m.group(1))
        return "" if val is None else str(val)
    return _PLACEHOLDER_RE.sub(sub, template)


def placeholders_used(template: str) -> set[str]:
    return {m.group(1) for m in _PLACEHOLDER_RE.finditer(template or "")}


# ---- xlsx ----

def _col_index(ref: str) -> int:
    """'A1' → 0, 'B2' → 1, 'AA5' → 26 (hücre referansından sütun sırası)."""
    idx = 0
    for ch in ref:
        if not ch.isalpha():
            break
        idx = idx * 26 + (ord(ch.upper()) - 64)
    return idx - 1


def _cell_text(cell: ET.Element, shared: list[str]) -> str:
    ctype = cell.get("t", "")
    if ctype == "inlineStr":
        node = cell.find(f"{_NS}is")
        return "".join(t.text or "" for t in node.iter(f"{_NS}t")) if node is not None else ""
    value = cell.find(f"{_NS}v")
    if value is None or value.text is None:
        return ""
    raw = value.text
    if ctype == "s":                       # paylaşılan metin tablosu
        try:
            return shared[int(raw)]
        except (ValueError, IndexError):
            return ""
    if ctype in ("str", "e"):              # formül sonucu / hata
        return raw
    # sayısal: tam sayıysa ondalık gösterme (1234.0 → 1234)
    try:
        num = float(raw)
        return str(int(num)) if num.is_integer() else str(num)
    except ValueError:
        return raw


def _parse_xlsx(data: bytes) -> list[list[str]]:
    with zipfile.ZipFile(io.BytesIO(data)) as z:
        shared: list[str] = []
        if "xl/sharedStrings.xml" in z.namelist():
            root = ET.fromstring(z.read("xl/sharedStrings.xml"))
            for si in root.iter(f"{_NS}si"):
                shared.append("".join(t.text or "" for t in si.iter(f"{_NS}t")))
        sheets = sorted(n for n in z.namelist() if n.startswith("xl/worksheets/sheet"))
        if not sheets:
            raise ValueError("Excel dosyasında sayfa bulunamadı.")
        root = ET.fromstring(z.read(sheets[0]))
        table: list[list[str]] = []
        for row in root.iter(f"{_NS}row"):
            cells: list[str] = []
            for cell in row.findall(f"{_NS}c"):
                pos = _col_index(cell.get("r", "")) if cell.get("r") else len(cells)
                while len(cells) < pos:      # atlanan boş hücreleri doldur
                    cells.append("")
                cells.append(_cell_text(cell, shared).strip())
            table.append(cells)
    return table


# ---- csv ----

def _parse_csv(data: bytes) -> list[list[str]]:
    text = None
    for enc in ("utf-8-sig", "cp1254", "latin-1"):
        try:
            text = data.decode(enc)
            break
        except UnicodeDecodeError:
            continue
    if text is None:
        raise ValueError("CSV dosyasının karakter kodlaması okunamadı.")
    sample = text[:4096]
    try:
        dialect = csv.Sniffer().sniff(sample, delimiters=",;\t|")
    except csv.Error:
        dialect = csv.excel
        dialect.delimiter = ";" if sample.count(";") > sample.count(",") else ","
    return [[(c or "").strip() for c in row] for row in csv.reader(io.StringIO(text), dialect)]


def _parse_numbers(data: bytes) -> list[list[str]]:
    try:
        from numbers_parser import Document
    except Exception:
        raise ValueError("Numbers dosyası için 'numbers-parser' bağımlılığı gerekli.")

    with tempfile.NamedTemporaryFile(suffix=".numbers") as tmp:
        tmp.write(data)
        tmp.flush()
        doc = Document(tmp.name)

    if not doc.sheets:
        raise ValueError("Numbers dosyasında sayfa bulunamadı.")
    sheet = doc.sheets[0]
    if not sheet.tables:
        raise ValueError("Numbers dosyasında tablo bulunamadı.")
    table = sheet.tables[0]

    rows = table.rows(values_only=True)
    out: list[list[str]] = []
    for raw in rows:
        out.append(["" if v is None else str(v).strip() for v in raw])
    return out


# ---- ortak ----

def parse_table(filename: str, data: bytes) -> dict:
    """Excel/CSV/Numbers içeriğini parse eder ve tahmin edilen sütunları döner."""
    name = (filename or "").lower()
    if name.endswith(".csv"):
        table = _parse_csv(data)
    elif name.endswith((".xlsx", ".xlsm")):
        table = _parse_xlsx(data)
    elif name.endswith(".numbers"):
        table = _parse_numbers(data)
    elif name.endswith(".xls"):
        raise ValueError("Eski .xls biçimi desteklenmiyor — dosyayı .xlsx veya .csv olarak kaydedin.")
    else:
        raise ValueError("Desteklenmeyen dosya türü — .numbers, .xlsx veya .csv yükleyin.")

    table = [r for r in table if any(str(c).strip() for c in r)]   # tamamen boş satırları at
    if len(table) < 2:
        raise ValueError("Dosyada başlık satırı ve en az bir veri satırı olmalı.")

    header = [str(c).strip() for c in table[0]]
    columns, seen = [], {}
    for i, col in enumerate(header):
        name_ = col or f"Sütun {i + 1}"
        if name_ in seen:                    # yinelenen başlıkları ayrıştır
            seen[name_] += 1
            name_ = f"{name_} ({seen[name_]})"
        else:
            seen[name_] = 1
        columns.append(name_)

    rows: list[dict] = []
    for raw in table[1:]:
        row = {columns[i]: (str(raw[i]).strip() if i < len(raw) else "") for i in range(len(columns))}
        if any(row.values()):
            rows.append(row)
        if len(rows) >= MAX_ROWS:
            break
    if not rows:
        raise ValueError("Dosyada veri satırı bulunamadı.")

    return {
        "columns": columns,
        "rows": rows,
        "total": len(rows),
        "preview": rows[:PREVIEW_ROWS],
        "guessed_email_column": guess_email_column(columns, rows),
        "guessed_subject_column": guess_subject_column(columns, rows),
        "guessed_body_column": guess_body_column(columns, rows),
    }


def guess_email_column(columns: list[str], rows: list[dict]) -> str:
    """Önce başlık adına, sonra içeriğe bakarak e-posta sütununu tahmin eder."""
    for col in columns:
        if re.search(r"e[\s_-]?mail|e[\s_-]?posta|mail|adres", col, re.I):
            if any(is_email(r.get(col)) for r in rows[:50]):
                return col
    for col in columns:
        if any(is_email(r.get(col)) for r in rows[:50]):
            return col
    return columns[0] if columns else ""


def _guess_column(columns: list[str], rows: list[dict], pattern: str) -> str:
    """Yalnızca başlık adına bakar; emin olamıyorsa boş döner.

    İçeriğe bakıp tahmin yürütmek burada tehlikeli: e-posta sütununda değerin
    gerçekten e-posta olduğu doğrulanabilir, ama bir metnin "konu" mu yoksa
    "isim" mi olduğu ayırt edilemez. Yanlış tahmin, konusu ve içeriği alıcının
    adından ibaret mailler gönderilmesine yol açar. Bu yüzden başlık eşleşmezse
    boş döner ve arayüz "Sabit metin kullan" seçeneğinde kalır.
    """
    regex = re.compile(pattern, re.I)
    for col in columns:
        if regex.search(col):
            # Başlık uyuyor ama sütun tamamen boşsa yine de seçme
            if any(str(r.get(col, "")).strip() for r in rows[:50]):
                return col
    return ""


def guess_subject_column(columns: list[str], rows: list[dict]) -> str:
    return _guess_column(columns, rows, r"konu|subject|başlık|baslik")


def guess_body_column(columns: list[str], rows: list[dict]) -> str:
    return _guess_column(columns, rows, r"içerik|icerik|mesaj|body|metin")


def valid_recipients(rows: list[dict], email_column: str) -> int:
    return sum(1 for r in rows if is_email(r.get(email_column)))
