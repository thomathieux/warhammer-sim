# -*- coding: utf-8 -*-
"""
Warhammer 40,000 — Simulateur de combat
Powered by Wahapedia
"""

import sys
import base64
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import streamlit as st
import plotly.graph_objects as go
import plotly.express as px

from data.loader import load_all_units, list_factions
from data.unit_builder import build_weapon_groups, build_defending_unit
from units.profiles import DefendingModel
from core.context import CombatContext
from core.simulation.attack_sequence import AttackSequence
from core.enums import RerollType
from stats.aggregator import StatsAggregator

# ---------------------------------------------------------------------------
# Config page
# ---------------------------------------------------------------------------

st.set_page_config(
    page_title="Warhammer 40K Simulator",
    page_icon="⚔️",
    layout="wide",
)

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Cinzel:wght@400;600;700&family=Lora:ital,wght@0,400;0,500;1,400&family=JetBrains+Mono:wght@400;500&display=swap');

/* Titres : Cinzel (inscription, lisible, field manual) */
.stApp h1, .stApp h2, .stApp h3, .stApp h4 {
    font-family: 'Cinzel', Georgia, serif !important;
    font-weight: 600;
    letter-spacing: 0.05em;
    color: #1a1a2e;
}

/* Corps de texte : Lora (serif lisible, elegante) */
.stApp p,
.stApp label,
.stApp .stMarkdown p,
.stApp .stMarkdown li,
.stApp .stMarkdown td,
.stApp .stSelectbox label,
.stApp .stMultiSelect label,
.stApp .stNumberInput label,
.stApp .stCheckbox label,
.stApp .stRadio label,
.stApp .stCaption,
.stApp .stText,
.stApp input,
.stApp textarea {
    font-family: 'Lora', Georgia, serif !important;
    font-size: 15px !important;
    color: #1a1a2e;
}

/* Boutons */
.stApp button {
    font-family: 'Cinzel', Georgia, serif !important;
}
.stButton > button[kind="primary"] {
    background-color: #C47A5A !important;
    color: #1a1a2e !important;
    border: none !important;
    font-size: 1rem !important;
    font-weight: 600 !important;
    letter-spacing: 0.12em !important;
    border-radius: 4px !important;
}
.stButton > button[kind="primary"]:hover {
    background-color: #1a1a2e !important;
    color: #F5F0E8 !important;
}

/* Metriques */
[data-testid="stMetricValue"] {
    font-family: 'JetBrains Mono', monospace !important;
    font-size: 1.4rem !important;
    color: #C47A5A !important;
}
[data-testid="stMetricLabel"] {
    font-family: 'Cinzel', serif !important;
    font-size: 0.68rem !important;
    letter-spacing: 0.08em;
    color: #5a5a7a !important;
}

/* Separateurs */
hr { border-color: #1a1a2e; opacity: 0.15; }

/* Expanders */
[data-testid="stExpander"] {
    border: 1px solid #c8bfb0 !important;
    border-radius: 4px !important;
    background: #FAF7F2 !important;
}
</style>
""", unsafe_allow_html=True)

# ---------------------------------------------------------------------------
# Icônes SVG
# ---------------------------------------------------------------------------

_ICONS_DIR = Path(__file__).parent / "assets" / "icons"
_icon_cache: dict[str, str] = {}

def _icon_b64(name: str) -> str:
    if name not in _icon_cache:
        p = _ICONS_DIR / f"{name}.svg"
        if p.exists():
            _icon_cache[name] = base64.b64encode(p.read_bytes()).decode()
        else:
            _icon_cache[name] = ""
    return _icon_cache[name]

def icon_img(name: str, size: int = 24) -> str:
    b64 = _icon_b64(name)
    if not b64:
        return ""
    return (
        f'<img src="data:image/svg+xml;base64,{b64}" '
        f'width="{size}" height="{size}" style="vertical-align:middle;margin-right:6px">'
    )

def get_unit_icon(unit) -> str:
    kws = {k.upper() for k in unit.keywords}
    if "CHARACTER" in kws:
        return "commander"
    if "MONSTER" in kws or "BEAST" in kws:
        return "creature"
    if "VEHICLE" in kws:
        return "vehicle"
    if "GRAVIS" in kws or "TERMINATOR" in kws:
        return "heavy"
    return "infantry"

def get_weapon_icon(weapon) -> str:
    name_l = weapon.name.lower()
    kw = weapon.keywords
    if weapon.range.lower() == "melee":
        return "blade"
    if getattr(kw, "torrent", False) or "flame" in name_l or "flamer" in name_l:
        return "flame"
    if getattr(kw, "blast", False) or "blast" in name_l:
        return "blast"
    if "plasma" in name_l:
        return "plasma"
    cannon_words = ("cannon", "lascannon", "autocannon", "railgun",
                    "missile", "mortar", "demolisher", "volcano")
    if any(w in name_l for w in cannon_words):
        return "cannon"
    try:
        if int(str(weapon.strength)) >= 8:
            return "cannon"
    except (ValueError, TypeError):
        pass
    return "bolter"

# ---------------------------------------------------------------------------
# Cache données Wahapedia
# ---------------------------------------------------------------------------

@st.cache_data
def get_factions():
    rows = list_factions()
    return {r["name"]: r["id"] for r in sorted(rows, key=lambda r: r["name"])}

@st.cache_data
def get_units_by_faction(faction_id):
    units = load_all_units(faction_id=faction_id)
    return {u.name: u for u in sorted(units, key=lambda u: u.name)}

@st.cache_data
def get_character_units(faction_id):
    units = load_all_units(faction_id=faction_id)
    chars = [u for u in units if "CHARACTER" in [k.upper() for k in u.keywords]]
    return {u.name: u for u in sorted(chars, key=lambda u: u.name)}

# ---------------------------------------------------------------------------
# Helpers — datacard HTML
# ---------------------------------------------------------------------------

_S_SECTION_H = (
    "font-family:'Cinzel',Georgia,serif;"
    "font-weight:600;font-size:1.15rem;letter-spacing:0.08em;"
    "color:#1a1a2e;border-bottom:1.5px solid #1a1a2e;"
    "padding-bottom:6px;margin-bottom:12px;"
    "display:flex;align-items:center;gap:8px;"
)

def section_header(icon_name: str, label: str):
    ico = icon_img(icon_name, size=26)
    st.markdown(
        f'<div style="{_S_SECTION_H}">{ico}{label}</div>',
        unsafe_allow_html=True,
    )

def _filter_abilities(abilities: list) -> list:
    """Exclut les abilities génériques non pertinentes pour la simulation."""
    result = []
    for ab in abilities:
        name = ab.get("name", "").strip().upper()
        desc = ab.get("description", "")
        # Règle générique LEADER (texte universel sur les unités attachées)
        if name == "LEADER":
            continue
        # Abilities de faction (texte commençant par "If your Army Faction is")
        if desc.lstrip().startswith("If your Army Faction is"):
            continue
        # Abilities avec HTML brut de Wahapedia (balises de mise en forme)
        if "<span" in desc or "<div" in desc:
            continue
        result.append(ab)
    return result

_S_CARD  = "background:#FAF7F2;border:1.5px solid #1a1a2e;border-radius:6px;padding:12px 16px;margin-bottom:8px;"
_S_TITLE = "font-family:'Cinzel',Georgia,serif;font-weight:600;font-size:0.95rem;letter-spacing:0.04em;color:#1a1a2e;margin-bottom:10px;display:flex;align-items:center;gap:8px;"
_S_ROW   = "display:flex;flex-direction:row;gap:8px;flex-wrap:wrap;margin-bottom:8px;"
_S_BOX   = "display:inline-block;background:#F0EBE0;border:1px solid #c8bfb0;border-radius:3px;padding:5px 12px;text-align:center;min-width:48px;"
_S_LBL   = "display:block;font-family:'JetBrains Mono',monospace;font-size:0.58rem;color:#6a6a8a;text-transform:uppercase;letter-spacing:0.1em;"
_S_VAL   = "display:block;font-family:'JetBrains Mono',monospace;font-size:1.1rem;font-weight:500;color:#1a1a2e;line-height:1.3;"
_S_KW    = "display:inline-block;background:#E8F0EC;color:#1a4030;border:1px solid #7A9E7E;border-radius:2px;padding:2px 7px;font-size:0.7rem;margin:2px 3px 0 0;font-family:'JetBrains Mono',monospace;"
_S_WARN  = "display:inline-block;background:#F5EDE4;color:#6a2a10;border:1px solid #C47A5A;border-radius:2px;padding:2px 7px;font-size:0.7rem;margin:2px 3px 0 0;font-family:'JetBrains Mono',monospace;"

def _kw_chip(text, warn=False):
    s = _S_WARN if warn else _S_KW
    return f'<span style="{s}">{text}</span>'

def _stat(label, value):
    return (
        f'<div style="{_S_BOX}">'
        f'<span style="{_S_LBL}">{label}</span>'
        f'<span style="{_S_VAL}">{value}</span>'
        f'</div>'
    )

def unit_datacard_html(unit, model=None) -> str:
    if model is None:
        model = unit.primary_model()
    if model is None:
        return ""

    inv = f"{model.invulnerable_save}+" if model.invulnerable_save else "—"
    kw_html = " ".join(_kw_chip(k) for k in unit.keywords[:8])
    ico = icon_img(get_unit_icon(unit), size=28)

    stats = (
        _stat("E", model.toughness)
        + _stat("SV", f"{model.save}+")
        + _stat("Inv", inv)
        + _stat("PV", model.wounds)
    )
    return (
        f'<div style="{_S_CARD}">'
        f'<div style="{_S_TITLE}">{ico}{unit.name}</div>'
        f'<div style="{_S_ROW}">{stats}</div>'
        f'<div style="margin-top:4px">{kw_html}</div>'
        f'</div>'
    )

def weapon_datacard_html(weapon) -> str:
    kw = weapon.keywords
    chips = []
    for attr, label in [
        ("torrent", "Torrent"), ("blast", "Blast"), ("lethal_hits", "Lethal Hits"),
        ("devastating_wounds", "Dev. Wounds"), ("ignores_cover", "Ignores Cover"),
        ("twin_linked", "Twin-linked"),
    ]:
        if getattr(kw, attr, False):
            chips.append(_kw_chip(label))
    if kw.sustained_hits:
        chips.append(_kw_chip(f"Sustained {kw.sustained_hits}"))
    if kw.rapid_fire:
        chips.append(_kw_chip(f"Rapid Fire {kw.rapid_fire}"))
    if kw.melta:
        chips.append(_kw_chip(f"Melta {kw.melta}"))
    if kw.anti_keyword:
        chips.append(_kw_chip(f"Anti-{kw.anti_keyword} {kw.anti_threshold}+"))
    for u in kw.unknown:
        chips.append(_kw_chip(u, warn=True))
    kw_html = " ".join(chips)
    rng = weapon.range if weapon.range.lower() != "melee" else "Mêlée"
    ico = icon_img(get_weapon_icon(weapon), size=24)

    stats = (
        _stat("Portée", rng)
        + _stat("A", weapon.attacks)
        + _stat("CC/CT", f"{weapon.skill}+")
        + _stat("F", weapon.strength)
        + _stat("PA", weapon.ap)
        + _stat("D", weapon.damage)
    )
    kw_block = f'<div style="margin-top:4px">{kw_html}</div>' if kw_html else ""
    return (
        f'<div style="{_S_CARD}">'
        f'<div style="{_S_TITLE}">{ico}{weapon.name}</div>'
        f'<div style="{_S_ROW}">{stats}</div>'
        f'{kw_block}'
        f'</div>'
    )

# ---------------------------------------------------------------------------
# Helpers — graphiques
# ---------------------------------------------------------------------------

REROLL_OPTIONS = {
    "Aucune": RerollType.NONE,
    "Relancer les 1": RerollType.ONE,
    "Relancer les échecs": RerollType.FAILED,
}

# Palette DA pour les graphiques
_DA_BG       = "#F5F0E8"
_DA_BG2      = "#FAF7F2"
_DA_INK      = "#1a1a2e"
_DA_GRID     = "#D8D0C0"
_DA_TERRACOTTA = "#C47A5A"
_DA_BLUE     = "#7A9EC4"
_DA_GREEN    = "#7A9E7E"

_CHART_BASE = dict(
    plot_bgcolor=_DA_BG2,
    paper_bgcolor=_DA_BG,
    font=dict(family="Cormorant Garamond, Georgia, serif", color=_DA_INK, size=13),
    title_font=dict(family="Cormorant Garamond, Georgia, serif", size=15, color=_DA_INK),
    margin=dict(t=40, l=40, r=20, b=40),
)

def _apply_grid(fig):
    fig.update_xaxes(gridcolor=_DA_GRID, linecolor=_DA_INK, zerolinecolor=_DA_GRID)
    fig.update_yaxes(gridcolor=_DA_GRID, linecolor=_DA_INK, zerolinecolor=_DA_GRID)
    return fig

def make_damage_histogram(results, weapon_name):
    damages = [r.allocation.damage_allocated for r in results]
    if not damages:
        return go.Figure()
    nbins = max(1, max(damages) - min(damages) + 1)
    fig = px.histogram(
        x=damages, nbins=nbins,
        labels={"x": "Dégâts alloués", "y": "Fréquence"},
        title="Distribution des dégâts",
        color_discrete_sequence=[_DA_TERRACOTTA],
    )
    fig.update_traces(marker_line_color=_DA_INK, marker_line_width=0.8)
    fig.update_layout(showlegend=False, bargap=0.06, **_CHART_BASE)
    return _apply_grid(fig)

def make_kill_chart(results, weapon_name, max_models):
    from collections import Counter
    kills = [r.allocation.models_killed for r in results]
    counts = Counter(kills)
    n = len(results)
    x = list(range(0, max_models + 1))
    y = [counts.get(k, 0) / n * 100 for k in x]
    fig = go.Figure(go.Bar(
        x=x, y=y,
        marker_color=_DA_BLUE,
        marker_line_color=_DA_INK,
        marker_line_width=0.8,
        text=[f"{v:.1f}%" for v in y], textposition="outside",
        textfont=dict(family="JetBrains Mono, monospace", size=11, color=_DA_INK),
    ))
    fig.update_layout(
        title="Figurines éliminées",
        xaxis_title="Figurines tuées", yaxis_title="Probabilité (%)",
        yaxis_range=[0, max(y) * 1.25 + 1] if max(y) > 0 else [0, 10],
        showlegend=False, **_CHART_BASE,
    )
    return _apply_grid(fig)

def make_cumulative_chart(results, weapon_name):
    damages = sorted([r.allocation.damage_allocated for r in results])
    n = len(damages)
    x, y = [], []
    for v in range(0, max(damages) + 2):
        x.append(v)
        y.append(sum(1 for d in damages if d >= v) / n * 100)
    fig = go.Figure(go.Scatter(
        x=x, y=y, mode="lines", fill="tozeroy",
        line=dict(color=_DA_GREEN, width=2.5),
        fillcolor=f"rgba(122,158,126,0.18)",
    ))
    fig.update_layout(
        title="P(dégâts ≥ X)",
        xaxis_title="Dégâts", yaxis_title="Probabilité (%)",
        yaxis_range=[0, 105],
        showlegend=False, **_CHART_BASE,
    )
    return _apply_grid(fig)

# ---------------------------------------------------------------------------
# Section attaquant
# ---------------------------------------------------------------------------

def render_attacker_section(factions):
    section_header("attacker", "Attaquant")

    atk_faction_name = st.selectbox("Faction", list(factions.keys()), key="atk_faction")
    atk_faction_id = factions[atk_faction_name]
    atk_units = get_units_by_faction(atk_faction_id)

    atk_unit_name = st.selectbox("Unité", list(atk_units.keys()), key="atk_unit")
    atk_unit = atk_units[atk_unit_name]
    primary = atk_unit.primary_model()

    if primary:
        st.markdown(unit_datacard_html(atk_unit, primary), unsafe_allow_html=True)

    # --- Répartition des armes ---
    st.markdown("**Répartition des armes**")
    weapon_names = [w.name for w in atk_unit.weapons]
    selected_weapons = st.multiselect(
        "Armes disponibles", weapon_names,
        default=weapon_names[:1] if weapon_names else [],
        key="atk_weapons",
    )

    _atk_default = atk_unit.max_models if atk_unit.max_models > 1 else 5
    total_models = st.number_input(
        "Figurines dans l'unité",
        min_value=1, value=_atk_default, key=f"atk_total_count_{atk_unit_name}",
    )

    weapon_dist = {}
    assigned = 0
    for wname in selected_weapons:
        weapon = atk_unit.get_weapon(wname)
        if weapon:
            st.markdown(weapon_datacard_html(weapon), unsafe_allow_html=True)
        remaining = int(total_models) - assigned
        count = st.number_input(
            f"Figurines avec **{wname}**",
            min_value=0, max_value=int(total_models),
            value=min(remaining, int(total_models)),
            key=f"wdist_{wname}",
        )
        weapon_dist[wname] = int(count)
        assigned += int(count)

    # Compteur total (indicatif uniquement)
    if selected_weapons:
        ok = assigned == int(total_models)
        color = "#7A9E7E" if ok else "#C47A5A"
        st.markdown(
            f'<span style="font-family:\'JetBrains Mono\',monospace;font-size:0.8rem;color:{color}">'
            f'{assigned} / {int(total_models)} figurines assignées</span>',
            unsafe_allow_html=True,
        )

    # --- Relances ---
    with st.expander("Relances"):
        hit_rr = REROLL_OPTIONS[st.selectbox("Relance touche", list(REROLL_OPTIONS.keys()), key="hit_rr")]
        wound_rr = REROLL_OPTIONS[st.selectbox("Relance blessure", list(REROLL_OPTIONS.keys()), key="wound_rr")]

    # --- Leaders attachés (attaquant) ---
    atk_hit_modifier = 0
    atk_leader_loadout = []

    with st.expander("👑 Attacher un leader / support"):
        char_units = get_character_units(atk_faction_id)
        if not char_units:
            st.caption("Aucune unité CHARACTER dans cette faction.")
        else:
            for slot_key, slot_label in [("leader", "Leader"), ("support", "Support (2e personnage)")]:
                attach = st.checkbox(f"Attacher un {slot_label}", key=f"atk_attach_{slot_key}")
                if attach:
                    char_name = st.selectbox(
                        slot_label, list(char_units.keys()), key=f"atk_{slot_key}_name"
                    )
                    char_unit = char_units[char_name]
                    cm = char_unit.primary_model()
                    if cm:
                        st.markdown(unit_datacard_html(char_unit, cm), unsafe_allow_html=True)

                    unit_kws = set(k.upper() for k in atk_unit.keywords)
                    char_kws = set(k.upper() for k in char_unit.keywords)
                    if not unit_kws.intersection(char_kws - {"CHARACTER"}):
                        st.warning("⚠️ Aucun mot-clé commun — vérifiez les règles d'attachement.")

                    char_weapons = [w.name for w in char_unit.weapons]
                    sel_w = st.multiselect(
                        f"Armes du {slot_label}", char_weapons,
                        default=char_weapons[:1] if char_weapons else [],
                        key=f"atk_{slot_key}_weapons",
                    )
                    for wname in sel_w:
                        w = char_unit.get_weapon(wname)
                        if w:
                            st.markdown(weapon_datacard_html(w), unsafe_allow_html=True)
                        atk_leader_loadout.append((char_unit, wname, 1))

                    abilities = _filter_abilities(char_unit.abilities)
                    if abilities:
                        st.markdown(f"**Abilities — {char_name}**")
                        for ab in abilities[:6]:
                            with st.expander(ab["name"], expanded=False):
                                st.caption(ab.get("description", ""))

                    st.markdown("**Effets simulables**")
                    if st.checkbox(f"+1 touche ({slot_label})", key=f"atk_{slot_key}_hit_plus"):
                        atk_hit_modifier += 1
                    if st.checkbox(f"-1 touche ({slot_label})", key=f"atk_{slot_key}_hit_minus"):
                        atk_hit_modifier -= 1

    return {
        "unit": atk_unit,
        "weapon_dist": weapon_dist,
        "hit_rr": hit_rr,
        "wound_rr": wound_rr,
        "hit_modifier": atk_hit_modifier,
        "leader_loadout": atk_leader_loadout,
    }

# ---------------------------------------------------------------------------
# Section défenseur
# ---------------------------------------------------------------------------

def render_defender_section(factions):
    section_header("defender", "Défenseur")

    def_faction_name = st.selectbox("Faction", list(factions.keys()), key="def_faction")
    def_faction_id = factions[def_faction_name]
    def_units = get_units_by_faction(def_faction_id)

    def_unit_name = st.selectbox("Unité", list(def_units.keys()), key="def_unit")
    def_unit = def_units[def_unit_name]
    dm = def_unit.primary_model()
    if dm:
        st.markdown(unit_datacard_html(def_unit, dm), unsafe_allow_html=True)

    def_model_count = st.number_input(
        "Nombre de figurines",
        min_value=1, max_value=max(def_unit.max_models, 1),
        value=max(def_unit.max_models, 1), key=f"def_count_{def_unit_name}",
    )

    # --- Leader attaché (défenseur) ---
    def_hit_modifier = 0
    def_wound_modifier = 0
    def_damage_reduction = 0
    def_fnp = None
    leader_defending_model = None
    support_defending_model = None

    with st.expander("👑 Attacher un leader / support"):
        char_units = get_character_units(def_faction_id)
        if not char_units:
            st.caption("Aucune unité CHARACTER dans cette faction.")
        else:
            attach_leader = st.checkbox("Attacher un leader", key="def_attach_leader")
            if attach_leader:
                leader_name = st.selectbox(
                    "Leader", list(char_units.keys()), key="def_leader_name"
                )
                leader_unit = char_units[leader_name]
                lm = leader_unit.primary_model()
                if lm:
                    st.markdown(unit_datacard_html(leader_unit, lm), unsafe_allow_html=True)
                    leader_defending_model = DefendingModel(
                        toughness=lm.toughness,
                        save=lm.save,
                        wounds=lm.wounds,
                        invulnerable_save=lm.invulnerable_save,
                    )

                unit_kws = set(k.upper() for k in def_unit.keywords)
                leader_kws = set(k.upper() for k in leader_unit.keywords)
                if not unit_kws.intersection(leader_kws - {"CHARACTER"}):
                    st.warning("⚠️ Aucun mot-clé commun — vérifiez les règles d'attachement.")

                abilities = _filter_abilities(leader_unit.abilities)
                if abilities:
                    st.markdown("**Abilities du leader**")
                    for ab in abilities[:6]:
                        with st.expander(ab["name"], expanded=False):
                            st.caption(ab.get("description", ""))

                st.markdown("**Effets simulables**")
                if st.checkbox("-1 à la touche pour l'attaquant", key="def_hit_minus"):
                    def_hit_modifier -= 1
                if st.checkbox("-1 à la blessure pour l'attaquant", key="def_wound_minus"):
                    def_wound_modifier -= 1
                if st.checkbox("-1 dégât pour l'unité", key="def_dmg_minus"):
                    def_damage_reduction += 1
                fnp_enabled = st.checkbox("FNP pour l'unité", key="def_fnp_enabled")
                if fnp_enabled:
                    def_fnp = st.select_slider(
                        "Valeur FNP", options=[4, 5, 6], value=6, key="def_fnp_val"
                    )

            attach_support = st.checkbox("Attacher un support (2e personnage)", key="def_attach_support")
            if attach_support:
                support_name = st.selectbox(
                    "Support", list(char_units.keys()), key="def_support_name"
                )
                support_unit = char_units[support_name]
                sm = support_unit.primary_model()
                if sm:
                    st.markdown(unit_datacard_html(support_unit, sm), unsafe_allow_html=True)
                    support_defending_model = DefendingModel(
                        toughness=sm.toughness,
                        save=sm.save,
                        wounds=sm.wounds,
                        invulnerable_save=sm.invulnerable_save,
                    )

    return {
        "unit": def_unit,
        "model_count": int(def_model_count),
        "hit_modifier": def_hit_modifier,
        "wound_modifier": def_wound_modifier,
        "damage_reduction": def_damage_reduction,
        "fnp": def_fnp,
        "leader_model": leader_defending_model,
        "support_model": support_defending_model,
    }

# ---------------------------------------------------------------------------
# Interface principale
# ---------------------------------------------------------------------------

st.markdown(
    '<h1 style="font-family:\'Cinzel\',Georgia,serif;'
    'font-size:2rem;font-weight:700;letter-spacing:0.08em;'
    'border-bottom:2px solid #1a1a2e;padding-bottom:8px;margin-bottom:4px">'
    'Warhammer 40,000 — Simulateur de combat</h1>',
    unsafe_allow_html=True,
)
st.markdown(
    '<p style="font-size:0.8rem;letter-spacing:0.12em;color:#8a8a9a;margin-top:0">'
    'POWERED BY WAHAPEDIA · wahapedia.ru</p>',
    unsafe_allow_html=True,
)

factions = get_factions()

col_atk, col_def, col_ctx = st.columns([1, 1, 1])

with col_atk:
    atk_cfg = render_attacker_section(factions)

with col_def:
    def_cfg = render_defender_section(factions)

with col_ctx:
    section_header("context", "Contexte")
    combat_type = st.radio("Type de combat", ["Distance", "Mêlée"], horizontal=True)
    within_half = st.checkbox("Dans la moitié de la portée (Rapid Fire, Melta)")
    target_cover = st.checkbox("Cible en couverture")
    charged = st.checkbox("Attaquant a chargé (Lance)")
    st.divider()
    n_runs = st.select_slider(
        "Simulations Monte Carlo",
        options=[500, 1000, 2000, 5000, 10000],
        value=2000,
    )

st.divider()
simulate_btn = st.button("▶ Simuler", type="primary", use_container_width=True)

# ---------------------------------------------------------------------------
# Simulation
# ---------------------------------------------------------------------------

if simulate_btn:
    context = CombatContext(
        combat_type="ranged" if combat_type == "Distance" else "melee",
        within_half_range=within_half,
        target_in_cover=target_cover,
        attacker_charged=charged,
    )

    # Construire tous les groupes d'armes (unité principale + armes du leader)
    all_groups = []

    # Unité principale
    loadout = [
        (wname, count)
        for wname, count in atk_cfg["weapon_dist"].items()
        if count > 0
    ]
    if loadout:
        try:
            groups = build_weapon_groups(
                atk_cfg["unit"], loadout, context,
                hit_reroll=atk_cfg["hit_rr"],
                wound_reroll=atk_cfg["wound_rr"],
                hit_modifier=atk_cfg["hit_modifier"],
            )
            all_groups.extend(groups)
        except ValueError as e:
            st.error(str(e))
            st.stop()

    # Armes du leader (attaquant)
    for leader_unit, wname, count in atk_cfg["leader_loadout"]:
        try:
            lg = build_weapon_groups(
                leader_unit, [(wname, count)], context,
                hit_reroll=atk_cfg["hit_rr"],
                wound_reroll=atk_cfg["wound_rr"],
                hit_modifier=atk_cfg["hit_modifier"],
            )
            all_groups.extend(lg)
        except ValueError:
            pass

    if not all_groups:
        st.warning("Aucune arme compatible avec le type de combat sélectionné.")
        st.stop()

    # Défenseur
    defender = build_defending_unit(
        def_cfg["unit"],
        model_count=def_cfg["model_count"],
        leader_model=def_cfg["leader_model"],
        support_model=def_cfg["support_model"],
        hit_modifier=def_cfg["hit_modifier"],
        wound_modifier=def_cfg["wound_modifier"],
        damage_reduction=def_cfg["damage_reduction"],
        fnp=def_cfg["fnp"],
    )

    with st.spinner(f"Simulation en cours ({n_runs} runs)..."):
        seq = AttackSequence()
        all_results = {g.weapon_name: [] for g in all_groups}

        for _ in range(n_runs):
            defender.reset()
            for group in all_groups:
                result = seq.resolve(group, defender, context)
                all_results[group.weapon_name].append(result)

    st.success(f"Simulation terminée — {n_runs} runs × {len(all_groups)} groupe(s) d'armes")

    for weapon_name, results in all_results.items():
        agg = StatsAggregator(results).aggregate()
        alloc = agg["allocation"]

        # Trouver l'arme pour l'icône
        _w = atk_cfg["unit"].get_weapon(weapon_name)
        _ico_name = get_weapon_icon(_w) if _w else "bolter"
        _ico_html = icon_img(_ico_name, size=28)
        st.markdown(
            f'<h3 style="display:flex;align-items:center;gap:8px">'
            f'{_ico_html}{weapon_name}</h3>',
            unsafe_allow_html=True,
        )

        initial_count = def_cfg["model_count"]
        destruction_rate = sum(
            1 for r in results if r.allocation.models_killed >= initial_count
        ) / len(results)
        models_remaining_mean = max(0, initial_count - alloc["models_killed_mean"])

        m1, m2, m3, m4, m5, m6 = st.columns(6)
        m1.metric("Dégâts moyens", f"{alloc['damage_allocated_mean']:.2f}")
        m2.metric("Figurines tuées (moy.)", f"{alloc['models_killed_mean']:.2f}")
        m3.metric("Figurines restantes (moy.)", f"{models_remaining_mean:.2f}")
        m4.metric("Taux de destruction", f"{destruction_rate*100:.1f}%",
                  help="Probabilité d'éliminer toute l'unité en un round")
        m5.metric("FNP ignorés", f"{alloc['fnp_ignored_damage_mean']:.2f}")
        m6.metric("Spillover perdu", f"{alloc['spillover_damage_mean']:.2f}")

        if alloc.get("leader_kill_rate", 0) > 0:
            st.info(f"Taux de mort du leader : {alloc['leader_kill_rate']*100:.1f}%")
        if alloc.get("support_kill_rate", 0) > 0:
            st.info(f"Taux de mort du support : {alloc['support_kill_rate']*100:.1f}%")

        gc1, gc2, gc3 = st.columns(3)
        with gc1:
            st.plotly_chart(make_damage_histogram(results, weapon_name), use_container_width=True)
        with gc2:
            st.plotly_chart(make_kill_chart(results, weapon_name, def_cfg["model_count"]), use_container_width=True)
        with gc3:
            st.plotly_chart(make_cumulative_chart(results, weapon_name), use_container_width=True)

        with st.expander("Stats détaillées par phase"):
            hit = agg["hit"]
            wound = agg["wound"]
            save = agg["save"]
            c1, c2, c3 = st.columns(3)
            with c1:
                st.markdown("**Touche**")
                st.write(f"Touches : {hit['hits_mean']:.2f} ± {hit['hits_std']:.2f}")
                st.write(f"Crits : {hit['critical_hits_mean']:.2f}")
                st.write(f"Auto-blessures (Lethal) : {hit['auto_wounds_mean']:.2f}")
                st.write(f"Sustained générés : {hit['sustained_hits_mean']:.2f}")
            with c2:
                st.markdown("**Blessure**")
                st.write(f"Blessures : {wound['wounds_mean']:.2f} ± {wound['wounds_std']:.2f}")
                st.write(f"Crits : {wound['critical_wounds_mean']:.2f}")
                st.write(f"Mortelles : {wound['mortal_wounds_mean']:.2f}")
            with c3:
                st.markdown("**Sauvegarde**")
                st.write(f"Tentées : {save['saves_attempted_mean']:.2f}")
                st.write(f"Ratées : {save['saves_failed_mean']:.2f}")

    st.divider()
    st.markdown(
        '<p style="font-size:0.72rem;letter-spacing:0.1em;color:#8a8a9a;text-align:center">'
        'POWERED BY WAHAPEDIA · wahapedia.ru &nbsp;·&nbsp; '
        'Warhammer 40,000 © Games Workshop Ltd — fan project, non affilié</p>',
        unsafe_allow_html=True,
    )
