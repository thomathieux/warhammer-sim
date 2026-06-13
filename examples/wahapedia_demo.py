"""
Démonstration de la pipeline Wahapedia.

Powered by Wahapedia — https://wahapedia.ru
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from data.loader import find_unit
from data.unit_builder import build_attacking_unit, build_weapon_groups, build_defending_unit
from core.context import CombatContext
from core.simulation.attack_sequence import AttackSequence
from stats.aggregator import StatsAggregator
from stats.text_report import TextReport

N_RUNS = 2000


# ---------------------------------------------------------------------------
# Affichage
# ---------------------------------------------------------------------------

def show_unit_info(unit) -> None:
    m = unit.primary_model()
    if not m:
        return
    inv = f"/{m.invulnerable_save}+" if m.invulnerable_save else ""
    print(f"  Stats    : M{m.movement}  T{m.toughness}  SV{m.save}+{inv}  W{m.wounds}  LD{m.leadership}+  OC{m.oc}")
    print(f"  Taille   : {unit.min_models}–{unit.max_models} figurines")
    print(f"  Armes    :")
    for w in unit.weapons:
        rng = f"{w.range}\"" if w.range != "Melee" else "Melee"
        kw  = w.keywords
        flags = []
        if kw.lethal_hits:        flags.append("Lethal Hits")
        if kw.sustained_hits:     flags.append(f"Sustained Hits {kw.sustained_hits}")
        if kw.devastating_wounds: flags.append("Devastating Wounds")
        if kw.twin_linked:        flags.append("Twin-Linked")
        if kw.torrent:            flags.append("Torrent")
        if kw.anti_keyword:       flags.append(f"Anti-{kw.anti_keyword} {kw.anti_threshold}+")
        tag = f"  [{', '.join(flags)}]" if flags else ""
        print(f"    {w.name:<30} {rng:>6}  A{w.attacks}  {w.skill}+  S{w.strength}  AP{w.ap}  D{w.damage}{tag}")
    print()


def _simulate_group(attacker, defender, seq, label: str) -> None:
    """Lance N_RUNS simulations pour un groupe d'attaque et affiche le rapport."""
    results = []
    for _ in range(N_RUNS):
        defender.reset()
        results.append(seq.resolve(attacker, defender))
    agg = StatsAggregator(results)
    print(f"\n  >> {label} ({attacker.model_count} fig.) :")
    print(TextReport(agg.aggregate(), runs=N_RUNS).render())


# ---------------------------------------------------------------------------
# Scénarios
# ---------------------------------------------------------------------------

def scenario_single_weapon():
    """Pattern simple : une unité, une arme."""
    print(f"\n{'='*60}")
    print("  Immortals (10) [Gauss blaster] vs Intercessor Squad (10)")
    print(f"{'='*60}")

    attacker_unit = find_unit("Immortals")
    defender_unit = find_unit("Intercessor Squad")

    print(f"\nATTAQUANT : {attacker_unit.name}  [{attacker_unit.faction_id}]")
    show_unit_info(attacker_unit)
    print(f"DEFENSEUR : {defender_unit.name}  [{defender_unit.faction_id}]")
    show_unit_info(defender_unit)

    attacker = build_attacking_unit(attacker_unit, "Gauss blaster", model_count=10)
    defender = build_defending_unit(defender_unit, model_count=10)
    seq = AttackSequence()

    print(f"\nResultats sur {N_RUNS} simulations :")
    _simulate_group(attacker, defender, seq, "Gauss blaster")


def scenario_mixed_loadout():
    """
    Pattern multi-groupes : Intercessor Squad avec un sergent armé différemment.

    Loadout :
      - 9 Intercessors  → Bolt rifle  (ranged)
      - 1 sergent       → Bolt pistol (ranged) + Power sword (melee)

    On simule la phase de tir (combat_type="ranged") :
    chaque groupe est analysé séparément.
    """
    print(f"\n{'='*60}")
    print("  Intercessor Squad — loadout mixte — phase de tir")
    print(f"{'='*60}")

    attacker_unit = find_unit("Intercessor Squad")
    defender_unit = find_unit("Boyz")

    print(f"\nATTAQUANT : {attacker_unit.name}  [{attacker_unit.faction_id}]")
    show_unit_info(attacker_unit)
    print(f"DEFENSEUR : {defender_unit.name}  [{defender_unit.faction_id}]")
    show_unit_info(defender_unit)

    loadout = [
        ("Bolt rifle",   9),   # 9 Intercessors
        ("Bolt pistol",  1),   # 1 sergent (ranged)
        ("Power weapon", 1),   # 1 sergent (melee — filtre en phase de tir)
    ]

    context = CombatContext(combat_type="ranged")
    groups = build_weapon_groups(attacker_unit, loadout, context=context)

    defender = build_defending_unit(defender_unit, model_count=10)
    seq = AttackSequence()

    print(f"\nResultats sur {N_RUNS} simulations — phase de TIR :")
    for group in groups:
        _simulate_group(group, defender, seq, group.weapon_name)


def scenario_melee_loadout():
    """
    Même Intercessor Squad, mais en phase de corps-à-corps.
    Seul le Power sword du sergent est actif.
    """
    print(f"\n{'='*60}")
    print("  Intercessor Squad — loadout mixte — phase de melee")
    print(f"{'='*60}")

    attacker_unit = find_unit("Intercessor Squad")
    defender_unit = find_unit("Boyz")

    loadout = [
        ("Bolt rifle",   9),
        ("Bolt pistol",  1),
        ("Power weapon", 1),
    ]

    context = CombatContext(combat_type="melee", attacker_charged=True)
    groups = build_weapon_groups(attacker_unit, loadout, context=context)

    defender = build_defending_unit(defender_unit, model_count=10)
    seq = AttackSequence()

    print(f"\nResultats sur {N_RUNS} simulations — phase de MELEE :")
    for group in groups:
        _simulate_group(group, defender, seq, group.weapon_name)


def main():
    print("Powered by Wahapedia — https://wahapedia.ru")
    print(f"Simulations : {N_RUNS} runs par groupe\n")

    scenario_single_weapon()
    scenario_mixed_loadout()
    scenario_melee_loadout()


if __name__ == "__main__":
    main()
