# -*- coding: utf-8 -*-
"""
Created on Sat Jan 24 10:58:27 2026

@author: thoma
"""

from core.events import AttackEvent
from core.context import CombatContext
from core.phases.hit import HitPhase
from core.phases.wound import WoundPhase
from core.phases.save import SavePhase
from core.phases.damage import DamagePhase
from core.phases.allocation import AllocationPhase

from stats.phase_stats import (
    HitPhaseStats,
    WoundPhaseStats,
    SavePhaseStats,
    DamagePhaseStats,
)
from stats.run_result import AttackRunResult


class AttackSequence:
    """
    Orchestration complète d'une attaque :
    Une unité A attaque une unité B une fois.

    Cette classe :
    - ne contient aucune règle
    - n'interprète pas les résultats
    - observe et structure les données d'un run
    """

    def __init__(self):
        self.hit_phase = HitPhase()
        self.wound_phase = WoundPhase()
        self.save_phase = SavePhase()
        self.damage_phase = DamagePhase()
        self.allocation_phase = AllocationPhase()

    def resolve(self, attacker, defender, context: CombatContext = None) -> AttackRunResult:
        # --------------------------------------------------
        # Initialisation des événements (1 attaque = 1 event)
        # --------------------------------------------------
        events = [
            AttackEvent(attacker, defender)
            for _ in range(attacker.total_attacks(context, defender.total_model_count))
        ]

        # ================= HIT PHASE =================
        hit_in = len(events)
        events = self.hit_phase.resolve(events)
        hit_out = len(events)

        hit_stats = HitPhaseStats(
            phase="HitPhase",
            events_in=hit_in,
            events_out=hit_out,
            hits=hit_out,
            critical_hits=sum(e.hit_critical for e in events),
            sustained_hits_generated=max(0, hit_out - hit_in),
            auto_wounds_generated=sum(e.auto_wound for e in events),
        )

        # ================= WOUND PHASE =================
        wound_in = len(events)
        events = self.wound_phase.resolve(events)
        wound_out = len(events)

        wound_stats = WoundPhaseStats(
            phase="WoundPhase",
            events_in=wound_in,
            events_out=wound_out,
            wounds=wound_out,
            critical_wounds=sum(e.wound_critical for e in events),
            mortal_wounds=sum(e.mortal_wound for e in events),
        )

        # ================= SAVE PHASE =================
        save_in = len(events)
        events = self.save_phase.resolve(events, context)
        save_out = len(events)

        save_stats = SavePhaseStats(
            phase="SavePhase",
            events_in=save_in,
            events_out=save_out,
            saves_attempted=save_in,
            saves_failed=save_out,
            invulnerable_used=sum(e.invulnerable_used for e in events),
        )

        # ================= DAMAGE PHASE =================
        events = self.damage_phase.resolve(events, context)

        damage_stats = DamagePhaseStats()

        for event in events:
            damage_stats.damage_events += 1
            damage_stats.raw_damage += event.raw_damage or 0
            damage_stats.reduced_damage += event.final_damage or 0

        # ================= ALLOCATION PHASE =================
        allocation_stats = self.allocation_phase.resolve(events, context)

        # --------------------------------------------------
        # Résultat global du run
        # --------------------------------------------------
        return AttackRunResult(
            hit=hit_stats,
            wound=wound_stats,
            save=save_stats,
            damage=damage_stats,
            allocation=allocation_stats,
            models_killed=allocation_stats.models_killed,
            wounds_remaining=allocation_stats.wounds_remaining,
            support_killed=allocation_stats.support_killed,
            leader_killed=allocation_stats.leader_killed,
        )
