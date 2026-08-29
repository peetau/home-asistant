"""
Vstupní bod projektu — tenhle soubor se spouští:

    python main.py

Zeptá se zařízení v domácnosti na jejich aktuální stav a vypíše ho.
"""

import requests

import config
from devices.nanoleaf import get_nanoleaf_status


def vypis_nanoleaf():
    """Načte a vytiskne stav Nanoleaf panelů."""
    # Nejdřív ověříme, že vůbec máme co poslat. Kdybychom to neudělali,
    # dostali bychom od panelu 401 a museli hádat, čím to je.
    if "sem-patri" in config.NANOLEAF_TOKEN:
        print("Nanoleaf: v config.py chybí token")
        return

    # Volání přes síť může selhat spoustou způsobů: panel je vypnutý,
    # jsi na jiné Wi-Fi, token přestal platit. Proto try/except —
    # jedno nedostupné zařízení nesmí shodit celý skript.
    try:
        stav = get_nanoleaf_status(config.NANOLEAF_IP, config.NANOLEAF_TOKEN)
    except requests.exceptions.RequestException as chyba:
        print(f"Nanoleaf: nepodařilo se přečíst stav ({chyba})")
        return

    # Hodnota "on" je True/False. Pro výpis ji přeložíme do lidštiny.
    svitit = "zapnuto" if stav["on"] else "vypnuto"

    print(f"Nanoleaf ({stav['name']}):")
    print(f"  stav:  {svitit}")
    print(f"  jas:   {stav['brightness']} %")
    print(f"  efekt: {stav['effect']}")


def main():
    print("=== Domácí asistent ===")
    print()

    vypis_nanoleaf()

    print()
    print("Další krok: Úkol B — čtení výkonu solárů ze SolaX.")


# Tahle podmínka znamená: "spusť main() jen když se soubor spouští přímo,
# ne když ho někdo jen importuje." Je to běžná pythonovská konvence.
if __name__ == "__main__":
    main()
