# -*- coding: utf-8 -*-
import random
from typing import Optional

from core.enums import RerollType
from units.profiles import AttackingModel


class AttackingUnit:
    def __init__(
        self,
        model: AttackingModel,
        model_count: int,
        hit_critical_on: int = 6,
        wound_critical_on: int = 6,
        # --- règles de touche ---
        lethal_hits: bool = False,
        sustained_hits: int = 0,
        torrent: bool = False,
        blast: bool = False,
        # --- règles de blessure ---
        devastating_wounds: bool = False,
        anti_keyword: Optional[str] = None,
        anti_threshold: Optional[int] = None,
        # --- règles de dégâts ---
        melta: int = 0,
        rapid_fire: int = 0,
        # --- règles de sauvegarde ---
        ignores_cover: bool = False,
        # --- modificateurs d'aura (leader abilities) ---
        hit_modifier: int = 0,
        # --- relances ---
        hit_reroll: RerollType = RerollType.NONE,
        wound_reroll: RerollType = RerollType.NONE,
        twin_linked: bool = False,
        # --- étiquette ---
        weapon_name: str = "",
    ):
        self.model = model
        self.model_count = model_count
        self.weapon_name = weapon_name

        self.hit_critical_on = hit_critical_on
        self.wound_critical_on = wound_critical_on

        self.lethal_hits = lethal_hits
        self.sustained_hits = sustained_hits
        self.torrent = torrent
        self.blast = blast

        self.devastating_wounds = devastating_wounds
        self.anti_keyword = anti_keyword
        self.anti_threshold = anti_threshold

        self.melta = melta
        self.rapid_fire = rapid_fire

        self.ignores_cover = ignores_cover

        self.hit_modifier = hit_modifier
        self.hit_reroll = hit_reroll
        self.wound_reroll = wound_reroll
        self.twin_linked = twin_linked

    def total_attacks(self, context=None, defender_count: int = 0) -> int:
        """
        Calcule le nombre total d'attaques de l'unité.

        Prend en compte :
        - Blast  : +1 attaque/figurine si cible ≥ 6, +D3 si ≥ 11
        - Rapid Fire N : +N attaques/figurine si dans la moitié de la portée
        """
        total = 0
        for _ in range(self.model_count):
            attacks = self.model.attacks.roll()
            if self.blast:
                attacks += defender_count // 5
            total += attacks

        if self.rapid_fire > 0 and context is not None and context.within_half_range:
            total += self.rapid_fire * self.model_count

        return total
