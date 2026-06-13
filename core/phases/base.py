# -*- coding: utf-8 -*-
"""
Created on Fri Jan 23 22:02:43 2026

@author: thoma
"""

from typing import List
from core.events import AttackEvent


class Phase:
    def resolve(self, events: List[AttackEvent]) -> List[AttackEvent]:
        raise NotImplementedError
