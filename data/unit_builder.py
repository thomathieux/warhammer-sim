"""
Conversion WahapediaUnit → AttackingUnit / DefendingUnit.

Ce module fait le pont entre les données Wahapedia et le moteur de simulation
existant. Les mots-clés non encore simulés génèrent un message INFO.
"""

import re
from typing import List, Optional, Tuple

from core.dice import DiceExpression, FixedValue, Dice
from core.enums import RerollType
from core.context import CombatContext
from units.profiles import AttackingModel, DefendingModel
from units.attacking import AttackingUnit
from units.defending import DefendingUnit
from data.models import WahapediaUnit, WeaponProfile


# ---------------------------------------------------------------------------
# Parsing des expressions de dés
# ---------------------------------------------------------------------------

def parse_dice(value: str) -> DiceExpression:
    """
    Convertit une chaîne Wahapedia en DiceExpression.

    Exemples :
        "2"    → FixedValue(2)
        "D3"   → Dice(1, 3)
        "D6"   → Dice(1, 6)
        "2D6"  → Dice(2, 6)
        "D6+1" → Dice(1, 6, bonus=1)
        "D3+3" → Dice(1, 3, bonus=3)
    """
    v = value.strip().upper()
    if v.isdigit():
        return FixedValue(int(v))

    m = re.fullmatch(r"(\d*)D(\d+)(?:\+(\d+))?", v)
    if m:
        n     = int(m.group(1)) if m.group(1) else 1
        faces = int(m.group(2))
        bonus = int(m.group(3)) if m.group(3) else 0
        return Dice(n, faces, bonus)

    # Fallback sécuritaire
    print(f"[WARN] parse_dice: valeur inconnue '{value}', remplacée par 1")
    return FixedValue(1)


# ---------------------------------------------------------------------------
# Avertissements sur les mots-clés non simulés
# ---------------------------------------------------------------------------

_NOT_SIMULATED = [
    # Règles désormais simulées : torrent, blast, ignores_cover, melta, rapid_fire, anti_keyword
    ("precision",      "allocation de blessure ciblée (precision)"),
    ("hazardous",      "blessure auto sur 1 (hazardous)"),
    ("one_shot",       "une seule utilisation (one shot)"),
    ("lance",          "lance"),
    ("psychic",        "psychic"),
    ("extra_attacks",  "attaques supplémentaires (extra attacks)"),
]


def _warn_not_simulated(unit_name: str, weapon_name: str, kw) -> None:
    prefix = f"[INFO] {unit_name} / {weapon_name}"
    for attr, label in _NOT_SIMULATED:
        val = getattr(kw, attr, None)
        if val:
            print(f"{prefix} : '{label}' non encore simulé")
    if kw.unknown:
        print(f"{prefix} : mots-clés inconnus ignorés → {kw.unknown}")


# ---------------------------------------------------------------------------
# Builders publics
# ---------------------------------------------------------------------------

def build_attacking_unit(
    unit: WahapediaUnit,
    weapon_name: str,
    model_count: Optional[int] = None,
    hit_reroll: RerollType = RerollType.NONE,
    wound_reroll: RerollType = RerollType.NONE,
) -> AttackingUnit:
    """
    Construit un AttackingUnit à partir d'une unité Wahapedia et du nom de son arme.

    Args:
        unit:         unité Wahapedia source
        weapon_name:  nom exact de l'arme (casse insensible)
        model_count:  nombre de figurines (défaut : max de l'unité)
        hit_reroll:   relance de touche externe (ex : Oath of Moment)
        wound_reroll: relance de blessure externe

    Returns:
        AttackingUnit prête pour le simulateur.

    Raises:
        ValueError: si l'arme ou les stats du modèle sont introuvables.
    """
    weapon = unit.get_weapon(weapon_name)
    if weapon is None:
        available = [w.name for w in unit.weapons]
        raise ValueError(
            f"Arme '{weapon_name}' introuvable dans '{unit.name}'. "
            f"Disponibles : {available}"
        )

    model_stats = unit.primary_model()
    if model_stats is None:
        raise ValueError(f"'{unit.name}' n'a pas de stats de modèle.")

    kw = weapon.keywords
    _warn_not_simulated(unit.name, weapon.name, kw)

    # twin-linked → relance blessures ratées (si pas déjà forcé)
    effective_wound_reroll = wound_reroll
    if kw.twin_linked and wound_reroll == RerollType.NONE:
        effective_wound_reroll = RerollType.FAILED

    count = model_count if model_count is not None else unit.max_models

    return AttackingUnit(
        model=AttackingModel(
            attacks=parse_dice(weapon.attacks),
            attack_skill=weapon.skill,
            strength=weapon.strength,
            ap=weapon.ap,
            damage=parse_dice(weapon.damage),
        ),
        model_count=count,
        lethal_hits=kw.lethal_hits,
        sustained_hits=kw.sustained_hits,
        torrent=kw.torrent,
        blast=kw.blast,
        devastating_wounds=kw.devastating_wounds,
        anti_keyword=kw.anti_keyword,
        anti_threshold=kw.anti_threshold,
        melta=kw.melta,
        rapid_fire=kw.rapid_fire,
        ignores_cover=kw.ignores_cover,
        twin_linked=kw.twin_linked,
        hit_reroll=hit_reroll,
        wound_reroll=effective_wound_reroll,
        weapon_name=weapon.name,
    )


def build_weapon_groups(
    unit: WahapediaUnit,
    loadout: List[Tuple[str, int]],
    context: Optional[CombatContext] = None,
    hit_reroll: RerollType = RerollType.NONE,
    wound_reroll: RerollType = RerollType.NONE,
    hit_modifier: int = 0,
) -> List[AttackingUnit]:
    """
    Construit un AttackingUnit par groupe d'armes d'un loadout explicite.

    Chaque groupe est simulé indépendamment : les résultats sont analysés
    séparément avant d'être croisés si besoin.

    Args:
        unit:        unité Wahapedia source
        loadout:     liste de (nom_arme, nb_figurines)
                     ex: [("Bolt rifle", 9), ("Power sword", 1)]
        context:     contexte de combat — filtre les armes par combat_type
                     ("ranged" garde les armes à portée > 0,
                      "melee"  garde les armes Melee).
                     None → aucun filtre, toutes les armes retenues.
        hit_reroll:  relance de touche externe (ex: Oath of Moment)
        wound_reroll:relance de blessure externe

    Returns:
        Liste d'AttackingUnit, une par groupe retenu après filtre.

    Raises:
        ValueError: si une arme du loadout est introuvable dans l'unité.
    """
    combat_type = context.combat_type if context is not None else None

    groups: List[AttackingUnit] = []
    for weapon_name, model_count in loadout:
        weapon = unit.get_weapon(weapon_name)
        if weapon is None:
            available = [w.name for w in unit.weapons]
            raise ValueError(
                f"Arme '{weapon_name}' introuvable dans '{unit.name}'. "
                f"Disponibles : {available}"
            )

        # --- Filtre combat_type ---
        is_melee = weapon.range.strip().lower() == "melee"
        if combat_type == "ranged" and is_melee:
            continue
        if combat_type == "melee" and not is_melee:
            continue

        kw = weapon.keywords
        _warn_not_simulated(unit.name, weapon.name, kw)

        effective_wound_reroll = wound_reroll
        if kw.twin_linked and wound_reroll == RerollType.NONE:
            effective_wound_reroll = RerollType.FAILED

        groups.append(AttackingUnit(
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
            rapid_fire=kw.rapid_fire,
            ignores_cover=kw.ignores_cover,
            twin_linked=kw.twin_linked,
            hit_modifier=hit_modifier,
            hit_reroll=hit_reroll,
            wound_reroll=effective_wound_reroll,
            weapon_name=weapon.name,
        ))

    return groups


def build_defending_unit(
    unit: WahapediaUnit,
    model_count: Optional[int] = None,
    leader_model: Optional[DefendingModel] = None,
    support_model: Optional[DefendingModel] = None,
    hit_modifier: int = 0,
    wound_modifier: int = 0,
    damage_reduction: int = 0,
    fnp: Optional[int] = None,
) -> DefendingUnit:
    """
    Construit un DefendingUnit à partir d'une unité Wahapedia.

    Args:
        unit:        unité Wahapedia source
        model_count: nombre de figurines (défaut : max de l'unité)

    Returns:
        DefendingUnit prête pour le simulateur.
    """
    model_stats = unit.primary_model()
    if model_stats is None:
        raise ValueError(f"'{unit.name}' n'a pas de stats de modèle.")

    count = model_count if model_count is not None else unit.max_models

    # FNP : si fourni en paramètre, prendre le meilleur (valeur la plus basse = meilleure)
    effective_fnp = model_stats.invulnerable_save  # placeholder — fnp est sur DefendingModel
    base_fnp = None  # Wahapedia ne fournit pas de FNP dans les CSV actuels
    if fnp is not None:
        effective_fnp = fnp if base_fnp is None else min(fnp, base_fnp)
    else:
        effective_fnp = base_fnp

    return DefendingUnit(
        model=DefendingModel(
            toughness=model_stats.toughness,
            save=model_stats.save,
            wounds=model_stats.wounds,
            invulnerable_save=model_stats.invulnerable_save,
            fnp=effective_fnp,
        ),
        model_count=count,
        leader_model=leader_model,
        support_model=support_model,
        hit_modifier=hit_modifier,
        wound_modifier=wound_modifier,
        damage_reduction=damage_reduction,
        keywords=unit.keywords,
    )
