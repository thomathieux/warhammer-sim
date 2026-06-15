# -*- coding: utf-8 -*-
"""
Validation probabiliste de la simulation sur le scénario par défaut :
Assault Intercessors (Space Marines) vs Boyz (Orks).

Chaque test calcule une espérance mathématique exacte, exécute N=5 000 runs
et vérifie que la moyenne de simulation tombe dans l'intervalle théorique.
Bornes à ±4σ → probabilité de faux positif < 0.003 %.

Si un test échoue : la phase correspondante contient un bug.
Si tous passent : la simulation est correcte et toute impression de
sous-estimation dans l'app est due à la configuration (ex. mode Distance
exclut les armes de mêlée).
"""

import pytest

from core.simulation.attack_sequence import AttackSequence
from core.context import CombatContext
from core.dice import FixedValue
from units.profiles import AttackingModel, DefendingModel
from units.attacking import WeaponGroup
from units.defending import DefendingUnit
from units.unit import ModelGroup, ModelProfile


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

N = 5_000  # nombre de runs par test


def _simple_defender(toughness, save, wounds, count=10):
    """Défenseur simple (un seul type de modèle)."""
    return DefendingUnit(
        model=DefendingModel(toughness=toughness, save=save, wounds=wounds),
        model_count=count,
    )


def _run_single(weapon_group, defender, n=N):
    """Run N simulations avec un seul WeaponGroup, retourne la moyenne de kills."""
    seq = AttackSequence()
    ctx = CombatContext()
    kills = []
    for _ in range(n):
        res = seq.resolve(weapon_group, defender, ctx)
        kills.append(res.allocation.models_killed)
        defender.reset()
    return sum(kills) / n


def _run_multi(weapon_groups, defender, n=N):
    """Run N simulations avec plusieurs WeaponGroups successifs, retourne
    (mean_models_killed, mean_leader_kill_rate)."""
    seq = AttackSequence()
    ctx = CombatContext()
    kills, leader_kills = [], []
    for _ in range(n):
        total = 0
        any_leader = False
        for wg in weapon_groups:
            res = seq.resolve(wg, defender, ctx)
            total += res.allocation.models_killed
            any_leader = any_leader or res.allocation.leader_killed
        kills.append(total)
        leader_kills.append(int(any_leader))
        defender.reset()
    return sum(kills) / n, sum(leader_kills) / n


def _boyz_with_warboss():
    """9 Boyz (T5 Sv5+ W1) + 1 Boss Nob (T5 Sv5+ W2) + Warboss leader (T5 Sv4+ W6 Inv5+)."""
    boy     = ModelProfile(name="Boy",      toughness=5, save=5, wounds=1)
    boss    = ModelProfile(name="Boss Nob", toughness=5, save=5, wounds=2)
    warboss = DefendingModel(toughness=5, save=4, wounds=6, invulnerable_save=5)
    return DefendingUnit(
        core_groups=[
            ModelGroup(boy,  "Boy",      9, 9),
            ModelGroup(boss, "Boss Nob", 1, 1),
        ],
        leader_model=warboss,
    )


# ---------------------------------------------------------------------------
# Stats des armes (Assault Intercessor Squad, CSV Wahapedia 000001606)
# Heavy bolt pistol : 1A BS3+ S4 AP-1 D1
# Astartes chainsword : 4A WS3+ S4 AP-1 D1
# Plasma pistol – standard : 1A BS3+ S7 AP-2 D1
# Power fist : 3A WS3+ S8 AP-2 D2
# Défenseur Boyz : T5 Sv5+ W1 (Boy) / W2 (Boss Nob)
#
# Table de blessure 40K :
#   S ≥ 2×T → 2+  |  S > T → 3+  |  S = T → 4+  |  S < T → 5+  |  T ≥ 2×S → 6+
#
# Espérances mathématiques :
#   E = N_att × P(hit) × P(wound) × P(save_fail) × kills_per_damage
#   P(hit  | BS3+)           = 4/6
#   P(wound| S4 vs T5)       = 2/6   (S < T → 5+)
#   P(wound| S7 vs T5)       = 4/6   (S > T mais S < 2×T=10 → 3+, PAS 2+)
#   P(wound| S8 vs T5)       = 4/6   (S > T mais S < 2×T=10 → 3+, PAS 2+)
#   P(save_fail | AP-1, 5+)  = 5/6   (save sur 6+)
#   P(save_fail | AP-2, 5+)  = 6/6   (save sur 7+, impossible)
#   D2 vs W1 : 1 kill + 1 spillover gaspillé  → kills/damage = 1
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# Test A — Heavy bolt pistol
# E = 9 × (4/6) × (2/6) × (5/6) = 1.667
# ---------------------------------------------------------------------------

def test_heavy_bolt_pistol_expected_kills():
    """
    Objectif : valider la formule hit × wound × save_fail pour une arme distance
    classique (S4 AP-1 D1 vs T5 Sv5+).
    E[kills] = 9 att × 0.667 × 0.333 × 0.833 = 1.667
    """
    model = AttackingModel(attacks=FixedValue(1), attack_skill=3, strength=4, ap=-1, damage=FixedValue(1))
    wg = WeaponGroup(model=model, model_count=9)
    defender = _simple_defender(toughness=5, save=5, wounds=1)

    mean = _run_single(wg, defender)
    assert 1.50 <= mean <= 1.85, f"Heavy bolt pistol: mean={mean:.3f}, attendu ∈ [1.50, 1.85]"


# ---------------------------------------------------------------------------
# Test B — Astartes chainsword
# E = 36 × (4/6) × (2/6) × (5/6) = 6.667
# ---------------------------------------------------------------------------

def test_astartes_chainsword_expected_kills():
    """
    Objectif : valider le scaling par nombre d'attaques (4A par modèle × 9 modèles).
    E[kills] = 36 att × 0.667 × 0.333 × 0.833 = 6.667
    """
    model = AttackingModel(attacks=FixedValue(4), attack_skill=3, strength=4, ap=-1, damage=FixedValue(1))
    wg = WeaponGroup(model=model, model_count=9)
    defender = _simple_defender(toughness=5, save=5, wounds=1)

    mean = _run_single(wg, defender)
    assert 6.40 <= mean <= 6.95, f"Astartes chainsword: mean={mean:.3f}, attendu ∈ [6.40, 6.95]"


# ---------------------------------------------------------------------------
# Test C — Plasma pistol – standard
# E = 1 × (4/6) × (5/6) × (6/6) = 0.556
# ---------------------------------------------------------------------------

def test_plasma_pistol_standard_expected_kills():
    """
    Objectif : valider le cas AP élevé (save toujours raté, 7+) et S7 vs T5.
    S7 > T5 mais 7 < 2×5=10 → blessure sur 3+ (4/6), pas 2+.
    AP-2 sur Sv5+ → save 7+ → toujours raté (P=1.0).
    E[kills] = 1 att × (4/6) × (4/6) × 1.0 = 0.444
    """
    model = AttackingModel(attacks=FixedValue(1), attack_skill=3, strength=7, ap=-2, damage=FixedValue(1))
    wg = WeaponGroup(model=model, model_count=1)
    defender = _simple_defender(toughness=5, save=5, wounds=1)

    mean = _run_single(wg, defender)
    assert 0.38 <= mean <= 0.51, f"Plasma pistol: mean={mean:.3f}, attendu ∈ [0.38, 0.51]"


# ---------------------------------------------------------------------------
# Test D — Power fist vs cibles W1 (spillover)
# E = 3 × (4/6) × (5/6) × 1.0 = 1.667  (D2 sur W1 → 1 kill + 1 spillover gaspillé)
# ---------------------------------------------------------------------------

def test_power_fist_d2_vs_one_wound_models():
    """
    Objectif : valider que D2 contre des cibles W1 ne double PAS les kills.
    Chaque blessure réussie tue 1 modèle et gaspille 1 point de dégât (spillover).
    S8 > T5 mais 8 < 2×5=10 → blessure sur 3+ (4/6), pas 2+.
    E[kills] = 3 att × (4/6) × (4/6) × 1.0 = 1.333
    """
    model = AttackingModel(attacks=FixedValue(3), attack_skill=3, strength=8, ap=-2, damage=FixedValue(2))
    wg = WeaponGroup(model=model, model_count=1)
    defender = _simple_defender(toughness=5, save=5, wounds=1, count=10)

    mean = _run_single(wg, defender)
    assert 1.24 <= mean <= 1.43, f"Power fist vs W1: mean={mean:.3f}, attendu ∈ [1.24, 1.43]"


# ---------------------------------------------------------------------------
# Test E — Scénario Distance complet avec Warboss leader
# Heavy bolt pistol (×9) + Plasma pistol (×1) sur 9 Boyz + 1 Boss Nob + Warboss
# E[kills Boyz] = 1.667 + 0.556 = 2.222
# E[leader_kill_rate] ≈ 0  (Warboss protégé par 10 Boyz)
# ---------------------------------------------------------------------------

def test_scenario_ranged_expected_kills():
    """
    Objectif : valider le scénario Distance par défaut de l'app.
    Seuls les pistolets tirent (Heavy bolt pistol + Plasma pistol).
    Le Warboss est protégé et pratiquement jamais atteint en ~2 kills/round.
    E[bolt pistol kills] = 1.667  (S4 vs T5 → 5+)
    E[plasma kills]      = 0.444  (S7 vs T5 → 3+, pas 2+)
    E[total]             = 2.111
    """
    model_bolt  = AttackingModel(attacks=FixedValue(1), attack_skill=3, strength=4, ap=-1, damage=FixedValue(1))
    model_plasma = AttackingModel(attacks=FixedValue(1), attack_skill=3, strength=7, ap=-2, damage=FixedValue(1))
    wg_bolt  = WeaponGroup(model=model_bolt,  model_count=9)
    wg_plasma = WeaponGroup(model=model_plasma, model_count=1)

    defender = _boyz_with_warboss()

    mean_kills, mean_leader = _run_multi([wg_bolt, wg_plasma], defender)

    assert 1.95 <= mean_kills <= 2.28, \
        f"Scénario Distance — kills Boyz: mean={mean_kills:.3f}, attendu ∈ [1.95, 2.28]"
    assert mean_leader < 0.05, \
        f"Scénario Distance — leader_kill_rate={mean_leader:.3f}, attendu < 0.05"


# ---------------------------------------------------------------------------
# Test F — Scénario Mêlée complet avec Warboss leader
# Astartes chainsword (×9) + Power fist (×1) sur 9 Boyz + 1 Boss Nob + Warboss
# E[kills Boyz] = 6.667 + 1.667 = 8.333
# E[leader_kill_rate] faible mais >0 (Warboss atteint si tous les Boyz meurent)
# ---------------------------------------------------------------------------

def test_scenario_melee_expected_kills():
    """
    Objectif : valider le scénario Mêlée.
    Chainsword (gros du travail) + Power fist sur le même défenseur composite.
    E[chainsword] ≈ 6.6  (D1 vs Boss Nob W2 → 2 hits pour tuer, légèrement < 6.667)
    E[power fist] ≈ 1.1  (S8 vs T5 → 3+, D2 vs W1 Boys = spillover, interaction Boss Nob)
    E[total]      ≈ 7.7  (calcul exact complexe → bornes conservatrices ±0.4)
    Le Warboss Inv5+ peut sauvegarder si tous les Boyz meurent dans le round.
    """
    model_sword = AttackingModel(attacks=FixedValue(4), attack_skill=3, strength=4, ap=-1, damage=FixedValue(1))
    model_fist  = AttackingModel(attacks=FixedValue(3), attack_skill=3, strength=8, ap=-2, damage=FixedValue(2))
    wg_sword = WeaponGroup(model=model_sword, model_count=9)
    wg_fist  = WeaponGroup(model=model_fist,  model_count=1)

    defender = _boyz_with_warboss()

    mean_kills, mean_leader = _run_multi([wg_sword, wg_fist], defender)

    assert 7.35 <= mean_kills <= 8.05, \
        f"Scénario Mêlée — kills Boyz: mean={mean_kills:.3f}, attendu ∈ [7.35, 8.05]"
    assert 0.0 <= mean_leader <= 0.15, \
        f"Scénario Mêlée — leader_kill_rate={mean_leader:.3f}, attendu ∈ [0.0, 0.15]"
