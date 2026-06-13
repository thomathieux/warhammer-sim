# -*- coding: utf-8 -*-
"""
Created on Sat Jan 24 11:19:15 2026

@author: thoma
"""

from dataclasses import dataclass


# --------------------------------------------------
# Base générique (optionnelle, mais utile)
# --------------------------------------------------

@dataclass
class PhaseStats:
    """
    Statistiques génériques pour une phase basée sur des événements.
    """
    phase: str
    events_in: int
    events_out: int


# --------------------------------------------------
# Hit Phase
# --------------------------------------------------

@dataclass
class HitPhaseStats(PhaseStats):
    hits: int = 0
    critical_hits: int = 0
    sustained_hits_generated: int = 0
    auto_wounds_generated: int = 0


# --------------------------------------------------
# Wound Phase
# --------------------------------------------------

@dataclass
class WoundPhaseStats(PhaseStats):
    wounds: int = 0
    critical_wounds: int = 0
    mortal_wounds: int = 0


# --------------------------------------------------
# Save Phase
# --------------------------------------------------

@dataclass
class SavePhaseStats(PhaseStats):
    saves_attempted: int = 0
    saves_failed: int = 0
    invulnerable_used: int = 0


# --------------------------------------------------
# Damage Phase
# --------------------------------------------------

@dataclass
class DamagePhaseStats:
    """
    Statistiques liées aux dégâts calculés par attaque.
    """
    damage_events: int = 0
    raw_damage: int = 0
    reduced_damage: int = 0


# --------------------------------------------------
# Allocation Phase
# --------------------------------------------------

@dataclass
class AllocationPhaseStats:
    """
    Statistiques liées à l'allocation des dégâts aux modèles.
    """
    damage_allocated: int = 0
    spillover_damage: int = 0
    models_killed: int = 0
    wounds_remaining: int = 0
    fnp_ignored_damage: int = 0
    support_killed: bool = False
    leader_killed: bool = False
