import unittest

from lamplighter.content import ROOMS
from lamplighter.validate import validate


class ContentTests(unittest.TestCase):
    def test_content_has_no_broken_references(self):
        self.assertEqual(validate(), [])

    def test_room_positions_are_tuples(self):
        for rid, room in ROOMS.items():
            self.assertIsInstance(room["pos"], tuple, rid)


if __name__ == "__main__":
    unittest.main()
