# -*- coding: utf-8 -*-
"""
Created on Fri Jan 23 22:02:53 2026

@author: thoma
"""

import random
from typing import List

from core.enums import AttackState, RerollType
from core.events import AttackEvent
from core.phases.base import Phase
from core.rules.hit_rules import LethalHitsRule, SustainedHitsRule




def apply_reroll(roll: int, success_on: int, reroll_type: RerollType) -> int:
    if reroll_type == RerollType.NONE:
        return roll

    if reroll_type == RerollType.ONE and roll == 1:
        return random.randint(1, 6)

    if reroll_type == RerollType.FAILED and roll < success_on:
        return random.randint(1, 6)

    return roll


class HitPhase(Phase):
    def __init__(self):
        self.rules = [
            LethalHitsRule(),
            SustainedHitsRule(),
        ]

    def resolve(self, events: List[AttackEvent]) -> List[AttackEvent]:
        resolved: List[AttackEvent] = []

        for event in events:
            attacker = event.attacker
            defender = event.defender
            model = attacker.model

            # --------------------------------------------------
            # 0. Torrent — auto-touche, pas de jet
            # Pas de hit_critical : Lethal/Sustained Hits ne s'activent pas.
            # --------------------------------------------------
            if attacker.torrent:
                event.state = AttackState.HIT_SUCCESS
                hit_events = [event]
                ctx = {"attacker": attacker, "defender": defender}
                for rule in self.rules:
                    hit_events = rule.apply(hit_events, ctx)
                resolved.extend(hit_events)
                continue

            # --------------------------------------------------
            # 1. Jet brut initial
            # --------------------------------------------------
            raw_roll = random.randint(1, 6)

            # --------------------------------------------------
            # 2. Calcul du modificateur connu (anticipé)
            # --------------------------------------------------
            modifier = 0
            if defender:
                modifier = defender.hit_modifier

            # Cap V10 ±1
            modifier = max(-1, min(1, modifier))

            # --------------------------------------------------
            # 3. Décision de relance (logique joueur rationnel)
            #    → on relance uniquement si le résultat FINAL
            #      serait un échec
            # --------------------------------------------------
            if attacker.hit_reroll != RerollType.NONE:
                projected_final = raw_roll + modifier
                if projected_final < model.attack_skill:
                    raw_roll = random.randint(1, 6)

            # --------------------------------------------------
            # 4. Auto-fail / auto-success (jet NON MODIFIÉ)
            # --------------------------------------------------
            if raw_roll == 1:
                event.hit_roll = 1
                continue

            if raw_roll == 6:
                event.hit_roll = 6
                event.state = AttackState.HIT_SUCCESS

                # Touche critique (jet non modifié)
                if raw_roll >= attacker.hit_critical_on:
                    event.hit_critical = True

                hit_events = [event]
            else:
                # --------------------------------------------------
                # 5. Application finale des modificateurs
                # --------------------------------------------------
                final_roll = raw_roll + modifier
                event.hit_roll = final_roll

                if final_roll < model.attack_skill:
                    continue

                event.state = AttackState.HIT_SUCCESS

                # Touche critique (jet non modifié)
                if raw_roll >= attacker.hit_critical_on:
                    event.hit_critical = True

                hit_events = [event]

            # --------------------------------------------------
            # 6. Application des règles de touche (Lethal, Sustained…)
            # --------------------------------------------------
            context = {
                "attacker": attacker,
                "defender": defender,
            }

            for rule in self.rules:
                hit_events = rule.apply(hit_events, context)

            resolved.extend(hit_events)

        return resolved

