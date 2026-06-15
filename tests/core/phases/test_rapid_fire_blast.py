# -*- coding: utf-8 -*-
"""
Tests Rapid Fire et Blast dans AttackingUnit.total_attacks().
"""

import pytest
from core.context import CombatContext
from units.profiles import AttackingModel
from units.attacking import WeaponGroup
from core.dice import FixedValue, Dice


def _unit(attacks=2, rapid_fire=0, blast=False, model_count=5):
    model = AttackingModel(attacks=FixedValue(attacks), attack_skill=3, strength=4)
    rf = FixedValue(rapid_fire) if rapid_fire else None
    return WeaponGroup(model=model, model_count=model_count,
                         rapid_fire=rf, blast=blast)


# ---------------------------------------------------------------------------
# Rapid Fire
# ---------------------------------------------------------------------------

def test_rapid_fire_doubles_at_half_range():
    """Rapid Fire 1 à mi-portée : +1 attaque par figurine."""
    unit = _unit(attacks=2, rapid_fire=1, model_count=5)
    ctx = CombatContext(within_half_range=True)

    # 5 fig × (2 attaques + 1 RF) = 15
    total = unit.total_attacks(ctx, defender_count=0)
    assert total == 15


def test_rapid_fire_no_bonus_at_full_range():
    """Rapid Fire 1 hors mi-portée : attaques normales."""
    unit = _unit(attacks=2, rapid_fire=1, model_count=5)
    ctx = CombatContext(within_half_range=False)

    total = unit.total_attacks(ctx, defender_count=0)
    assert total == 10


def test_rapid_fire_no_bonus_without_context():
    """Sans context, pas de bonus Rapid Fire."""
    unit = _unit(attacks=2, rapid_fire=1, model_count=5)

    total = unit.total_attacks(context=None, defender_count=0)
    assert total == 10


def test_rapid_fire_2_at_half_range():
    """Rapid Fire 2 à mi-portée : +2 attaques par figurine."""
    unit = _unit(attacks=1, rapid_fire=2, model_count=3)
    ctx = CombatContext(within_half_range=True)

    # 3 fig × (1 + 2) = 9
    total = unit.total_attacks(ctx, defender_count=0)
    assert total == 9


# ---------------------------------------------------------------------------
# Blast
# ---------------------------------------------------------------------------

def test_blast_no_bonus_below_5_models():
    """Blast contre 4 figurines : 4 // 5 = 0, aucun bonus."""
    unit = _unit(attacks=2, blast=True, model_count=1)

    total = unit.total_attacks(context=None, defender_count=4)
    assert total == 2


def test_blast_plus_one_at_5_models():
    """Blast contre 5 figurines : +1 attaque (5 // 5 = 1)."""
    unit = _unit(attacks=2, blast=True, model_count=1)

    total = unit.total_attacks(context=None, defender_count=5)
    assert total == 3


def test_blast_plus_two_at_10_models():
    """Blast contre 10 figurines : +2 attaques (10 // 5 = 2)."""
    unit = _unit(attacks=2, blast=True, model_count=1)

    total = unit.total_attacks(context=None, defender_count=10)
    assert total == 4


def test_blast_plus_three_at_15_models():
    """Blast contre 15 figurines : +3 attaques (15 // 5 = 3)."""
    unit = _unit(attacks=2, blast=True, model_count=1)

    total = unit.total_attacks(context=None, defender_count=15)
    assert total == 5


def test_blast_and_rapid_fire_stack():
    """Blast + Rapid Fire cumulés à mi-portée contre 10 figurines."""
    unit = _unit(attacks=2, rapid_fire=1, blast=True, model_count=2)
    ctx = CombatContext(within_half_range=True)

    # Par figurine : 2 (base) + 2 (Blast 10//5) = 4
    # Total arme : 2 fig × 4 = 8 + Rapid Fire 1×2 fig = 10
    total = unit.total_attacks(ctx, defender_count=10)
    assert total == 10


# ---------------------------------------------------------------------------
# Rapid Fire avec DiceExpression
# ---------------------------------------------------------------------------

def test_rapid_fire_none_no_bonus_at_half_range():
    """
    Objectif : rapid_fire=None signifie « pas de Rapid Fire ».
    Même à mi-portée, aucun bonus n'est ajouté.
    """
    model = AttackingModel(attacks=FixedValue(2), attack_skill=3, strength=4)
    unit = WeaponGroup(model=model, model_count=3, rapid_fire=None)
    ctx = CombatContext(within_half_range=True)

    assert unit.total_attacks(ctx) == 6  # 3 fig × 2 attaques, pas de RF


def test_rapid_fire_dice_expr_d3_bounds():
    """
    Objectif : rapid_fire=parse_dice("d3") ajoute entre 1 et 3 attaques par
    figurine à mi-portée. Sur 200 tirages avec 1 modèle / 2 attaques de base,
    les totaux doivent être dans [3, 5].
    """
    from core.dice import parse_dice

    model = AttackingModel(attacks=FixedValue(2), attack_skill=3, strength=4)
    unit = WeaponGroup(model=model, model_count=1, rapid_fire=parse_dice("d3"))
    ctx = CombatContext(within_half_range=True)

    totals = [unit.total_attacks(ctx) for _ in range(200)]
    assert min(totals) >= 3   # 2 base + 1 RF minimum
    assert max(totals) <= 5   # 2 base + 3 RF maximum


def test_keyword_parser_rapid_fire_d3_stores_str():
    """
    Objectif : parse_keywords("rapid fire d3") stocke la chaîne dé dans
    rapid_fire_str et laisse rapid_fire (int) à 0.
    """
    from data.keyword_parser import parse_keywords

    kw = parse_keywords("rapid fire d3")
    assert kw.rapid_fire_str == "d3"
    assert kw.rapid_fire == 0


def test_keyword_parser_rapid_fire_d6plus3_stores_str():
    """
    Objectif : parse_keywords("rapid fire d6+3") capture l'expression
    composée complète dans rapid_fire_str.
    """
    from data.keyword_parser import parse_keywords

    kw = parse_keywords("rapid fire d6+3")
    assert kw.rapid_fire_str == "d6+3"
    assert kw.rapid_fire == 0
