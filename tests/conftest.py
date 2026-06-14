# -*- coding: utf-8 -*-
"""
Created on Fri Jan 23 22:24:41 2026

@author: thoma
"""
import sys
from pathlib import Path

# Ajoute la racine du projet au PYTHONPATH
PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

import pytest
from core.dice import FixedValue
from units.profiles import AttackingModel
from units.attacking import WeaponGroup
from core.enums import RerollType




@pytest.fixture
def basic_attacking_unit():
    model = AttackingModel(
        attacks=FixedValue(1),
        attack_skill=3,
        strength=4,
    )
    return WeaponGroup(
        model=model,
        model_count=1,
        hit_critical_on=6,
        wound_critical_on=6,
        lethal_hits=False,
        sustained_hits=0,
        hit_reroll=RerollType.NONE,
    )
