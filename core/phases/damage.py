# -*- coding: utf-8 -*-
from typing import List, Optional

from core.enums import AttackState
from core.events import AttackEvent
from core.phases.base import Phase


class DamagePhase(Phase):
    def resolve(self, events: List[AttackEvent], context=None) -> List[AttackEvent]:
        """
        Calcule les dégâts pour chaque attaque ayant échoué sa sauvegarde.

        - Dégâts bruts (jet de dés)
        - Melta N : +N dégâts si dans la moitié de la portée
        - Réduction de dégâts (minimum 1)
        """
        resolved: List[AttackEvent] = []

        for event in events:
            if event.state != AttackState.SAVE_FAILED:
                continue

            attacker = event.attacker
            defender = event.defender

            # --- Dégâts bruts ---
            raw_damage = attacker.model.damage.roll()

            # --- Melta N : +N dégâts à mi-portée ---
            if attacker.melta > 0 and context is not None and context.within_half_range:
                raw_damage += attacker.melta

            # --- Réduction de dégâts (minimum 1) ---
            reduction = defender.damage_reduction if defender else 0
            final_damage = max(1, raw_damage - reduction)

            event.raw_damage = raw_damage
            event.final_damage = final_damage
            event.damage = final_damage
            event.state = AttackState.RESOLVED
            resolved.append(event)

        return resolved
