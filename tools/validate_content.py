"""Check all game content for broken references. Exit code 1 if anything is wrong.

usage: python tools/validate_content.py
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from lamplighter import content  # noqa: E402
from lamplighter.validate import validate  # noqa: E402

errors = validate()
if errors:
    print("%d problem(s):" % len(errors))
    for e in errors:
        print("  -", e)
    sys.exit(1)
print("content OK: %d rooms, %d items, %d enemies, %d regions" % (
    len(content.ROOMS), len(content.ITEMS), len(content.ENEMIES), len(content.REGIONS)))
