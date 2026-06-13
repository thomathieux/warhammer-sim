# -*- coding: utf-8 -*-
"""
Created on Sat Jan 24 11:43:50 2026

@author: thoma
"""

import statistics
from typing import List, Dict

from stats.run_result import AttackRunResult


class StatsAggregator:
    """
    Agrège une liste de AttackRunResult en statistiques exploitables
    (moyennes, écarts-types).
    """

    def __init__(self, results: List[AttackRunResult]):
        if not results:
            raise ValueError("StatsAggregator requires at least one result")

        self.results = results
        self.count = len(results)

    # --------------------------------------------------
    # Helpers
    # --------------------------------------------------

    def _mean(self, values: List[float]) -> float:
        return statistics.mean(values)

    def _std(self, values: List[float]) -> float:
        # écart-type population (plus stable pour Monte Carlo)
        return statistics.pstdev(values)

    # --------------------------------------------------
    # Agrégation principale
    # --------------------------------------------------

    def aggregate(self) -> Dict[str, Dict[str, float]]:
        return {
            "hit": self._aggregate_hit(),
            "wound": self._aggregate_wound(),
            "save": self._aggregate_save(),
            "damage": self._aggregate_damage(),
            "allocation": self._aggregate_allocation(),
        }

    # --------------------------------------------------
    # Phases
    # --------------------------------------------------

    def _aggregate_hit(self) -> Dict[str, float]:
        hits = [r.hit.hits for r in self.results]
        crits = [r.hit.critical_hits for r in self.results]
        autos = [r.hit.auto_wounds_generated for r in self.results]
        sustained = [r.hit.sustained_hits_generated for r in self.results]

        return {
            "hits_mean": self._mean(hits),
            "hits_std": self._std(hits),
            "critical_hits_mean": self._mean(crits),
            "auto_wounds_mean": self._mean(autos),
            "sustained_hits_mean": self._mean(sustained),
        }

    def _aggregate_wound(self) -> Dict[str, float]:
        wounds = [r.wound.wounds for r in self.results]
        crits = [r.wound.critical_wounds for r in self.results]
        mortals = [r.wound.mortal_wounds for r in self.results]

        return {
            "wounds_mean": self._mean(wounds),
            "wounds_std": self._std(wounds),
            "critical_wounds_mean": self._mean(crits),
            "mortal_wounds_mean": self._mean(mortals),
        }

    def _aggregate_save(self) -> Dict[str, float]:
        attempted = [r.save.saves_attempted for r in self.results]
        failed = [r.save.saves_failed for r in self.results]

        return {
            "saves_attempted_mean": self._mean(attempted),
            "saves_failed_mean": self._mean(failed),
        }

    def _aggregate_damage(self) -> Dict[str, float]:
        raw = [r.damage.raw_damage for r in self.results]
        reduced = [r.damage.reduced_damage for r in self.results]

        return {
            "raw_damage_mean": self._mean(raw),
            "reduced_damage_mean": self._mean(reduced),
        }

    def _aggregate_allocation(self) -> Dict[str, float]:
        allocated = [r.allocation.damage_allocated for r in self.results]
        spill = [r.allocation.spillover_damage for r in self.results]
        killed = [r.allocation.models_killed for r in self.results]
        remaining = [r.allocation.wounds_remaining for r in self.results]
        fnp_ignored = [r.allocation.fnp_ignored_damage for r in self.results]
        support_kills = [1 if r.allocation.support_killed else 0 for r in self.results]
        leader_kills = [1 if r.allocation.leader_killed else 0 for r in self.results]

        return {
            "damage_allocated_mean": self._mean(allocated),
            "spillover_damage_mean": self._mean(spill),
            "models_killed_mean": self._mean(killed),
            "models_killed_std": self._std(killed),
            "wounds_remaining_mean": self._mean(remaining),
            "fnp_ignored_damage_mean": self._mean(fnp_ignored),
            "support_kill_rate": self._mean(support_kills),
            "leader_kill_rate": self._mean(leader_kills),
        }
