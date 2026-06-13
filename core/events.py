# -*- coding: utf-8 -*-
"""
Created on Fri Jan 23 22:01:46 2026

@author: thoma
"""

from typing import Optional
from core.enums import AttackState


class AttackEvent:
    def __init__(self, attacker, defender):
        self.attacker = attacker
        self.defender = defender

        # état
        self.state = None

        # HIT
        self.hit_roll = None
        self.hit_critical = False
        self.auto_wound = False

        # WOUND
        self.wound_roll = None
        self.wound_critical = False
        self.mortal_wound = False

        # SAVE
        self.save_roll = None
        self.invulnerable_used = False   # 👈 AJOUT ICI

        # DAMAGE
        self.raw_damage = None
        self.final_damage = None
        self.damage = 0
