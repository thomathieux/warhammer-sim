"""
Chargement des données Wahapedia depuis les CSV locaux.

Les CSV sont stockés dans data/csv/ et peuvent être re-téléchargés
avec data/downloader.py si nécessaire.

Source : https://wahapedia.ru  —  Powered by Wahapedia
"""

import csv
import re
from pathlib import Path
from typing import Dict, List, Optional, Tuple

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


def _strip_html(text: str) -> str:
    return re.sub(r"<[^>]+>", "", text).strip()


def _parse_composition(rows: List[Dict]) -> Tuple[int, int]:
    """
    Retourne (min_models, max_models) en sommant toutes les lignes de composition.
    Gère les formats : "5-10 Immortals", "1 Warboss", "9-19 Boyz + 1 Boss Nob".
    """
    if not rows:
        return 1, 1
    total_min, total_max = 0, 0
    for row in rows:
        text = _strip_html(row.get("description", ""))
        m = re.search(r"(\d+)-(\d+)", text)
        if m:
            total_min += int(m.group(1))
            total_max += int(m.group(2))
        else:
            nums = re.findall(r"\d+", text)
            if nums:
                n = int(nums[0])
                total_min += n
                total_max += n
    return max(1, total_min), max(1, total_max)


def _link_comp_to_models(
    comp_rows: List[Dict], unit_models: List[UnitModel]
) -> List[Tuple[int, int, int]]:
    """
    Relie les lignes de composition aux lignes de modèles par name-matching.

    L'ordre des lignes CSV de composition et des lignes de modèles n'est pas
    garanti identique (ex: pour Boyz, comp[0]='Boss Nob' mais model[0]=BOY).
    On utilise une correspondance par mots communs.

    Retourne [(model_index, min_count, max_count)] trié par max_count décroissant.
    """
    if not comp_rows or not unit_models:
        return []

    result = []
    used_models = set()

    for row in comp_rows:
        text = _strip_html(row.get("description", ""))

        # Extraire le compte
        m_range = re.search(r"(\d+)-(\d+)", text)
        if m_range:
            min_c, max_c = int(m_range.group(1)), int(m_range.group(2))
        else:
            nums = re.findall(r"\d+", text)
            n = int(nums[0]) if nums else 1
            min_c = max_c = n

        # Extraire le fragment de nom (sans préfixe numérique)
        name_fragment = re.sub(r"^\d[\d\-]*\s+", "", text).lower()

        # Trouver le modèle avec le plus de mots en commun
        best_idx = None
        best_score = -1
        fragment_words = set(name_fragment.split())
        for i, model in enumerate(unit_models):
            if i in used_models:
                continue
            model_words = set(model.name.lower().split())
            score = len(fragment_words & model_words)
            if score > best_score:
                best_score = score
                best_idx = i

        # Fallback positionnel si score nul
        if best_score == 0 or best_idx is None:
            for i in range(len(unit_models)):
                if i not in used_models:
                    best_idx = i
                    break

        if best_idx is not None:
            used_models.add(best_idx)
            result.append((best_idx, min_c, max_c))

    # Trier par max_count décroissant (groupe le plus nombreux en premier)
    result.sort(key=lambda x: x[2], reverse=True)
    return result


def _parse_loadout_quantities(loadout_html: str, weapon_names: List[str]) -> Dict[str, int]:
    """
    Parse le champ loadout HTML pour extraire les quantités d'armes.

    Ex: "2 hurricane bolters; twin assault cannon" → {"hurricane bolter": 2}

    Retourne un Dict[weapon_name, quantity]. Défaut : 1.
    """
    quantities: Dict[str, int] = {}
    text = _strip_html(loadout_html)
    items = [item.strip() for item in text.split(";") if item.strip()]

    for item in items:
        # Cherche un préfixe numérique
        m = re.match(r"^(\d+)\s+(.+)$", item)
        if not m:
            continue
        count = int(m.group(1))
        fragment = m.group(2).lower().rstrip("s.")  # normaliser pluriel

        # Matcher contre les noms d'armes connus
        for wname in weapon_names:
            wname_lower = wname.lower()
            # Correspondance substring
            if wname_lower in fragment or fragment in wname_lower:
                quantities[wname] = count
                break

    return quantities


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

        # --- Quantités d'armes depuis le champ loadout ---
        loadout_html = ds.get("loadout", "")
        if loadout_html and weapons:
            weapon_names = [w.name for w in weapons]
            quantities = _parse_loadout_quantities(loadout_html, weapon_names)
            for w in weapons:
                if w.name in quantities:
                    w.quantity = quantities[w.name]

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
        unit_comp_rows = comp_by_id.get(ds_id, [])
        min_m, max_m = _parse_composition(unit_comp_rows)
        model_composition = _link_comp_to_models(unit_comp_rows, unit_models)
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
            model_composition=model_composition,
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

    for u in units:
        if u.name.lower() == name_lower:
            return u

    for u in units:
        if u.name.lower().startswith(name_lower):
            return u

    for u in units:
        if name_lower in u.name.lower():
            return u

    return None


def list_factions() -> List[Dict]:
    """Retourne la liste des factions disponibles."""
    return _read_csv("Factions.csv")
