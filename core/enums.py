# -*- coding: utf-8 -*-
"""
Created on Fri Jan 23 22:01:20 2026

@author: thoma
"""

from enum import Enum


class RerollType(Enum):
    NONE = "none"
    ONE = "one"
    FAILED = "failed"


class AttackState(Enum):
    PENDING_HIT = "pending_hit"
    HIT_SUCCESS = "hit_success"
    WOUND_SUCCESS = "wound_success"
    SAVE_FAILED = "save_failed"
    RESOLVED = "resolved"