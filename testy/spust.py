# -*- coding: utf-8 -*-
r"""
Pustí všechny testy najednou a vypíše souhrn.

    .venv\Scripts\python.exe testy\spust.py

Skončí s návratovým kódem 1, když něco spadlo - podle toho se dá poznat
neúspěch i bez čtení výpisu.
"""

import os
import sys

# Aby šlo `import spolecne` i při spuštění odjinud než ze složky testy.
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import spolecne  # noqa: E402  (musí být první, přepíná na dočasnou databázi)
import test_domacnost  # noqa: E402
import test_nakup  # noqa: E402
import test_prihlaseni  # noqa: E402
import test_registrace  # noqa: E402
import test_sprava  # noqa: E402
import test_spojeni  # noqa: E402
import test_stranky  # noqa: E402

SOUBORY = [
    (test_spojeni, "Spojení s databází"),
    (test_prihlaseni, "Strop na přihlašování"),
    (test_domacnost, "Domácnost"),
    (test_registrace, "Registrace"),
    (test_sprava, "Správa"),
    (test_nakup, "Nákup"),
    (test_stranky, "Stránky"),
]


def main():
    celkem = 0
    spadlo_celkem = 0

    for modul, nazev in SOUBORY:
        kolik, spadlo = spolecne.spust(vars(modul), nazev)
        celkem += kolik
        spadlo_celkem += spadlo
        print("")

    if spadlo_celkem:
        print("SPADLO %d z %d testů." % (spadlo_celkem, celkem))
        return 1

    print("Všech %d testů prošlo." % celkem)
    return 0


if __name__ == "__main__":
    sys.exit(main())
