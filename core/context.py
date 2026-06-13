from dataclasses import dataclass, field


@dataclass
class CombatContext:
    """
    Conditions contextuelles d'un round de combat.

    Ces paramètres ne peuvent pas être déduits automatiquement depuis les
    données de l'unité — ils dépendent de l'état de la partie et sont
    déclarés explicitement par l'utilisateur avant la simulation.
    """

    combat_type: str = "ranged"
    """'ranged' ou 'melee' — détermine quels groupes d'armes sont actifs."""

    unit_moved: bool = False
    """L'unité attaquante s'est déplacée ce tour.
    Effets : Heavy (-1 touche si True), Assault (annule le malus si True)."""

    within_half_range: bool = False
    """La cible est dans la moitié de la portée de l'arme.
    Effets : Rapid Fire +N attaques, Melta +N dégâts."""

    target_in_cover: bool = False
    """La cible bénéficie d'une couverture (+1 à sa sauvegarde d'armure)."""

    attacker_charged: bool = False
    """L'unité attaquante a chargé ce tour.
    Effets : Lance (ignore les saves invulnérables sur 6+ en blessure)."""
