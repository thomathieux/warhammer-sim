# -*- coding: utf-8 -*-
"""
Created on Sat Jan 24 15:04:38 2026

@author: thoma
"""

from typing import Optional
from core.dice import DiceExpression, FixedValue


class AttackingModel:
    def __init__(
        self,
        attacks: DiceExpression,
        attack_skill: int,
        strength: int,
        ap: int = 0,
        damage: DiceExpression = FixedValue(1),
    ):
        self.attacks = attacks
        self.attack_skill = attack_skill
        self.strength = strength
        self.ap = ap
        self.damage = damage


class DefendingModel:
    def __init__(
        self,
        toughness: int,
        save: int,
        wounds: int,
        invulnerable_save: Optional[int] = None,
        fnp: Optional[int] = None,
    ):
        self.toughness = toughness
        self.save = save
        self.invulnerable_save = invulnerable_save
        self.wounds = wounds
        self.fnp = fnp
