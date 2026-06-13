import re
from data.models import ParsedKeywords

# Mots-clés simples → attribut booléen
_SIMPLE = {
    "lethal hits":       "lethal_hits",
    "devastating wounds":"devastating_wounds",
    "twin-linked":       "twin_linked",
    "torrent":           "torrent",
    "blast":             "blast",
    "ignores cover":     "ignores_cover",
    "precision":         "precision",
    "hazardous":         "hazardous",
    "one shot":          "one_shot",
    "assault":           "assault",
    "heavy":             "heavy",
    "pistol":            "pistol",
    "indirect fire":     "indirect_fire",
    "lance":             "lance",
    "psychic":           "psychic",
    "extra attacks":     "extra_attacks",
}

# Mots-clés connus mais spécifiques à une faction/règle exotique → ignorés silencieusement
_IGNORED = {
    "bubblechukka", "conversion", "c'tan power", "dead choppy",
    "harpooned", "hooked", "impaled", "snagged", "plasma warhead",
    "overcharge", "reverberating summons", "psychic assassin", "linked fire",
}


def parse_keywords(description: str) -> ParsedKeywords:
    """
    Parse le champ description d'une arme Wahapedia vers ParsedKeywords.

    Exemples :
        "lethal hits"                     → lethal_hits=True
        "sustained hits 2"                → sustained_hits=2
        "sustained hits d3"               → sustained_hits=2, sustained_hits_is_dice=True
        "anti-infantry 4+"                → anti_keyword='infantry', anti_threshold=4
        "assault, sustained hits 2"       → assault=True, sustained_hits=2
    """
    kw = ParsedKeywords()
    if not description:
        return kw

    parts = [p.strip().lower() for p in description.split(",")]

    for part in parts:
        if not part:
            continue

        # --- Mots-clés simples ---
        if part in _SIMPLE:
            setattr(kw, _SIMPLE[part], True)
            continue

        # --- sustained hits N ou D3 ---
        m = re.fullmatch(r"sustained hits (\d+|d3)", part)
        if m:
            val = m.group(1)
            if val == "d3":
                kw.sustained_hits = 2   # approximation : valeur moyenne arrondie
                kw.sustained_hits_is_dice = True
            else:
                kw.sustained_hits = int(val)
            continue

        # --- rapid fire N (ou D3/D6) ---
        m = re.fullmatch(r"rapid fire (\d+|d\d+(?:\+\d+)?)", part)
        if m:
            val = m.group(1)
            kw.rapid_fire = int(val) if val.isdigit() else 1
            continue

        # --- melta N ---
        m = re.fullmatch(r"melta (\d+)", part)
        if m:
            kw.melta = int(m.group(1))
            continue

        # --- anti-KEYWORD N+ ---
        m = re.fullmatch(r"anti-(.+?) (\d)\+", part)
        if m:
            kw.anti_keyword = m.group(1)
            kw.anti_threshold = int(m.group(2))
            continue

        # --- ignorés silencieusement ---
        if part in _IGNORED:
            continue

        # --- inconnu ---
        kw.unknown.append(part)

    return kw
