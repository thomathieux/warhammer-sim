# -*- coding: utf-8 -*-
"""
Tests pour la règle Garde du Corps (Leader + Bodyguards).

Règle V10 :
  Les blessures sont allouées aux gardes du corps en priorité.
  Le leader ne prend de dégâts que lorsque tous les gardes sont morts.
  Pas de spillover entre modèles (excédent de dégâts d'une attaque est perdu).
"""

import pytest
from core.phases.allocation import AllocationPhase
from core.events import AttackEvent
from core.enums import AttackState
from units.profiles import AttackingModel, DefendingModel
from units.attacking import WeaponGroup
from units.defending import DefendingUnit
from core.dice import FixedValue


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _attacker(damage=2):
    model = AttackingModel(attacks=FixedValue(1), attack_skill=3, strength=4,
                           ap=0, damage=FixedValue(damage))
    return WeaponGroup(model=model, model_count=1)


def _bodyguard_model(wounds=2, save=3, fnp=None):
    return DefendingModel(toughness=4, save=save, wounds=wounds, fnp=fnp)


def _leader_model(wounds=4, save=3, fnp=None):
    return DefendingModel(toughness=4, save=save, wounds=wounds, fnp=fnp)


def _unit(bodyguard_count=3, bodyguard_wounds=2, leader_wounds=None,
          bodyguard_fnp=None, leader_fnp=None):
    bg = _bodyguard_model(wounds=bodyguard_wounds, fnp=bodyguard_fnp)
    leader = _leader_model(wounds=leader_wounds, fnp=leader_fnp) if leader_wounds else None
    return DefendingUnit(model=bg, model_count=bodyguard_count, leader_model=leader)


def _resolved_event(attacker, defender, damage):
    e = AttackEvent(attacker, defender)
    e.state = AttackState.RESOLVED
    e.damage = damage
    return e


# ---------------------------------------------------------------------------
# Structure de l'unité
# ---------------------------------------------------------------------------

def test_total_model_count_with_leader():
    """3 gardes + 1 leader = 4 figurines total."""
    unit = _unit(bodyguard_count=3, leader_wounds=4)
    assert unit.total_model_count == 4


def test_total_model_count_without_leader():
    """Sans leader, total_model_count == model_count."""
    unit = _unit(bodyguard_count=5)
    assert unit.total_model_count == 5


def test_leader_alive_initially():
    unit = _unit(bodyguard_count=2, leader_wounds=5)
    assert unit.leader_alive is True
    assert unit.current_leader_wounds == 5


# ---------------------------------------------------------------------------
# Allocation — gardes protègent le leader
# ---------------------------------------------------------------------------

def test_bodyguards_absorb_damage_leader_untouched(monkeypatch):
    """
    1 garde (2 PV) prend 2 dégâts → mort.
    Leader (4 PV) n'est pas touché.
    """
    monkeypatch.setattr("random.randint", lambda a, b: 1)  # FNP désactivé (pas de FNP ici)

    attacker = _attacker(damage=2)
    defender = _unit(bodyguard_count=1, bodyguard_wounds=2, leader_wounds=4)

    events = [_resolved_event(attacker, defender, damage=2)]
    stats = AllocationPhase().resolve(events)

    assert stats.models_killed == 1
    assert defender.model_count == 0
    assert defender.leader_alive is True
    assert defender.current_leader_wounds == 4   # leader intact
    assert stats.leader_killed is False


def test_leader_takes_damage_after_all_bodyguards_dead():
    """
    3 gardes (2 PV chacun) + leader (4 PV).
    6 attaques de 2 dégâts :
      - 3 tuent les 3 gardes (6 dégâts absorbés)
      - 1 attaque atteint le leader et l'inflige 2 dégâts
    """
    attacker = _attacker(damage=2)
    defender = _unit(bodyguard_count=3, bodyguard_wounds=2, leader_wounds=4)

    events = [_resolved_event(attacker, defender, damage=2) for _ in range(4)]
    stats = AllocationPhase().resolve(events)

    assert stats.models_killed == 3
    assert defender.model_count == 0
    assert defender.leader_alive is True
    assert defender.current_leader_wounds == 2   # 4 - 2 = 2 PV restants
    assert stats.leader_killed is False


def test_leader_killed_after_bodyguards():
    """
    1 garde (2 PV) + leader (2 PV).
    2 attaques de 2 dégâts → garde mort puis leader mort.
    """
    attacker = _attacker(damage=2)
    defender = _unit(bodyguard_count=1, bodyguard_wounds=2, leader_wounds=2)

    events = [_resolved_event(attacker, defender, damage=2) for _ in range(2)]
    stats = AllocationPhase().resolve(events)

    assert stats.models_killed == 1         # 1 garde
    assert stats.leader_killed is True
    assert defender.leader_alive is False
    assert defender.current_leader_wounds == 0


def test_no_spillover_between_bodyguard_and_leader():
    """
    Garde (2 PV) prend 5 dégâts : 2 appliqués, 3 perdus (pas de spillover vers leader).
    """
    attacker = _attacker(damage=5)
    defender = _unit(bodyguard_count=1, bodyguard_wounds=2, leader_wounds=4)

    events = [_resolved_event(attacker, defender, damage=5)]
    stats = AllocationPhase().resolve(events)

    assert stats.models_killed == 1
    assert stats.spillover_damage == 3
    assert defender.leader_alive is True
    assert defender.current_leader_wounds == 4   # leader intact


def test_no_spillover_within_bodyguard_sequence():
    """
    2 gardes (2 PV). 1 attaque de 5 dégâts sur le 1er garde :
    2 appliqués, 3 perdus. Le 2ème garde reste intact.
    """
    attacker = _attacker(damage=5)
    defender = _unit(bodyguard_count=2, bodyguard_wounds=2)

    events = [_resolved_event(attacker, defender, damage=5)]
    stats = AllocationPhase().resolve(events)

    assert stats.models_killed == 1
    assert defender.model_count == 1
    assert defender.current_model_wounds == 2    # 2ème garde intact


# ---------------------------------------------------------------------------
# Wounds restants (stats)
# ---------------------------------------------------------------------------

def test_wounds_remaining_tracks_current_bodyguard():
    """
    2 gardes (3 PV chacun). 1 attaque de 1 dégât → 1er garde à 2 PV.
    wounds_remaining = 2.
    """
    attacker = _attacker(damage=1)
    defender = _unit(bodyguard_count=2, bodyguard_wounds=3)

    events = [_resolved_event(attacker, defender, damage=1)]
    stats = AllocationPhase().resolve(events)

    assert stats.wounds_remaining == 2


def test_wounds_remaining_tracks_leader_when_bodyguards_dead():
    """
    1 garde (2 PV) + leader (4 PV).
    2 attaques : 1 tue le garde, 1 inflige 1 dégât au leader.
    wounds_remaining = 3 (PV leader restants).
    """
    attacker = _attacker(damage=2)
    defender = _unit(bodyguard_count=1, bodyguard_wounds=2, leader_wounds=4)

    events = [
        _resolved_event(attacker, defender, damage=2),  # tue le garde
        _resolved_event(attacker, defender, damage=1),  # 1 dégât au leader
    ]
    stats = AllocationPhase().resolve(events)

    assert stats.wounds_remaining == 3


# ---------------------------------------------------------------------------
# Reset
# ---------------------------------------------------------------------------

def test_reset_restores_leader_state():
    """Après un reset, le leader est de nouveau en vie avec ses PV initiaux."""
    attacker = _attacker(damage=2)
    defender = _unit(bodyguard_count=1, bodyguard_wounds=2, leader_wounds=4)

    events = [_resolved_event(attacker, defender, damage=2) for _ in range(2)]
    AllocationPhase().resolve(events)

    assert defender.model_count == 0
    assert defender.leader_alive is True
    assert defender.current_leader_wounds == 2

    defender.reset()

    assert defender.model_count == 1
    assert defender.leader_alive is True
    assert defender.current_leader_wounds == 4


# ---------------------------------------------------------------------------
# FNP différent entre gardes et leader
# ---------------------------------------------------------------------------

def test_fnp_on_leader_not_bodyguards(monkeypatch):
    """
    Gardes sans FNP, leader avec FNP 5+ (tous les jets réussissent → leader ignore tout).
    1 garde (2 PV) tué, leader (4 PV) FNP 5+.
    4 dégâts sur leader → tous ignorés si jet >= 5.
    """
    # Jets de dés : 1 pour tuer le garde (pas de FNP), puis 6 pour le FNP du leader
    call_count = [0]

    def fake_randint(a, b):
        call_count[0] += 1
        return 6  # FNP 5+ réussi toujours

    monkeypatch.setattr("random.randint", fake_randint)

    attacker = _attacker(damage=2)
    bg = _bodyguard_model(wounds=2, fnp=None)
    leader = _leader_model(wounds=4, fnp=5)
    defender = DefendingUnit(model=bg, model_count=1, leader_model=leader)

    events = [
        _resolved_event(attacker, defender, damage=2),  # tue le garde (pas de FNP)
        _resolved_event(attacker, defender, damage=4),  # 4 dégâts sur leader, FNP 5+
    ]
    stats = AllocationPhase().resolve(events)

    assert stats.models_killed == 1
    assert defender.leader_alive is True
    assert stats.fnp_ignored_damage == 4   # 4 dégâts ignorés par le leader
    assert stats.leader_killed is False
