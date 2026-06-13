# -*- coding: utf-8 -*-
"""
Warhammer 40,000 — Simulateur de combat
Powered by Wahapedia
"""

import sys
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
.datacard {
    background: #1a1f2e;
    border: 1px solid #2d3748;
    border-radius: 8px;
    padding: 10px 14px;
    margin-bottom: 8px;
    font-size: 0.85rem;
}
.datacard-title {
    font-weight: bold;
    font-size: 0.95rem;
    color: #e2e8f0;
    margin-bottom: 6px;
}
.stat-row {
    display: flex;
    gap: 12px;
    flex-wrap: wrap;
}
.stat-box {
    background: #2d3748;
    border-radius: 4px;
    padding: 4px 8px;
    text-align: center;
    min-width: 42px;
}
.stat-label {
    font-size: 0.65rem;
    color: #a0aec0;
    text-transform: uppercase;
}
.stat-value {
    font-size: 1.05rem;
    font-weight: bold;
    color: #f6e05e;
}
.kw-chip {
    display: inline-block;
    background: #2c5282;
    color: #bee3f8;
    border-radius: 3px;
    padding: 1px 6px;
    font-size: 0.7rem;
    margin: 2px 2px 0 0;
}
.warn-chip {
    display: inline-block;
    background: #744210;
    color: #fbd38d;
    border-radius: 3px;
    padding: 1px 6px;
    font-size: 0.7rem;
    margin: 2px 2px 0 0;
}
</style>
""", unsafe_allow_html=True)

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

def _kw_chip(text, warn=False):
    cls = "warn-chip" if warn else "kw-chip"
    return f'<span class="{cls}">{text}</span>'

def unit_datacard_html(unit, model=None) -> str:
    if model is None:
        model = unit.primary_model()
    if model is None:
        return ""

    inv = f"{model.invulnerable_save}+" if model.invulnerable_save else "—"
    kw_html = " ".join(_kw_chip(k) for k in unit.keywords[:8])

    return f"""
<div class="datacard">
  <div class="datacard-title">🛡 {unit.name}</div>
  <div class="stat-row">
    <div class="stat-box"><div class="stat-label">E</div><div class="stat-value">{model.toughness}</div></div>
    <div class="stat-box"><div class="stat-label">SV</div><div class="stat-value">{model.save}+</div></div>
    <div class="stat-box"><div class="stat-label">Inv</div><div class="stat-value">{inv}</div></div>
    <div class="stat-box"><div class="stat-label">PV</div><div class="stat-value">{model.wounds}</div></div>
  </div>
  <div style="margin-top:6px">{kw_html}</div>
</div>"""

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

    return f"""
<div class="datacard">
  <div class="datacard-title">🔫 {weapon.name}</div>
  <div class="stat-row">
    <div class="stat-box"><div class="stat-label">Portée</div><div class="stat-value">{rng}</div></div>
    <div class="stat-box"><div class="stat-label">A</div><div class="stat-value">{weapon.attacks}</div></div>
    <div class="stat-box"><div class="stat-label">CC/CT</div><div class="stat-value">{weapon.skill}+</div></div>
    <div class="stat-box"><div class="stat-label">F</div><div class="stat-value">{weapon.strength}</div></div>
    <div class="stat-box"><div class="stat-label">PA</div><div class="stat-value">{weapon.ap}</div></div>
    <div class="stat-box"><div class="stat-label">D</div><div class="stat-value">{weapon.damage}</div></div>
  </div>
  {"<div style='margin-top:6px'>" + kw_html + "</div>" if kw_html else ""}
</div>"""

# ---------------------------------------------------------------------------
# Helpers — graphiques
# ---------------------------------------------------------------------------

REROLL_OPTIONS = {
    "Aucune": RerollType.NONE,
    "Relancer les 1": RerollType.ONE,
    "Relancer les échecs": RerollType.FAILED,
}

def make_damage_histogram(results, weapon_name):
    damages = [r.allocation.damage_allocated for r in results]
    if not damages:
        return go.Figure()
    nbins = max(1, max(damages) - min(damages) + 1)
    fig = px.histogram(
        x=damages, nbins=nbins,
        labels={"x": "Dégâts alloués", "y": "Fréquence"},
        title=f"Distribution dégâts — {weapon_name}",
        color_discrete_sequence=["#e63946"],
    )
    fig.update_layout(showlegend=False, plot_bgcolor="#0e1117",
                      paper_bgcolor="#0e1117", font_color="#fafafa", bargap=0.05)
    return fig

def make_kill_chart(results, weapon_name, max_models):
    from collections import Counter
    kills = [r.allocation.models_killed for r in results]
    counts = Counter(kills)
    n = len(results)
    x = list(range(0, max_models + 1))
    y = [counts.get(k, 0) / n * 100 for k in x]
    fig = go.Figure(go.Bar(
        x=x, y=y, marker_color="#457b9d",
        text=[f"{v:.1f}%" for v in y], textposition="outside",
    ))
    fig.update_layout(
        title=f"P(kills ≥ N) — {weapon_name}",
        xaxis_title="Figurines tuées", yaxis_title="Probabilité (%)",
        yaxis_range=[0, max(y) * 1.2 + 1] if max(y) > 0 else [0, 10],
        plot_bgcolor="#0e1117", paper_bgcolor="#0e1117",
        font_color="#fafafa", showlegend=False,
    )
    return fig

def make_cumulative_chart(results, weapon_name):
    damages = sorted([r.allocation.damage_allocated for r in results])
    n = len(damages)
    x, y = [], []
    for v in range(0, max(damages) + 2):
        x.append(v)
        y.append(sum(1 for d in damages if d >= v) / n * 100)
    fig = go.Figure(go.Scatter(x=x, y=y, mode="lines", fill="tozeroy",
                               line=dict(color="#48bb78", width=2)))
    fig.update_layout(
        title=f"P(dégâts ≥ X) — {weapon_name}",
        xaxis_title="Dégâts", yaxis_title="Probabilité (%)",
        yaxis_range=[0, 105],
        plot_bgcolor="#0e1117", paper_bgcolor="#0e1117",
        font_color="#fafafa", showlegend=False,
    )
    return fig

# ---------------------------------------------------------------------------
# Section attaquant
# ---------------------------------------------------------------------------

def render_attacker_section(factions):
    st.subheader("⚔️ Attaquant")

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

    total_models = st.number_input(
        "Figurines dans l'unité",
        min_value=1, max_value=max(atk_unit.max_models, 1),
        value=max(atk_unit.max_models, 1), key=f"atk_total_count_{atk_unit_name}",
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

    # Compteur total
    if selected_weapons:
        ok = assigned == int(total_models)
        color = "#48bb78" if ok else "#fc8181"
        st.markdown(
            f'<span style="color:{color};font-weight:bold">'
            f'Figurines assignées : {assigned} / {int(total_models)}</span>',
            unsafe_allow_html=True,
        )
        if not ok:
            st.info("ℹ️ Le total assigné ne correspond pas au nombre de figurines — la simulation utilisera les valeurs telles quelles.")

    # --- Relances ---
    with st.expander("Relances"):
        hit_rr = REROLL_OPTIONS[st.selectbox("Relance touche", list(REROLL_OPTIONS.keys()), key="hit_rr")]
        wound_rr = REROLL_OPTIONS[st.selectbox("Relance blessure", list(REROLL_OPTIONS.keys()), key="wound_rr")]

    # --- Leader attaché (attaquant) ---
    atk_hit_modifier = 0
    atk_leader_loadout = []

    with st.expander("👑 Attacher un leader / support"):
        char_units = get_character_units(atk_faction_id)
        if not char_units:
            st.caption("Aucune unité CHARACTER dans cette faction.")
        else:
            attach_leader = st.checkbox("Attacher un leader", key="atk_attach_leader")
            if attach_leader:
                leader_name = st.selectbox(
                    "Leader", list(char_units.keys()), key="atk_leader_name"
                )
                leader_unit = char_units[leader_name]
                lm = leader_unit.primary_model()
                if lm:
                    st.markdown(unit_datacard_html(leader_unit, lm), unsafe_allow_html=True)

                # Vérification keywords (non bloquant)
                unit_kws = set(k.upper() for k in atk_unit.keywords)
                leader_kws = set(k.upper() for k in leader_unit.keywords)
                if not unit_kws.intersection(leader_kws - {"CHARACTER"}):
                    st.warning("⚠️ Aucun mot-clé commun entre le leader et l'unité — vérifiez les règles d'attachement.")

                # Armes du leader → groupes supplémentaires
                leader_weapons = [w.name for w in leader_unit.weapons]
                sel_leader_w = st.multiselect(
                    "Armes du leader", leader_weapons,
                    default=leader_weapons[:1] if leader_weapons else [],
                    key="atk_leader_weapons",
                )
                for wname in sel_leader_w:
                    w = leader_unit.get_weapon(wname)
                    if w:
                        st.markdown(weapon_datacard_html(w), unsafe_allow_html=True)
                    atk_leader_loadout.append((leader_unit, wname, 1))

                # Abilities
                st.markdown("**Abilities du leader**")
                abilities = leader_unit.abilities
                if abilities:
                    for ab in abilities[:6]:
                        with st.expander(ab["name"], expanded=False):
                            st.caption(ab.get("description", ""))
                else:
                    st.caption("Aucune ability renseignée dans les données.")

                st.markdown("**Effets simulables**")
                if st.checkbox("+1 à la touche pour toute l'unité", key="atk_hit_plus"):
                    atk_hit_modifier += 1
                if st.checkbox("-1 à la touche pour toute l'unité", key="atk_hit_minus"):
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
    st.subheader("🛡 Défenseur")

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

                abilities = leader_unit.abilities
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

st.title("⚔️ Warhammer 40,000 — Simulateur de combat")
st.caption("Powered by Wahapedia · wahapedia.ru")

factions = get_factions()

col_atk, col_def, col_ctx = st.columns([1, 1, 1])

with col_atk:
    atk_cfg = render_attacker_section(factions)

with col_def:
    def_cfg = render_defender_section(factions)

with col_ctx:
    st.subheader("🎲 Contexte")
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

        st.subheader(f"🔫 {weapon_name}")

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
    st.caption("Powered by Wahapedia · wahapedia.ru · Données utilisées avec attribution")
