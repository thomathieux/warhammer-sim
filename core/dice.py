# -*- coding: utf-8 -*-
"""
Created on Fri Jan 23 22:01:32 2026

@author: thoma
"""

import random


class DiceExpression:
    def roll(self) -> int:
        raise NotImplementedError


class FixedValue(DiceExpression):
    def __init__(self, value: int):
        self.value = value

    def roll(self) -> int:
        return self.value


class Dice(DiceExpression):
    def __init__(self, dice: int, faces: int, bonus: int = 0):
        self.dice = dice
        self.faces = faces
        self.bonus = bonus

    def roll(self) -> int:
        return sum(random.randint(1, self.faces) for _ in range(self.dice)) + self.bonus
