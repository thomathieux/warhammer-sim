# -*- coding: utf-8 -*-
"""
Created on Fri Jan 23 23:46:29 2026

@author: thoma
"""

def test_allocation_partial_damage_no_kill(basic_attacking_unit):
    from core.phases.allocation import AllocationPhase
    from units.profiles import DefendingModel
    from units.defending import DefendingUnit
    from core.events import AttackEvent
    from core.enums import AttackState

    defender_model = DefendingModel(
        toughness=4,
        save=3,
        wounds=3,
    )
    defender = DefendingUnit(defender_model, model_count=2)

    event = AttackEvent(basic_attacking_unit, defender)
    event.state = AttackState.RESOLVED
    event.damage = 2

    phase = AllocationPhase()
    result = phase.resolve([event])

    assert defender.current_model_wounds == 1
    assert defender.model_count == 2

def test_allocation_exact_kill(basic_attacking_unit):
    from core.phases.allocation import AllocationPhase
    from units.profiles import DefendingModel
    from units.defending import DefendingUnit
    from core.events import AttackEvent
    from core.enums import AttackState

    defender_model = DefendingModel(
        toughness=4,
        save=3,
        wounds=3,
    )
    defender = DefendingUnit(defender_model, model_count=2)

    event = AttackEvent(basic_attacking_unit, defender)
    event.state = AttackState.RESOLVED
    event.damage = 3

    phase = AllocationPhase()
    phase.resolve([event])

    assert defender.model_count == 1
    assert defender.current_model_wounds == 3

def test_allocation_no_spillover(basic_attacking_unit):
    from core.phases.allocation import AllocationPhase
    from units.profiles import DefendingModel
    from units.defending import DefendingUnit
    from core.events import AttackEvent
    from core.enums import AttackState

    defender_model = DefendingModel(
        toughness=4,
        save=3,
        wounds=2,
    )
    defender = DefendingUnit(defender_model, model_count=2)

    event = AttackEvent(basic_attacking_unit, defender)
    event.state = AttackState.RESOLVED
    event.damage = 5  # dépasse largement les PV

    phase = AllocationPhase()
    phase.resolve([event])

    assert defender.model_count == 1
    assert defender.current_model_wounds == 2  # reset, pas entamé

def test_allocation_continues_on_wounded_model(basic_attacking_unit):
    from core.phases.allocation import AllocationPhase
    from units.profiles import DefendingModel
    from units.defending import DefendingUnit
    from core.events import AttackEvent
    from core.enums import AttackState

    defender_model = DefendingModel(
        toughness=4,
        save=3,
        wounds=4,
    )
    defender = DefendingUnit(defender_model, model_count=2)
    defender.current_model_wounds = 2  # déjà blessé

    event = AttackEvent(basic_attacking_unit, defender)
    event.state = AttackState.RESOLVED
    event.damage = 1

    phase = AllocationPhase()
    phase.resolve([event])

    assert defender.current_model_wounds == 1
