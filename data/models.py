from dataclasses import dataclass, field
from typing import Optional, List, Tuple


@dataclass
class ParsedKeywords:
    """Mots-clés d'arme Wahapedia structurés, prêts pour le moteur de simulation."""

    # Phases de combat
    lethal_hits: bool = False
    sustained_hits: int = 0           # 0 = désactivé, N = N hits supplémentaires par critique
    sustained_hits_is_dice: bool = False  # True si D3 (sustained_hits contient la valeur moyenne)
    devastating_wounds: bool = False
    twin_linked: bool = False         # relance des blessures ratées (géré → wound_reroll)

    # Auto-touche
    torrent: bool = False

    # Modificateurs de portée (non simulés — pas de tracking de portée)
    rapid_fire: int = 0
    rapid_fire_str: str = ""   # non vide quand la valeur est un dé (ex: "d3", "d6+3")
    melta: int = 0
    assault: bool = False
    heavy: bool = False
    pistol: bool = False
    indirect_fire: bool = False

    # Autres effets de combat
    blast: bool = False
    ignores_cover: bool = False
    precision: bool = False           # pas encore simulé
    hazardous: bool = False           # pas encore simulé
    one_shot: bool = False            # pas encore simulé
    lance: bool = False               # pas encore simulé
    psychic: bool = False             # pas encore simulé
    extra_attacks: bool = False       # pas encore simulé

    # Anti-mot-clé (ex: anti-infantry 4+)
    anti_keyword: Optional[str] = None
    anti_threshold: Optional[int] = None

    # Mots-clés non reconnus (pour debug)
    unknown: List[str] = field(default_factory=list)


@dataclass
class WeaponProfile:
    name: str
    range: str           # "24" ou "Melee"
    type: str            # "Ranged" ou "Melee"
    attacks: str         # brut : "2", "D3", "D6+1"
    skill: int           # 3 pour 3+, 4 pour 4+
    strength: int
    ap: int              # valeur réelle : -1 pour AP -1, 0 pour AP 0
    damage: str          # brut : "1", "D3", "D6"
    keywords: ParsedKeywords = field(default_factory=ParsedKeywords)
    quantity: int = 1  # nb d'exemplaires portés par l'unité (ex: 2 pour "2 hurricane bolters")


@dataclass
class UnitModel:
    name: str
    movement: str                          # "5\""
    toughness: int
    save: int                              # 3 pour 3+
    invulnerable_save: Optional[int] = None  # None si pas d'invulnérable
    wounds: int = 1
    leadership: int = 7
    oc: int = 1
    base_size: str = ""


@dataclass
class WahapediaUnit:
    id: str
    name: str
    faction_id: str
    link: str
    models: List[UnitModel] = field(default_factory=list)
    weapons: List[WeaponProfile] = field(default_factory=list)
    abilities: List[dict] = field(default_factory=list)  # {name, description, type}
    min_models: int = 1
    max_models: int = 1
    costs: List[dict] = field(default_factory=list)      # [{description, cost}]
    keywords: List[str] = field(default_factory=list)
    model_composition: List[Tuple[int, int, int]] = field(default_factory=list)
    # [(model_index, min_count, max_count)] trié par max_count décroissant

    def get_weapon(self, name: str) -> Optional[WeaponProfile]:
        name_lower = name.lower()
        for w in self.weapons:
            if w.name.lower() == name_lower:
                return w
        return None

    def ranged_weapons(self) -> List[WeaponProfile]:
        return [w for w in self.weapons if w.type == "Ranged"]

    def melee_weapons(self) -> List[WeaponProfile]:
        return [w for w in self.weapons if w.type == "Melee"]

    def primary_model(self) -> Optional[UnitModel]:
        return self.models[0] if self.models else None
