# -*- coding: utf-8 -*-
"""
Created on Fri Jan 23 23:31:49 2026

@author: thoma
"""

from core.events import AttackEvent
from core.enums import AttackState
from core.dice import FixedValue, Dice


def test_fixed_damage(basic_attacking_unit):
    basic_attacking_unit.model.damage = FixedValue(2)

    event = AttackEvent(basic_attacking_unit, defender=None)
    event.state = AttackState.SAVE_FAILED

    from core.phases.damage import DamagePhase
    phase = DamagePhase()

    result = phase.resolve([event])

    assert len(result) == 1
    assert result[0].damage == 2
    assert result[0].state == AttackState.RESOLVED
    
def test_random_damage(monkeypatch, basic_attacking_unit):
    basic_attacking_unit.model.damage = Dice(1, 3)

    def fake_randint(a, b):
        return 2

    monkeypatch.setattr("random.randint", fake_randint)

    event = AttackEvent(basic_attacking_unit, defender=None)
    event.state = AttackState.SAVE_FAILED

    from core.phases.damage import DamagePhase
    phase = DamagePhase()

    result = phase.resolve([event])

    assert result[0].damage == 2

def test_mortal_wound_damage(basic_attacking_unit):
    basic_attacking_unit.model.damage = FixedValue(3)

    event = AttackEvent(basic_attacking_unit, defender=None)
    event.state = AttackState.SAVE_FAILED
    event.mortal_wound = True

    from core.phases.damage import DamagePhase
    phase = DamagePhase()

    result = phase.resolve([event])

    assert result[0].damage == 3
    
    
def test_damage_phase_ignores_non_failed_events(basic_attacking_unit):
    event = AttackEvent(basic_attacking_unit, defender=None)
    event.state = AttackState.WOUND_SUCCESS

    from core.phases.damage import DamagePhase
    phase = DamagePhase()

    result = phase.resolve([event])

    assert result == []


def test_minus_one_damage_applied(basic_attacking_unit):
    from core.phases.damage import DamagePhase
    from units.profiles import DefendingModel
    from units.defending import DefendingUnit
    from core.events import AttackEvent
    from core.enums import AttackState
    from core.dice import FixedValue

    basic_attacking_unit.model.damage = FixedValue(3)

    defender = DefendingUnit(
        DefendingModel(toughness=4, save=3, wounds=5),
        model_count=1,
        damage_reduction=1,
    )

    event = AttackEvent(basic_attacking_unit, defender)
    event.state = AttackState.SAVE_FAILED

    phase = DamagePhase()
    result = phase.resolve([event])

    assert result[0].damage == 2
    
    
def test_minus_one_damage_minimum_one(basic_attacking_unit):
    from core.phases.damage import DamagePhase
    from units.profiles import DefendingModel
    from units.defending import DefendingUnit
    from core.events import AttackEvent
    from core.enums import AttackState
    from core.dice import FixedValue

    basic_attacking_unit.model.damage = FixedValue(1)

    defender = DefendingUnit(
        DefendingModel(toughness=4, save=3, wounds=5),
        model_count=1,
        damage_reduction=1,
    )

    event = AttackEvent(basic_attacking_unit, defender)
    event.state = AttackState.SAVE_FAILED

    phase = DamagePhase()
    result = phase.resolve([event])

    assert result[0].damage == 1