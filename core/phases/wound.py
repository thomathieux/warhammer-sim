# -*- coding: utf-8 -*-
"""
Created on Fri Jan 23 22:03:05 2026

@author: thoma
"""

import random
from typing import List

from core.enums import AttackState, RerollType
from core.events import AttackEvent
from core.phases.base import Phase


def wound_threshold(strength: int, toughness: int) -> int:
    if strength >= 2 * toughness:
        return 2
    if strength > toughness:
        return 3
    if strength == toughness:
        return 4
    if strength * 2 <= toughness:
        return 6
    return 5


def apply_reroll(roll: int, success_on: int, reroll_type: RerollType) -> int:
    if reroll_type == RerollType.NONE:
        return roll

    if reroll_type == RerollType.ONE and roll == 1:
        return random.randint(1, 6)

    if reroll_type == RerollType.FAILED and roll < success_on:
        return random.randint(1, 6)

    return roll


def _check_critical_wound(event, attacker, defender, raw_roll: int) -> None:
    """
    Détermine si le jet de blessure est une blessure critique.

    Sources de critique :
    - Jet >= wound_critical_on de l'arme (par défaut 6)
    - Anti-X N+ : critique sur N+ si la cible possède le mot-clé X
    """
    is_critical = raw_roll >= attacker.wound_critical_on

    if (
        not is_critical
        and attacker.anti_keyword is not None
        and attacker.anti_threshold is not None
        and raw_roll >= attacker.anti_threshold
        and defender is not None
        and attacker.anti_keyword.upper() in defender.keywords
    ):
        is_critical = True

    if is_critical:
        event.wound_critical = True
        if attacker.devastating_wounds:
            event.mortal_wound = True


class WoundPhase(Phase):
    def resolve(self, events: List[AttackEvent]) -> List[AttackEvent]:
        resolved: List[AttackEvent] = []

        for event in events:
            attacker = event.attacker
            defender = event.defender
            model = attacker.model

            # --------------------------------------------------
            # 0. Auto-wound (Lethal Hits)
            # --------------------------------------------------
            if event.auto_wound:
                event.state = AttackState.WOUND_SUCCESS
                resolved.append(event)
                continue

            # --------------------------------------------------
            # 1. Seuil de blessure de base
            # --------------------------------------------------
            base_threshold = wound_threshold(
                strength=model.strength,
                toughness=defender.model.toughness,
            )

            # --------------------------------------------------
            # 2. Modificateur anticipé (capacité défensive)
            #    -1 wound si :
            #      - la capacité est active
            #      - F > E
            # --------------------------------------------------
            modifier = 0
            if (
                defender.wound_minus_one_if_weaker
                and model.strength > defender.model.toughness
            ):
                modifier = -1

            # Application du modificateur au seuil (cap 2+ / 6+)
            modified_threshold = min(
                6,
                max(2, base_threshold - modifier),
            )

            # --------------------------------------------------
            # 3. Jet brut
            # --------------------------------------------------
            raw_roll = random.randint(1, 6)

            # --------------------------------------------------
            # 4. Décision de relance (Twin-linked ou aura)
            #    - pas de relance sur auto-wound
            #    - pas de cumul
            # --------------------------------------------------
            can_reroll = False
            
            if not event.auto_wound:
                if attacker.twin_linked:
                    can_reroll = True
                elif attacker.wound_reroll != RerollType.NONE:
                    can_reroll = True
            
            if can_reroll and raw_roll < modified_threshold:
                raw_roll = random.randint(1, 6)

            # --------------------------------------------------
            # 5. Auto-fail / auto-success (jet NON MODIFIÉ)
            # --------------------------------------------------
            if raw_roll == 1:
                event.wound_roll = 1
                continue

            if raw_roll == 6:
                event.wound_roll = 6
                event.state = AttackState.WOUND_SUCCESS
                _check_critical_wound(event, attacker, defender, raw_roll)
                resolved.append(event)
                continue

            # --------------------------------------------------
            # 6. Résolution normale
            # --------------------------------------------------
            event.wound_roll = raw_roll

            if raw_roll < modified_threshold:
                continue

            event.state = AttackState.WOUND_SUCCESS
            _check_critical_wound(event, attacker, defender, raw_roll)
            resolved.append(event)

        return resolved

