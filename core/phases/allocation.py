import random
from typing import List, Optional, Tuple

from core.enums import AttackState
from core.events import AttackEvent
from core.phases.base import Phase
from stats.phase_stats import AllocationPhaseStats


def _apply_fnp(damage: int, wounds_before: int, fnp: int) -> Tuple[int, int]:
    """
    Roule le FNP point par point.
    Retourne (dégâts effectifs, dégâts ignorés).
    S'arrête dès que le modèle atteint 0 PV (excédent perdu).
    """
    effective = 0
    ignored = 0
    for _ in range(damage):
        if random.randint(1, 6) >= fnp:
            ignored += 1
        else:
            effective += 1
            if effective >= wounds_before:
                break
    return effective, ignored


def _passes_save(save_roll: int, model, attacker, context) -> bool:
    """
    Re-évalue un jet de save contre le profil d'un personnage (V11).

    Utilisé quand un événement ayant échoué le save des gardes du corps
    atteint un personnage avec un meilleur profil de sauvegarde.
    Retourne True si le save PASSE (aucun dégât).
    """
    if save_roll == 1:
        return False

    cover_bonus = 0
    if context is not None and context.target_in_cover and not attacker.ignores_cover:
        cover_bonus = 1

    armour_save = model.save - attacker.model.ap - cover_bonus
    invuln = model.invulnerable_save

    if invuln is not None:
        save_target = min(armour_save, invuln)
    else:
        save_target = armour_save

    return save_roll >= save_target


def _apply_damage_to_slot(
    damage: int,
    wounds_before: int,
    fnp,
    stats: AllocationPhaseStats,
) -> Tuple[int, bool]:
    """
    Applique les dégâts à un slot.
    Retourne (PV restants après dégâts, modèle est mort).
    """
    if fnp is not None:
        damage, ignored = _apply_fnp(damage, wounds_before, fnp)
        stats.fnp_ignored_damage += ignored

    if damage <= 0:
        return wounds_before, False

    effective = min(damage, wounds_before)
    spillover = max(0, damage - wounds_before)
    stats.damage_allocated += effective
    stats.spillover_damage += spillover

    remaining = wounds_before - effective
    return remaining, remaining <= 0


class AllocationPhase(Phase):
    def resolve(self, events: List[AttackEvent], context=None) -> AllocationPhaseStats:
        """
        Alloue les dégâts attaque par attaque à l'unité défensive.

        Ordre d'allocation V11 :
          1. Groupes intra-card (core_groups[0] → core_groups[1] → ...)
             — pas de re-évaluation save (même règles pour tous)
          2. Support inter-card — re-évalue save avec son propre profil
          3. Leader inter-card — re-évalue save avec son propre profil
        """
        stats = AllocationPhaseStats()
        defender = events[0].defender if events else None

        for event in events:
            if event.state != AttackState.RESOLVED or event.damage <= 0:
                continue

            defender = event.defender

            # ==================================================
            # 1. Groupes intra-card (core_groups)
            # ==================================================
            handled = False
            for i, group in enumerate(defender.core_groups):
                state = defender.group_states[i]
                if state.count > 0:
                    remaining, died = _apply_damage_to_slot(
                        event.damage,
                        state.current_wounds,
                        group.profile.fnp,
                        stats,
                    )
                    state.current_wounds = remaining

                    if died:
                        stats.models_killed += 1
                        state.count -= 1
                        state.current_wounds = (
                            group.profile.wounds if state.count > 0 else 0
                        )
                    handled = True
                    break

            if handled:
                continue

            # ==================================================
            # 2. Support inter-card (re-évaluation save V11)
            # ==================================================
            if defender.support_alive:
                if (
                    not event.mortal_wound
                    and event.save_roll is not None
                    and _passes_save(
                        event.save_roll,
                        defender.support_model,
                        event.attacker,
                        context,
                    )
                ):
                    continue

                remaining, died = _apply_damage_to_slot(
                    event.damage,
                    defender.current_support_wounds,
                    defender.support_model.fnp,
                    stats,
                )
                defender.current_support_wounds = remaining

                if died:
                    stats.support_killed = True
                    defender.support_alive = False
                    defender.current_support_wounds = 0
                continue

            # ==================================================
            # 3. Leader inter-card (re-évaluation save V11)
            # ==================================================
            if defender.leader_alive:
                if (
                    not event.mortal_wound
                    and event.save_roll is not None
                    and _passes_save(
                        event.save_roll,
                        defender.leader_model,
                        event.attacker,
                        context,
                    )
                ):
                    continue

                remaining, died = _apply_damage_to_slot(
                    event.damage,
                    defender.current_leader_wounds,
                    defender.leader_model.fnp,
                    stats,
                )
                defender.current_leader_wounds = remaining

                if died:
                    stats.leader_killed = True
                    defender.leader_alive = False
                    defender.current_leader_wounds = 0

        # --------------------------------------------------
        # Wounds restants (sur la figurine actuellement ciblée)
        # --------------------------------------------------
        if defender is not None:
            # Premier groupe intra-card encore vivant
            for i, group in enumerate(defender.core_groups):
                state = defender.group_states[i]
                if state.count > 0:
                    stats.wounds_remaining = state.current_wounds
                    break
            else:
                if defender.support_alive:
                    stats.wounds_remaining = defender.current_support_wounds
                elif defender.leader_alive:
                    stats.wounds_remaining = defender.current_leader_wounds
                else:
                    stats.wounds_remaining = 0

        return stats
