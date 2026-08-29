"""
Čtení stavu Nanoleaf panelů.

Nanoleaf má REST API přímo v zařízení — mluvíme s ním po domácí síti,
žádný cloud, žádný internet. Adresa vypadá takto:

    http://<IP-panelu>:16021/api/v1/<token>/

Když na ni pošleme GET, panel vrátí JSON s kompletním popisem sebe sama:
jméno, model, rozložení panelů, seznam efektů, aktuální stav. My si z toho
vybereme jen to, co nás zajímá.
"""

import requests


def get_nanoleaf_status(ip, token):
    """
    Zjistí aktuální stav Nanoleaf panelů.

    Vrací slovník:
        {
            "name": "Shapes E019",   # jméno zařízení
            "on": False,             # svítí / nesvítí
            "brightness": 31,        # jas 0-100
            "effect": "Dark cycle",  # název právě zvoleného efektu
        }

    Když se spojení nepovede nebo panel odmítne token,
    vyhodí výjimku (requests.exceptions.RequestException).
    """
    # Sestavíme adresu. Token je součástí URL - tak to Nanoleaf chce.
    url = f"http://{ip}:16021/api/v1/{token}/"

    # GET = "dej mi data, nic neměň". Tohle je opak POSTu,
    # kterým jsme v ziskej_token.py token vyráběli.
    odpoved = requests.get(url, timeout=5)

    # raise_for_status() je pojistka: když panel odpoví chybou
    # (401 = špatný token, 404 = špatná adresa...), skript se zastaví
    # a řekne proč. Bez ní bychom se dole snažili číst data,
    # která vůbec nedorazila, a spadli bychom na nesrozumitelné chybě.
    odpoved.raise_for_status()

    # .json() převede textovou odpověď na pythonovský slovník.
    data = odpoved.json()

    # A teď to hlavní: prokousat se zanořením k hodnotám, které chceme.
    # Panel nám poslal desítky údajů, my si bereme čtyři.
    #
    # Pozor na tvar: "on" není rovnou True/False, ale slovník {"value": ...}.
    # Proto ty dvoje hranaté závorky.
    return {
        "name": data["name"],
        "on": data["state"]["on"]["value"],
        "brightness": data["state"]["brightness"]["value"],
        "effect": data["effects"]["select"],   # efekt je jinde než zbytek stavu
    }
