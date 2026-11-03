"""Add a redeemable code to the game.

usage: python tools/make_code.py CODE GEMS "label shown to the player"
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from lamplighter.codes import code_hash  # noqa: E402

path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "lamplighter", "data", "codes.json")
if len(sys.argv) != 4:
    sys.exit(__doc__)
code, gems, label = sys.argv[1], int(sys.argv[2]), sys.argv[3]
data = json.load(open(path, encoding="utf-8"))
data[code_hash(code)] = {"gems": gems, "label": label}
with open(path, "w", encoding="utf-8", newline="\n") as f:
    json.dump(data, f, indent=1)
    f.write("\n")
print("added %s: %d gems" % (code.upper(), gems))
