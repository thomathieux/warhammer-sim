# -*- coding: utf-8 -*-
"""
Created on Sat Jan 24 11:21:51 2026

@author: thoma
"""

from dataclasses import dataclass

from stats.phase_stats import (
    HitPhaseStats,
    WoundPhaseStats,
    SavePhaseStats,
    DamagePhaseStats,
    AllocationPhaseStats,
)


@dataclass
class AttackRunResult:
    """
    Résultat d'une seule simulation complète :
    Une unité A attaque une unité B une fois.
    """

    # Phases principales
    hit: HitPhaseStats
    wound: WoundPhaseStats
    save: SavePhaseStats
    damage: DamagePhaseStats
    allocation: AllocationPhaseStats

    # Résumé global (facilite l'analyse)
    models_killed: int
    wounds_remaining: int
    support_killed: bool = False
    leader_killed: bool = False