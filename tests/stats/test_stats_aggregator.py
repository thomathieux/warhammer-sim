# -*- coding: utf-8 -*-
"""
Tests pour StatsAggregator.

Vérifie que l'agrégation de runs identiques produit les bonnes moyennes
et que les champs spécifiques (FNP ignorés, leader kill rate) sont corrects.
"""

from stats.aggregator import StatsAggregator
from stats.run_result import AttackRunResult
from stats.phase_stats import (
    HitPhaseStats,
    WoundPhaseStats,
    SavePhaseStats,
    DamagePhaseStats,
    AllocationPhaseStats,
)


# ---------------------------------------------------------------------------
# Helper — construit un AttackRunResult avec des valeurs fixes
# ---------------------------------------------------------------------------

def _result(
    hits=3, wounds=2, saves_failed=1, raw_damage=2, reduced_damage=2,
    models_killed=1, wounds_remaining=0,
    fnp_ignored=0, leader_killed=False, support_killed=False,
):
    return AttackRunResult(
        hit=HitPhaseStats(
            phase="HitPhase", events_in=4, events_out=hits,
            hits=hits,
        ),
        wound=WoundPhaseStats(
            phase="WoundPhase", events_in=hits, events_out=wounds,
            wounds=wounds,
        ),
        save=SavePhaseStats(
            phase="SavePhase", events_in=wounds, events_out=saves_failed,
            saves_attempted=wounds, saves_failed=saves_failed,
        ),
        damage=DamagePhaseStats(
            damage_events=saves_failed, raw_damage=raw_damage, reduced_damage=reduced_damage,
        ),
        allocation=AllocationPhaseStats(
            damage_allocated=reduced_damage, models_killed=models_killed,
            wounds_remaining=wounds_remaining, fnp_ignored_damage=fnp_ignored,
            leader_killed=leader_killed, support_killed=support_killed,
        ),
        models_killed=models_killed,
        wounds_remaining=wounds_remaining,
        leader_killed=leader_killed,
        support_killed=support_killed,
    )


# ---------------------------------------------------------------------------
# Test 5.1 — Moyennes de base sur des runs identiques
# ---------------------------------------------------------------------------

def test_aggregator_basic_means():
    """
    Objectif : sur N runs identiques, hits_mean, wounds_mean et
    models_killed_mean doivent valoir exactement les valeurs de chaque run.
    """
    results = [_result(hits=4, wounds=3, models_killed=2) for _ in range(10)]
    agg = StatsAggregator(results).aggregate()

    assert agg["hit"]["hits_mean"]              == 4.0
    assert agg["wound"]["wounds_mean"]          == 3.0
    assert agg["allocation"]["models_killed_mean"] == 2.0
    assert agg["allocation"]["models_killed_std"]  == 0.0  # variance nulle (tous identiques)


# ---------------------------------------------------------------------------
# Test 5.2 — fnp_ignored_damage_mean correctement agrégé
# ---------------------------------------------------------------------------

def test_aggregator_fnp_ignored_mean():
    """
    Objectif : fnp_ignored_damage_mean correspond à la moyenne des valeurs
    fnp_ignored_damage sur tous les runs.
    """
    results = [
        _result(fnp_ignored=2),
        _result(fnp_ignored=4),
        _result(fnp_ignored=0),
    ]
    agg = StatsAggregator(results).aggregate()

    assert agg["allocation"]["fnp_ignored_damage_mean"] == 2.0  # (2+4+0)/3


# ---------------------------------------------------------------------------
# Test 5.3 — leader_kill_rate = fraction des runs où leader_killed=True
# ---------------------------------------------------------------------------

def test_aggregator_leader_kill_rate():
    """
    Objectif : leader_kill_rate doit être la proportion de runs où
    le leader est mort (0.5 si killed dans la moitié des runs, 1.0 si tous).
    """
    results = [
        _result(leader_killed=True),
        _result(leader_killed=True),
        _result(leader_killed=False),
        _result(leader_killed=False),
    ]
    agg = StatsAggregator(results).aggregate()

    assert agg["allocation"]["leader_kill_rate"] == 0.5

    # 100 % : killed dans tous les runs
    all_dead = [_result(leader_killed=True) for _ in range(5)]
    assert StatsAggregator(all_dead).aggregate()["allocation"]["leader_kill_rate"] == 1.0
