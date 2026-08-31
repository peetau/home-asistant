r"""
Sběrač měření — plní databázi daty ze solární elektrárny.

Běží pořád dokola: přečte solár, uloží řádek, počká, opakuje.
Spusť ho v samostatném okně a nech běžet vedle webu:

    .venv\Scripts\python.exe sber.py

Ve výchozím stavu měří každých 5 minut. Pro rychlé vyzkoušení můžeš
interval zkrátit číslem v sekundách:

    .venv\Scripts\python.exe sber.py 10      (měří každých 10 s)

Zastavíš ho Ctrl+C.
"""

import sys
import time
from datetime import datetime

import config
import database
from devices.solax import get_solax_status

# Jak často měřit (v sekundách). 300 s = 5 minut.
# Když skript spustíš s číslem za názvem, přepíše se tímhle (viz úvod).
INTERVAL_SEKUND = 300


def zmer_a_uloz():
    """
    Jedno kolo: přečte solár a uloží ho jako řádek do databáze.

    Vrátí dvojici (čas, naměřené hodnoty) pro výpis, nebo vyhodí výjimku,
    když se čtení nepovede - o tu se postará volající ve smyčce.
    """
    sx = get_solax_status(config.SOLAX_DONGLE_IP, config.SOLAX_WIFI_SN)
    cas = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    database.uloz_mereni(
        cas=cas,
        vykon_panelu=sx["vykon_panelu"],
        denni_vyroba=sx["denni_vyroba"],
        baterie_soc=sx["baterie_soc"],
        spotreba_domu=sx["spotreba_domu"],
        tok_site=sx["tok_site"],
        vykon_baterie=sx["vykon_baterie"],
    )
    return cas, sx


def main():
    # Umožníme zadat interval jako argument: python sber.py 10
    interval = INTERVAL_SEKUND
    if len(sys.argv) > 1:
        interval = int(sys.argv[1])

    # Než začneme sbírat, ujistíme se, že tabulka existuje.
    database.init_db()

    print(f"Sběrač spuštěn. Měřím každých {interval} s. Zastav Ctrl+C.")
    print()

    # Nekonečná smyčka - tohle je ten "server, který běží pořád".
    while True:
        try:
            cas, sx = zmer_a_uloz()
            # {:+} znamená "vypiš i znaménko plus". U sítě a baterie je
            # to podstatné - z holého čísla by nebylo poznat, jestli se
            # do sítě dodává, nebo se z ní bere.
            print(f"[{cas}] panely {sx['vykon_panelu']} W, "
                  f"dům {sx['spotreba_domu']} W, "
                  f"síť {sx['tok_site']:+} W, "
                  f"baterie {sx['vykon_baterie']:+} W ({sx['baterie_soc']} %)",
                  flush=True)
        except Exception as chyba:
            # Zařízení možná chvíli neodpovědělo. Nevadí - napíšeme to
            # a jedeme dál. Jeden výpadek nesmí shodit celý sběr.
            teed = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            print(f"[{teed}] chyba čtení, přeskakuji: {chyba}", flush=True)

        # Počkáme do dalšího měření. time.sleep uspí program na daný počet sekund.
        time.sleep(interval)


if __name__ == "__main__":
    main()
