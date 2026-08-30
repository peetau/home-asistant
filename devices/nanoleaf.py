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


def set_nanoleaf_on(ip, token, zapnuto):
    """
    Zapne nebo vypne panely.

    Tohle je první funkce, která do zařízení ZAPISUJE. Rozdíl proti čtení:
        GET  = "dej mi stav"        -> nic nemění
        PUT  = "nastav tenhle stav" -> mění

    PUT (na rozdíl od POST) znamená "ať je to takhle". Když ho pošleš dvakrát,
    výsledek je stejný jako po jednom - a to je u ovládání světla přesně to,
    co chceš: opakovaný příkaz "buď zapnuto" nic nerozbije.

    Tělo požadavku musí mít stejný tvar, v jakém se stav i čte:
        {"on": {"value": true}}
    """
    url = f"http://{ip}:16021/api/v1/{token}/state"

    # json= zařídí dvě věci: převede slovník na JSON text a přidá hlavičku,
    # která říká "posílám JSON". Ručně by to byly dva kroky.
    odpoved = requests.put(url, json={"on": {"value": bool(zapnuto)}}, timeout=5)
    odpoved.raise_for_status()

    # Nanoleaf na úspěšný zápis vrací prázdnou odpověď s kódem 204
    # ("hotovo, není co vracet"). Není tedy co číst.
    return True


def set_nanoleaf_brightness(ip, token, jas):
    """Nastaví jas panelů (0-100)."""
    # Omezíme rozsah tady, ať se do zařízení nedostane nesmyslná hodnota
    # ani když ji někdo podstrčí ve formuláři.
    jas = max(0, min(100, int(jas)))
    url = f"http://{ip}:16021/api/v1/{token}/state"
    odpoved = requests.put(url, json={"brightness": {"value": jas}}, timeout=5)
    odpoved.raise_for_status()
    return jas


def set_nanoleaf_effect(ip, token, nazev):
    """Přepne na efekt daného jména."""
    # Efekty mají vlastní adresu, ne /state - je to jiná část API.
    url = f"http://{ip}:16021/api/v1/{token}/effects"
    odpoved = requests.put(url, json={"select": nazev}, timeout=5)
    odpoved.raise_for_status()
    return True


def get_nanoleaf_detail(ip, token):
    """
    Vše, co potřebuje detailní stránka - JEDNÍM dotazem.

    Zařízení stejně vrací všechno naráz, takže by bylo zbytečné ptát se
    zvlášť na stav, zvlášť na efekty a zvlášť na rozložení.

    Vrací stav (jako get_nanoleaf_status) plus:
        "efekty"    - seznam všech dostupných efektů
        "rozlozeni" - panely připravené ke kreslení v SVG
    """
    url = f"http://{ip}:16021/api/v1/{token}/"
    odpoved = requests.get(url, timeout=5)
    odpoved.raise_for_status()
    data = odpoved.json()

    return {
        "name": data["name"],
        "on": data["state"]["on"]["value"],
        "brightness": data["state"]["brightness"]["value"],
        "effect": data["effects"]["select"],
        "efekty": sorted(data["effects"]["effectsList"], key=str.lower),
        "rozlozeni": _rozlozeni_na_svg(data["panelLayout"]["layout"]),
    }


def _rozlozeni_na_svg(layout):
    """
    Převede pozice panelů na tvary, které jde nakreslit v SVG.

    Zařízení dává u každého panelu STŘED (x, y), NATOČENÍ ve stupních
    a typ tvaru. Z toho si vrcholy musíme spočítat sami.

    Dvě věci, na které je potřeba dát pozor:

    1) Nanoleaf měří osu y NAHORU (jako v matematice), SVG DOLŮ.
       Proto se y na konci překlápí, jinak by rozložení bylo vzhůru nohama.

    2) Střed trojúhelníku není uprostřed jeho výšky. Vzdálenost od středu
       k vrcholu je strana / odmocnina ze 3 - proto ta konstanta níž.
    """
    import math

    STRANA = layout.get("sideLength", 134)
    polomer = STRANA / math.sqrt(3)      # střed -> vrchol

    tvary = []
    for panel in layout["positionData"]:
        x, y, uhel = panel["x"], panel["y"], panel["o"]

        if panel["shapeType"] == 12:
            # Řídicí jednotka - není to svítící panel, nakreslíme ji
            # jako malý čtvereček, ať je vidět, kde v sestavě sedí.
            r = STRANA / 5
            body = [(x - r, y - r), (x + r, y - r), (x + r, y + r), (x - r, y + r)]
            druh = "ovladac"
        else:
            # Trojúhelník: tři vrcholy po 120 stupních kolem středu.
            body = [
                (x + polomer * math.cos(math.radians(uhel + 90 + k * 120)),
                 y + polomer * math.sin(math.radians(uhel + 90 + k * 120)))
                for k in range(3)
            ]
            druh = "panel"

        tvary.append({"druh": druh, "body": body})

    # Překlopení osy y + posun, aby rozložení začínalo v nule.
    vsechny_y = [b[1] for t in tvary for b in t["body"]]
    vsechny_x = [b[0] for t in tvary for b in t["body"]]
    min_x, max_y = min(vsechny_x), max(vsechny_y)
    okraj = STRANA / 10

    for tvar in tvary:
        prevedene = [(bx - min_x + okraj, max_y - by + okraj)
                     for bx, by in tvar["body"]]
        tvar["body"] = " ".join(f"{bx:.0f},{by:.0f}" for bx, by in prevedene)

        # Řídicí jednotku kreslíme jako zaoblený čtverec, ne mnohoúhelník -
        # vypadá pak jako tlačítko, kterým taky je. Potřebuje k tomu
        # levý horní roh a rozměry, ne seznam vrcholů.
        if tvar["druh"] == "ovladac":
            xs = [bx for bx, _ in prevedene]
            ys = [by for _, by in prevedene]
            tvar["x"] = round(min(xs))
            tvar["y"] = round(min(ys))
            tvar["strana"] = round(max(xs) - min(xs))

    return {
        "tvary": tvary,
        "sirka": round(max(vsechny_x) - min_x + 2 * okraj),
        "vyska": round(max_y - min(vsechny_y) + 2 * okraj),
    }


def get_nanoleaf_paleta(ip, token, nazev_efektu):
    """
    Zjistí barvy, ze kterých je efekt složený.

    Zařízení umí o efektu vrátit jeho definici - my z ní bereme paletu.
    Barvy jsou v HSB (odstín 0-360, sytost 0-100, jas 0-100); převedeme
    je na hex, kterému rozumí prohlížeč.

    Používá se pro NÁHLED v prohlížeči. Panely se přitom vůbec nemění -
    jen se ptáme, jak by efekt vypadal.
    """
    url = f"http://{ip}:16021/api/v1/{token}/effects"
    odpoved = requests.put(
        url,
        json={"write": {"command": "request", "animName": nazev_efektu}},
        timeout=5,
    )
    odpoved.raise_for_status()
    data = odpoved.json()

    return {
        "nazev": data.get("animName", nazev_efektu),
        "typ": data.get("animType", "?"),
        "barvy": [_hsb_na_hex(b["hue"], b["saturation"], b["brightness"])
                  for b in data.get("palette", [])],
    }


def _hsb_na_hex(h, s, b):
    """
    Převede barvu z HSB na hexadecimální zápis pro prohlížeč.

    HSB = odstín (kolem barevného kruhu), sytost (kolik barvy) a jas.
    Prohlížeč chce RGB - tedy kolik je v barvě červené, zelené a modré.
    Převod je standardní vzoreček, ne nic vymyšleného.
    """
    s, b = s / 100, b / 100
    c = b * s                      # sytá složka
    x = c * (1 - abs((h / 60) % 2 - 1))
    m = b - c                      # doplnění do cílového jasu

    trojice = [
        (c, x, 0), (x, c, 0), (0, c, x),
        (0, x, c), (x, 0, c), (c, 0, x),
    ][int(h // 60) % 6]

    return "#" + "".join(f"{round((slozka + m) * 255):02x}" for slozka in trojice)
