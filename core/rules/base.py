# -*- coding: utf-8 -*-
"""
Created on Fri Jan 23 22:05:53 2026

@author: thoma
"""

from typing import List
from core.events import AttackEvent


class Rule:
    def apply(self, events: List[AttackEvent], context: dict) -> List[AttackEvent]:
        return events


class HitRule(Rule):
    pass
