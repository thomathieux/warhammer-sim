# -*- coding: utf-8 -*-
"""
Tests Melta dans DamagePhase.

Melta N : +N dégâts si la cible est dans la moitié de la portée.
"""

import pytest
from core.phases.damage import DamagePhase
from core.context import CombatContext
from core.events import AttackEvent
from core.enums import AttackState
from units.profiles import AttackingModel, DefendingModel
from units.attacking import AttackingUnit
from units.defending import DefendingUnit
from core.dice import FixedValue


def _attacker(damage=1, melta=0):
    model = AttackingModel(attacks=FixedValue(1), attack_skill=3, strength=8,
                           ap=-4, damage=FixedValue(damage))
    return AttackingUnit(model=model, model_count=1, melta=melta)


def _defender():
    m = DefendingModel(toughness=8, save=3, wounds=10)
    return DefendingUnit(m, model_count=1)


def _save_failed_event(attacker, defender):
    e = AttackEvent(attacker, defender)
    e.state = AttackState.SAVE_FAILED
    return e


def test_melta_adds_damage_at_half_range(monkeypatch):
    """Melta 2 à mi-portée : dégâts fixes 3 + 2 = 5."""
    attacker = _attacker(damage=3, melta=2)
    defender = _defender()
    ctx = CombatContext(within_half_range=True)

    result = DamagePhase().resolve([_save_failed_event(attacker, defender)], context=ctx)

    assert result[0].raw_damage == 5


def test_melta_no_bonus_at_full_range():
    """Melta 2 hors mi-portée : dégâts normaux."""
    attacker = _attacker(damage=3, melta=2)
    defender = _defender()
    ctx = CombatContext(within_half_range=False)

    result = DamagePhase().resolve([_save_failed_event(attacker, defender)], context=ctx)

    assert result[0].raw_damage == 3


def test_melta_no_bonus_without_context():
    """Sans context, pas de bonus Melta."""
    attacker = _attacker(damage=3, melta=2)
    defender = _defender()

    result = DamagePhase().resolve([_save_failed_event(attacker, defender)], context=None)

    assert result[0].raw_damage == 3


def test_melta_zero_no_effect():
    """melta=0 : aucun bonus même à mi-portée."""
    attacker = _attacker(damage=2, melta=0)
    defender = _defender()
    ctx = CombatContext(within_half_range=True)

    result = DamagePhase().resolve([_save_failed_event(attacker, defender)], context=ctx)

    assert result[0].raw_damage == 2


def test_melta_does_not_bypass_damage_reduction():
    """Melta 2 + réduction 1 : (3+2) - 1 = 4. Minimum 1 garanti."""
    m = DefendingModel(toughness=8, save=3, wounds=10)
    defender = DefendingUnit(m, model_count=1, damage_reduction=1)

    attacker = _attacker(damage=3, melta=2)
    ctx = CombatContext(within_half_range=True)

    result = DamagePhase().resolve([_save_failed_event(attacker, defender)], context=ctx)

    assert result[0].raw_damage == 5
    assert result[0].final_damage == 4
