# -*- coding: utf-8 -*-
"""
Created on Sat Jan 24 11:41:07 2026

@author: thoma
"""

from typing import Dict


class TextReport:
    """
    Génère un rapport texte lisible à partir de statistiques agrégées.
    """

    def __init__(self, aggregated_stats: Dict[str, Dict[str, float]], runs: int):
        """
        aggregated_stats:
            {
                "hit": {...},
                "wound": {...},
                "save": {...},
                "damage": {...},
                "allocation": {...},
            }
        """
        self.stats = aggregated_stats
        self.runs = runs

    def render(self) -> str:
        lines = []

        lines.append("=" * 50)
        lines.append("ATTACK SIMULATION REPORT")
        lines.append("=" * 50)
        lines.append("")
        lines.append(f"Simulations run : {self.runs}")
        lines.append("")

        self._render_hit(lines)
        self._render_wound(lines)
        self._render_save(lines)
        self._render_damage(lines)
        self._render_allocation(lines)

        lines.append("=" * 50)

        return "\n".join(lines)

    # --------------------------------------------------
    # Sections
    # --------------------------------------------------

    def _render_hit(self, lines):
        s = self.stats["hit"]
        lines.append("--- HIT PHASE ---")
        lines.append(f"Hits                       : {s['hits_mean']:.2f} ± {s['hits_std']:.2f}")
        lines.append(f"Critical hits              : {s['critical_hits_mean']:.2f}")
        lines.append(f"Auto-wounds (Lethal)       : {s['auto_wounds_mean']:.2f}")
        lines.append(f"Sustained hits generated   : {s['sustained_hits_mean']:.2f}")
        lines.append("")

    def _render_wound(self, lines):
        s = self.stats["wound"]
        lines.append("--- WOUND PHASE ---")
        lines.append(f"Wounds                     : {s['wounds_mean']:.2f} ± {s['wounds_std']:.2f}")
        lines.append(f"Critical wounds            : {s['critical_wounds_mean']:.2f}")
        lines.append(f"Mortal wounds              : {s['mortal_wounds_mean']:.2f}")
        lines.append("")

    def _render_save(self, lines):
        s = self.stats["save"]
        lines.append("--- SAVE PHASE ---")
        lines.append(f"Saves attempted            : {s['saves_attempted_mean']:.2f}")
        lines.append(f"Saves failed               : {s['saves_failed_mean']:.2f}")
        lines.append("")

    def _render_damage(self, lines):
        s = self.stats["damage"]
        lines.append("--- DAMAGE PHASE ---")
        lines.append(f"Raw damage                 : {s['raw_damage_mean']:.2f}")
        lines.append(f"Damage after reduction     : {s['reduced_damage_mean']:.2f}")
        lines.append("")

    def _render_allocation(self, lines):
        s = self.stats["allocation"]
        lines.append("--- ALLOCATION PHASE ---")
        lines.append(f"Damage allocated           : {s['damage_allocated_mean']:.2f}")
        lines.append(f"FNP ignored damage         : {s['fnp_ignored_damage_mean']:.2f}")
        lines.append(f"Spillover damage (lost)    : {s['spillover_damage_mean']:.2f}")
        lines.append(
            f"Models killed              : {s['models_killed_mean']:.2f} ± {s['models_killed_std']:.2f}"
        )
        lines.append(f"Wounds remaining           : {s['wounds_remaining_mean']:.2f}")
        if s.get("support_kill_rate", 0) > 0:
            lines.append(f"Support kill rate          : {s['support_kill_rate'] * 100:.1f}%")
        if s.get("leader_kill_rate", 0) > 0:
            lines.append(f"Leader kill rate           : {s['leader_kill_rate'] * 100:.1f}%")
        lines.append("")
