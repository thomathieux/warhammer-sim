# -*- coding: utf-8 -*-
"""
Warhammer 40,000 — Simulateur de combat
Powered by Wahapedia
"""

import sys
from pathlib import Path

# Permet d'importer les modules du projet depuis n'importe quel contexte
sys.path.insert(0, str(Path(__file__).parent.parent))

import streamlit as st
import plotly.graph_objects as go
import plotly.express as px

from data.loader import load_all_units, list_factions
from data.unit_builder import build_weapon_groups, build_defending_unit
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

# ---------------------------------------------------------------------------
# Cache des données Wahapedia (chargé une seule fois)
# ---------------------------------------------------------------------------

@st.cache_data
def get_factions():
    rows = list_factions()
    return {r["name"]: r["id"] for r in sorted(rows, key=lambda r: r["name"])}

@st.cache_data
def get_units_by_faction(faction_id):
    units = load_all_units(faction_id=faction_id)
    return {u.name: u for u in sorted(units, key=lambda u: u.name)}

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

REROLL_OPTIONS = {
    "Aucune": RerollType.NONE,
    "Relancer les 1": RerollType.ONE,
    "Relancer les échecs": RerollType.FAILED,
}

def run_simulation(attacker_unit, weapon_groups, defender, context, n_runs):
    """Lance N simulations et retourne les résultats bruts."""
    seq = AttackSequence()
    results = []
    for _ in range(n_runs):
        defender.reset()
        for group in weapon_groups:
            result = seq.resolve(group, defender, context)
            results.append(result)
    return results

def make_damage_histogram(results, weapon_name):
    damages = [r.allocation.damage_allocated for r in results]
    fig = px.histogram(
        x=damages,
        nbins=max(1, max(damages) - min(damages) + 1) if damages else 1,
        labels={"x": "Dégâts alloués", "y": "Fréquence"},
        title=f"Distribution des dégâts — {weapon_name}",
        color_discrete_sequence=["#e63946"],
    )
    fig.update_layout(
        showlegend=False,
        plot_bgcolor="#0e1117",
        paper_bgcolor="#0e1117",
        font_color="#fafafa",
        bargap=0.05,
    )
    return fig

def make_kill_chart(results, weapon_name, max_models):
    from collections import Counter
    kills = [r.allocation.models_killed for r in results]
    counts = Counter(kills)
    n = len(results)
    x = list(range(0, max_models + 1))
    y = [counts.get(k, 0) / n * 100 for k in x]

    fig = go.Figure(go.Bar(
        x=x, y=y,
        marker_color="#457b9d",
        text=[f"{v:.1f}%" for v in y],
        textposition="outside",
    ))
    fig.update_layout(
        title=f"Probabilité de tuer N figurines — {weapon_name}",
        xaxis_title="Figurines tuées",
        yaxis_title="Probabilité (%)",
        yaxis_range=[0, max(y) * 1.2 + 1],
        plot_bgcolor="#0e1117",
        paper_bgcolor="#0e1117",
        font_color="#fafafa",
        showlegend=False,
    )
    return fig

# ---------------------------------------------------------------------------
# Interface principale
# ---------------------------------------------------------------------------

st.title("⚔️ Warhammer 40,000 — Simulateur de combat")
st.caption("Powered by Wahapedia · Données issues de wahapedia.ru")

col_atk, col_def, col_ctx = st.columns([1, 1, 1])

# ===========================================================================
# COLONNE ATTAQUANT
# ===========================================================================
with col_atk:
    st.subheader("Attaquant")

    factions = get_factions()
    atk_faction_name = st.selectbox(
        "Faction", list(factions.keys()), key="atk_faction"
    )
    atk_faction_id = factions[atk_faction_name]
    atk_units = get_units_by_faction(atk_faction_id)

    atk_unit_name = st.selectbox(
        "Unité", list(atk_units.keys()), key="atk_unit"
    )
    atk_unit = atk_units[atk_unit_name]

    # Sélection des armes disponibles
    weapon_names = [w.name for w in atk_unit.weapons]
    selected_weapons = st.multiselect(
        "Armes", weapon_names,
        default=weapon_names[:1] if weapon_names else [],
        key="atk_weapons",
    )

    atk_model_count = st.number_input(
        "Nombre de figurines",
        min_value=1,
        max_value=max(atk_unit.max_models, 1),
        value=max(atk_unit.max_models, 1),
        key="atk_count",
    )

    st.markdown("**Relances**")
    hit_reroll_label = st.selectbox("Relance touche", list(REROLL_OPTIONS.keys()), key="hit_rr")
    wound_reroll_label = st.selectbox("Relance blessure", list(REROLL_OPTIONS.keys()), key="wound_rr")

# ===========================================================================
# COLONNE DÉFENSEUR
# ===========================================================================
with col_def:
    st.subheader("Défenseur")

    def_faction_name = st.selectbox(
        "Faction", list(factions.keys()), key="def_faction"
    )
    def_faction_id = factions[def_faction_name]
    def_units = get_units_by_faction(def_faction_id)

    def_unit_name = st.selectbox(
        "Unité", list(def_units.keys()), key="def_unit"
    )
    def_unit = def_units[def_unit_name]

    def_model_count = st.number_input(
        "Nombre de figurines",
        min_value=1,
        max_value=max(def_unit.max_models, 1),
        value=max(def_unit.max_models, 1),
        key="def_count",
    )

    # Stats du défenseur (aperçu)
    m = def_unit.primary_model()
    if m:
        st.markdown(f"**Profil :** E{m.toughness} · SV{m.save}+ · {m.wounds}PV"
                    + (f" · Inv{m.invulnerable_save}+" if m.invulnerable_save else ""))

# ===========================================================================
# COLONNE CONTEXTE
# ===========================================================================
with col_ctx:
    st.subheader("Contexte de combat")

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

# ===========================================================================
# BOUTON SIMULER
# ===========================================================================
st.divider()
simulate_btn = st.button("▶ Simuler", type="primary", use_container_width=True)

if simulate_btn:
    if not selected_weapons:
        st.warning("Sélectionne au moins une arme.")
    else:
        context = CombatContext(
            combat_type="ranged" if combat_type == "Distance" else "melee",
            within_half_range=within_half,
            target_in_cover=target_cover,
            attacker_charged=charged,
        )
        hit_rr = REROLL_OPTIONS[hit_reroll_label]
        wound_rr = REROLL_OPTIONS[wound_reroll_label]

        # Construire les groupes d'armes (une par arme sélectionnée)
        loadout = [(w, int(atk_model_count)) for w in selected_weapons]
        try:
            weapon_groups = build_weapon_groups(
                atk_unit, loadout, context,
                hit_reroll=hit_rr,
                wound_reroll=wound_rr,
            )
        except ValueError as e:
            st.error(str(e))
            st.stop()

        if not weapon_groups:
            st.warning("Aucune arme compatible avec le type de combat sélectionné.")
            st.stop()

        defender = build_defending_unit(def_unit, model_count=int(def_model_count))

        with st.spinner(f"Simulation en cours ({n_runs} runs)..."):
            seq = AttackSequence()
            all_results = {group.weapon_name: [] for group in weapon_groups}

            for _ in range(n_runs):
                defender.reset()
                for group in weapon_groups:
                    result = seq.resolve(group, defender, context)
                    all_results[group.weapon_name].append(result)

        # ===========================================================================
        # RÉSULTATS
        # ===========================================================================
        st.success(f"Simulation terminée — {n_runs} runs par groupe d'armes")

        for weapon_name, results in all_results.items():
            agg = StatsAggregator(results).aggregate()
            alloc = agg["allocation"]

            st.subheader(f"🔫 {weapon_name}")

            # Métriques clés
            m1, m2, m3, m4 = st.columns(4)
            m1.metric("Dégâts moyens", f"{alloc['damage_allocated_mean']:.2f}")
            m2.metric("Figurines tuées (moy.)", f"{alloc['models_killed_mean']:.2f}")
            m3.metric("FNP ignorés", f"{alloc['fnp_ignored_damage_mean']:.2f}")
            m4.metric("Spillover perdu", f"{alloc['spillover_damage_mean']:.2f}")

            if alloc.get("leader_kill_rate", 0) > 0:
                st.info(f"Taux de mort du leader : {alloc['leader_kill_rate']*100:.1f}%")
            if alloc.get("support_kill_rate", 0) > 0:
                st.info(f"Taux de mort du support : {alloc['support_kill_rate']*100:.1f}%")

            # Graphiques
            gc1, gc2 = st.columns(2)
            with gc1:
                st.plotly_chart(
                    make_damage_histogram(results, weapon_name),
                    use_container_width=True,
                )
            with gc2:
                st.plotly_chart(
                    make_kill_chart(results, weapon_name, int(def_model_count)),
                    use_container_width=True,
                )

            # Stats détaillées (expandable)
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
                    st.write(f"Blessures critiques : {wound['critical_wounds_mean']:.2f}")
                    st.write(f"Blessures mortelles : {wound['mortal_wounds_mean']:.2f}")
                with c3:
                    st.markdown("**Sauvegarde**")
                    st.write(f"Tentées : {save['saves_attempted_mean']:.2f}")
                    st.write(f"Ratées : {save['saves_failed_mean']:.2f}")

        st.divider()
        st.caption("Powered by Wahapedia · wahapedia.ru · Données utilisées avec attribution")
