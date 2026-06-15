# -*- coding: utf-8 -*-
"""
Tests pour AttackingUnit.to_weapon_groups().

Vérifie :
  1. Le nombre de WeaponGroup produits correspond au loadout.
  2. Le filtre combat_type=ranged exclut les armes de mêlée.
  3. Le filtre combat_type=melee exclut les armes à distance.
"""

from units.attacking import AttackingUnit
from units.unit import ModelGroup, ModelProfile
from data.models import WeaponProfile, ParsedKeywords
from core.context import CombatContext


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _profile():
    return ModelProfile(name="Marine", toughness=4, save=3, wounds=2)


def _bolter():
    return WeaponProfile(
        name="Bolter", range="24", type="Ranged",
        attacks="2", skill=3, strength=4, ap=0, damage="1",
    )


def _chainsword():
    return WeaponProfile(
        name="Chainsword", range="Melee", type="Melee",
        attacks="3", skill=3, strength=4, ap=0, damage="1",
    )


def _unit(weapons):
    group = ModelGroup(_profile(), "Marine", 5, 5)
    loadout = [(w.name, 5) for w in weapons]
    return AttackingUnit(
        name="Space Marine Squad",
        core_groups=[group],
        weapons=weapons,
        active_loadout=loadout,
    )


# ---------------------------------------------------------------------------
# Test 3.1 — Loadout 2 armes → 2 WeaponGroup
# ---------------------------------------------------------------------------

def test_to_weapon_groups_one_per_weapon():
    """
    Objectif : to_weapon_groups() retourne un WeaponGroup par arme du loadout
    quand aucun filtre combat_type n'est appliqué.
    """
    unit   = _unit([_bolter(), _chainsword()])
    groups = unit.to_weapon_groups()

    assert len(groups) == 2
    names = {g.weapon_name for g in groups}
    assert "Bolter" in names
    assert "Chainsword" in names


# ---------------------------------------------------------------------------
# Test 3.2 — combat_type=ranged filtre les armes de mêlée
# ---------------------------------------------------------------------------

def test_to_weapon_groups_ranged_filters_melee():
    """
    Objectif : avec combat_type='ranged', les armes dont range='Melee'
    sont exclues du résultat.
    """
    unit   = _unit([_bolter(), _chainsword()])
    ctx    = CombatContext(combat_type="ranged")
    groups = unit.to_weapon_groups(ctx)

    assert len(groups) == 1
    assert groups[0].weapon_name == "Bolter"


# ---------------------------------------------------------------------------
# Test 3.3 — combat_type=melee filtre les armes à distance
# ---------------------------------------------------------------------------

def test_to_weapon_groups_melee_filters_ranged():
    """
    Objectif : avec combat_type='melee', les armes à distance (range != 'Melee')
    sont exclues du résultat.
    """
    unit   = _unit([_bolter(), _chainsword()])
    ctx    = CombatContext(combat_type="melee")
    groups = unit.to_weapon_groups(ctx)

    assert len(groups) == 1
    assert groups[0].weapon_name == "Chainsword"
