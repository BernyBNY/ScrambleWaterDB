import csv
import json
import re
import unicodedata
from pathlib import Path
from datetime import datetime, timezone

BASE = Path(__file__).resolve().parent.parent
SRC = BASE / "source" / "waterpoints.csv"
OUT = BASE / "dist" / "waterpoints.json"
DEFAULT_COUNTRY_CODE = "FR"

def parse_coord(coord: str):
    """
    Exemples:
      "N 45°33’/ E 005°48’"
      "N 44°43’/ W 000°27’"
    Retour: (lat, lon) en décimal
    """
    if not coord:
        return None

    s = coord.strip().upper()
    # Normaliser apostrophes / séparateurs
    s = s.replace("’", "'").replace("′", "'").replace("’", "'")
    s = s.replace(" / ", "/").replace(" /", "/").replace("/ ", "/")
    s = s.replace("° ", "°")

    # Regex: H  dd°mm'  /  H  ddd°mm'
    m = re.search(
        r"\b([NS])\s*(\d{1,2})\s*°\s*(\d{1,2})\s*['’]?\s*/\s*([EW])\s*(\d{1,3})\s*°\s*(\d{1,2})\s*['’]?\b",
        s
    )
    if not m:
        return None

    lat_hemi, lat_deg, lat_min, lon_hemi, lon_deg, lon_min = m.groups()

    lat = int(lat_deg) + int(lat_min) / 60.0
    lon = int(lon_deg) + int(lon_min) / 60.0

    if lat_hemi == "S":
        lat = -lat
    if lon_hemi == "W":
        lon = -lon

    return (round(lat, 6), round(lon, 6))

def slug_id(name: str) -> str:
    s = (name or "").strip()
    s = unicodedata.normalize("NFKD", s)
    s = "".join(ch for ch in s if not unicodedata.combining(ch))
    s = s.upper()
    s = re.sub(r"[^\w]+", "_", s, flags=re.UNICODE)
    s = re.sub(r"_+", "_", s).strip("_")
    return s[:48] if s else "WATERPOINT"

def parse_decimal(value: str):
    if value is None:
        return None

    s = str(value).strip().replace(",", ".")
    if not s:
        return None

    try:
        return round(float(s), 6)
    except ValueError:
        return None

def parse_row_coordinates(row):
    lat = parse_decimal(row.get("LAT") or row.get("lat") or row.get("Latitude"))
    lon = parse_decimal(row.get("LON") or row.get("LONG") or row.get("lon") or row.get("Longitude"))
    if lat is not None and lon is not None:
        return lat, lon

    coord_raw = (row.get("COORDONNEES") or "").strip()
    return parse_coord(coord_raw)

waterpoints = []
seen_ids = set()

with SRC.open("r", encoding="utf-8", newline="") as f:
    r = csv.DictReader(f, delimiter=";")
    # Nettoyage des noms de colonnes (au cas où)
    r.fieldnames = [fn.strip() if fn else "" for fn in (r.fieldnames or [])]

    # Legacy rows can use COORDONNEES; newer rows can use decimal LAT/LON.
    for row in r:
        name = (row.get("NOM") or "").strip()
        if not name:
            continue

        parsed = parse_row_coordinates(row)
        if not parsed:
            continue

        lat, lon = parsed
        country_code = (row.get("COUNTRY_CODE") or row.get("countryCode") or DEFAULT_COUNTRY_CODE).strip().upper()
        wid = slug_id(name)
        # Garantir unicité
        base_id = wid
        k = 2
        while wid in seen_ids:
            wid = f"{base_id}_{k}"
            k += 1
        seen_ids.add(wid)

        waterpoints.append({
            "id": wid,
            "name": name.title() if name.isupper() else name,
            "countryCode": country_code,
            "lat": lat,
            "lon": lon
        })

db = {
    "version": 1,
    "updatedAt": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    "waterPoints": waterpoints
}

OUT.parent.mkdir(parents=True, exist_ok=True)
with OUT.open("w", encoding="utf-8") as f:
    json.dump(db, f, ensure_ascii=False, indent=2)

print(f"OK: {len(waterpoints)} waterpoints -> {OUT}")
