# -*- coding: utf-8 -*-
"""
Created on Fri Jan 23 22:26:22 2026

@author: thoma
"""

from core.phases.hit import HitPhase
from core.events import AttackEvent
from core.enums import AttackState
from core.enums import RerollType
from units.profiles import DefendingModel
from units.defending import DefendingUnit
from core.events import AttackEvent
from core.phases.hit import HitPhase


def test_hit_success(monkeypatch, basic_attacking_unit):
    def fake_randint(a, b):
        return 4  # touche à 3+

    monkeypatch.setattr("random.randint", fake_randint)

    event = AttackEvent(
        attacker=basic_attacking_unit,
        defender=None,
    )

    phase = HitPhase()
    result = phase.resolve([event])

    assert len(result) == 1
    assert result[0].state == AttackState.HIT_SUCCESS
    assert not result[0].hit_critical
    
    
def test_hit_fail(monkeypatch, basic_attacking_unit):
    def fake_randint(a, b):
        return 1  # raté

    monkeypatch.setattr("random.randint", fake_randint)

    event = AttackEvent(
        attacker=basic_attacking_unit,
        defender=None,
    )

    phase = HitPhase()
    result = phase.resolve([event])

    assert result == []





def test_lethal_hits(monkeypatch, basic_attacking_unit):
    basic_attacking_unit.lethal_hits = True

    def fake_randint(a, b):
        return 6  # critique

    monkeypatch.setattr("random.randint", fake_randint)

    event = AttackEvent(
        attacker=basic_attacking_unit,
        defender=None,
    )

    phase = HitPhase()
    result = phase.resolve([event])

    assert len(result) == 1
    assert result[0].auto_wound is True
    assert result[0].state == AttackState.WOUND_SUCCESS
    

def test_sustained_hits(monkeypatch, basic_attacking_unit):
    basic_attacking_unit.sustained_hits = 2

    def fake_randint(a, b):
        return 6  # critique

    monkeypatch.setattr("random.randint", fake_randint)

    event = AttackEvent(
        attacker=basic_attacking_unit,
        defender=None,
    )

    phase = HitPhase()
    result = phase.resolve([event])

    assert len(result) == 3  # 1 original + 2 sustained
    assert sum(e.hit_critical for e in result) == 1




def test_reroll_one(monkeypatch, basic_attacking_unit):
    basic_attacking_unit.hit_reroll = RerollType.ONE

    rolls = iter([1, 5])  # 1 → reroll → 5

    def fake_randint(a, b):
        return next(rolls)

    monkeypatch.setattr("random.randint", fake_randint)

    event = AttackEvent(
        attacker=basic_attacking_unit,
        defender=None,
    )

    phase = HitPhase()
    result = phase.resolve([event])

    assert len(result) == 1
    assert result[0].hit_roll == 5
    
    
def test_minus_one_hit_reduces_margin_but_still_hits(monkeypatch, basic_attacking_unit):
    def fake_randint(a, b):
        return 4

    monkeypatch.setattr("random.randint", fake_randint)

    defender = DefendingUnit(
        DefendingModel(toughness=4, save=3, wounds=2),
        model_count=1,
        hit_modifier=-1,
    )

    event = AttackEvent(basic_attacking_unit, defender)
    result = HitPhase().resolve([event])

    assert len(result) == 1
    assert result[0].hit_roll == 3
    
def test_hit_modifier_capped_at_minus_one(monkeypatch, basic_attacking_unit):
    # Jet de 5 : même avec -2 théorique, le cap empêche -2
    def fake_randint(a, b):
        return 5

    monkeypatch.setattr("random.randint", fake_randint)

    from units.profiles import DefendingModel
    from units.defending import DefendingUnit
    from core.events import AttackEvent
    from core.phases.hit import HitPhase

    defender = DefendingUnit(
        DefendingModel(toughness=4, save=3, wounds=2),
        model_count=1,
        hit_modifier=-2,  # ex: plusieurs sources
    )

    event = AttackEvent(basic_attacking_unit, defender)
    result = HitPhase().resolve([event])

    assert len(result) == 1  # 5 → 4 après cap, touche encore


def test_unmodified_one_always_fails(monkeypatch, basic_attacking_unit):
    def fake_randint(a, b):
        return 1  # jet brut

    monkeypatch.setattr("random.randint", fake_randint)

    from units.profiles import DefendingModel
    from units.defending import DefendingUnit
    from core.events import AttackEvent
    from core.phases.hit import HitPhase

    # Bonus artificiel (+1 hit)
    defender = DefendingUnit(
        DefendingModel(toughness=4, save=3, wounds=2),
        model_count=1,
        hit_modifier=+1,
    )

    event = AttackEvent(basic_attacking_unit, defender)
    result = HitPhase().resolve([event])

    assert result == []
    
def test_unmodified_six_always_succeeds(monkeypatch, basic_attacking_unit):
    def fake_randint(a, b):
        return 6  # jet brut

    monkeypatch.setattr("random.randint", fake_randint)

    from units.profiles import DefendingModel
    from units.defending import DefendingUnit
    from core.events import AttackEvent
    from core.phases.hit import HitPhase

    # Malus artificiel (-1 hit)
    defender = DefendingUnit(
        DefendingModel(toughness=4, save=3, wounds=2),
        model_count=1,
        hit_modifier=-1,
    )

    event = AttackEvent(basic_attacking_unit, defender)
    result = HitPhase().resolve([event])

    assert len(result) == 1
    assert result[0].hit_roll == 6

def test_reroll_on_future_failure(monkeypatch, basic_attacking_unit):
    basic_attacking_unit.hit_reroll = RerollType.FAILED

    rolls = iter([3, 5])  # 3 → futur échec (3-1), relancé → 5

    def fake_randint(a, b):
        return next(rolls)

    monkeypatch.setattr("random.randint", fake_randint)

    defender = DefendingUnit(
        DefendingModel(toughness=4, save=3, wounds=2),
        model_count=1,
        hit_modifier=-1,
    )

    event = AttackEvent(basic_attacking_unit, defender)
    result = HitPhase().resolve([event])

    assert len(result) == 1
    assert result[0].hit_roll == 4  # 5-1