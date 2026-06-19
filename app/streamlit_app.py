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
import streamlit.components.v1 as _st_components
import plotly.graph_objects as go
import plotly.express as px
import numpy as np

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
    qty = getattr(weapon, "quantity", 1)
    qty_badge = (
        f' <span style="background:#C47A5A;color:#fff;border-radius:3px;'
        f'padding:1px 6px;font-size:0.72rem;font-family:\'JetBrains Mono\',monospace;">'
        f'×{qty}</span>'
        if qty > 1 else ""
    )
    return (
        f'<div style="{_S_CARD}">'
        f'<div style="{_S_TITLE}">{ico}{weapon.name}{qty_badge}</div>'
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
_DA_ROSE     = "#C4867A"
_DA_SAND     = "#C4A87A"

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
    # KDE via noyau gaussien (numpy, sans scipy)
    data = np.array(damages, dtype=float)
    bw = max(1.06 * np.std(data) * len(data) ** (-0.2), 0.5)
    x_kde = np.linspace(max(0.0, float(min(damages)) - 1), float(max(damages)) + 2, 200)
    kde_y = np.zeros_like(x_kde)
    for xi in data:
        kde_y += np.exp(-0.5 * ((x_kde - xi) / bw) ** 2)
    kde_y /= (len(data) * bw * np.sqrt(2 * np.pi))

    fig = go.Figure()
    fig.add_trace(go.Histogram(
        x=damages, nbinsx=nbins, histnorm="probability density",
        marker_color=_DA_TERRACOTTA, marker_line_color=_DA_INK, marker_line_width=0.6,
        opacity=0.65, name="Distribution",
    ))
    fig.add_trace(go.Scatter(
        x=x_kde, y=kde_y, mode="lines",
        line=dict(color=_DA_INK, width=2),
        name="KDE",
    ))
    fig.update_layout(
        title="Distribution des dégâts",
        xaxis_title="Dégâts alloués", yaxis_title="Densité",
        showlegend=True, bargap=0.06,
        legend=dict(font=dict(size=9), bgcolor="rgba(250,247,242,0.8)", x=0.68, y=0.95),
        **_CHART_BASE,
    )
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

def make_percentile_bands_chart(results):
    damages = [r.allocation.damage_allocated for r in results]
    if not damages:
        return go.Figure()
    max_d = max(damages)
    x_vals = list(range(0, max_d + 2))
    n = len(damages)
    surv = [sum(1 for d in damages if d >= v) / n * 100 for v in x_vals]

    p10 = float(np.percentile(damages, 10))
    p25 = float(np.percentile(damages, 25))
    p75 = float(np.percentile(damages, 75))
    p90 = float(np.percentile(damages, 90))
    med = float(np.median(damages))

    def _band(lo, hi, color, name):
        xs = [v for v in x_vals if lo <= v <= hi]
        ys = [surv[v] for v in xs]
        if not xs:
            return None
        return go.Scatter(
            x=xs + xs[::-1], y=ys + [0] * len(ys),
            fill="toself", fillcolor=color,
            line=dict(color="rgba(0,0,0,0)"),
            name=name, showlegend=True,
        )

    fig = go.Figure()
    b80 = _band(p10, p90, "rgba(122,158,126,0.18)", "P10–P90 (80%)")
    b50 = _band(p25, p75, "rgba(122,158,126,0.42)", "P25–P75 (50%)")
    if b80:
        fig.add_trace(b80)
    if b50:
        fig.add_trace(b50)
    fig.add_trace(go.Scatter(
        x=x_vals, y=surv, mode="lines",
        line=dict(color=_DA_GREEN, width=2.5),
        showlegend=False,
    ))
    fig.add_vline(
        x=med, line_dash="dot", line_color=_DA_TERRACOTTA, line_width=1.5,
        annotation_text=f"Médiane : {med:.0f}",
        annotation_position="top right",
        annotation_font_size=9, annotation_font_color=_DA_INK,
    )
    fig.update_layout(
        title="P(dégâts >= X)",
        xaxis_title="Dégâts", yaxis_title="Probabilité (%)",
        yaxis_range=[0, 105],
        legend=dict(font=dict(size=9), bgcolor="rgba(250,247,242,0.8)", x=0.55, y=0.95),
        **_CHART_BASE,
    )
    return _apply_grid(fig)

# ---------------------------------------------------------------------------
# Helpers — rapport enrichi (gauge, narratif, funnel)
# ---------------------------------------------------------------------------

def compute_threat_score(destruction_rate: float, models_killed_mean: float, model_count: int) -> float:
    kills_ratio = min(1.0, models_killed_mean / max(model_count, 1))
    return min(1.0, 0.40 * destruction_rate + 0.60 * kills_ratio)


def make_threat_gauge(score: float):
    if score < 0.25:
        bar_color, verdict = _DA_GREEN, "IMPACT LIMITÉ"
    elif score < 0.50:
        bar_color, verdict = _DA_SAND, "PRESSION MODÉRÉE"
    elif score < 0.75:
        bar_color, verdict = _DA_TERRACOTTA, "MENACE ÉLEVÉE"
    else:
        bar_color, verdict = _DA_ROSE, "MENACE CRITIQUE"

    fig = go.Figure(go.Indicator(
        mode="gauge+number",
        value=round(score * 100),
        number=dict(
            suffix="%",
            font=dict(family="JetBrains Mono, monospace", size=30, color=bar_color),
        ),
        title=dict(
            text=f"<b>{verdict}</b>",
            font=dict(family="Cinzel, Georgia, serif", size=12, color=_DA_INK),
        ),
        gauge=dict(
            axis=dict(range=[0, 100], tickwidth=1, tickcolor=_DA_INK, tickfont=dict(size=8)),
            bar=dict(color=bar_color, thickness=0.22),
            bgcolor=_DA_BG2,
            borderwidth=1.5,
            bordercolor=_DA_INK,
            steps=[
                dict(range=[0, 25],   color="rgba(122,158,126,0.22)"),
                dict(range=[25, 50],  color="rgba(196,168,122,0.22)"),
                dict(range=[50, 75],  color="rgba(196,122,90,0.22)"),
                dict(range=[75, 100], color="rgba(196,134,122,0.22)"),
            ],
        ),
    ))
    fig.update_layout(
        height=210,
        margin=dict(t=55, l=15, r=15, b=5),
        paper_bgcolor=_DA_BG,
        font=dict(family="Cinzel, Georgia, serif", color=_DA_INK),
    )
    return fig


def _narrative_math(alloc: dict, results: list, model_count: int) -> str:
    dmg_vals = [r.allocation.damage_allocated for r in results]
    p10 = int(np.percentile(dmg_vals, 10))
    p90 = int(np.percentile(dmg_vals, 90))
    mean_ = alloc["damage_allocated_mean"]
    kills_mean = alloc["models_killed_mean"]
    destr = sum(1 for r in results if r.allocation.models_killed >= model_count) / len(results)
    return (
        f"{mean_:.1f} dégâts en moyenne &nbsp;·&nbsp; "
        f"80% des simulations entre {p10} et {p90} dégâts &nbsp;·&nbsp; "
        f"{kills_mean:.1f}/{model_count} figurine(s) éliminée(s) &nbsp;·&nbsp; "
        f"destruction totale : {destr * 100:.0f}%"
    )


def _narrative_flavor(
    score: float, alloc: dict, weapon_name: str,
    atk_unit_name: str, def_unit_name: str, model_count: int, results: list,
) -> str:
    kills_mean = alloc["models_killed_mean"]
    destr = sum(1 for r in results if r.allocation.models_killed >= model_count) / len(results)
    pct = destr * 100

    if score >= 0.75:
        return (
            f"Le <em>{weapon_name}</em> des {atk_unit_name} s'avère implacable contre les {def_unit_name}. "
            f"L'anéantissement total est accompli dans {pct:.0f} % des engagements — "
            f"peu d'unités peuvent prétendre résister à une telle puissance de feu."
        )
    elif score >= 0.50:
        return (
            f"Sous le feu du <em>{weapon_name}</em>, les {def_unit_name} subissent des pertes sévères. "
            f"En moyenne, {kills_mean:.1f} figurine(s) ne survivent pas à l'assaut. "
            f"La destruction totale reste une issue probable dans {pct:.0f} % des cas."
        )
    elif score >= 0.25:
        return (
            f"Le <em>{weapon_name}</em> maintient les {def_unit_name} sous pression constante "
            f"sans garantir leur anéantissement. La menace est réelle, mais les {def_unit_name} "
            f"disposent de la résistance nécessaire pour absorber l'essentiel de l'assaut."
        )
    else:
        return (
            f"Face à la résistance des {def_unit_name}, le <em>{weapon_name}</em> "
            f"peine à creuser des brèches décisives. "
            f"Les {atk_unit_name} devront envisager un soutien supplémentaire "
            f"pour emporter l'engagement."
        )


_S_NARR_MATH = (
    "margin:8px 0 4px 0;padding:8px 14px 8px 12px;"
    "background:#F0EBE0;border-left:3px solid #c8bfb0;border-radius:0 3px 3px 0;"
)
_S_NARR_FLAV = (
    "margin:4px 0 14px 0;padding:8px 14px 8px 12px;"
    "background:#F5EDE4;border-left:3px solid #C47A5A;border-radius:0 3px 3px 0;"
)
_S_MATH_TXT = (
    "font-family:'JetBrains Mono',monospace;font-size:0.78rem;"
    "color:#5a5a7a;line-height:1.65;display:block;"
)
_S_FLAV_TXT = (
    "font-family:'Lora',Georgia,serif;font-size:0.88rem;"
    "font-style:italic;color:#1a1a2e;line-height:1.7;display:block;"
)


def render_narrative_duo(text_math: str, text_flavor: str):
    st.markdown(
        f'<div style="{_S_NARR_MATH}"><span style="{_S_MATH_TXT}">{text_math}</span></div>'
        f'<div style="{_S_NARR_FLAV}"><span style="{_S_FLAV_TXT}">{text_flavor}</span></div>',
        unsafe_allow_html=True,
    )


def make_funnel_chart(agg: dict, results: list):
    attacks_mean  = float(np.mean([r.hit.events_in for r in results]))
    hits_mean     = agg["hit"]["hits_mean"]
    wounds_mean   = agg["wound"]["wounds_mean"]
    saves_failed  = agg["save"]["saves_failed_mean"]

    labels = ["Attaques", "Touches", "Blessures", "Non\nsauveg."]
    values = [attacks_mean, hits_mean, wounds_mean, saves_failed]
    colors = [_DA_TERRACOTTA, _DA_SAND, _DA_GREEN, _DA_BLUE]
    pcts   = [v / attacks_mean * 100 if attacks_mean > 0 else 0 for v in values]
    texts  = [
        f"{v:.1f}" if i == 0 else f"{v:.1f}<br>({p:.0f}%)"
        for i, (v, p) in enumerate(zip(values, pcts))
    ]

    fig = go.Figure(go.Bar(
        x=labels, y=values,
        marker_color=colors, marker_line_color=_DA_INK, marker_line_width=0.8,
        text=texts, textposition="outside",
        textfont=dict(family="JetBrains Mono, monospace", size=10, color=_DA_INK),
    ))
    fig.update_layout(
        title="Phases de combat",
        yaxis_title="Moyenne / round",
        showlegend=False,
        yaxis=dict(range=[0, max(values) * 1.42]),
        **_CHART_BASE,
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

    _atk_default = atk_unit.max_models
    total_models = st.number_input(
        "Figurines dans l'unité",
        min_value=1, value=_atk_default, key=f"atk_total_count_{atk_unit_name}",
    )

    weapon_dist = {}
    for wname in selected_weapons:
        weapon = atk_unit.get_weapon(wname)
        if weapon:
            st.markdown(weapon_datacard_html(weapon), unsafe_allow_html=True)
        count = st.number_input(
            f"Figurines avec **{wname}**",
            min_value=0, max_value=int(total_models),
            value=int(total_models),
            key=f"wdist_{wname}",
        )
        weapon_dist[wname] = int(count)

    atk_pts = st.number_input(
        "Coût de l'unité (pts)", min_value=0, value=0, step=5, key="atk_pts",
        help="Laissez à 0 pour ignorer le calcul d'efficacité points",
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
        "pts": int(atk_pts),
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

    group_counts = None
    if len(getattr(def_unit, "model_composition", [])) > 1:
        st.info("Composition intégrée — plusieurs types de figurines sur la même fiche.")
        group_counts = []
        for model_idx, _min_c, max_c in getattr(def_unit, "model_composition", []):
            if model_idx < len(def_unit.models):
                m = def_unit.models[model_idx]
                st.markdown(unit_datacard_html(def_unit, m), unsafe_allow_html=True)
                cnt = st.number_input(
                    f"Nombre de {m.name}",
                    min_value=0, max_value=max_c,
                    value=max_c, key=f"def_grp_{model_idx}_{def_unit_name}",
                )
                group_counts.append(int(cnt))
        def_model_count = sum(group_counts)
    else:
        dm = def_unit.primary_model()
        if dm:
            st.markdown(unit_datacard_html(def_unit, dm), unsafe_allow_html=True)
        def_model_count = st.number_input(
            "Nombre de figurines",
            min_value=1, max_value=max(def_unit.max_models, 1),
            value=max(def_unit.max_models, 1), key=f"def_count_{def_unit_name}",
        )

    def_pts = st.number_input(
        "Coût de l'unité (pts)", min_value=0, value=0, step=5, key="def_pts",
        help="Laissez à 0 pour ignorer le calcul d'efficacité points",
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
        "group_counts": group_counts,
        "hit_modifier": def_hit_modifier,
        "wound_modifier": def_wound_modifier,
        "damage_reduction": def_damage_reduction,
        "fnp": def_fnp,
        "leader_model": leader_defending_model,
        "support_model": support_defending_model,
        "pts": int(def_pts),
    }

# ---------------------------------------------------------------------------
# Sidebar — Listes d'armée
# ---------------------------------------------------------------------------

def render_army_list_sidebar(factions):
    from army_list import parse_and_match

    with st.sidebar:
        st.markdown(
            '<p style="font-family:\'Cinzel\',Georgia,serif;font-size:1rem;'
            'font-weight:700;letter-spacing:0.06em;margin-bottom:8px">'
            'Listes d\'armée</p>',
            unsafe_allow_html=True,
        )

        uploaded_files = st.file_uploader(
            "Fichiers JSON (BattleScribe)",
            type=["json"],
            accept_multiple_files=True,
            key="army_list_files",
            label_visibility="collapsed",
        )

        if not uploaded_files:
            st.caption("Glissez un ou plusieurs fichiers JSON BattleScribe.")
            return

        # Recalcul uniquement si les fichiers ont changé
        file_sig = frozenset((f.name, f.size) for f in uploaded_files)
        if st.session_state.get("_army_lists_sig") != file_sig:
            parsed = []
            for f in uploaded_files:
                try:
                    f.seek(0)
                    result = parse_and_match(f, factions, get_units_by_faction)
                    parsed.append(result)
                except Exception as exc:
                    st.error(f"Erreur dans {f.name} : {exc}")
            st.session_state["army_lists_matched"] = parsed
            st.session_state["_army_lists_sig"] = file_sig

        all_lists = st.session_state.get("army_lists_matched", [])

        for li, roster in enumerate(all_lists):
            label = f"{roster['roster_name']} — {roster['roster_pts']} pts"
            with st.expander(label, expanded=(len(all_lists) == 1)):
                for ui, matched in enumerate(roster["units"]):
                    found = (
                        matched["wahapedia_unit"] is not None
                        and matched.get("wahapedia_faction") is not None
                    )
                    color = "#1a1a2e" if found else "#aaaaaa"
                    n_weapons = len(matched.get("matched_weapons", []))
                    weapon_hint = (
                        f" · {n_weapons} arme{'s' if n_weapons > 1 else ''}"
                        if found and n_weapons
                        else ""
                    )
                    st.markdown(
                        f'<div style="margin-bottom:2px">'
                        f'<span style="font-size:0.8rem;color:{color}">'
                        f'{matched["name"]}</span>'
                        f'<span style="font-size:0.7rem;color:#8a8a9a"> — '
                        f'{matched["pts"]} pts{weapon_hint}</span></div>',
                        unsafe_allow_html=True,
                    )
                    b_atk, b_def = st.columns(2)
                    with b_atk:
                        if st.button(
                            "ATK", key=f"atk_{li}_{ui}", disabled=not found,
                            help="Charger en Attaquant",
                            use_container_width=True,
                        ):
                            ss = st.session_state
                            ss["atk_faction"] = matched["wahapedia_faction"]
                            ss["atk_unit"] = matched["wahapedia_unit"].name
                            ss["atk_pts"] = matched["pts"]
                            ss["atk_weapons"] = matched.get("matched_weapons") or []
                            ss["atk_attach_leader"] = False
                            ss["atk_attach_support"] = False
                    with b_def:
                        if st.button(
                            "DÉF", key=f"def_{li}_{ui}", disabled=not found,
                            help="Charger en Défenseur",
                            use_container_width=True,
                        ):
                            ss = st.session_state
                            ss["def_faction"] = matched["wahapedia_faction"]
                            ss["def_unit"] = matched["wahapedia_unit"].name
                            ss["def_pts"] = matched["pts"]
                            ss["def_attach_leader"] = False
                            ss["def_attach_support"] = False
                    if ui < len(roster["units"]) - 1:
                        st.markdown(
                            '<hr style="margin:4px 0;border-color:#e8e0d0;opacity:0.5">',
                            unsafe_allow_html=True,
                        )


# ---------------------------------------------------------------------------
# Sidebar — Profils sauvegardés
# ---------------------------------------------------------------------------

def render_profiles_sidebar():
    from streamlit_javascript import st_javascript
    from profiles import extract_profile, restore_profile, deserialize_profiles, js_read, js_write, MAX_PROFILES

    # Lecture localStorage (retourne 0 sur le premier rendu, puis la valeur réelle)
    raw = st_javascript(js_read(), key="wh40k_read_profiles")
    profiles = deserialize_profiles(raw)

    # Écriture en attente posée lors d'un save/delete
    if "_profiles_to_write" in st.session_state:
        pending = st.session_state.pop("_profiles_to_write")
        st_javascript(js_write(pending), key="wh40k_write_profiles")

    with st.sidebar:
        st.markdown(
            '<p style="font-family:\'Cinzel\',Georgia,serif;font-size:1rem;'
            'font-weight:700;letter-spacing:0.06em;margin-bottom:8px">'
            'Profils sauvegardés</p>',
            unsafe_allow_html=True,
        )

        col_name, col_btn = st.columns([3, 1])
        with col_name:
            profile_name = st.text_input(
                "Nom", placeholder="Nom du profil",
                key="profile_name_input", label_visibility="collapsed",
            )
        with col_btn:
            save_clicked = st.button("💾", help="Sauvegarder la configuration actuelle")

        if save_clicked:
            name = profile_name.strip()
            if not name:
                st.sidebar.error("Saisissez un nom.")
            elif len(name) > 40:
                st.sidebar.error("Nom trop long (max 40 caractères).")
            else:
                new_profile = extract_profile(name)
                updated = [p for p in profiles if p.get("name") != name]
                updated.insert(0, new_profile)
                if len(updated) > MAX_PROFILES:
                    updated = updated[:MAX_PROFILES]
                    st.sidebar.warning(f"Limite de {MAX_PROFILES} profils atteinte.")
                st.session_state["_profiles_to_write"] = updated
                st.rerun()

        if not profiles:
            st.sidebar.caption("Aucun profil sauvegardé.")
        else:
            st.sidebar.markdown(
                f'<p style="font-size:0.75rem;color:#8a8a9a;margin:4px 0 8px">'
                f'{len(profiles)} profil(s)</p>',
                unsafe_allow_html=True,
            )
            for i, p in enumerate(profiles):
                c_name, c_load, c_del = st.sidebar.columns([4, 1, 1])
                with c_name:
                    ts = p.get("created_at", "")[:10]
                    st.markdown(
                        f'<span style="font-size:0.85rem;font-weight:600">{p["name"]}</span>'
                        f'<br><span style="font-size:0.7rem;color:#8a8a9a">{ts}</span>',
                        unsafe_allow_html=True,
                    )
                with c_load:
                    if st.button("↩", key=f"load_profile_{i}", help="Charger ce profil"):
                        try:
                            restore_profile(p)
                        except ValueError:
                            st.sidebar.error("Profil incompatible (version ancienne).")
                        else:
                            st.rerun()
                with c_del:
                    if st.button("🗑", key=f"del_profile_{i}", help="Supprimer ce profil"):
                        updated = [q for j, q in enumerate(profiles) if j != i]
                        st.session_state["_profiles_to_write"] = updated
                        st.rerun()


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
render_profiles_sidebar()
with st.sidebar:
    st.sidebar.divider()
render_army_list_sidebar(factions)

# Défauts première utilisation — scénario Space Marines vs Orks
_PLASMA_PISTOL = "Plasma pistol – standard"   # en-dash U+2013 depuis le CSV Wahapedia

if "atk_faction" not in st.session_state:
    # Attaquant : Assault Intercessor Squad (10 fig)
    #   - 9 Assault Intercessors : Heavy bolt pistol + Astartes chainsword
    #   - 1 Sergeant             : Plasma pistol + Power fist
    if "Space Marines" in factions:
        st.session_state["atk_faction"] = "Space Marines"
    st.session_state["atk_unit"] = "Assault Intercessor Squad"
    st.session_state["atk_weapons"] = [
        "Heavy bolt pistol", "Astartes chainsword", _PLASMA_PISTOL, "Power fist"
    ]
    st.session_state["atk_total_count_Assault Intercessor Squad"] = 10
    st.session_state["wdist_Heavy bolt pistol"] = 9
    st.session_state["wdist_Astartes chainsword"] = 9
    st.session_state[f"wdist_{_PLASMA_PISTOL}"] = 1
    st.session_state["wdist_Power fist"] = 1

    # Défenseur : Boyz (9 Boyz + 1 Boss Nob) + Warboss en leader
    if "Orks" in factions:
        st.session_state["def_faction"] = "Orks"
    st.session_state["def_unit"] = "Boyz"
    st.session_state["def_grp_0_Boyz"] = 9    # BOY
    st.session_state["def_grp_1_Boyz"] = 1    # BOSS NOB
    st.session_state["def_attach_leader"] = True
    st.session_state["def_leader_name"] = "Warboss"

col_atk, col_def, col_ctx = st.columns([1, 1, 1])

with col_atk:
    atk_cfg = render_attacker_section(factions)

with col_def:
    def_cfg = render_defender_section(factions)

with col_ctx:
    section_header("context", "Contexte")
    combat_type = st.radio("Type de combat", ["Distance", "Mêlée"], horizontal=True, key="combat_type")
    within_half = st.checkbox("Dans la moitié de la portée (Rapid Fire, Melta)", key="within_half")
    target_cover = st.checkbox("Cible en couverture", key="target_cover")
    charged = st.checkbox("Attaquant a chargé (Lance)", key="charged")
    st.caption("⚠️ Le mot-clé Lance (Force +1 si charge) n'est pas simulé.")
    st.divider()
    n_runs = st.select_slider(
        "Simulations Monte Carlo",
        options=[500, 1000, 2000, 5000, 10000],
        value=2000,
        key="n_runs",
    )

st.divider()
simulate_btn = st.button("▶ Simuler", type="primary", use_container_width=True)

# ---------------------------------------------------------------------------
# Simulation
# ---------------------------------------------------------------------------

if simulate_btn:
    _st_components.html(
        "<script>setTimeout(function(){"
        "var el=window.parent.document.querySelector('[data-testid=\"stMain\"]');"
        "if(el)el.scrollTo({top:el.scrollHeight,behavior:'smooth'});"
        "},150);</script>",
        height=0,
    )
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
        (wname, count * getattr(atk_cfg["unit"].get_weapon(wname), "quantity", 1))
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
        group_counts=def_cfg.get("group_counts"),
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

        # En-tête arme
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
        threat_score = compute_threat_score(
            destruction_rate, alloc["models_killed_mean"], initial_count
        )

        # --- Métriques clés (FNP / Spillover masqués si nuls) ---
        _metrics = [
            ("Dégâts moyens",            f"{alloc['damage_allocated_mean']:.2f}",  None),
            ("Figurines tuées (moy.)",   f"{alloc['models_killed_mean']:.2f}",     None),
            ("Figurines restantes (moy.)",f"{models_remaining_mean:.2f}",           None),
            ("Taux de destruction",      f"{destruction_rate*100:.1f}%",
             "Probabilité d'éliminer toute l'unité en un round"),
        ]
        if alloc["fnp_ignored_damage_mean"] > 0:
            _metrics.append(("FNP ignorés", f"{alloc['fnp_ignored_damage_mean']:.2f}", None))
        if alloc["spillover_damage_mean"] > 0:
            _metrics.append(("Spillover perdu", f"{alloc['spillover_damage_mean']:.2f}", None))
        for _col, (_label, _val, _help) in zip(st.columns(len(_metrics)), _metrics):
            _col.metric(_label, _val, help=_help)

        if alloc.get("leader_kill_rate", 0) > 0:
            st.info(f"Taux de mort du leader : {alloc['leader_kill_rate']*100:.1f}%")
        if alloc.get("support_kill_rate", 0) > 0:
            st.info(f"Taux de mort du support : {alloc['support_kill_rate']*100:.1f}%")

        # --- Efficacité points ---
        _eff_metrics = []
        _dmg = alloc["damage_allocated_mean"]
        _kills = alloc["models_killed_mean"]
        _atk_pts = atk_cfg.get("pts", 0)
        _def_pts = def_cfg.get("pts", 0)
        if _atk_pts > 0:
            _eff_metrics.append((
                "Dégâts / 100 pts ATK",
                f"{_dmg / _atk_pts * 100:.1f}",
                "Dégâts moyens infligés pour 100 pts investis en attaque",
            ))
        if _def_pts > 0:
            _eff_metrics.append((
                "Dégâts / 100 pts DÉF",
                f"{_dmg / _def_pts * 100:.1f}",
                "Dégâts moyens infligés pour 100 pts de la cible — mesure si l'attaque 'vaut le coup'",
            ))
        if _atk_pts > 0 and _def_pts > 0:
            _ratio = _dmg / _atk_pts * _def_pts
            _eff_metrics.append((
                "Ratio valeur ATK/DÉF",
                f"{_ratio:.2f}×",
                "Rapport dégâts/pts ATK rapporté au coût DÉF. >1 = l'attaquant est rentable, <1 = le défenseur résiste bien",
            ))
        if _eff_metrics:
            st.markdown(
                '<p style="font-size:0.8rem;letter-spacing:0.08em;color:#8a8a9a;margin:12px 0 4px">'
                'EFFICACITÉ POINTS</p>',
                unsafe_allow_html=True,
            )
            for _col, (_label, _val, _help) in zip(st.columns(len(_eff_metrics)), _eff_metrics):
                _col.metric(_label, _val, help=_help)

        # --- Gauge + Narratif ---
        g_col, n_col = st.columns([1, 2])
        with g_col:
            st.plotly_chart(make_threat_gauge(threat_score), use_container_width=True)
        with n_col:
            atk_name = atk_cfg["unit"].name
            def_name = def_cfg["unit"].name
            text_math = _narrative_math(alloc, results, initial_count)
            text_flav = _narrative_flavor(
                threat_score, alloc, weapon_name, atk_name, def_name, initial_count, results
            )
            render_narrative_duo(text_math, text_flav)

        # --- Graphiques : 2x2 ---
        row1_c1, row1_c2 = st.columns(2)
        with row1_c1:
            st.plotly_chart(make_funnel_chart(agg, results), use_container_width=True)
            st.caption(
                "À chaque phase, une partie des dés est perdue. "
                "La chute la plus forte entre deux barres révèle votre principal frein — "
                "c'est là qu'un bonus (relance, PA, modificateur) aurait le plus d'impact."
            )
        with row1_c2:
            st.plotly_chart(make_damage_histogram(results, weapon_name), use_container_width=True)
            st.caption(
                "La courbe lissée (KDE) révèle la forme réelle de la distribution. "
                "Une courbe étroite = résultats prévisibles. Large et étalée = forte variabilité, "
                "les dés peuvent surprendre dans les deux sens."
            )

        row2_c1, row2_c2 = st.columns(2)
        with row2_c1:
            st.plotly_chart(make_kill_chart(results, weapon_name, def_cfg["model_count"]), use_container_width=True)
            st.caption(
                "Probabilité de tuer exactement N figurines en un round. "
                "Un pic élevé à 0 signifie que cette arme peine régulièrement à traverser les défenses — "
                "envisagez un profil avec plus de PA ou de dégâts."
            )
        with row2_c2:
            st.plotly_chart(make_percentile_bands_chart(results), use_container_width=True)
            st.caption(
                "Zone sombre = résultat obtenu dans 1 combat sur 2 (P25–P75). "
                "Zone claire = résultat obtenu dans 4 combats sur 5 (P10–P90). "
                "La médiane est votre résultat le plus 'typique'."
            )

        with st.expander("Détails par phase"):
            hit = agg["hit"]
            wound = agg["wound"]
            save = agg["save"]
            c1, c2, c3 = st.columns(3)
            with c1:
                st.markdown("**Touche**")
                st.write(f"Touches : {hit['hits_mean']:.2f} ± {hit['hits_std']:.2f}")
                st.write(f"Crits : {hit['critical_hits_mean']:.2f}")
                st.write(f"Auto-blessures (Lethal) : {hit['auto_wounds_mean']:.2f}")
                st.write(f"Sustained : {hit['sustained_hits_mean']:.2f}")
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
