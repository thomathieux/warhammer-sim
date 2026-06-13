# -*- coding: utf-8 -*-
"""
Tests FNP dans AllocationPhase.

Vérifie le comportement point-par-point :
- Stop dès que le modèle atteint 0 PV
- Les points de dégâts excédentaires sont perdus (pas de FNP sur spillover)
"""

import pytest
from core.phases.allocation import AllocationPhase
from core.events import AttackEvent
from core.enums import AttackState
from units.profiles import DefendingModel
from units.defending import DefendingUnit


def _make_event(attacker, toughness, save, wounds, model_count, damage, fnp=None):
    model = DefendingModel(toughness=toughness, save=save, wounds=wounds, fnp=fnp)
    defender = DefendingUnit(model, model_count=model_count)
    event = AttackEvent(attacker, defender)
    event.state = AttackState.RESOLVED
    event.damage = damage
    return event, defender


def test_fnp_all_saves_model_survives(monkeypatch, basic_attacking_unit):
    """FNP réussit sur chaque point → aucun dégât appliqué."""
    monkeypatch.setattr("random.randint", lambda a, b: 6)  # toujours 6 = sauvegarde

    event, defender = _make_event(
        basic_attacking_unit,
        toughness=4, save=3, wounds=3, model_count=1, damage=3, fnp=5,
    )
    result = AllocationPhase().resolve([event])

    assert defender.model_count == 1
    assert defender.current_model_wounds == 3
    assert result.fnp_ignored_damage == 3
    assert result.models_killed == 0


def test_fnp_no_saves_damage_applied(monkeypatch, basic_attacking_unit):
    """FNP échoue sur chaque point → dégâts normaux."""
    monkeypatch.setattr("random.randint", lambda a, b: 1)  # toujours 1 = échec

    event, defender = _make_event(
        basic_attacking_unit,
        toughness=4, save=3, wounds=3, model_count=1, damage=2, fnp=5,
    )
    AllocationPhase().resolve([event])

    assert defender.model_count == 1
    assert defender.current_model_wounds == 1


def test_fnp_stops_at_model_death_no_excess_rolls(monkeypatch, basic_attacking_unit):
    """
    Modèle 2 PV, dégât 5, FNP toujours raté.
    FNP doit s'arrêter après 2 lancers (modèle mort) — les 3 restants sont perdus.
    """
    roll_count = {"n": 0}

    def counting_fail(a, b):
        roll_count["n"] += 1
        return 1  # toujours raté

    monkeypatch.setattr("random.randint", counting_fail)

    event, defender = _make_event(
        basic_attacking_unit,
        toughness=4, save=3, wounds=2, model_count=2, damage=5, fnp=5,
    )
    result = AllocationPhase().resolve([event])

    assert roll_count["n"] == 2           # exactement 2 lancers, pas 5
    assert result.models_killed == 1
    assert defender.model_count == 1
    assert defender.current_model_wounds == 2  # second modèle intact
    assert result.fnp_ignored_damage == 0


def test_fnp_partial_saves_stops_at_death(monkeypatch, basic_attacking_unit):
    """
    Modèle 2 PV, dégât 5, séquence : raté, réussi, raté → mort au 3e lancer.
    Les lancers 4 et 5 ne doivent pas avoir lieu.
    """
    rolls = iter([1, 6, 1])  # raté → sauvegarde → raté (= mort)
    roll_count = {"n": 0}

    def controlled_roll(a, b):
        roll_count["n"] += 1
        return next(rolls)

    monkeypatch.setattr("random.randint", controlled_roll)

    event, defender = _make_event(
        basic_attacking_unit,
        toughness=4, save=3, wounds=2, model_count=2, damage=5, fnp=5,
    )
    result = AllocationPhase().resolve([event])

    assert roll_count["n"] == 3           # 3 lancers : raté, sauvegarde, raté
    assert result.fnp_ignored_damage == 1  # 1 seule sauvegarde réussie
    assert result.models_killed == 1
    assert defender.model_count == 1
    assert defender.current_model_wounds == 2


def test_fnp_save_prevents_kill(monkeypatch, basic_attacking_unit):
    """
    Modèle 2 PV, dégât 2, FNP sauve le premier point.
    1 seul dégât appliqué → modèle survit avec 1 PV.
    """
    rolls = iter([6, 1])  # sauvegarde puis raté

    monkeypatch.setattr("random.randint", lambda a, b: next(rolls))

    event, defender = _make_event(
        basic_attacking_unit,
        toughness=4, save=3, wounds=2, model_count=1, damage=2, fnp=5,
    )
    AllocationPhase().resolve([event])

    assert defender.model_count == 1
    assert defender.current_model_wounds == 1
