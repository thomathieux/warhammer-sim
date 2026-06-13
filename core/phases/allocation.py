import random
from typing import List, Optional, Tuple

from core.enums import AttackState
from core.events import AttackEvent
from core.phases.base import Phase
from stats.phase_stats import AllocationPhaseStats
from units.profiles import DefendingModel


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


def _passes_save(
    save_roll: int,
    model: DefendingModel,
    attacker,
    context,
) -> bool:
    """
    Re-évalue un jet de save contre le profil d'un personnage (V11).

    Utilisé quand un événement ayant échoué le save des gardes du corps
    atteint un personnage avec un meilleur profil de sauvegarde.
    Retourne True si le save PASSE (aucun dégât).

    1 échoue toujours. 6 réussit toujours (capped par la logique du seuil).
    """
    if save_roll == 1:
        return False  # auto-échec

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
    Applique les dégâts à un slot (garde ou personnage).
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

        Ordre d'allocation V11 (Garde du Corps) :
          1. Gardes du corps  — absorbent les dice les plus bas (déjà triés)
          2. Support          — 2e personnage, pris avant le leader
          3. Leader           — personnage principal, dernier à recevoir des dégâts

        Pour chaque personnage (support, leader) :
          - Le jet de save est réévalué contre le propre profil du personnage.
          - Si le save passe avec le profil du personnage → aucun dégât.
          - Cela corrige le biais du V10 où tous les saves utilisaient
            le profil des gardes du corps.
        """
        stats = AllocationPhaseStats()

        defender = events[0].defender if events else None

        for event in events:
            if event.state != AttackState.RESOLVED or event.damage <= 0:
                continue

            defender = event.defender

            # ==================================================
            # 1. Gardes du corps
            # ==================================================
            if defender.model_count > 0:
                remaining, died = _apply_damage_to_slot(
                    event.damage,
                    defender.current_model_wounds,
                    defender.model.fnp,
                    stats,
                )
                defender.current_model_wounds = remaining

                if died:
                    stats.models_killed += 1
                    defender.model_count -= 1
                    defender.current_model_wounds = (
                        defender.model.wounds if defender.model_count > 0 else 0
                    )
                continue

            # ==================================================
            # 2. Support (2e personnage, V11)
            # ==================================================
            if defender.support_alive:
                # Re-évaluation save V11 : le support peut avoir un meilleur save
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
                    continue  # save passe → aucun dégât au support

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
            # 3. Leader (personnage principal, dernier, V11)
            # ==================================================
            if defender.leader_alive:
                # Re-évaluation save V11
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
                    continue  # save passe → leader protégé

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
            if defender.model_count > 0:
                stats.wounds_remaining = defender.current_model_wounds
            elif defender.support_alive:
                stats.wounds_remaining = defender.current_support_wounds
            elif defender.leader_alive:
                stats.wounds_remaining = defender.current_leader_wounds
            else:
                stats.wounds_remaining = 0

        return stats
