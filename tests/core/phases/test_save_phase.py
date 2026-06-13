# -*- coding: utf-8 -*-
"""
Created on Fri Jan 23 23:20:38 2026

@author: thoma
"""

from core.events import AttackEvent
from core.enums import AttackState
from units.profiles import DefendingModel
from units.defending import DefendingUnit

def test_armour_save_success(monkeypatch, basic_attacking_unit):
    def fake_randint(a, b):
        return 5  # sauvegarde réussie sur 3+

    monkeypatch.setattr("random.randint", fake_randint)

    defender_model = DefendingModel(
        toughness=4,
        save=3,
        wounds=2,
    )
    defender = DefendingUnit(defender_model, 1)

    event = AttackEvent(basic_attacking_unit, defender)
    event.state = AttackState.WOUND_SUCCESS

    from core.phases.save import SavePhase
    phase = SavePhase()

    result = phase.resolve([event])

    assert result == []
    
def test_armour_save_fail(monkeypatch, basic_attacking_unit):
    def fake_randint(a, b):
        return 1  # raté

    monkeypatch.setattr("random.randint", fake_randint)

    defender_model = DefendingModel(
        toughness=4,
        save=3,
        wounds=2,
    )
    defender = DefendingUnit(defender_model, 1)

    event = AttackEvent(basic_attacking_unit, defender)
    event.state = AttackState.WOUND_SUCCESS

    from core.phases.save import SavePhase
    phase = SavePhase()

    result = phase.resolve([event])

    assert len(result) == 1
    assert result[0].state == AttackState.SAVE_FAILED

def test_armour_save_with_ap(monkeypatch, basic_attacking_unit):
    basic_attacking_unit.model.ap = -2  # PA -2

    def fake_randint(a, b):
        return 4  # 3+ devient 5+, donc raté

    monkeypatch.setattr("random.randint", fake_randint)

    defender_model = DefendingModel(
        toughness=4,
        save=3,
        wounds=2,
    )
    defender = DefendingUnit(defender_model, 1)

    event = AttackEvent(basic_attacking_unit, defender)
    event.state = AttackState.WOUND_SUCCESS

    from core.phases.save import SavePhase
    phase = SavePhase()

    result = phase.resolve([event])

    assert result[0].state == AttackState.SAVE_FAILED


def test_invulnerable_save_used(monkeypatch, basic_attacking_unit):
    basic_attacking_unit.model.ap = -4

    def fake_randint(a, b):
        return 4  # réussi sur invu 4+

    monkeypatch.setattr("random.randint", fake_randint)

    defender_model = DefendingModel(
        toughness=4,
        save=2,
        invulnerable_save=4,
        wounds=3,
    )
    defender = DefendingUnit(defender_model, 1)

    event = AttackEvent(basic_attacking_unit, defender)
    event.state = AttackState.WOUND_SUCCESS

    from core.phases.save import SavePhase
    phase = SavePhase()

    result = phase.resolve([event])

    assert result == []
    
def test_mortal_wound_ignores_save(monkeypatch, basic_attacking_unit):
    def fake_randint(a, b):
        raise AssertionError("Save roll should not be called")

    monkeypatch.setattr("random.randint", fake_randint)

    defender_model = DefendingModel(
        toughness=4,
        save=2,
        wounds=3,
    )
    defender = DefendingUnit(defender_model, 1)

    event = AttackEvent(basic_attacking_unit, defender)
    event.state = AttackState.WOUND_SUCCESS
    event.mortal_wound = True

    from core.phases.save import SavePhase
    phase = SavePhase()

    result = phase.resolve([event])

    assert len(result) == 1
    assert result[0].state == AttackState.SAVE_FAILED