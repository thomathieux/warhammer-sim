# -*- coding: utf-8 -*-
"""
Tests Rapid Fire et Blast dans AttackingUnit.total_attacks().
"""

import pytest
from core.context import CombatContext
from units.profiles import AttackingModel
from units.attacking import AttackingUnit
from core.dice import FixedValue, Dice


def _unit(attacks=2, rapid_fire=0, blast=False, model_count=5):
    model = AttackingModel(attacks=FixedValue(attacks), attack_skill=3, strength=4)
    return AttackingUnit(model=model, model_count=model_count,
                         rapid_fire=rapid_fire, blast=blast)


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
