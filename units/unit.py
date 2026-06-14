from __future__ import annotations
from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class ModelProfile:
    """Stats d'un type de modèle au sein d'une datacard."""
    name: str
    toughness: int
    save: int
    wounds: int
    invulnerable_save: Optional[int] = None
    fnp: Optional[int] = None
    movement: str = ""


@dataclass
class ModelGroup:
    """Un type de modèle au sein d'une même datacard (intra-card)."""
    profile: ModelProfile
    name: str
    min_count: int
    max_count: int


@dataclass
class GroupWoundState:
    """État des PV d'un groupe de modèles intra-card pendant la simulation."""
    count: int
    current_wounds: int
    initial_count: int
    initial_wounds: int


class Unit:
    """
    Représentation d'une datacard Wahapedia.
    Classe de base pour AttackingUnit et DefendingUnit.

    Deux niveaux de composition :
    - Intra-card  : core_groups (ex: BOY + BOSS NOB sur la même fiche)
    - Inter-card  : leader / support (unités attachées depuis d'autres fiches)

    La même unité peut être vue en attaque ou en défense — seule la sous-classe
    (AttackingUnit / DefendingUnit) diffère.
    """

    def __init__(
        self,
        name: str,
        core_groups: List[ModelGroup],
        weapons: Optional[List] = None,
        keywords: Optional[List[str]] = None,
        leader: Optional[Unit] = None,
        support: Optional[Unit] = None,
    ):
        self.name: str = name
        self.core_groups: List[ModelGroup] = core_groups
        self.weapons: List = weapons or []
        self.keywords: List[str] = [k.upper() for k in (keywords or [])]
        self.leader: Optional[Unit] = leader
        self.support: Optional[Unit] = support

    @property
    def primary_group(self) -> Optional[ModelGroup]:
        """Premier groupe intra-card (le plus nombreux, index 0)."""
        return self.core_groups[0] if self.core_groups else None

    @property
    def default_model_count(self) -> int:
        """Nombre total de figurines (somme des max_count intra-card)."""
        return sum(g.max_count for g in self.core_groups)
