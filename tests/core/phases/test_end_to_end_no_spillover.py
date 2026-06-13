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
    from units.attacking import AttackingUnit
    from core.enums import RerollType

    attacking_model = AttackingModel(
        attacks=FixedValue(1),
        attack_skill=2,
        strength=10,
        ap=-5,
        damage=FixedValue(5),
    )

    attacker = AttackingUnit(
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
