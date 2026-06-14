# -*- coding: utf-8 -*-
from __future__ import annotations
from typing import List, Optional

from units.unit import Unit, ModelGroup, ModelProfile, GroupWoundState


class DefendingUnit(Unit):
    """
    Unité en configuration de défense, avec état de PV mutable pendant la simulation.
    Hérite de Unit (core_groups + leader/support inter-card).

    Deux niveaux de composition :
    - core_groups     : types de modèles intra-card (BOY + BOSS NOB)
      → chacun a son propre GroupWoundState (count, current_wounds)
    - leader / support : personnages attachés inter-card (autre datacard)
      → gérés séparément avec re-évaluation save V11

    Constructeur compatible avec l'ancien API (model: DefendingModel, model_count: int)
    pour maintenir la compatibilité avec les tests existants.
    """

    def __init__(
        self,
        # --- Ancien API (compatibilité) ---
        model=None,            # DefendingModel ou None
        model_count: int = None,
        # --- Nouvel API ---
        core_groups: Optional[List[ModelGroup]] = None,
        name: str = "",
        keywords: Optional[List[str]] = None,
        # --- Personnages attachés inter-card ---
        leader_model=None,     # DefendingModel ou ModelProfile
        support_model=None,    # DefendingModel ou ModelProfile
        # --- Règles défensives ---
        defensive_rules: Optional[List] = None,
        damage_reduction: int = 0,
        hit_modifier: int = 0,
        wound_modifier: int = 0,
        stealth: bool = False,
        wound_minus_one_if_weaker: bool = False,
    ):
        # Conversion ancien API → nouveau
        if model is not None and core_groups is None:
            profile = ModelProfile(
                name=getattr(model, "name", "Model") or "Model",
                toughness=model.toughness,
                save=model.save,
                wounds=model.wounds,
                invulnerable_save=model.invulnerable_save,
                fnp=model.fnp,
            )
            count = model_count if model_count is not None else 1
            core_groups = [ModelGroup(profile, profile.name, count, count)]

        super().__init__(name=name, core_groups=core_groups or [], keywords=keywords)

        # État des PV par groupe intra-card (parallèle à self.core_groups)
        self.group_states: List[GroupWoundState] = [
            GroupWoundState(
                count=g.max_count,
                current_wounds=g.profile.wounds,
                initial_count=g.max_count,
                initial_wounds=g.profile.wounds,
            )
            for g in self.core_groups
        ]

        # --- Personnages inter-card (leader / support) ---
        self.leader_model = leader_model
        self.leader_alive = leader_model is not None
        self.initial_leader_alive = leader_model is not None
        self.current_leader_wounds = leader_model.wounds if leader_model else 0
        self.initial_leader_wounds = leader_model.wounds if leader_model else 0

        self.support_model = support_model
        self.support_alive = support_model is not None
        self.initial_support_alive = support_model is not None
        self.current_support_wounds = support_model.wounds if support_model else 0
        self.initial_support_wounds = support_model.wounds if support_model else 0

        # --- Règles défensives ---
        self.defensive_rules = defensive_rules or []
        self.damage_reduction = damage_reduction
        self.hit_modifier = hit_modifier
        self.wound_modifier = wound_modifier
        self.wound_minus_one_if_weaker = wound_minus_one_if_weaker
        self.stealth = stealth

    # ------------------------------------------------------------------
    # Propriétés de compatibilité (API ancien → nouveau)
    # ------------------------------------------------------------------

    @property
    def model(self):
        """Profil du premier groupe intra-card (compatibilité avec l'ancien code)."""
        return self.core_groups[0].profile if self.core_groups else None

    @property
    def model_count(self) -> int:
        return self.group_states[0].count if self.group_states else 0

    @model_count.setter
    def model_count(self, value: int):
        if self.group_states:
            self.group_states[0].count = value

    @property
    def current_model_wounds(self) -> int:
        return self.group_states[0].current_wounds if self.group_states else 0

    @current_model_wounds.setter
    def current_model_wounds(self, value: int):
        if self.group_states:
            self.group_states[0].current_wounds = value

    @property
    def initial_model_count(self) -> int:
        return self.group_states[0].initial_count if self.group_states else 0

    # ------------------------------------------------------------------
    # Propriétés calculées
    # ------------------------------------------------------------------

    @property
    def total_model_count(self) -> int:
        """Nombre total de figurines vivantes (tous groupes + personnages)."""
        return (
            sum(s.count for s in self.group_states)
            + (1 if self.support_alive else 0)
            + (1 if self.leader_alive else 0)
        )

    # ------------------------------------------------------------------
    # Réinitialisation entre simulations
    # ------------------------------------------------------------------

    def reset(self):
        """Réinitialise l'état de l'unité avant une nouvelle simulation."""
        for state in self.group_states:
            state.count = state.initial_count
            state.current_wounds = state.initial_wounds
        self.support_alive = self.initial_support_alive
        self.current_support_wounds = self.initial_support_wounds
        self.leader_alive = self.initial_leader_alive
        self.current_leader_wounds = self.initial_leader_wounds
