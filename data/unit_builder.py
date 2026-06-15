"""
Conversion WahapediaUnit → AttackingUnit / DefendingUnit.

Ce module fait le pont entre les données Wahapedia et le moteur de simulation.
Les mots-clés non encore simulés génèrent un message INFO.
"""

from typing import List, Optional, Tuple

from core.dice import DiceExpression, FixedValue, parse_dice
from core.enums import RerollType
from core.context import CombatContext
from units.profiles import AttackingModel, DefendingModel
from units.attacking import WeaponGroup, AttackingUnit
from units.defending import DefendingUnit
from units.unit import ModelGroup, ModelProfile
from data.models import WahapediaUnit, WeaponProfile


# ---------------------------------------------------------------------------
# Avertissements sur les mots-clés non simulés
# ---------------------------------------------------------------------------

_NOT_SIMULATED = [
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
# Helpers de conversion
# ---------------------------------------------------------------------------

def _wahapedia_to_model_groups(unit: WahapediaUnit) -> List[ModelGroup]:
    """
    Convertit les modèles Wahapedia en ModelGroup en utilisant model_composition
    pour le name-matching (quand disponible), sinon un groupe unique.
    """
    if not unit.models:
        return []

    if unit.model_composition:
        groups = []
        for model_idx, min_c, max_c in unit.model_composition:
            if model_idx < len(unit.models):
                m = unit.models[model_idx]
                profile = ModelProfile(
                    name=m.name,
                    toughness=m.toughness,
                    save=m.save,
                    wounds=m.wounds,
                    invulnerable_save=m.invulnerable_save,
                    movement=m.movement,
                )
                groups.append(ModelGroup(profile, m.name, min_c, max_c))
        return groups

    # Fallback: un seul groupe avec les stats du premier modèle
    m = unit.models[0]
    profile = ModelProfile(
        name=m.name,
        toughness=m.toughness,
        save=m.save,
        wounds=m.wounds,
        invulnerable_save=m.invulnerable_save,
        movement=m.movement,
    )
    return [ModelGroup(profile, m.name, unit.min_models, unit.max_models)]


# ---------------------------------------------------------------------------
# Builders publics
# ---------------------------------------------------------------------------

def build_weapon_groups(
    unit: WahapediaUnit,
    loadout: List[Tuple[str, int]],
    context: Optional[CombatContext] = None,
    hit_reroll: RerollType = RerollType.NONE,
    wound_reroll: RerollType = RerollType.NONE,
    hit_modifier: int = 0,
) -> List[WeaponGroup]:
    """
    Construit un WeaponGroup par groupe d'armes d'un loadout explicite.

    Args:
        unit:        unité Wahapedia source
        loadout:     liste de (nom_arme, nb_figurines)
        context:     contexte de combat — filtre les armes par combat_type
        hit_reroll:  relance de touche externe
        wound_reroll:relance de blessure externe

    Returns:
        Liste de WeaponGroup (une par groupe retenu après filtre).
    """
    combat_type = context.combat_type if context is not None else None

    groups: List[WeaponGroup] = []
    for weapon_name, model_count in loadout:
        weapon = unit.get_weapon(weapon_name)
        if weapon is None:
            available = [w.name for w in unit.weapons]
            raise ValueError(
                f"Arme '{weapon_name}' introuvable dans '{unit.name}'. "
                f"Disponibles : {available}"
            )

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
            hit_modifier=hit_modifier,
            hit_reroll=hit_reroll,
            wound_reroll=effective_wound_reroll,
            weapon_name=weapon.name,
        ))

    return groups


def build_attacking_unit_config(
    unit: WahapediaUnit,
    active_loadout: Optional[List[Tuple[str, int]]] = None,
    hit_reroll: RerollType = RerollType.NONE,
    wound_reroll: RerollType = RerollType.NONE,
    hit_modifier: int = 0,
) -> AttackingUnit:
    """
    Construit un AttackingUnit (vue haute-niveau) depuis une WahapediaUnit.
    Utilise la composition parsée (model_composition) pour les core_groups.
    """
    core_groups = _wahapedia_to_model_groups(unit)
    return AttackingUnit(
        name=unit.name,
        core_groups=core_groups,
        weapons=unit.weapons,
        keywords=unit.keywords,
        active_loadout=active_loadout or [],
        hit_reroll=hit_reroll,
        wound_reroll=wound_reroll,
        hit_modifier=hit_modifier,
    )


def build_defending_unit(
    unit: WahapediaUnit,
    model_count: Optional[int] = None,
    group_counts: Optional[List[int]] = None,
    leader_model: Optional[DefendingModel] = None,
    support_model: Optional[DefendingModel] = None,
    hit_modifier: int = 0,
    wound_modifier: int = 0,
    damage_reduction: int = 0,
    fnp: Optional[int] = None,
) -> DefendingUnit:
    """
    Construit un DefendingUnit depuis une WahapediaUnit.
    Utilise model_composition pour créer les core_groups intra-card.
    group_counts applique un effectif par groupe (unités composites).
    model_count s'applique uniquement au premier groupe si group_counts absent.
    """
    if not unit.models:
        raise ValueError(f"'{unit.name}' n'a pas de stats de modèle.")

    core_groups = _wahapedia_to_model_groups(unit)

    if group_counts is not None and len(group_counts) == len(core_groups):
        core_groups = [
            ModelGroup(g.profile, g.name, cnt, cnt)
            for g, cnt in zip(core_groups, group_counts)
        ]
    elif model_count is not None and core_groups:
        g = core_groups[0]
        core_groups[0] = ModelGroup(g.profile, g.name, model_count, model_count)

    # FNP : appliqué au profil du premier groupe
    if fnp is not None and core_groups:
        p = core_groups[0].profile
        core_groups[0] = ModelGroup(
            ModelProfile(
                name=p.name,
                toughness=p.toughness,
                save=p.save,
                wounds=p.wounds,
                invulnerable_save=p.invulnerable_save,
                fnp=fnp,
                movement=p.movement,
            ),
            core_groups[0].name,
            core_groups[0].min_count,
            core_groups[0].max_count,
        )

    return DefendingUnit(
        core_groups=core_groups,
        name=unit.name,
        keywords=unit.keywords,
        leader_model=leader_model,
        support_model=support_model,
        hit_modifier=hit_modifier,
        wound_modifier=wound_modifier,
        damage_reduction=damage_reduction,
    )
