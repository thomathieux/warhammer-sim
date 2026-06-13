"""
Téléchargement des CSV Wahapedia vers data/csv/.

Usage :
    python -m data.downloader            # télécharge tous les fichiers
    python -m data.downloader --force    # force le re-téléchargement

Source : https://wahapedia.ru  —  Powered by Wahapedia
"""

import sys
import urllib.request
from pathlib import Path

BASE_URL = "https://wahapedia.ru/wh40k10ed"
CSV_DIR  = Path(__file__).parent / "csv"

FILES = [
    "Factions.csv",
    "Source.csv",
    "Datasheets.csv",
    "Datasheets_models.csv",
    "Datasheets_wargear.csv",
    "Datasheets_abilities.csv",
    "Datasheets_keywords.csv",
    "Datasheets_unit_composition.csv",
    "Datasheets_models_cost.csv",
    "Abilities.csv",
    "Detachments.csv",
    "Detachment_abilities.csv",
]

_HEADERS = {"User-Agent": "warhammer_sim/1.0 (educational project)"}


def download_all(force: bool = False) -> None:
    """Télécharge tous les CSV Wahapedia dans data/csv/."""
    CSV_DIR.mkdir(parents=True, exist_ok=True)

    for filename in FILES:
        dest = CSV_DIR / filename
        if dest.exists() and not force:
            print(f"  skip  {filename}  (existe déjà)")
            continue

        url = f"{BASE_URL}/{filename}"
        print(f"  DL    {filename} ...", end=" ", flush=True)
        req = urllib.request.Request(url, headers=_HEADERS)
        with urllib.request.urlopen(req, timeout=30) as resp:
            dest.write_bytes(resp.read())
        size = round(dest.stat().st_size / 1024, 1)
        print(f"OK ({size} KB)")


if __name__ == "__main__":
    force = "--force" in sys.argv
    print(f"Téléchargement des données Wahapedia (force={force})")
    print("Powered by Wahapedia — https://wahapedia.ru\n")
    download_all(force=force)
    print("\nTerminé.")
