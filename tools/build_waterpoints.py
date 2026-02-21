import csv
import json
import re
from pathlib import Path
from datetime import datetime, timezone

BASE = Path(__file__).resolve().parent.parent
SRC = BASE / "source" / "waterpoints.csv"
OUT = BASE / "dist" / "waterpoints.json"

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
    s = (name or "").strip().upper()
    s = re.sub(r"[^\w]+", "_", s, flags=re.UNICODE)
    s = re.sub(r"_+", "_", s).strip("_")
    return s[:48] if s else "WATERPOINT"

waterpoints = []
seen_ids = set()

with SRC.open("r", encoding="utf-8", newline="") as f:
    r = csv.DictReader(f, delimiter=";")
    # Nettoyage des noms de colonnes (au cas où)
    r.fieldnames = [fn.strip() if fn else "" for fn in (r.fieldnames or [])]

    # Tes colonnes s'appellent bien "NOM" et "COORDONNEES"
    for row in r:
        name = (row.get("NOM") or "").strip()
        coord_raw = (row.get("COORDONNEES") or "").strip()

        if not name or not coord_raw:
            continue

        parsed = parse_coord(coord_raw)
        if not parsed:
            continue

        lat, lon = parsed
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
            "countryCode": "FR",  # si tu veux gérer plusieurs pays plus tard, on fera un mapping
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
