"""
Vstupní bod projektu — tenhle soubor se spouští:

    python main.py

Zeptá se zařízení v domácnosti na jejich aktuální stav a vypíše ho.
"""

import requests

import config
from devices.nanoleaf import get_nanoleaf_status
from devices.solax import get_solax_status


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


def vypis_solax():
    """Načte a vytiskne aktuální stav solární elektrárny."""
    if "sem-patri" in config.SOLAX_WIFI_SN:
        print("SolaX: v config.py chybí registrační číslo dongle")
        return

    # Stejná pojistka jako u Nanoleafu: čtení přes síť může selhat,
    # jedno nedostupné zařízení nesmí shodit celý skript.
    try:
        stav = get_solax_status(config.SOLAX_DONGLE_IP, config.SOLAX_WIFI_SN)
    except (OSError, ValueError, KeyError) as chyba:
        print(f"SolaX: nepodařilo se přečíst stav ({chyba})")
        return

    print("SolaX (solární elektrárna):")
    print(f"  výkon panelů:  {stav['vykon_panelu']} W "
          f"(string 1: {stav['mppt1']} W, string 2: {stav['mppt2']} W)")
    print(f"  výkon střídače:{stav['vykon_stridace']:6} W")
    print(f"  spotřeba domu: {stav['spotreba_domu']:6} W")
    print(f"  tok sítě:      {stav['tok_site']:6} W")
    print(f"  výkon baterie: {stav['vykon_baterie']:6} W")
    print(f"  dnešní výroba: {stav['denni_vyroba']} kWh")
    print(f"  baterie:       {stav['baterie_soc']} % "
          f"({stav['baterie_zbyva']} kWh)")
    print(f"  frekvence:     {stav['frekvence']} Hz")


def main():
    print("=== Domácí asistent ===")
    print()

    vypis_nanoleaf()
    print()
    vypis_solax()


# Tahle podmínka znamená: "spusť main() jen když se soubor spouští přímo,
# ne když ho někdo jen importuje." Je to běžná pythonovská konvence.
if __name__ == "__main__":
    main()
