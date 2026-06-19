# -*- coding: utf-8 -*-
"""
Lecteur de listes d'armée au format BattleScribe JSON.
Parsing + matching vers les unités Wahapedia existantes.
"""

import json


def _extract_weapon_names(selections: list) -> list:
    """
    Retourne les noms de tous les upgrades dans l'arborescence BattleScribe,
    à tous les niveaux de profondeur. Le matching Wahapedia filtre les non-armes.
    """
    names: list = []
    seen: set = set()

    def _collect(sels: list) -> None:
        for sub in sels:
            name = sub.get("name", "").strip()
            if sub.get("type") == "upgrade" and name and name not in seen:
                names.append(name)
                seen.add(name)
            _collect(sub.get("selections", []))

    _collect(selections)
    return names


def parse_army_list(json_data: dict) -> list:
    """Extrait les unités depuis un JSON BattleScribe."""
    units = []
    for force in json_data.get("roster", {}).get("forces", []):
        for sel in force.get("selections", []):
            if sel.get("type") not in ("model", "unit"):
                continue
            name = sel.get("name", "").strip()
            if not name:
                continue
            pts = next(
                (c["value"] for c in sel.get("costs", []) if c.get("name") == "pts"),
                0,
            )
            cats = [c.get("name", "") for c in sel.get("categories", [])]
            faction_raw = next(
                (c.replace("Faction: ", "") for c in cats if c.startswith("Faction: ")),
                None,
            )
            is_character = any("Character" in c for c in cats)
            units.append({
                "name": name,
                "pts": pts,
                "faction_raw": faction_raw,
                "is_character": is_character,
                "weapon_names_raw": _extract_weapon_names(sel.get("selections", [])),
            })
    return units


def get_roster_name(json_data: dict) -> str:
    return json_data.get("roster", {}).get("name", "Ma liste")


def get_roster_pts(json_data: dict) -> int:
    for cost in json_data.get("roster", {}).get("costs", []):
        if cost.get("name") == "pts":
            return cost.get("value", 0)
    return 0


def match_units_to_wahapedia(army_units: list, factions: dict, get_units_fn) -> list:
    """
    Pour chaque unité de la liste brute, trouve la WahapediaUnit correspondante.

    factions       : dict {display_name: faction_id} issu de get_factions()
    get_units_fn   : callable(faction_id) → dict {name: WahapediaUnit}
    """
    seen_factions = {u["faction_raw"] for u in army_units if u["faction_raw"]}
    unit_index: dict = {}           # name_lower → WahapediaUnit
    faction_display: dict = {}      # faction_raw → wahapedia display name

    for faction_raw in seen_factions:
        match = next(
            (
                fname for fname in factions
                if faction_raw.lower() in fname.lower()
                or fname.lower() in faction_raw.lower()
            ),
            None,
        )
        if match:
            faction_display[faction_raw] = match
            for unit in get_units_fn(factions[match]).values():
                unit_index[unit.name.lower()] = unit

    result = []
    for u in army_units:
        wunit = unit_index.get(u["name"].lower())
        matched_weapons = []
        if wunit:
            wunit_lower = {w.name.lower(): w.name for w in wunit.weapons}
            seen: set = set()
            for raw_name in u.get("weapon_names_raw", []):
                wname = wunit_lower.get(raw_name.lower())
                if wname and wname not in seen:
                    matched_weapons.append(wname)
                    seen.add(wname)
        result.append({
            **u,
            "wahapedia_unit": wunit,
            "wahapedia_faction": faction_display.get(u["faction_raw"]),
            "matched_weapons": matched_weapons,
        })
    return result


def parse_and_match(uploaded_file, factions: dict, get_units_fn) -> dict:
    """
    Wrapper complet : lit le fichier uploadé, parse, match.
    Retourne un dict {roster_name, roster_pts, units: [matched...]}.
    """
    raw = json.loads(uploaded_file.read())
    army_units = parse_army_list(raw)
    matched = match_units_to_wahapedia(army_units, factions, get_units_fn)
    return {
        "roster_name": get_roster_name(raw),
        "roster_pts": get_roster_pts(raw),
        "units": matched,
    }
