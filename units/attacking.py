# -*- coding: utf-8 -*-
from __future__ import annotations
from typing import List, Optional, Tuple

from core.dice import DiceExpression, FixedValue, parse_dice
from core.enums import RerollType
from units.profiles import AttackingModel
from units.unit import Unit, ModelGroup


class WeaponGroup:
    """
    Groupe d'armes prêt pour le moteur de simulation.
    Représente un ensemble de modèles attaquant avec la même arme.
    (Anciennement nommé AttackingUnit dans le moteur de simulation.)
    """

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
        rapid_fire: Optional[DiceExpression] = None,
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
        """Calcule le nombre total d'attaques (Blast + Rapid Fire inclus)."""
        total = 0
        for _ in range(self.model_count):
            attacks = self.model.attacks.roll()
            if self.blast:
                attacks += defender_count // 5
            total += attacks

        if self.rapid_fire is not None and context is not None and context.within_half_range:
            for _ in range(self.model_count):
                total += self.rapid_fire.roll()

        return total


class AttackingUnit(Unit):
    """
    Unité en configuration d'attaque (vue haute-niveau d'une datacard).
    Hérite de Unit et ajoute la sélection d'armes + modificateurs offensifs.
    Génère des WeaponGroup pour le moteur de simulation via to_weapon_groups().
    """

    def __init__(
        self,
        name: str,
        core_groups: List[ModelGroup],
        weapons: Optional[List] = None,
        keywords: Optional[List[str]] = None,
        leader: Optional[Unit] = None,
        support: Optional[Unit] = None,
        # Config d'attaque
        active_loadout: Optional[List[Tuple[str, int]]] = None,
        hit_reroll: RerollType = RerollType.NONE,
        wound_reroll: RerollType = RerollType.NONE,
        hit_modifier: int = 0,
    ):
        super().__init__(name, core_groups, weapons, keywords, leader, support)
        self.active_loadout: List[Tuple[str, int]] = active_loadout or []
        self.hit_reroll = hit_reroll
        self.wound_reroll = wound_reroll
        self.hit_modifier = hit_modifier

    def to_weapon_groups(self, context=None) -> List[WeaponGroup]:
        """
        Projette l'AttackingUnit en liste de WeaponGroup pour le moteur de simulation.
        Applique le filtre combat_type (ranged / melee) si context est fourni.
        """
        combat_type = context.combat_type if context is not None else None
        groups: List[WeaponGroup] = []

        for weapon_name, model_count in self.active_loadout:
            weapon = next(
                (w for w in self.weapons if w.name.lower() == weapon_name.lower()),
                None,
            )
            if weapon is None:
                continue

            is_melee = weapon.range.strip().lower() == "melee"
            if combat_type == "ranged" and is_melee:
                continue
            if combat_type == "melee" and not is_melee:
                continue

            kw = weapon.keywords
            effective_wound_reroll = self.wound_reroll
            if kw.twin_linked and self.wound_reroll == RerollType.NONE:
                effective_wound_reroll = RerollType.FAILED

            groups.append(WeaponGroup(
                model=AttackingModel(
                    attacks=parse_dice(weapon.attacks),
                    attack_skill=weapon.skill,
                    strength=weapon.strength,
                    ap=weapon.ap,
                    damage=parse_dice(weapon.damage),
                ),
                model_count=model_count,
                lethal_hits=kw.lethal_hits,
                sustained_hits=kw.sustained_hits,
                torrent=kw.torrent,
                blast=kw.blast,
                devastating_wounds=kw.devastating_wounds,
                anti_keyword=kw.anti_keyword,
                anti_threshold=kw.anti_threshold,
                melta=kw.melta,
                rapid_fire=(
                    parse_dice(kw.rapid_fire_str) if kw.rapid_fire_str
                    else FixedValue(kw.rapid_fire) if kw.rapid_fire
                    else None
                ),
                ignores_cover=kw.ignores_cover,
                twin_linked=kw.twin_linked,
                hit_modifier=self.hit_modifier,
                hit_reroll=self.hit_reroll,
                wound_reroll=effective_wound_reroll,
                weapon_name=weapon.name,
            ))

        return groups
