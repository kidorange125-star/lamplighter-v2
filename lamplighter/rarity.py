"""Item rarity: names, symbols and colours. Every tier has a symbol AND a word, so colour is never the only signal."""
from .content import ITEMS

RARITIES = ["common", "uncommon", "rare", "epic", "ultra", "legendary", "godlike"]
INFO = {
    "common": {"name": "Common", "symbol": "", "colour": "white"},
    "uncommon": {"name": "Uncommon", "symbol": "◇", "colour": "bgreen"},
    "rare": {"name": "Rare", "symbol": "◆", "colour": "bblue"},
    "epic": {"name": "Epic", "symbol": "◆◆", "colour": "hollow"},
    "ultra": {"name": "Ultra", "symbol": "◈", "colour": "bmagenta"},
    "legendary": {"name": "Legendary", "symbol": "✦", "colour": "gold"},
    "godlike": {"name": "Godlike", "symbol": "✦✦", "colour": "bcyan"},
}


def rarity_of(iid):
    return ITEMS[iid].get("rarity", "common")


def label(iid):
    """A coloured item name with its rarity symbol, ready for ui.say."""
    info = INFO[rarity_of(iid)]
    sym = (" " + info["symbol"]) if info["symbol"] else ""
    return "{%s}%s%s{/}" % (info["colour"], ITEMS[iid]["name"], sym)


def describe_name(tier):
    info = INFO[tier]
    return "{%s}%s%s{/}" % (info["colour"], info["name"], (" " + info["symbol"]) if info["symbol"] else "")


def describe(iid):
    info = INFO[rarity_of(iid)]
    return "{%s}%s%s{/}" % (info["colour"], info["name"], (" " + info["symbol"]) if info["symbol"] else "")
