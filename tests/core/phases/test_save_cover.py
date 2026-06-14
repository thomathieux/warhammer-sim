# -*- coding: utf-8 -*-
"""
Tests Couverture et Ignores Cover dans SavePhase.

Couverture : +1 à la sauvegarde d'armure (seuil réduit de 1).
Ignores Cover : annule le bonus de couverture.
"""

import pytest
from core.phases.save import SavePhase
from core.context import CombatContext
from core.events import AttackEvent
from core.enums import AttackState
from units.profiles import AttackingModel, DefendingModel
from units.attacking import WeaponGroup
from units.defending import DefendingUnit
from core.dice import FixedValue


def _attacker(ap=0, ignores_cover=False):
    model = AttackingModel(attacks=FixedValue(1), attack_skill=3, strength=4, ap=ap)
    return WeaponGroup(model=model, model_count=1, ignores_cover=ignores_cover)


def _defender(save=4, invuln=None):
    m = DefendingModel(toughness=4, save=save, wounds=1, invulnerable_save=invuln)
    return DefendingUnit(m, model_count=1)


def _wound_event(attacker, defender):
    e = AttackEvent(attacker, defender)
    e.state = AttackState.WOUND_SUCCESS
    return e


def test_cover_improves_save(monkeypatch):
    """
    Défenseur SV4+, AP0, couverture → effective SV3+.
    Un jet de 3 réussit avec couverture mais raterait sans.
    """
    monkeypatch.setattr("random.randint", lambda a, b: 3)

    attacker = _attacker(ap=0)
    defender = _defender(save=4)
    ctx = CombatContext(target_in_cover=True)

    result = SavePhase().resolve([_wound_event(attacker, defender)], context=ctx)

    assert len(result) == 0  # sauvegarde réussie (aucun event ne passe)


def test_no_cover_save_fails_on_same_roll(monkeypatch):
    """Sans couverture, le même jet de 3 rate une SV4+."""
    monkeypatch.setattr("random.randint", lambda a, b: 3)

    attacker = _attacker(ap=0)
    defender = _defender(save=4)
    ctx = CombatContext(target_in_cover=False)

    result = SavePhase().resolve([_wound_event(attacker, defender)], context=ctx)

    assert len(result) == 1  # sauvegarde ratée


def test_ignores_cover_negates_bonus(monkeypatch):
    """Ignores Cover : couverture déclarée mais annulée → SV normale."""
    monkeypatch.setattr("random.randint", lambda a, b: 3)

    attacker = _attacker(ap=0, ignores_cover=True)
    defender = _defender(save=4)
    ctx = CombatContext(target_in_cover=True)

    result = SavePhase().resolve([_wound_event(attacker, defender)], context=ctx)

    assert len(result) == 1  # couverture ignorée, 3 < 4 → raté


def test_cover_with_ap_stacks_correctly(monkeypatch):
    """SV3+ AP-1 couverture → effective 3 - (-1) - 1 = 3. Jet 3 = réussi."""
    monkeypatch.setattr("random.randint", lambda a, b: 3)

    attacker = _attacker(ap=-1)
    defender = _defender(save=3)
    ctx = CombatContext(target_in_cover=True)

    result = SavePhase().resolve([_wound_event(attacker, defender)], context=ctx)

    assert len(result) == 0  # 3 - (-1) - 1 = 3 → jet 3 >= 3 → réussi


def test_no_context_no_cover():
    """Sans context, pas de couverture appliquée."""
    # Pas de monkeypatch — on vérifie juste que la phase tourne sans context
    attacker = _attacker(ap=0)
    defender = _defender(save=3)

    # Appel sans context → aucune erreur
    SavePhase().resolve([_wound_event(attacker, defender)], context=None)
