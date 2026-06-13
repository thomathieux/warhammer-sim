# -*- coding: utf-8 -*-
import random
from typing import List, Optional

from core.enums import AttackState
from core.events import AttackEvent
from core.phases.base import Phase


class SavePhase(Phase):
    def resolve(self, events: List[AttackEvent], context=None) -> List[AttackEvent]:
        """
        Résout les sauvegardes contre le profil des gardes du corps.

        V11 — tri ascendant des dice :
          Les dice les plus bas (les plus susceptibles d'échouer) sont assignés
          aux gardes du corps en premier. Les dice les plus hauts sont conservés
          pour les personnages, qui bénéficieront d'une réévaluation contre leur
          propre profil dans AllocationPhase.

        Note : les blessures mortelles (Devastating Wounds) sautent les saves.
        """
        resolved: List[AttackEvent] = []

        for event in events:
            defender = event.defender
            attacker = event.attacker
            model = defender.model  # profil des gardes du corps

            # --------------------------------------------------
            # Blessures mortelles → pas de sauvegarde
            # --------------------------------------------------
            if event.mortal_wound:
                event.state = AttackState.SAVE_FAILED
                event.invulnerable_used = False
                event.save_roll = None
                resolved.append(event)
                continue

            # --------------------------------------------------
            # Couverture : +1 à la sauvegarde d'armure
            # (annulé par Ignores Cover)
            # --------------------------------------------------
            cover_bonus = 0
            if (
                context is not None
                and context.target_in_cover
                and not attacker.ignores_cover
            ):
                cover_bonus = 1

            # --------------------------------------------------
            # Calcul des sauvegardes disponibles (profil garde du corps)
            # --------------------------------------------------
            armour_save = model.save - attacker.model.ap - cover_bonus
            invuln_save = model.invulnerable_save

            possible_saves = [(armour_save, False)]
            if invuln_save is not None:
                possible_saves.append((invuln_save, True))

            save_target, used_invuln = min(possible_saves, key=lambda x: x[0])

            # --------------------------------------------------
            # Jet de sauvegarde
            # --------------------------------------------------
            roll = random.randint(1, 6)
            event.save_roll = roll
            event.invulnerable_used = used_invuln

            if roll < save_target:
                event.state = AttackState.SAVE_FAILED
                resolved.append(event)

        # --------------------------------------------------
        # V11 : tri ascendant par dice de sauvegarde.
        # Les dice les plus bas vont aux gardes (bodyguards) en premier ;
        # les dice les plus hauts atteignent les personnages en dernier,
        # qui bénéficieront ainsi de leurs meilleures sauvegardes.
        # Les blessures mortelles (save_roll=None) passent en tête.
        # --------------------------------------------------
        resolved.sort(key=lambda e: e.save_roll if e.save_roll is not None else -1)

        return resolved
