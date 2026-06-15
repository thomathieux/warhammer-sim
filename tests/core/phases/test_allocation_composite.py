# -*- coding: utf-8 -*-
"""
Tests d'allocation pour unités composites (multi core_groups intra-card).

Ex : Boyz = [BOY × 5 (2 PV), BOSS NOB × 1 (4 PV)] sur la même fiche.
L'AllocationPhase doit consommer les groupes dans l'ordre (core_groups[0] → [1])
et ne passer au suivant que lorsque le précédent est totalement épuisé.
"""

from core.phases.allocation import AllocationPhase
from core.events import AttackEvent
from core.enums import AttackState
from units.attacking import WeaponGroup
from units.defending import DefendingUnit
from units.unit import ModelGroup, ModelProfile
from units.profiles import AttackingModel
from core.dice import FixedValue


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _composite_defender():
    """BOY × 5 (E4, Sv5+, 2 PV) + BOSS NOB × 1 (E5, Sv4+, 4 PV)."""
    boy  = ModelProfile(name="Boy",      toughness=4, save=5, wounds=2)
    boss = ModelProfile(name="Boss Nob", toughness=5, save=4, wounds=4)
    return DefendingUnit(core_groups=[
        ModelGroup(boy,  "Boy",      5, 5),
        ModelGroup(boss, "Boss Nob", 1, 1),
    ])


def _attacker():
    model = AttackingModel(attacks=FixedValue(1), attack_skill=3, strength=4)
    return WeaponGroup(model=model, model_count=1)


def _event(defender, damage):
    """Crée un AttackEvent pré-résolu avec le dégât indiqué."""
    atk = _attacker()
    ev = AttackEvent(atk, defender)
    ev.state  = AttackState.RESOLVED
    ev.damage = damage
    return ev


# ---------------------------------------------------------------------------
# Test 1.1 — Le 1er groupe absorbe les dégâts pendant qu'il est vivant
# ---------------------------------------------------------------------------

def test_first_group_absorbs_damage_while_alive():
    """
    Objectif : les dégâts vont au BOY (core_groups[0]) tant qu'il reste
    des BOY — le BOSS NOB (core_groups[1]) doit rester intouché.
    """
    defender = _composite_defender()
    phase    = AllocationPhase()

    # 1 attaque, 2 dégâts → tue exactement 1 BOY (2 PV)
    phase.resolve([_event(defender, 2)])

    assert defender.group_states[0].count == 4          # 1 BOY tué
    assert defender.group_states[0].current_wounds == 2 # prochain BOY à plein PV
    assert defender.group_states[1].count == 1          # BOSS NOB intact
    assert defender.group_states[1].current_wounds == 4 # BOSS NOB à plein PV


# ---------------------------------------------------------------------------
# Test 1.2 — Débordement vers le 2e groupe quand le 1er est épuisé
# ---------------------------------------------------------------------------

def test_overflow_to_second_group_when_first_depleted():
    """
    Objectif : une fois tous les BOY morts, les attaques suivantes
    atteignent le BOSS NOB — les dégâts ne sont pas perdus.
    """
    defender = _composite_defender()
    phase    = AllocationPhase()

    # Tuer les 5 BOY (2 PV chacun → 5 attaques de 2 dégâts)
    phase.resolve([_event(defender, 2) for _ in range(5)])
    assert defender.group_states[0].count == 0  # tous les BOY morts

    # 6e attaque : doit atteindre le BOSS NOB (4 PV → reste 3 PV)
    phase.resolve([_event(defender, 1)])

    assert defender.group_states[1].count == 1          # BOSS NOB vivant
    assert defender.group_states[1].current_wounds == 3 # a reçu 1 dégât


# ---------------------------------------------------------------------------
# Test 1.3 — total_model_count additionne tous les groupes vivants
# ---------------------------------------------------------------------------

def test_total_model_count_sums_all_groups():
    """
    Objectif : total_model_count = somme des counts vivants de tous les groupes
    (ici 5 BOY + 1 BOSS NOB = 6), et décroît correctement avec les pertes.
    """
    defender = _composite_defender()
    phase    = AllocationPhase()

    assert defender.total_model_count == 6  # état initial

    # Tuer 2 BOY
    phase.resolve([_event(defender, 2) for _ in range(2)])
    assert defender.total_model_count == 4  # 3 BOY + 1 BOSS NOB


# ---------------------------------------------------------------------------
# Test 1.4 — reset() restaure tous les group_states
# ---------------------------------------------------------------------------

def test_reset_restores_all_group_states():
    """
    Objectif : defender.reset() remet chaque group_state à son état initial
    (count et current_wounds), même si un modèle a été partiellement blessé.
    """
    defender = _composite_defender()
    phase    = AllocationPhase()

    # Blesser partiellement le 1er BOY et tuer 1 BOY
    phase.resolve([_event(defender, 1)])  # BOY perd 1 PV sur 2 → reste 1 PV
    phase.resolve([_event(defender, 2)])  # tue le BOY blessé, passe au suivant

    # État intermédiaire : 4 BOY restants, 1 BOSS NOB intact
    assert defender.group_states[0].count == 4

    defender.reset()

    assert defender.group_states[0].count          == 5  # 5 BOY restaurés
    assert defender.group_states[0].current_wounds == 2  # PV max restaurés
    assert defender.group_states[1].count          == 1  # BOSS NOB restauré
    assert defender.group_states[1].current_wounds == 4  # PV max restaurés
