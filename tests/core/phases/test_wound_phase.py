# -*- coding: utf-8 -*-
"""
Created on Fri Jan 23 22:48:59 2026

@author: thoma
"""

import pytest
from core.events import AttackEvent
from core.enums import AttackState
from units.defending import DefendingUnit
from units.profiles import DefendingModel

def test_wound_success(monkeypatch, basic_attacking_unit):
    def fake_randint(a, b):
        return 4  # suffit pour blesser S4 vs T4 (4+)

    monkeypatch.setattr("random.randint", fake_randint)

    defender_model = DefendingModel(
        toughness=4,
        save=3,
        wounds=2,
    )
    defender = DefendingUnit(defender_model, model_count=1)

    event = AttackEvent(basic_attacking_unit, defender)
    event.state = AttackState.HIT_SUCCESS

    from core.phases.wound import WoundPhase
    phase = WoundPhase()

    result = phase.resolve([event])

    assert len(result) == 1
    assert result[0].state == AttackState.WOUND_SUCCESS
    
def test_wound_fail(monkeypatch, basic_attacking_unit):
    def fake_randint(a, b):
        return 1  # échec

    monkeypatch.setattr("random.randint", fake_randint)

    defender_model = DefendingModel(
        toughness=4,
        save=3,
        wounds=2,
    )
    defender = DefendingUnit(defender_model, model_count=1)

    event = AttackEvent(basic_attacking_unit, defender)
    event.state = AttackState.HIT_SUCCESS

    from core.phases.wound import WoundPhase
    phase = WoundPhase()

    result = phase.resolve([event])

    assert result == []
    
def test_auto_wound_skips_roll(monkeypatch, basic_attacking_unit):
    def fake_randint(a, b):
        pytest.fail("wound roll should not be called")

    monkeypatch.setattr("random.randint", fake_randint)

    defender_model = DefendingModel(
        toughness=10,
        save=2,
        wounds=5,
    )
    defender = DefendingUnit(defender_model, model_count=1)

    event = AttackEvent(basic_attacking_unit, defender)
    event.auto_wound = True
    event.state = AttackState.WOUND_SUCCESS

    from core.phases.wound import WoundPhase
    phase = WoundPhase()

    result = phase.resolve([event])

    assert len(result) == 1
    assert result[0].state == AttackState.WOUND_SUCCESS
    
    
def test_devastating_wounds(monkeypatch, basic_attacking_unit):
    basic_attacking_unit.devastating_wounds = True

    def fake_randint(a, b):
        return 6  # wound critique

    monkeypatch.setattr("random.randint", fake_randint)

    defender_model = DefendingModel(
        toughness=4,
        save=2,
        wounds=5,
    )
    defender = DefendingUnit(defender_model, model_count=1)

    event = AttackEvent(basic_attacking_unit, defender)
    event.state = AttackState.HIT_SUCCESS

    from core.phases.wound import WoundPhase
    phase = WoundPhase()

    result = phase.resolve([event])

    assert len(result) == 1
    assert result[0].mortal_wound is True
    
    
def test_auto_wound_not_devastating(monkeypatch, basic_attacking_unit):
    basic_attacking_unit.devastating_wounds = True

    def fake_randint(a, b):
        pytest.fail("wound roll should not occur")

    monkeypatch.setattr("random.randint", fake_randint)

    defender_model = DefendingModel(
        toughness=4,
        save=3,
        wounds=3,
    )
    defender = DefendingUnit(defender_model, model_count=1)

    event = AttackEvent(basic_attacking_unit, defender)
    event.auto_wound = True
    event.state = AttackState.WOUND_SUCCESS

    from core.phases.wound import WoundPhase
    phase = WoundPhase()

    result = phase.resolve([event])

    assert result[0].mortal_wound is False

def test_minus_one_wound_applies_when_defensive_rule_active(monkeypatch, basic_attacking_unit):
    basic_attacking_unit.model.strength = 5  # F > E

    def fake_randint(a, b):
        return 3  # normalement réussi à 3+

    monkeypatch.setattr("random.randint", fake_randint)

    from units.profiles import DefendingModel
    from units.defending import DefendingUnit
    from core.events import AttackEvent
    from core.phases.wound import WoundPhase
    from core.enums import AttackState

    defender = DefendingUnit(
        DefendingModel(toughness=4, save=3, wounds=2),
        model_count=1,
        wound_minus_one_if_weaker=True,
    )

    event = AttackEvent(basic_attacking_unit, defender)
    event.state = AttackState.HIT_SUCCESS

    result = WoundPhase().resolve([event])

    assert result == []
    
def test_no_minus_one_wound_without_defensive_rule(monkeypatch, basic_attacking_unit):
    basic_attacking_unit.model.strength = 5  # F > E

    def fake_randint(a, b):
        return 3  # 3+ → réussi

    monkeypatch.setattr("random.randint", fake_randint)

    from units.profiles import DefendingModel
    from units.defending import DefendingUnit
    from core.events import AttackEvent
    from core.phases.wound import WoundPhase
    from core.enums import AttackState

    defender = DefendingUnit(
        DefendingModel(toughness=4, save=3, wounds=2),
        model_count=1,
        wound_minus_one_if_weaker=False,
    )

    event = AttackEvent(basic_attacking_unit, defender)
    event.state = AttackState.HIT_SUCCESS

    result = WoundPhase().resolve([event])

    assert len(result) == 1