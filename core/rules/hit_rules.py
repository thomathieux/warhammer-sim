# -*- coding: utf-8 -*-
"""
Created on Fri Jan 23 22:06:07 2026

@author: thoma
"""

from typing import List
from core.events import AttackEvent
from core.enums import AttackState
from core.rules.base import HitRule


class LethalHitsRule(HitRule):
    def apply(self, events: List[AttackEvent], context: dict) -> List[AttackEvent]:
        if not events:
            return events  

        attacker = context["attacker"]
        result = []

        for event in events:
            if event.hit_critical and attacker.lethal_hits:
                event.auto_wound = True
                event.state = AttackState.WOUND_SUCCESS
            result.append(event)

        return result


class SustainedHitsRule(HitRule):
    def apply(self, events: List[AttackEvent], context: dict) -> List[AttackEvent]:
        if not events:
            return events  

        attacker = context["attacker"]
        result = []

        for event in events:
            result.append(event)

            if event.hit_critical and attacker.sustained_hits > 0:
                for _ in range(attacker.sustained_hits):
                    sustained = AttackEvent(
                        attacker=event.attacker,
                        defender=event.defender,
                    )
                    sustained.state = AttackState.HIT_SUCCESS
                    result.append(sustained)

        return result
