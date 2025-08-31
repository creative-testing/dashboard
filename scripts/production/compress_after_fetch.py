#!/usr/bin/env python3
"""Compat wrapper: délègue à scripts/transform_to_columnar.py.
Évite les soucis de symlink (Windows, archives, CI/CD)."""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPTS_DIR = os.path.dirname(HERE)  # .../scripts
sys.path.insert(0, SCRIPTS_DIR)

try:
    import transform_to_columnar as t2c
except Exception as e:
    sys.stderr.write(f"❌ Impossible d'importer transform_to_columnar depuis {SCRIPTS_DIR}: {e}\n")
    sys.exit(1)

if __name__ == "__main__":
    # Passe les mêmes arguments à transform_to_columnar.main()
    t2c.main()