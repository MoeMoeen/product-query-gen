import json
import unicodedata
import re
from typing import Any, Tuple

FILE_PATH = "app/data/merged_products.json"
CLEAN_PATH = "app/data/merged_products_clean.json"


# --- Classification sets ---
# Common ambiguous characters that should be replaced or removed
NEEDS_CLEANING = set("“”‘’‚‛❝❞❛❜–—―…•\u00A0\u200B\uFEFF")
# Benign Latin supplement characters (é, ü, ç, etc.)
BENIGN_RANGES = [
    (0x00C0, 0x017F),  # Latin-1 Supplement + Extended-A
    (0x0180, 0x024F),  # Latin Extended-B
]

# Characters we want to normalize in string fields
REPLACEMENTS = {
    "“": '"', "”": '"', "„": '"', "‟": '"', "❝": '"', "❞": '"',
    "‘": "'", "’": "'", "‚": "'", "‛": "'", "❛": "'", "❜": "'",
    "–": "-", "—": "-", "―": "-", "…": "...", "•": "*",
    "\u00A0": " ", "\u200B": "", "\uFEFF": "",
}

CTRL_CHARS_RE = re.compile(r"[\x00-\x08\x0B-\x0C\x0E-\x1F\x7F]")
TRAILING_COMMAS_RE = re.compile(r",(\s*[}\]])")


def classify_char(ch: str) -> str:
    """Classify character as 'benign', 'needs_cleaning', or 'other'."""
    if ch in NEEDS_CLEANING:
        return "needs_cleaning"
    code = ord(ch)
    for start, end in BENIGN_RANGES:
        if start <= code <= end:
            return "benign"
    return "other"


def detect_ambiguous_characters(path: str):
    """Scan file for non-ASCII characters and classify them."""
    with open(path, "r", encoding="utf-8") as f:
        lines = f.readlines()

    anomalies = []
    for line_no, line in enumerate(lines, start=1):
        for col_no, ch in enumerate(line, start=1):
            if ord(ch) > 127:  # non-ASCII
                category = classify_char(ch)
                name = unicodedata.name(ch, "UNKNOWN")
                anomalies.append((line_no, col_no, ch, name, category))

    benign = [a for a in anomalies if a[4] == "benign"]
    cleaning = [a for a in anomalies if a[4] == "needs_cleaning"]
    other = [a for a in anomalies if a[4] == "other"]

    if not anomalies:
        print("✅ No non-ASCII characters found.")
    else:
        print(f"\nDetected {len(anomalies)} non-ASCII characters:")
        print(f"  🟢 Benign: {len(benign)}")
        print(f"  🔴 Needs cleaning: {len(cleaning)}")
        print(f"  🟡 Other/Unclassified: {len(other)}")

        print("\n🔴 Characters that need cleaning (first 30 shown):")
        for line_no, col_no, ch, name, _ in cleaning[:30]:
            print(f"Line {line_no:<6} Col {col_no:<4} Char: {repr(ch)} -> {name}")

        if len(cleaning) > 30:
            print(f"...and {len(cleaning) - 30} more.\n")

    return anomalies, cleaning


def strip_trailing_commas(text: str) -> str:
    """Remove trailing commas before '}' or ']' to help JSON parsing."""
    return TRAILING_COMMAS_RE.sub(r"\1", text)


def normalize_string(s: str) -> str:
    """Normalize and replace ambiguous Unicode characters, keep ASCII safe."""
    s = unicodedata.normalize("NFKC", s)
    for bad, good in REPLACEMENTS.items():
        s = s.replace(bad, good)
    s = CTRL_CHARS_RE.sub("", s)
    return s


def normalize_obj(obj: Any) -> Any:
    if isinstance(obj, str):
        return normalize_string(obj)
    if isinstance(obj, list):
        return [normalize_obj(v) for v in obj]
    if isinstance(obj, dict):
        return {k: normalize_obj(v) for k, v in obj.items()}
    return obj


def clean_products(products: Any) -> Any:
    """Drop empty product dicts or non-dict entries; keep minimal schema."""
    if not isinstance(products, list):
        return products
    cleaned = []
    for p in products:
        if not isinstance(p, dict) or not p:
            continue
        # Optional minimal schema gate; relax as needed
        if "id" not in p or "title" not in p:
            # keep if it has at least one non-empty field to avoid over-dropping
            if any(v not in (None, "", [], {}) for v in p.values()):
                cleaned.append(p)
            continue
        cleaned.append(p)
    return cleaned


def clean_unicode_text(text: str) -> str:
    """Normalize Unicode, replace known ambiguous characters with ASCII equivalents."""
    text = unicodedata.normalize("NFKC", text)
    for bad, good in REPLACEMENTS.items():
        text = text.replace(bad, good)
    text = CTRL_CHARS_RE.sub("", text)
    return text


def parse_and_clean_json(text: str) -> Tuple[dict, str]:
    """Pre-clean raw text to make it JSON-parseable, then normalize values."""
    # First, clear control chars and BOM and trailing commas to allow parsing
    pre = text.lstrip("\ufeff")
    pre = CTRL_CHARS_RE.sub("", pre)
    pre = strip_trailing_commas(pre)

    try:
        data = json.loads(pre)
    except json.JSONDecodeError as e:
        start = max(e.pos - 120, 0)
        end = min(e.pos + 120, len(pre))
        snippet = pre[start:end].replace("\n", "\\n")
        raise RuntimeError(f"JSON parse failed at pos {e.pos}: {e}\nContext: {snippet}")

    # Normalize strings safely after parsing so quotes get escaped on dump
    data = normalize_obj(data)

    # Domain-specific: clean products list if present
    if isinstance(data, dict) and isinstance(data.get("products"), list):
        before = len(data["products"]) if isinstance(data["products"], list) else 0
        data["products"] = clean_products(data["products"])
        after = len(data["products"]) if isinstance(data["products"], list) else 0
    else:
        before = after = 0

    summary = f"Products kept: {after} / {before}"
    return data, summary


def clean_file(path_in: str, path_out: str):
    with open(path_in, "r", encoding="utf-8") as f:
        original = f.read()

    # Try robust JSON-based cleaning; fall back to raw text cleaning
    try:
        data, summary = parse_and_clean_json(original)
        with open(path_out, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        print(f"✅ Cleaned file saved to: {path_out} ({summary})")
    except Exception as e:
        print(f"⚠️ JSON-based cleaning failed: {e}\nFalling back to text normalization (quotes may still break JSON).")
        cleaned = clean_unicode_text(original)
        # As a last resort, also strip trailing commas in text
        cleaned = strip_trailing_commas(cleaned)
        with open(path_out, "w", encoding="utf-8") as f:
            f.write(cleaned)
        print(f"✅ Fallback cleaned file saved to: {path_out}")


if __name__ == "__main__":
    # Step 1: detect anomalies in the original file to inform the user
    anomalies, cleaning = detect_ambiguous_characters(FILE_PATH)
    # Step 2: always attempt cleaning (unicode + JSON-safe), even if only benign
    print("\n🧹 Cleaning file now...\n")
    clean_file(FILE_PATH, CLEAN_PATH)
    # Step 3: validate the cleaned JSON and re-scan for anomalies
    try:
        with open(CLEAN_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        products_count = (
            len(data.get("products", [])) if isinstance(data, dict) else 0
        )
        print(f"✅ Validation: cleaned JSON parsed OK. products={products_count}")
    except Exception as e:
        print(f"❌ Validation: cleaned JSON still invalid: {e}")

    print("\n🔎 Re-scanning cleaned file for non-ASCII...")
    anomalies2, cleaning2 = detect_ambiguous_characters(CLEAN_PATH)
    print(
        f"Summary: original anomalies={len(anomalies)}, cleaned anomalies={len(anomalies2)}"
    )
