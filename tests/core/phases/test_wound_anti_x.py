# -*- coding: utf-8 -*-
"""
Tests Anti-X dans WoundPhase.

Anti-KEYWORD N+ : blessure critique sur N+ si la cible possède le mot-clé KEYWORD.
"""

import pytest
from core.phases.wound import WoundPhase
from core.events import AttackEvent
from core.enums import AttackState
from units.profiles import AttackingModel, DefendingModel
from units.attacking import AttackingUnit
from units.defending import DefendingUnit
from core.dice import FixedValue


def _attacker(anti_keyword=None, anti_threshold=None, devastating_wounds=False):
    model = AttackingModel(attacks=FixedValue(1), attack_skill=3, strength=4)
    return AttackingUnit(
        model=model, model_count=1,
        anti_keyword=anti_keyword,
        anti_threshold=anti_threshold,
        devastating_wounds=devastating_wounds,
    )


def _defender(keywords=None):
    m = DefendingModel(toughness=4, save=3, wounds=2)
    return DefendingUnit(m, model_count=1, keywords=keywords or [])


def _hit_event(attacker, defender):
    e = AttackEvent(attacker, defender)
    e.state = AttackState.HIT_SUCCESS
    return e


def test_anti_x_critical_when_keyword_and_threshold_met(monkeypatch):
    """Anti-INFANTRY 4+ : un 4 ou plus contre une cible INFANTRY → critique."""
    monkeypatch.setattr("random.randint", lambda a, b: 4)

    attacker = _attacker(anti_keyword="INFANTRY", anti_threshold=4)
    defender = _defender(keywords=["INFANTRY", "CORE"])

    result = WoundPhase().resolve([_hit_event(attacker, defender)])

    assert len(result) == 1
    assert result[0].wound_critical is True


def test_anti_x_no_critical_below_threshold(monkeypatch):
    """Anti-INFANTRY 4+ : un 3 contre INFANTRY → pas de critique (blessure normale si 3 >= seuil blessure)."""
    monkeypatch.setattr("random.randint", lambda a, b: 3)

    attacker = _attacker(anti_keyword="INFANTRY", anti_threshold=4)
    defender = _defender(keywords=["INFANTRY"])

    result = WoundPhase().resolve([_hit_event(attacker, defender)])

    # S4 vs T4 → seuil 4+, jet 3 → raté : aucune blessure
    assert len(result) == 0


def test_anti_x_no_critical_without_keyword(monkeypatch):
    """Anti-INFANTRY 4+ : le défenseur n'a pas le mot-clé → critique normal seulement."""
    monkeypatch.setattr("random.randint", lambda a, b: 5)  # >= 4 mais cible pas INFANTRY

    attacker = _attacker(anti_keyword="INFANTRY", anti_threshold=4)
    defender = _defender(keywords=["VEHICLE"])  # pas INFANTRY

    result = WoundPhase().resolve([_hit_event(attacker, defender)])

    assert len(result) == 1
    assert result[0].wound_critical is False


def test_anti_x_keyword_case_insensitive(monkeypatch):
    """Les mots-clés sont comparés en majuscules (insensible à la casse)."""
    monkeypatch.setattr("random.randint", lambda a, b: 5)

    attacker = _attacker(anti_keyword="infantry", anti_threshold=4)  # minuscule
    defender = _defender(keywords=["Infantry"])  # casse mixte

    result = WoundPhase().resolve([_hit_event(attacker, defender)])

    assert result[0].wound_critical is True


def test_anti_x_with_devastating_wounds_causes_mortal(monkeypatch):
    """Anti-X + Devastating Wounds : critique Anti-X → blessure mortelle."""
    monkeypatch.setattr("random.randint", lambda a, b: 4)

    attacker = _attacker(anti_keyword="INFANTRY", anti_threshold=4, devastating_wounds=True)
    defender = _defender(keywords=["INFANTRY"])

    result = WoundPhase().resolve([_hit_event(attacker, defender)])

    assert result[0].wound_critical is True
    assert result[0].mortal_wound is True


def test_anti_x_does_not_override_standard_critical(monkeypatch):
    """Un 6 déclenche le critique normal (wound_critical_on=6) indépendamment d'Anti-X."""
    monkeypatch.setattr("random.randint", lambda a, b: 6)

    # Anti-X inactif (cible sans le mot-clé), mais 6 → critique standard
    attacker = _attacker(anti_keyword="INFANTRY", anti_threshold=4)
    defender = _defender(keywords=[])  # pas de INFANTRY

    result = WoundPhase().resolve([_hit_event(attacker, defender)])

    assert result[0].wound_critical is True
