"""The six elements and how to show them. Combat uses these for weaknesses and resistances."""

ELEMENTS = ["fire", "ice", "water", "light", "shadow", "earth"]
INFO = {
    "fire": {"name": "Fire", "colour": "flame"},
    "ice": {"name": "Ice", "colour": "sky"},
    "water": {"name": "Water", "colour": "bblue"},
    "light": {"name": "Light", "colour": "byellow"},
    "shadow": {"name": "Shadow", "colour": "hollow"},
    "earth": {"name": "Earth", "colour": "moss"},
    "all": {"name": "All", "colour": "bwhite"},
}


def tag(element):
    info = INFO[element]
    return "{%s}%s{/}" % (info["colour"], info["name"])


def tags(elements):
    return " ".join(tag(e) for e in elements)
