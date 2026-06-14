# -*- coding: utf-8 -*-
"""
Created on Fri Jan 23 22:01:32 2026

@author: thoma
"""

import re
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


def parse_dice(value: str) -> DiceExpression:
    """Convertit une chaîne Wahapedia en DiceExpression (ex: "D6+1" → Dice(1,6,1))."""
    v = value.strip().upper()
    if v.isdigit():
        return FixedValue(int(v))
    m = re.fullmatch(r"(\d*)D(\d+)(?:\+(\d+))?", v)
    if m:
        n     = int(m.group(1)) if m.group(1) else 1
        faces = int(m.group(2))
        bonus = int(m.group(3)) if m.group(3) else 0
        return Dice(n, faces, bonus)
    print(f"[WARN] parse_dice: valeur inconnue '{value}', remplacée par 1")
    return FixedValue(1)
