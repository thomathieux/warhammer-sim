# -*- coding: utf-8 -*-
"""
Profils sauvegardés — sérialisation/restauration de la configuration UI.
Pas d'import Streamlit au niveau module (importé à la demande dans les fonctions).
"""

import json
from datetime import datetime

PROFILE_VERSION = 1
STORAGE_KEY = "wh40k_profiles"
MAX_PROFILES = 20


# ---------------------------------------------------------------------------
# Extraction (session_state → dict)
# ---------------------------------------------------------------------------

def extract_profile(name: str) -> dict:
    import streamlit as st
    ss = st.session_state

    atk_unit = ss.get("atk_unit", "")
    def_unit = ss.get("def_unit", "")

    # group_counts : chercher les clés def_grp_*_{def_unit} dans session_state
    prefix = "def_grp_"
    suffix = f"_{def_unit}"
    raw_groups = {
        key[len(prefix):-len(suffix)]: int(val)
        for key, val in ss.items()
        if key.startswith(prefix) and key.endswith(suffix) and key[len(prefix):-len(suffix)].isdigit()
    }
    group_counts = raw_groups if raw_groups else None

    return {
        "version": PROFILE_VERSION,
        "name": name,
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "attacker": {
            "faction": ss.get("atk_faction", ""),
            "unit": atk_unit,
            "total_models": ss.get(f"atk_total_count_{atk_unit}", 1),
            "weapons": list(ss.get("atk_weapons", [])),
            "weapon_dist": {
                w: ss.get(f"wdist_{w}", 0)
                for w in ss.get("atk_weapons", [])
            },
            "pts": ss.get("atk_pts", 0),
            "hit_rr": ss.get("hit_rr", "Aucune"),
            "wound_rr": ss.get("wound_rr", "Aucune"),
            "attach_leader": bool(ss.get("atk_attach_leader", False)),
            "leader_name": ss.get("atk_leader_name") or None,
            "leader_weapons": list(ss.get("atk_leader_weapons", [])),
            "leader_hit_plus": bool(ss.get("atk_leader_hit_plus", False)),
            "leader_hit_minus": bool(ss.get("atk_leader_hit_minus", False)),
            "attach_support": bool(ss.get("atk_attach_support", False)),
            "support_name": ss.get("atk_support_name") or None,
            "support_weapons": list(ss.get("atk_support_weapons", [])),
            "support_hit_plus": bool(ss.get("atk_support_hit_plus", False)),
            "support_hit_minus": bool(ss.get("atk_support_hit_minus", False)),
        },
        "defender": {
            "faction": ss.get("def_faction", ""),
            "unit": def_unit,
            "model_count": ss.get(f"def_count_{def_unit}", 1),
            "group_counts": group_counts,
            "attach_leader": bool(ss.get("def_attach_leader", False)),
            "leader_name": ss.get("def_leader_name") or None,
            "attach_support": bool(ss.get("def_attach_support", False)),
            "support_name": ss.get("def_support_name") or None,
            "hit_minus": bool(ss.get("def_hit_minus", False)),
            "wound_minus": bool(ss.get("def_wound_minus", False)),
            "dmg_minus": bool(ss.get("def_dmg_minus", False)),
            "fnp_enabled": bool(ss.get("def_fnp_enabled", False)),
            "fnp_val": ss.get("def_fnp_val", 6),
            "pts": ss.get("def_pts", 0),
        },
        "context": {
            "combat_type": ss.get("combat_type", "Distance"),
            "within_half": bool(ss.get("within_half", False)),
            "target_cover": bool(ss.get("target_cover", False)),
            "charged": bool(ss.get("charged", False)),
            "n_runs": ss.get("n_runs", 2000),
        },
    }


# ---------------------------------------------------------------------------
# Restauration (dict → session_state)
# ---------------------------------------------------------------------------

def restore_profile(profile: dict) -> None:
    """Écrit le profil dans st.session_state. N'appelle pas st.rerun()."""
    import streamlit as st
    ss = st.session_state

    if profile.get("version", 0) != PROFILE_VERSION:
        raise ValueError(f"Version de profil non supportée : {profile.get('version')}")

    atk = profile["attacker"]
    dfn = profile["defender"]
    ctx = profile["context"]

    # --- Attaquant ---
    ss["atk_faction"] = atk["faction"]
    ss["atk_unit"] = atk["unit"]
    ss["atk_weapons"] = atk["weapons"]
    ss[f"atk_total_count_{atk['unit']}"] = atk["total_models"]
    for wname, count in atk.get("weapon_dist", {}).items():
        ss[f"wdist_{wname}"] = count
    ss["atk_pts"] = atk.get("pts", 0)
    ss["hit_rr"] = atk.get("hit_rr", "Aucune")
    ss["wound_rr"] = atk.get("wound_rr", "Aucune")
    ss["atk_attach_leader"] = atk.get("attach_leader", False)
    ss["atk_leader_name"] = atk.get("leader_name") or ""
    ss["atk_leader_weapons"] = atk.get("leader_weapons", [])
    ss["atk_leader_hit_plus"] = atk.get("leader_hit_plus", False)
    ss["atk_leader_hit_minus"] = atk.get("leader_hit_minus", False)
    ss["atk_attach_support"] = atk.get("attach_support", False)
    ss["atk_support_name"] = atk.get("support_name") or ""
    ss["atk_support_weapons"] = atk.get("support_weapons", [])
    ss["atk_support_hit_plus"] = atk.get("support_hit_plus", False)
    ss["atk_support_hit_minus"] = atk.get("support_hit_minus", False)

    # --- Défenseur ---
    ss["def_faction"] = dfn["faction"]
    ss["def_unit"] = dfn["unit"]
    def_unit = dfn["unit"]
    if dfn.get("group_counts"):
        for idx_str, cnt in dfn["group_counts"].items():
            ss[f"def_grp_{idx_str}_{def_unit}"] = cnt
    else:
        ss[f"def_count_{def_unit}"] = dfn.get("model_count", 1)
    ss["def_attach_leader"] = dfn.get("attach_leader", False)
    ss["def_leader_name"] = dfn.get("leader_name") or ""
    ss["def_attach_support"] = dfn.get("attach_support", False)
    ss["def_support_name"] = dfn.get("support_name") or ""
    ss["def_hit_minus"] = dfn.get("hit_minus", False)
    ss["def_wound_minus"] = dfn.get("wound_minus", False)
    ss["def_dmg_minus"] = dfn.get("dmg_minus", False)
    ss["def_fnp_enabled"] = dfn.get("fnp_enabled", False)
    ss["def_fnp_val"] = dfn.get("fnp_val", 6)
    ss["def_pts"] = dfn.get("pts", 0)

    # --- Contexte ---
    ss["combat_type"] = ctx.get("combat_type", "Distance")
    ss["within_half"] = ctx.get("within_half", False)
    ss["target_cover"] = ctx.get("target_cover", False)
    ss["charged"] = ctx.get("charged", False)
    ss["n_runs"] = ctx.get("n_runs", 2000)


# ---------------------------------------------------------------------------
# Sérialisation / Désérialisation
# ---------------------------------------------------------------------------

def deserialize_profiles(raw) -> list:
    """Interprète la valeur brute retournée par st_javascript."""
    if raw in (0, None, "null", "undefined"):
        return []
    try:
        profiles = json.loads(raw)
        if not isinstance(profiles, list):
            return []
        return [p for p in profiles if isinstance(p, dict) and p.get("version") == PROFILE_VERSION]
    except (json.JSONDecodeError, TypeError):
        return []


def js_read() -> str:
    return f"localStorage.getItem('{STORAGE_KEY}')"


def js_write(profiles: list) -> str:
    json_str = json.dumps(profiles, ensure_ascii=False)
    safe = json_str.replace("\\", "\\\\").replace("`", "\\`")
    return f"localStorage.setItem('{STORAGE_KEY}', `{safe}`)"
