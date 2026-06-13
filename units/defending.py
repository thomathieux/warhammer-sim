# -*- coding: utf-8 -*-
from typing import List, Optional
from units.profiles import DefendingModel


class DefendingUnit:
    def __init__(
        self,
        model: DefendingModel,
        model_count: int,
        leader_model: Optional[DefendingModel] = None,
        support_model: Optional[DefendingModel] = None,
        defensive_rules: Optional[List] = None,
        damage_reduction: int = 0,
        hit_modifier: int = 0,
        wound_modifier: int = 0,
        stealth: bool = False,
        wound_minus_one_if_weaker: bool = False,
        keywords: Optional[List[str]] = None,
    ):
        """
        Représente une unité défensive avec état interne.

        Trois rôles V11 :
          - model / model_count : gardes du corps (bodyguards)
          - support_model       : 2e personnage (Support), doit être attaché
          - leader_model        : personnage principal (Leader)

        Ordre d'allocation (Garde du Corps V11) :
          bodyguards → support → leader
          Les personnages passent toujours après les gardes du corps.
          Le leader est le plus protégé (dernier à recevoir des blessures).

        Save Phase V11 :
          Les saves sont triés du plus bas au plus haut avant allocation.
          Les dice les plus bas (les plus dangereux) vont aux gardes du corps.
          Les dice les plus hauts (les plus faciles à passer) vont aux personnages.
          Chaque personnage est réévalué avec son propre profil de save.
        """
        # --- Gardes du corps ---
        self.model = model
        self.model_count = model_count
        self.initial_model_count = model_count
        self.current_model_wounds = model.wounds

        # --- Support (2e personnage) ---
        self.support_model = support_model
        self.support_alive = support_model is not None
        self.initial_support_alive = support_model is not None
        self.current_support_wounds = support_model.wounds if support_model else 0
        self.initial_support_wounds = support_model.wounds if support_model else 0

        # --- Leader (personnage principal) ---
        self.leader_model = leader_model
        self.leader_alive = leader_model is not None
        self.initial_leader_alive = leader_model is not None
        self.current_leader_wounds = leader_model.wounds if leader_model else 0
        self.initial_leader_wounds = leader_model.wounds if leader_model else 0

        # --- Règles défensives ---
        self.defensive_rules = defensive_rules or []
        self.keywords = [k.upper() for k in (keywords or [])]
        self.damage_reduction = damage_reduction
        self.hit_modifier = hit_modifier
        self.wound_modifier = wound_modifier
        self.wound_minus_one_if_weaker = wound_minus_one_if_weaker
        self.stealth = stealth

    @property
    def total_model_count(self) -> int:
        """Nombre total de figurines vivantes (gardes + support + leader)."""
        return (
            self.model_count
            + (1 if self.support_alive else 0)
            + (1 if self.leader_alive else 0)
        )

    def reset(self):
        """Réinitialise l'unité avant une nouvelle simulation."""
        self.model_count = self.initial_model_count
        self.current_model_wounds = self.model.wounds
        self.support_alive = self.initial_support_alive
        self.current_support_wounds = self.initial_support_wounds
        self.leader_alive = self.initial_leader_alive
        self.current_leader_wounds = self.initial_leader_wounds
