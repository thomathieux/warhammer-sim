# -*- coding: utf-8 -*-
"""
Tests Torrent dans HitPhase.

Torrent : auto-touche, pas de jet de dé.
Pas de touche critique → Lethal Hits et Sustained Hits ne s'activent pas.
"""

import pytest
from core.phases.hit import HitPhase
from core.events import AttackEvent
from core.enums import AttackState
from units.profiles import AttackingModel, DefendingModel
from units.attacking import AttackingUnit
from units.defending import DefendingUnit
from core.dice import FixedValue


def _make_torrent_attacker(model_count=1, lethal_hits=False, sustained_hits=0):
    model = AttackingModel(attacks=FixedValue(3), attack_skill=4, strength=3, ap=0, damage=FixedValue(1))
    return AttackingUnit(model=model, model_count=model_count, torrent=True,
                         lethal_hits=lethal_hits, sustained_hits=sustained_hits)


def _make_defender():
    m = DefendingModel(toughness=4, save=3, wounds=1)
    return DefendingUnit(m, model_count=5)


def _events(attacker, defender, n):
    events = [AttackEvent(attacker, defender) for _ in range(n)]
    return events


def test_torrent_all_events_hit(monkeypatch):
    """Tous les events passent en HIT_SUCCESS, peu importe le dé."""
    monkeypatch.setattr("random.randint", lambda a, b: 1)  # toujours 1 = raté normal

    attacker = _make_torrent_attacker()
    defender = _make_defender()
    events = _events(attacker, defender, 3)

    result = HitPhase().resolve(events)

    assert len(result) == 3
    assert all(e.state == AttackState.HIT_SUCCESS for e in result)


def test_torrent_no_critical_hit():
    """Pas de hit_critical sur des attaques Torrent (pas de jet = pas de 6)."""
    attacker = _make_torrent_attacker()
    defender = _make_defender()
    events = _events(attacker, defender, 5)

    result = HitPhase().resolve(events)

    assert all(not e.hit_critical for e in result)


def test_torrent_lethal_hits_does_not_trigger():
    """Lethal Hits nécessite une touche critique → inactif avec Torrent."""
    attacker = _make_torrent_attacker(lethal_hits=True)
    defender = _make_defender()
    events = _events(attacker, defender, 4)

    result = HitPhase().resolve(events)

    assert all(not e.auto_wound for e in result)


def test_torrent_sustained_hits_does_not_trigger():
    """Sustained Hits nécessite une touche critique → inactif avec Torrent."""
    attacker = _make_torrent_attacker(sustained_hits=2)
    defender = _make_defender()
    events = _events(attacker, defender, 3)

    # Pas d'events supplémentaires (Sustained Hits inactif)
    result = HitPhase().resolve(events)
    assert len(result) == 3


def test_torrent_coexists_with_normal_attacks(monkeypatch):
    """Unité avec Torrent : tous les events touchent même avec un mauvais BS."""
    monkeypatch.setattr("random.randint", lambda a, b: 1)

    # BS 6+ (très mauvais) mais Torrent → tout touche
    model = AttackingModel(attacks=FixedValue(2), attack_skill=6, strength=3)
    attacker = AttackingUnit(model=model, model_count=3, torrent=True)
    defender = _make_defender()
    events = _events(attacker, defender, 6)

    result = HitPhase().resolve(events)
    assert len(result) == 6
