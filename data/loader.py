"""
Chargement des données Wahapedia depuis les CSV locaux.

Les CSV sont stockés dans data/csv/ et peuvent être re-téléchargés
avec data/downloader.py si nécessaire.

Source : https://wahapedia.ru  —  Powered by Wahapedia
"""

import csv
from pathlib import Path
from typing import Dict, List, Optional

from data.models import WahapediaUnit, UnitModel, WeaponProfile
from data.keyword_parser import parse_keywords

CSV_DIR = Path(__file__).parent / "csv"


# ---------------------------------------------------------------------------
# Helpers de parsing
# ---------------------------------------------------------------------------

def _read_csv(filename: str) -> List[Dict]:
    path = CSV_DIR / filename
    with open(path, encoding="utf-8-sig") as f:
        return list(csv.DictReader(f, delimiter="|"))


def _group_by(rows: List[Dict], key: str = "datasheet_id") -> Dict[str, List[Dict]]:
    result: Dict[str, List[Dict]] = {}
    for r in rows:
        result.setdefault(r[key], []).append(r)
    return result


def _stat_int(value: str) -> int:
    """'3+' → 3, '5*' → 5, '7' → 7, '' → 0."""
    v = value.strip().rstrip("+*") if value else ""
    return int(v) if v.lstrip("-").isdigit() else 0


def _invuln(value: str) -> Optional[int]:
    """'-' ou '' → None, '4' → 4, '4*' → 4."""
    v = value.strip().rstrip("+*") if value else ""
    if not v or v == "-":
        return None
    return int(v) if v.isdigit() else None


def _parse_composition(rows: List[Dict]) -> tuple:
    """Retourne (min_models, max_models) depuis la ligne de composition.

    Gère les formats : "5-10 Immortals", "1 Warboss", "5 Boyz".
    """
    if not rows:
        return 1, 1
    text = rows[0].get("description", "")
    # Cherche d'abord un intervalle "N-M"
    import re
    m = re.search(r"(\d+)-(\d+)", text)
    if m:
        return int(m.group(1)), int(m.group(2))
    # Sinon le premier nombre trouvé
    nums = re.findall(r"\d+", text)
    if nums:
        n = int(nums[0])
        return n, n
    return 1, 1


# ---------------------------------------------------------------------------
# Chargement principal
# ---------------------------------------------------------------------------

def load_all_units(faction_id: Optional[str] = None) -> List[WahapediaUnit]:
    """
    Charge toutes les unités (ou filtrées par faction_id) depuis les CSV Wahapedia.

    Args:
        faction_id: code faction Wahapedia (ex : 'NEC', 'SM', 'ORK').
                    None charge toutes les factions.
    """
    datasheets     = {r["id"]: r for r in _read_csv("Datasheets.csv")}
    models_rows    = _read_csv("Datasheets_models.csv")
    wargear_rows   = _read_csv("Datasheets_wargear.csv")
    abilities_rows = _read_csv("Datasheets_abilities.csv")
    shared_ab      = {r["id"]: r for r in _read_csv("Abilities.csv")}
    comp_rows      = _read_csv("Datasheets_unit_composition.csv")
    costs_rows     = _read_csv("Datasheets_models_cost.csv")
    kw_rows        = _read_csv("Datasheets_keywords.csv")

    models_by_id    = _group_by(models_rows)
    wargear_by_id   = _group_by(wargear_rows)
    abilities_by_id = _group_by(abilities_rows)
    comp_by_id      = _group_by(comp_rows)
    costs_by_id     = _group_by(costs_rows)
    kw_by_id        = _group_by(kw_rows)

    units: List[WahapediaUnit] = []

    for ds_id, ds in datasheets.items():
        if faction_id and ds["faction_id"] != faction_id:
            continue

        # --- Modèles ---
        unit_models = [
            UnitModel(
                name=m["name"],
                movement=m["M"],
                toughness=_stat_int(m["T"]),
                save=_stat_int(m["Sv"]),
                invulnerable_save=_invuln(m.get("inv_sv", "")),
                wounds=_stat_int(m["W"]),
                leadership=_stat_int(m["Ld"]),
                oc=_stat_int(m["OC"]),
                base_size=m.get("base_size", ""),
            )
            for m in models_by_id.get(ds_id, [])
        ]

        # --- Armes ---
        raw_wargear = sorted(
            wargear_by_id.get(ds_id, []),
            key=lambda r: (int(r["line"]) if r["line"].isdigit() else 0,
                           int(r["line_in_wargear"]) if r["line_in_wargear"].isdigit() else 0),
        )
        weapons = []
        for w in raw_wargear:
            s_raw = w["S"].strip()
            ap_raw = w["AP"].strip()
            weapons.append(WeaponProfile(
                name=w["name"],
                range=w["range"],
                type=w["type"],
                attacks=w["A"].strip() or "1",
                skill=_stat_int(w["BS_WS"]),
                strength=int(s_raw) if s_raw.lstrip("-").isdigit() else 4,
                ap=int(ap_raw) if ap_raw.lstrip("-").isdigit() else 0,
                damage=w["D"].strip() or "1",
                keywords=parse_keywords(w.get("description", "")),
            ))

        # --- Abilities ---
        abilities = []
        for a in abilities_by_id.get(ds_id, []):
            ab_id = a.get("ability_id", "").strip()
            if ab_id and ab_id in shared_ab:
                s = shared_ab[ab_id]
                abilities.append({
                    "name": s["name"],
                    "description": s["description"],
                    "type": a.get("type", ""),
                })
            elif a.get("name", "").strip():
                abilities.append({
                    "name": a["name"],
                    "description": a.get("description", ""),
                    "type": a.get("type", "Datasheet"),
                })

        # --- Composition & coûts ---
        min_m, max_m = _parse_composition(comp_by_id.get(ds_id, []))
        costs = [
            {"description": c["description"], "cost": int(c["cost"])}
            for c in costs_by_id.get(ds_id, [])
            if c.get("cost", "").strip().isdigit()
        ]

        # --- Mots-clés d'unité ---
        keywords = [k["keyword"] for k in kw_by_id.get(ds_id, [])]

        units.append(WahapediaUnit(
            id=ds_id,
            name=ds["name"],
            faction_id=ds["faction_id"],
            link=ds.get("link", ""),
            models=unit_models,
            weapons=weapons,
            abilities=abilities,
            min_models=min_m,
            max_models=max_m,
            costs=costs,
            keywords=keywords,
        ))

    return units


def find_unit(name: str, faction_id: Optional[str] = None) -> Optional[WahapediaUnit]:
    """
    Cherche une unité par nom (exact puis partiel, insensible à la casse).

    Args:
        name:       nom de l'unité (ex : 'Immortals', 'intercessors')
        faction_id: filtrer par faction (optionnel)
    """
    units = load_all_units(faction_id)
    name_lower = name.lower()

    # Correspondance exacte
    for u in units:
        if u.name.lower() == name_lower:
            return u

    # Commence par le mot-clé (ex: "Intercessors" → "Intercessors with Bolt Rifles")
    for u in units:
        if u.name.lower().startswith(name_lower):
            return u

    # Contient le mot-clé (en dernier recours)
    for u in units:
        if name_lower in u.name.lower():
            return u

    return None


def list_factions() -> List[Dict]:
    """Retourne la liste des factions disponibles."""
    return _read_csv("Factions.csv")
