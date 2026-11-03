"""Importing the test package points the game's data folder at a throwaway directory for the whole run.

Without this, any test that saves a game outside temp_home() writes into the player's real save folder and
rotates their real save into main.bak.json. (tests/test_save_migration.py has a test that fails if this stops working.)
"""
import atexit
import os
import shutil
import tempfile

SANDBOX = tempfile.mkdtemp(prefix="ll_tests_")
os.environ["LAMPLIGHTER_HOME"] = SANDBOX
atexit.register(shutil.rmtree, SANDBOX, True)
