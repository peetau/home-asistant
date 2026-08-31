"""
Příprava dat pro graf.

Graf kreslíme sami pomocí SVG - formátu pro vektorovou grafiku, kterému
prohlížeč rozumí přímo. Žádná knihovna, žádný JavaScript.

PROČ SI HO KRESLÍME SAMI: graf je jen přepočet čísel na souřadnice. Když
to jednou uděláš ručně, budeš vědět, co každá hotová knihovna dělá uvnitř -
a nebude to pro tebe černá skříňka.

JAK SVG FUNGUJE: je to plátno se souřadnicemi. Bod [0,0] je vlevo NAHOŘE
a osa y roste SMĚREM DOLŮ (opačně, než jsi zvyklý z matematiky). Proto se
v přepočtu níže od výšky odečítá - vysoká hodnota musí skončit nízko na ose y.

ZÁPORNÉ HODNOTY: tok sítě jde oběma směry a znaménko určuje kterým. Takový
graf potřebuje nulu uprostřed, ne dole - jinak by se odběr ze sítě neměl kam
nakreslit. Osa se proto počítá z rozsahu (od nejmenší po největší hodnotu),
ne jen z maxima. U grafů, které do záporu nejdou, vyjde spodní hranice nula
a všechno zůstane jako dřív.
"""

from datetime import datetime

# Rozměry plátna v jednotkách SVG (ne pixelech - SVG se umí zvětšit
# na jakoukoliv velikost, tohle je jen vnitřní souřadný systém).
SIRKA = 720
VYSKA = 200

# Okraje: místo na popisky os. Uvnitř nich je vlastní kreslicí plocha.
OKRAJ_VLEVO = 48
OKRAJ_VPRAVO = 14
OKRAJ_NAHORE = 12
OKRAJ_DOLE = 26

PLOCHA_SIRKA = SIRKA - OKRAJ_VLEVO - OKRAJ_VPRAVO
PLOCHA_VYSKA = VYSKA - OKRAJ_NAHORE - OKRAJ_DOLE


def _hezke_maximum(hodnota):
    """
    Zaokrouhlí horní hranici osy nahoru na "hezké" číslo.

    Osa končící na 7238 vypadá špatně, osa končící na 8000 dobře.
    Hledáme nejbližší vyšší násobek 1, 2 nebo 5 (krát mocnina deseti) -
    to jsou dělitelé, které dávají čitelné popisky.
    """
    if hodnota <= 0:
        return 1

    # Řád velikosti: pro 7238 vyjde 1000
    rad = 10 ** (len(str(int(hodnota))) - 1)

    for nasobek in (1, 2, 2.5, 5, 10):
        strop = rad * nasobek
        if strop >= hodnota:
            return strop
    return rad * 10


def _cislo(hodnota, desetin):
    """Zapíše číslo česky, s desetinnou čárkou místo tečky."""
    return f"{hodnota:.{desetin}f}".replace(".", ",")


def _cas_na_popisek(text_casu):
    """Z '2026-08-30 01:15:00' udělá '01:15'."""
    return datetime.strptime(text_casu, "%Y-%m-%d %H:%M:%S").strftime("%H:%M")


def priprav(mereni, index_hodnoty, barva, jednotka, delitel=1, desetin=0,
            klic="graf", barva_zaporna=None):
    """
    Převede měření na vše, co šablona potřebuje k nakreslení grafu.

    mereni        - seznam řádků z databáze
    index_hodnoty - který sloupec v řádku kreslíme (1 = výkon, 3 = baterie,
                    4 = spotřeba domu, 5 = tok sítě)
    barva         - barva čáry; předává se jako CSS proměnná
                    (např. "var(--serie-vykon)"), aby se sama
                    přepnula ve světlém i tmavém režimu
    jednotka      - text k popiskům osy y ("kW", "%")
    delitel       - čím hodnotu vydělit (1000 pro převod W na kW)
    desetin       - na kolik desetinných míst popisky zaokrouhlit
    klic          - krátký název grafu; potřebuje ho šablona, aby si
                    dva grafy na jedné stránce nepřebily ořezy
    barva_zaporna - když je zadaná, kreslí se hodnoty pod nulou touhle
                    barvou (u toku sítě: dodávka jednou, odběr druhou)

    Vrací slovník; když nejsou data, vrátí None a šablona to ošetří.
    """
    if not mereni:
        return None

    # Vytáhneme dvojice (čas, hodnota) a rovnou převedeme na cílovou jednotku.
    #
    # Řádky s prázdnou hodnotou VYNECHÁVÁME. Měření z doby, než se začaly
    # sbírat nové veličiny, mají v těch sloupcích prázdno - dopočítávat si
    # je nebudeme a nakreslit nejdou, takže je graf prostě přeskočí.
    dvojice = [(r[0], r[index_hodnoty]) for r in mereni
               if r[index_hodnoty] is not None]
    if not dvojice:
        return None

    casy = [c for c, _ in dvojice]
    hodnoty = [h / delitel for _, h in dvojice]

    # Osa y nikdy neusekne nulu - useknutá osa opticky zveličuje rozdíly
    # a je to klasický klam. Horní hranice se hledá z maxima, spodní jen
    # tehdy, když se vůbec do záporu jde.
    nejvic, nejmin = max(hodnoty), min(hodnoty)
    y_max = _hezke_maximum(nejvic) if nejvic > 0 else 0
    y_min = -_hezke_maximum(-nejmin) if nejmin < 0 else 0
    if y_max == y_min:
        # Samé nuly - ať má osa aspoň nějakou výšku.
        y_max = 1

    # --- Přepočet hodnoty na souřadnice ---
    # x: pozice v pořadí  ->  rovnoměrně po šířce plochy
    # y: hodnota          ->  výška, ale OTOČENĚ (viz vysvětlení v úvodu)
    def x_pro(i):
        if len(hodnoty) == 1:
            return OKRAJ_VLEVO + PLOCHA_SIRKA / 2
        return OKRAJ_VLEVO + (i / (len(hodnoty) - 1)) * PLOCHA_SIRKA

    def y_pro(hodnota):
        # Podíl v rozsahu osy: 0 = úplně dole, 1 = úplně nahoře.
        podil = (hodnota - y_min) / (y_max - y_min)
        return OKRAJ_NAHORE + PLOCHA_VYSKA - podil * PLOCHA_VYSKA

    body = [(x_pro(i), y_pro(h)) for i, h in enumerate(hodnoty)]

    # Čára grafu: "x,y x,y x,y ..." pro SVG prvek <polyline>
    cara = " ".join(f"{x:.1f},{y:.1f}" for x, y in body)

    # Výplň pod čárou: stejná cesta, ale uzavřená k čáře nuly.
    #
    # U grafu, který do záporu nejde, leží nula rovnou na dně a výplň
    # vypadá stejně jako dřív. U toku sítě se nula zvedne doprostřed
    # a výplň se tím sama rozdělí na část nad ní a část pod ní.
    dno = OKRAJ_NAHORE + PLOCHA_VYSKA
    nula = y_pro(0)
    vypln = (f"M {body[0][0]:.1f},{nula:.1f} "
             + " ".join(f"L {x:.1f},{y:.1f}" for x, y in body)
             + f" L {body[-1][0]:.1f},{nula:.1f} Z")

    # --- Popisky osy y ---
    # U obyčejného grafu nula, půlka a maximum. U toku sítě dole minimum,
    # uprostřed nula a nahoře maximum - nula je tam ta důležitá čára,
    # protože odděluje "dodáváme" od "bereme".
    if y_min < 0:
        ukazat = (y_min, 0, y_max)
    else:
        ukazat = (0, y_max / 2, y_max)

    y_popisky = [{"y": y_pro(h), "text": _cislo(h, desetin)} for h in ukazat]

    # --- Popisky osy x: začátek, prostředek, konec ---
    x_popisky = []
    for i in dict.fromkeys([0, len(casy) // 2, len(casy) - 1]):
        x_popisky.append({"x": x_pro(i), "text": _cas_na_popisek(casy[i])})

    # --- Body pro najetí myší ---
    # Neviditelné kroužky s <title>: prohlížeč u nich sám ukáže bublinu
    # s hodnotou. Chudší než opravdový tooltip, ale bez jediného řádku
    # JavaScriptu - a data jsou tím dostupná i pro čtečky obrazovky.
    tecky = [
        {"x": x, "y": y,
         "popis": f"{_cas_na_popisek(casy[i])} — {_cislo(hodnoty[i], desetin)} {jednotka}"}
        for i, (x, y) in enumerate(body)
    ]

    return {
        "sirka": SIRKA,
        "vyska": VYSKA,
        "klic": klic,
        "barva": barva,
        "barva_zaporna": barva_zaporna,
        "jednotka": jednotka,
        "cara": cara,
        "vypln": vypln,
        "y_popisky": y_popisky,
        "x_popisky": x_popisky,
        "tecky": tecky,
        "dno": dno,
        "nula": nula,
        "strop": OKRAJ_NAHORE,
        "vlevo": OKRAJ_VLEVO,
        "vpravo": SIRKA - OKRAJ_VPRAVO,
        "pocet": len(hodnoty),
        "posledni": _cislo(hodnoty[-1], desetin),
        "maximum": _cislo(nejvic, desetin),
        # Poslední hodnota se v hlavičce obarví podle toho, na které
        # straně nuly leží - u toku sítě je to celá informace.
        "barva_posledni": (barva_zaporna if (barva_zaporna and hodnoty[-1] < 0)
                           else barva),
    }
