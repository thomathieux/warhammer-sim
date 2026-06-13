# -*- coding: utf-8 -*-
"""
Tests V11 : Save Phase par profil + tri ascendant + rôle Support.

Mécaniques V11 testées :
  1. Tri des saves ascendant : les dice les plus bas vont aux gardes en premier.
  2. Re-évaluation du save pour les personnages avec leur propre profil.
  3. Rôle Support : 2e personnage, alloué avant le leader.
  4. Ordre complet : bodyguards → support → leader.
  5. total_model_count inclut les trois rôles.
"""

import pytest
from core.phases.save import SavePhase
from core.phases.allocation import AllocationPhase, _passes_save
from core.phases.damage import DamagePhase
from core.context import CombatContext
from core.events import AttackEvent
from core.enums import AttackState
from units.profiles import AttackingModel, DefendingModel
from units.attacking import AttackingUnit
from units.defending import DefendingUnit
from core.dice import FixedValue


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _attacker(ap=0, damage=1):
    model = AttackingModel(
        attacks=FixedValue(1), attack_skill=3, strength=4,
        ap=ap, damage=FixedValue(damage),
    )
    return AttackingUnit(model=model, model_count=1)


def _bg(wounds=2, save=5, fnp=None):
    return DefendingModel(toughness=4, save=save, wounds=wounds, fnp=fnp)


def _char(wounds=4, save=2, fnp=None):
    return DefendingModel(toughness=4, save=save, wounds=wounds, fnp=fnp)


def _unit(bg_count=3, bg_save=5, bg_wounds=2,
          leader_save=None, leader_wounds=4,
          support_save=None, support_wounds=3):
    bg = _bg(wounds=bg_wounds, save=bg_save)
    leader = _char(wounds=leader_wounds, save=leader_save) if leader_save else None
    support = _char(wounds=support_wounds, save=support_save) if support_save else None
    return DefendingUnit(model=bg, model_count=bg_count,
                         leader_model=leader, support_model=support)


def _resolved_event(attacker, defender, damage):
    e = AttackEvent(attacker, defender)
    e.state = AttackState.RESOLVED
    e.damage = damage
    return e


def _save_failed_event(attacker, defender, damage, save_roll):
    """Événement ayant échoué le save des gardes, avec un dice connu."""
    e = AttackEvent(attacker, defender)
    e.state = AttackState.SAVE_FAILED
    e.save_roll = save_roll
    e.damage = damage
    return e


# ---------------------------------------------------------------------------
# Feature 2 : Structure à trois rôles
# ---------------------------------------------------------------------------

def test_total_model_count_three_roles():
    """3 gardes + 1 support + 1 leader = 5 figurines."""
    unit = _unit(bg_count=3, leader_save=2, support_save=3)
    assert unit.total_model_count == 5


def test_total_model_count_no_characters():
    unit = _unit(bg_count=4)
    assert unit.total_model_count == 4


def test_support_alive_initially():
    unit = _unit(bg_count=2, support_save=3, support_wounds=3)
    assert unit.support_alive is True
    assert unit.current_support_wounds == 3


def test_reset_restores_all_three_slots():
    """Après un reset, les trois rôles reviennent à leur état initial."""
    attacker = _attacker(damage=10)
    unit = _unit(bg_count=1, bg_wounds=2, leader_save=2, leader_wounds=4,
                 support_save=3, support_wounds=3)

    # Vider l'unité entièrement
    events = [_resolved_event(attacker, unit, damage=10) for _ in range(3)]
    AllocationPhase().resolve(events)

    assert unit.model_count == 0
    assert unit.support_alive is False
    assert unit.leader_alive is False

    unit.reset()

    assert unit.model_count == 1
    assert unit.support_alive is True
    assert unit.current_support_wounds == 3
    assert unit.leader_alive is True
    assert unit.current_leader_wounds == 4


# ---------------------------------------------------------------------------
# Feature 1 : Tri ascendant des saves (V11)
# ---------------------------------------------------------------------------

def test_save_phase_sorts_by_roll_ascending(monkeypatch):
    """
    Avec des jets fixes [5, 2, 4] (dans cet ordre), SavePhase doit retourner
    les événements triés [2, 4, 5] (les plus bas en premier).
    Tous échouent contre SV6+ (gardes très faibles).
    """
    rolls = iter([5, 2, 4])
    monkeypatch.setattr("random.randint", lambda a, b: next(rolls))

    attacker = _attacker(ap=0)
    # SV6+ : seulement un 6 sauve → tous les jets 2,4,5 échouent
    bg = DefendingModel(toughness=4, save=6, wounds=2)
    defender = DefendingUnit(model=bg, model_count=3)

    events = [AttackEvent(attacker, defender) for _ in range(3)]
    for e in events:
        e.state = AttackState.WOUND_SUCCESS

    result = SavePhase().resolve(events)

    # Les 3 échouent (2<6, 4<6, 5<6), triés par save_roll
    assert len(result) == 3
    assert [e.save_roll for e in result] == [2, 4, 5]


def test_save_phase_mortal_wounds_sorted_first(monkeypatch):
    """
    Les blessures mortelles (save_roll=None) passent avant les saves triés.
    """
    monkeypatch.setattr("random.randint", lambda a, b: 3)

    attacker = _attacker(ap=0)
    bg = DefendingModel(toughness=4, save=6, wounds=2)
    defender = DefendingUnit(model=bg, model_count=2)

    normal = AttackEvent(attacker, defender)
    normal.state = AttackState.WOUND_SUCCESS

    mortal = AttackEvent(attacker, defender)
    mortal.state = AttackState.WOUND_SUCCESS
    mortal.mortal_wound = True

    result = SavePhase().resolve([normal, mortal])

    # Blessure mortelle d'abord (save_roll=None → priorité)
    assert result[0].mortal_wound is True
    assert result[1].save_roll == 3


# ---------------------------------------------------------------------------
# Feature 1 : Re-évaluation save pour les personnages (V11)
# ---------------------------------------------------------------------------

def test_passes_save_helper_strong_character():
    """_passes_save retourne True si le dice passe le save du personnage."""
    attacker = _attacker(ap=0)
    leader = _char(save=2)  # SV2+ : presque tout passe
    assert _passes_save(4, leader, attacker, None) is True
    assert _passes_save(2, leader, attacker, None) is True
    assert _passes_save(1, leader, attacker, None) is False  # 1 échoue toujours


def test_passes_save_helper_with_ap():
    """AP-2 : armour_save = 2 - (-2) = 4+. Un 4 passe, un 3 échoue."""
    attacker = _attacker(ap=-2)
    leader = _char(save=2)  # SV2+, AP-2 → seuil effectif 4+
    assert _passes_save(4, leader, attacker, None) is True
    assert _passes_save(3, leader, attacker, None) is False


def test_leader_protected_by_better_save(monkeypatch):
    """
    Garde SV6+, Leader SV2+. AP0.
    2 wounds: rolls [3, 5] (les deux échouent SV6+).
    - Roll 3 → garde meurt (1W, 1 dégât).
    - Roll 5 → leader : re-éval SV2+ → 5>=2 PASSE → leader intact.
    """
    rolls = iter([3, 5])
    monkeypatch.setattr("random.randint", lambda a, b: next(rolls))

    attacker = _attacker(ap=0, damage=1)
    bg = DefendingModel(toughness=4, save=6, wounds=1)
    leader_m = DefendingModel(toughness=4, save=2, wounds=4)
    defender = DefendingUnit(model=bg, model_count=1, leader_model=leader_m)

    # SavePhase : rolls [3, 5], tous échouent SV6+, triés [3, 5]
    wound_events = [AttackEvent(attacker, defender) for _ in range(2)]
    for e in wound_events:
        e.state = AttackState.WOUND_SUCCESS

    save_events = SavePhase().resolve(wound_events)
    assert [e.save_roll for e in save_events] == [3, 5]  # triés

    # DamagePhase
    dmg_events = DamagePhase().resolve(save_events)

    # AllocationPhase : garde meurt, puis roll 5 re-évalué vs SV2+ → passe
    stats = AllocationPhase().resolve(dmg_events)

    assert stats.models_killed == 1      # 1 garde mort
    assert stats.leader_killed is False  # leader indemne (save 5>=2 passe)
    assert defender.leader_alive is True
    assert defender.current_leader_wounds == 4


def test_leader_damaged_when_save_fails_their_profile(monkeypatch):
    """
    Garde SV6+, Leader SV5+. AP0.
    Roll 3 : échoue SV6+ ET échoue SV5+ (3<5) → leader prend des dégâts.
    """
    rolls = iter([2, 3])
    monkeypatch.setattr("random.randint", lambda a, b: next(rolls))

    attacker = _attacker(ap=0, damage=1)
    bg = DefendingModel(toughness=4, save=6, wounds=1)
    leader_m = DefendingModel(toughness=4, save=5, wounds=4)
    defender = DefendingUnit(model=bg, model_count=1, leader_model=leader_m)

    wound_events = [AttackEvent(attacker, defender) for _ in range(2)]
    for e in wound_events:
        e.state = AttackState.WOUND_SUCCESS

    save_events = SavePhase().resolve(wound_events)
    dmg_events = DamagePhase().resolve(save_events)
    stats = AllocationPhase().resolve(dmg_events)

    assert stats.models_killed == 1       # garde mort
    assert defender.current_leader_wounds == 3  # 4 - 1 = 3 PV restants
    assert stats.leader_killed is False


def test_mortal_wound_bypasses_character_save(monkeypatch):
    """
    Une blessure mortelle (Devastating Wounds) ignore le save du leader SV2+.
    """
    monkeypatch.setattr("random.randint", lambda a, b: 6)  # FNP etc.

    attacker = _attacker(ap=0, damage=3)
    bg = DefendingModel(toughness=4, save=6, wounds=1)
    leader_m = DefendingModel(toughness=4, save=2, wounds=4)
    defender = DefendingUnit(model=bg, model_count=0, leader_model=leader_m)

    # Événement mortal wound atteignant directement le leader
    e = _resolved_event(attacker, defender, damage=3)
    e.mortal_wound = True
    e.save_roll = None  # pas de jet de save

    stats = AllocationPhase().resolve([e])

    # Leader perd 3 PV malgré SV2+
    assert defender.current_leader_wounds == 1
    assert stats.leader_killed is False


# ---------------------------------------------------------------------------
# Feature 2 : Rôle Support (2e personnage)
# ---------------------------------------------------------------------------

def test_support_takes_damage_before_leader():
    """
    Ordre : gardes → support → leader.
    Gardes morts → dégâts vont au support, pas au leader.
    """
    attacker = _attacker(damage=3)
    bg = DefendingModel(toughness=4, save=6, wounds=1)
    support_m = DefendingModel(toughness=4, save=2, wounds=3)
    leader_m = DefendingModel(toughness=4, save=2, wounds=4)
    defender = DefendingUnit(model=bg, model_count=0,  # gardes déjà morts
                             support_model=support_m, leader_model=leader_m)

    e = _resolved_event(attacker, defender, damage=2)
    stats = AllocationPhase().resolve([e])

    assert defender.current_support_wounds == 1  # 3 - 2 = 1
    assert defender.current_leader_wounds == 4   # leader intact
    assert stats.support_killed is False
    assert stats.leader_killed is False


def test_support_killed_before_leader():
    """
    Support (3 PV) reçoit 3 dégâts → mort.
    Attaque suivante va au leader.
    """
    attacker = _attacker(damage=3)
    bg = DefendingModel(toughness=4, save=6, wounds=1)
    support_m = DefendingModel(toughness=4, save=6, wounds=3)
    leader_m = DefendingModel(toughness=4, save=6, wounds=4)
    defender = DefendingUnit(model=bg, model_count=0,
                             support_model=support_m, leader_model=leader_m)

    events = [
        _resolved_event(attacker, defender, damage=3),  # tue le support
        _resolved_event(attacker, defender, damage=2),  # 2 dégâts au leader
    ]
    stats = AllocationPhase().resolve(events)

    assert stats.support_killed is True
    assert defender.support_alive is False
    assert defender.current_leader_wounds == 2  # 4 - 2
    assert stats.leader_killed is False


def test_full_unit_sequence_bodyguard_support_leader():
    """
    Scénario complet : 1 garde (2 PV) + support (3 PV) + leader (4 PV).
    4 attaques de 3 dégâts chacune (12 dégâts totaux, pas de spillover).
    - Att 1 : garde mort (2 PV utilisés, 1 perdu → spillover)
    - Att 2 : support prend 3 dégâts → mort
    - Att 3 : leader prend 3 dégâts → 1 PV restant
    - Att 4 : leader prend 1 dégât (1 PV) → mort
    """
    attacker = _attacker(damage=3)
    bg = DefendingModel(toughness=4, save=6, wounds=2)
    support_m = DefendingModel(toughness=4, save=6, wounds=3)
    leader_m = DefendingModel(toughness=4, save=6, wounds=4)
    defender = DefendingUnit(model=bg, model_count=1,
                             support_model=support_m, leader_model=leader_m)

    events = [_resolved_event(attacker, defender, damage=3) for _ in range(4)]
    stats = AllocationPhase().resolve(events)

    assert stats.models_killed == 1      # 1 garde
    assert stats.support_killed is True
    assert stats.leader_killed is True
    assert defender.model_count == 0
    assert defender.support_alive is False
    assert defender.leader_alive is False
    # Att 1 : 3 dmg sur 2 PV garde → 1 spillover
    # Att 4 : 3 dmg sur 1 PV leader restant → 2 spillover
    assert stats.spillover_damage == 3
    assert stats.damage_allocated == 9   # 2 + 3 + 3 + 1


def test_support_protected_by_better_save(monkeypatch):
    """
    Garde SV6+, Support SV2+. AP0.
    Roll 4 échoue SV6+ → garde meurt.
    Roll 5 échoue SV6+ → support re-éval SV2+ → 5>=2 PASSE → support intact.
    """
    rolls = iter([4, 5])
    monkeypatch.setattr("random.randint", lambda a, b: next(rolls))

    attacker = _attacker(ap=0, damage=1)
    bg = DefendingModel(toughness=4, save=6, wounds=1)
    support_m = DefendingModel(toughness=4, save=2, wounds=3)
    defender = DefendingUnit(model=bg, model_count=1, support_model=support_m)

    wound_events = [AttackEvent(attacker, defender) for _ in range(2)]
    for e in wound_events:
        e.state = AttackState.WOUND_SUCCESS

    save_events = SavePhase().resolve(wound_events)
    dmg_events = DamagePhase().resolve(save_events)
    stats = AllocationPhase().resolve(dmg_events)

    assert stats.models_killed == 1
    assert stats.support_killed is False
    assert defender.current_support_wounds == 3  # support intact


def test_no_spillover_between_support_and_leader():
    """
    Support (2 PV) prend 5 dégâts : 2 appliqués, 3 perdus (pas de spillover vers leader).
    """
    attacker = _attacker(damage=5)
    bg = DefendingModel(toughness=4, save=6, wounds=1)
    support_m = DefendingModel(toughness=4, save=6, wounds=2)
    leader_m = DefendingModel(toughness=4, save=6, wounds=4)
    defender = DefendingUnit(model=bg, model_count=0,
                             support_model=support_m, leader_model=leader_m)

    events = [_resolved_event(attacker, defender, damage=5)]
    stats = AllocationPhase().resolve(events)

    assert stats.support_killed is True
    assert stats.spillover_damage == 3
    assert defender.leader_alive is True
    assert defender.current_leader_wounds == 4  # leader intact
