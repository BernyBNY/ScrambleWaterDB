import csv
import json
from pathlib import Path
from datetime import datetime, timezone
import re
import unicodedata

BASE = Path(__file__).resolve().parent.parent
SRC = BASE / "source" / "waterpoints.csv"
OUT = BASE / "waterpoints.json"

def clean_text(s: str) -> str:
    s = (s or "").strip()
    # normalise les apostrophes typographiques (’ → ')
    s = s.replace("’", "'").replace("′", "'").replace("“", '"').replace("”", '"').replace("″", '"')
    return s

def dms_to_decimal(deg: float, minute: float = 0, sec: float = 0, hemi: str = "N") -> float:
    val = abs(deg) + (minute / 60.0) + (sec / 3600.0)
    if hemi in ("S", "W"):
        val = -val
    return val

def parse_single_dms(part: str):
    """
    part ex:
      "N 45°33'"
      "E 005°48'"
      "W 000°27'"
      "N 43°29'12\""
    Retourne (hemi, deg, min, sec) ou None
    """
    part = clean_text(part).upper()
    part = part.replace("O", "W")  # parfois Ouest = O

    # Extrait: HEMI + deg + min + (sec optionnel)
    # accepte ° ou espace, minutes ' ou rien, secondes " optionnel
    m = re.search(r"\b([NSEW])\s*([0-9]{1,3})\s*(?:°|\s)\s*([0-9]{1,2})?\s*'?[\s]*([0-9]{1,2})?\s*\"?", part)
    if not m:
        return None

    hemi = m.group(1)
    deg = float(m.group(2))
    minute = float(m.group(3) or 0)
    sec = float(m.group(4) or 0)
    return hemi, deg, minute, sec

def parse_coord(raw: str):
    """
    Gère:
      "N 45°33' / E 005°48'"
      "N 45°33' E 005°48'"
      "45.123, 5.456" (au cas où)
    Retourne (lat, lon) en décimal.
    """
    s = clean_text(raw).upper()
    if not s:
        return None

    # cas decimal "lat,lon"
    m = re.match(r"^\s*([+-]?\d+(\.\d+)?)\s*[,;]\s*([+-]?\d+(\.\d+)?)\s*$", s)
    if m:
        return float(m.group(1)), float(m.group(3))

    # split en 2 morceaux autour de "/" si présent
    parts = [p.strip() for p in re.split(r"/", s) if p.strip()]
    if len(parts) == 1:
        # parfois: "N ... E ..."
        parts = [s]

    # cherche N/S et E/W dans la chaîne
    lat_part = None
    lon_part = None

    # si on a 2 morceaux, souvent 1 = lat, 2 = lon
    if len(parts) >= 2:
        lat_part = parts[0]
        lon_part = parts[1]
    else:
        # sinon on essaye de découper par présence de E/W
        # ex: "N 45°33' E 005°48'"
        m2 = re.search(r"\b([EW])\b", s.replace("O", "W"))
        if m2:
            idx = m2.start()
            lat_part = s[:idx]
            lon_part = s[idx:]
        else:
            return None

    lat_dms = parse_single_dms(lat_part)
    lon_dms = parse_single_dms(lon_part)
    if not lat_dms or not lon_dms:
        return None

    h1, d1, m1, s1 = lat_dms
    h2, d2, m2, s2 = lon_dms

    lat = dms_to_decimal(d1, m1, s1, h1)
    lon = dms_to_decimal(d2, m2, s2, h2)
    return lat, lon

def make_id(name: str):
    s = (name or "").strip().upper()
    s = re.sub(r"[^A-Z0-9]+", "_", s)
    s = re.sub(r"_+", "_", s).strip("_")
    return s[:48] if s else "WATER"

items = []
errors = []

with SRC.open(newline="", encoding="utf-8") as f:
    r = csv.DictReader(f)
    for i, row in enumerate(r, start=2):
        name = (row.get("NOM") or row.get("name") or "").strip()
        coords = (row.get("COORDONNEES") or row.get("coords") or "").strip()

        if not name or not coords:
            errors.append(f"Ligne {i}: NOM/COORDONNEES manquant")
            continue

        parsed = parse_coord(coords)
        if not parsed:
            errors.append(f"Ligne {i}: coords invalide -> {coords}")
            continue

        lat, lon = parsed
        items.append({
            "id": make_id(name),
            "name": name,
            "countryCode": "FR",   # tu peux laisser vide si tu préfères
            "lat": round(lat, 6),
            "lon": round(lon, 6),
        })

items.sort(key=lambda x: x["name"].lower())

db = {
    "version": 1,
    "updatedAt": datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
    "waterPoints": items
}

OUT.write_text(json.dumps(db, ensure_ascii=False, indent=2), encoding="utf-8")

print(f"OK: {len(items)} plans d’eau -> {OUT}")
if errors:
    print("\nErreurs (à corriger dans Numbers/CSV) :")
    for e in errors[:50]:
        print(" -", e)
    if len(errors) > 50:
        print(f" ... +{len(errors)-50} autres")
