"""
Jednorázový pomocník: vygeneruje Nanoleaf token.

Tenhle skript spustíš JEDNOU. Až budeš mít token v config.py,
už ho nikdy nepotřebuješ (klidně ho pak smažeme).

POSTUP:
  1) Jdi k panelu a podrž tlačítko napájení 5-7 sekund,
     dokud LED nezačne blikat. Tím se panel na ~30 sekund
     přepne do párovacího režimu.
  2) Hned potom spusť:  python ziskej_token.py
  3) Vypsaný token zkopíruj do config.py
"""

import requests   # knihovna na posílání HTTP dotazů
import config     # náš soubor s IP adresou


def main():
    # Adresa, na kterou se ptáme. Koncovka /new znamená
    # "chci nový token" - tak je to popsané v dokumentaci Nanoleafu.
    url = f"http://{config.NANOLEAF_IP}:16021/api/v1/new"

    print(f"Posílám požadavek na {url} ...")

    # POST, ne GET - a to je důležitý rozdíl:
    #   GET  = "dej mi data" (nic nemění, jen čte)
    #   POST = "vytvoř/proveď něco" (mění stav na druhé straně)
    # Tady chceme, aby panel VYROBIL nový token, proto POST.
    #
    # timeout=5 znamená "když se do 5 sekund neozve, vzdej to".
    # Bez něj by skript mohl viset donekonečna.
    try:
        odpoved = requests.post(url, timeout=5)
    except requests.exceptions.RequestException as chyba:
        print(f"Nepodařilo se spojit s panelem: {chyba}")
        print("Je panel zapnutý a na stejné Wi-Fi? Sedí IP v config.py?")
        return

    # Každá HTTP odpověď má číselný stavový kód. Pár, které potkáš:
    #   200 = OK, mám pro tebe data
    #   401 = nepustím tě dál (chybí/neplatné oprávnění)
    #   404 = taková adresa neexistuje
    print(f"Panel odpověděl kódem: {odpoved.status_code}")

    if odpoved.status_code == 200:
        # Odpověď je text ve formátu JSON. Metoda .json() ho převede
        # na obyčejný pythonovský slovník (dict), se kterým se dá pracovat.
        data = odpoved.json()
        token = data["auth_token"]

        print()
        print("HOTOVO! Tvůj token je:")
        print()
        print(f"    {token}")
        print()
        print("Zkopíruj ho do config.py na řádek NANOLEAF_TOKEN.")
    else:
        print()
        print("Token se nepodařilo získat.")
        print("Nejčastější důvod: panel zrovna není v párovacím režimu.")
        print("Podrž tlačítko napájení 5-7 s a spusť skript do 30 sekund.")


if __name__ == "__main__":
    main()
