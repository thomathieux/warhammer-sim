# -*- coding: utf-8 -*-
"""
Created on Fri Jan 23 23:56:46 2026

@author: thoma
"""
from core.enums import RerollType

def test_twin_linked_reroll_success(monkeypatch, basic_attacking_unit):
    basic_attacking_unit.twin_linked = True

    rolls = iter([1, 5])  # 1 = raté, 5 = réussi

    def fake_randint(a, b):
        return next(rolls)

    monkeypatch.setattr("random.randint", fake_randint)

    from units.profiles import DefendingModel
    from units.defending import DefendingUnit
    from core.events import AttackEvent
    from core.enums import AttackState
    from core.phases.wound import WoundPhase

    defender = DefendingUnit(
        DefendingModel(toughness=4, save=3, wounds=2),
        model_count=1,
    )

    event = AttackEvent(basic_attacking_unit, defender)
    event.state = AttackState.HIT_SUCCESS

    phase = WoundPhase()
    result = phase.resolve([event])

    assert len(result) == 1
    assert result[0].state == AttackState.WOUND_SUCCESS

def test_twin_linked_ignored_on_auto_wound(monkeypatch, basic_attacking_unit):
    basic_attacking_unit.twin_linked = True

    def fake_randint(a, b):
        raise AssertionError("Wound roll should not be called")

    monkeypatch.setattr("random.randint", fake_randint)

    from units.profiles import DefendingModel
    from units.defending import DefendingUnit
    from core.events import AttackEvent
    from core.enums import AttackState
    from core.phases.wound import WoundPhase

    defender = DefendingUnit(
        DefendingModel(toughness=4, save=3, wounds=2),
        model_count=1,
    )

    event = AttackEvent(basic_attacking_unit, defender)
    event.auto_wound = True
    event.state = AttackState.WOUND_SUCCESS

    phase = WoundPhase()
    result = phase.resolve([event])

    assert len(result) == 1

def test_no_double_reroll_twin_linked_and_aura(monkeypatch, basic_attacking_unit):
    basic_attacking_unit.twin_linked = True
    basic_attacking_unit.wound_reroll = RerollType.FAILED

    rolls = iter([1, 1])  # raté, relancé une fois, raté encore

    def fake_randint(a, b):
        return next(rolls)

    monkeypatch.setattr("random.randint", fake_randint)

    # setup defender...
    # assert qu'il n'y a qu'UNE relance