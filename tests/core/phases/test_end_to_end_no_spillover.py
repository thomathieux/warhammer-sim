# -*- coding: utf-8 -*-
"""
Created on Fri Jan 23 23:52:39 2026

@author: thoma
"""

def test_end_to_end_no_spillover(monkeypatch):
    """
    Test end-to-end :
    - pipeline complet
    - dégâts supérieurs aux PV
    - aucun spillover autorisé
    """

    # -------------------------------------------------
    # Forcer les dés (tout réussit)
    # -------------------------------------------------
    def fake_randint(a, b):
        return 6

    monkeypatch.setattr("random.randint", fake_randint)

    # -------------------------------------------------
    # Attaquant
    # -------------------------------------------------
    from core.dice import FixedValue
    from units.profiles import AttackingModel
    from units.attacking import WeaponGroup
    from core.enums import RerollType

    attacking_model = AttackingModel(
        attacks=FixedValue(1),
        attack_skill=2,
        strength=10,
        ap=-5,
        damage=FixedValue(5),
    )

    attacker = WeaponGroup(
        model=attacking_model,
        model_count=1,
        hit_critical_on=6,
        wound_critical_on=6,
        lethal_hits=False,
        sustained_hits=0,
        devastating_wounds=False,
        hit_reroll=RerollType.NONE,
        wound_reroll=RerollType.NONE,
    )

    # -------------------------------------------------
    # Défenseur
    # -------------------------------------------------
    from units.profiles import DefendingModel
    from units.defending import DefendingUnit

    defending_model = DefendingModel(
        toughness=4,
        save=7,   # impossible à réussir
        wounds=2,
    )

    defender = DefendingUnit(
        model=defending_model,
        model_count=2,
    )

    # -------------------------------------------------
    # Création de l’attaque
    # -------------------------------------------------
    from core.events import AttackEvent

    events = [
        AttackEvent(attacker, defender)
    ]

    # -------------------------------------------------
    # Pipeline complet
    # -------------------------------------------------
    from core.phases.hit import HitPhase
    from core.phases.wound import WoundPhase
    from core.phases.save import SavePhase
    from core.phases.damage import DamagePhase
    from core.phases.allocation import AllocationPhase

    phases = [
        HitPhase(),
        WoundPhase(),
        SavePhase(),
        DamagePhase(),
        AllocationPhase(),
    ]

    for phase in phases:
        events = phase.resolve(events)

    # -------------------------------------------------
    # Assertions finales (CRUCIALES)
    # -------------------------------------------------
    assert defender.model_count == 1          # un seul modèle mort
    assert defender.current_model_wounds == 2 # le second est intact


# ---------------------------------------------------------------------------
# Test 4.1 — AttackSequence.resolve() : structure du résultat
# ---------------------------------------------------------------------------

def test_attack_sequence_result_structure():
    """
    Objectif : AttackSequence.resolve() retourne un AttackRunResult complet
    avec des valeurs cohérentes inter-phases (hits ≥ wounds ≥ saves_failed).
    """
    from core.simulation.attack_sequence import AttackSequence
    from core.context import CombatContext
    from core.dice import FixedValue
    from units.profiles import AttackingModel, DefendingModel
    from units.attacking import WeaponGroup
    from units.defending import DefendingUnit

    attacker = WeaponGroup(
        model=AttackingModel(attacks=FixedValue(4), attack_skill=3, strength=4, ap=0, damage=FixedValue(1)),
        model_count=1,
    )
    defender = DefendingUnit(
        model=DefendingModel(toughness=4, save=4, wounds=1),
        model_count=5,
    )
    ctx = CombatContext()

    result = AttackSequence().resolve(attacker, defender, ctx)

    assert result.hit.hits >= 0
    assert result.wound.wounds >= 0
    assert result.save.saves_failed >= 0
    assert result.hit.hits >= result.wound.wounds          # les blessures ≤ touches
    assert result.wound.wounds >= result.save.saves_failed # les saves ≤ blessures
    assert result.allocation.models_killed >= 0
    assert result.allocation.models_killed <= 5


# ---------------------------------------------------------------------------
# Test 4.2 — Deux WeaponGroup successifs accumulent les dégâts
# ---------------------------------------------------------------------------

def test_two_weapon_groups_accumulate_damage(monkeypatch):
    """
    Objectif : simuler deux WeaponGroup sur le même défenseur (sans reset)
    produit plus de pertes que l'un seul. Reproduit le comportement réel
    de l'app (une résolution par groupe d'armes sur le même défenseur).
    """
    monkeypatch.setattr("random.randint", lambda a, b: 6)  # tout réussit

    from core.simulation.attack_sequence import AttackSequence
    from core.context import CombatContext
    from core.dice import FixedValue
    from units.profiles import AttackingModel, DefendingModel
    from units.attacking import WeaponGroup
    from units.defending import DefendingUnit

    def _weapon_group():
        return WeaponGroup(
            model=AttackingModel(attacks=FixedValue(2), attack_skill=3, strength=5, ap=-1, damage=FixedValue(1)),
            model_count=1,
        )

    defender = DefendingUnit(
        model=DefendingModel(toughness=4, save=7, wounds=1),  # save impossible → toujours échoué
        model_count=5,
    )
    ctx = CombatContext()
    seq = AttackSequence()

    result1 = seq.resolve(_weapon_group(), defender, ctx)
    killed_after_group1 = result1.allocation.models_killed

    result2 = seq.resolve(_weapon_group(), defender, ctx)
    killed_after_group2 = result2.allocation.models_killed

    # Les deux groupes tuent chacun au moins 1 figurine (dés forcés à 6)
    assert killed_after_group1 >= 1
    assert killed_after_group2 >= 1
    # Le total de pertes dépasse ce qu'un seul groupe peut infliger seul
    assert killed_after_group1 + killed_after_group2 > killed_after_group1
