"""
Příprava diagramu toku energie.

Diagram ukazuje, kudy zrovna teče proud: z panelů do střídače, ze střídače
do baterie nebo z ní, do domu a do sítě nebo ze sítě. Kreslí se ve vlastním
SVG, stejně jako graf v graf.py - žádná knihovna, žádný JavaScript.

JAK SE POZNÁ SMĚR: u baterie a u sítě rozhoduje ZNAMÉNKO hodnoty z dongle.
Kladný tok sítě znamená, že přetoky dodáváme ven, záporný že si bereme.
Kladný výkon baterie znamená nabíjení, záporný vybíjení. Bez toho by byl
diagram k ničemu - čísla by seděla, ale šipky by ukazovaly náhodně.

JAK SE ŠIPKA OTOČÍ: mohli bychom nechat čáru na místě a přehazovat, na
kterém konci je hrot. Jednodušší je OTOČIT SAMOTNOU ČÁRU - když teče proud
opačně, prohodíme počáteční a koncový bod. Šablona pak vždycky kreslí totéž
(od začátku ke konci, hrot na konci) a o směru nemusí vědět vůbec nic.

SOUŘADNICE: SVG má bod [0,0] vlevo NAHOŘE a osa y roste SMĚREM DOLŮ.
Rozvržení odpovídá předloze ze SolaX aplikace: panely nahoře, pod nimi
střídač, vedle něj baterie, dole rozvaděč a z něj síť a dům.
"""

# Rozměry plátna ve vnitřních jednotkách SVG. Šířka je zvolená tak, aby
# na největší velikosti (viz .diagram v style.css) vycházela jednotka
# zhruba na pixel - popisky pak mají čitelnou velikost i na mobilu.
SIRKA = 460
VYSKA = 420

# Výřez, který se z plátna doopravdy ukáže (levý okraj, horní okraj,
# šířka, výška). Kresba nesahá až ke krajům plátna - kolem dokola zbývá
# pruh prázdna. Oříznutím se na stejném místě vykreslí zhruba o desetinu
# větší, což se hodí hlavně na mobilu, kde jsou popisky u hranice
# čitelnosti. Čísla jsou schválně o kus volnější než skutečné okraje
# kresby, aby delší hodnota ("12,34 kW") neměla kam vylézt.
VYREZ = "14 24 404 392"

# Středy jednotlivých uzlů (ikon).
UZLY_POZICE = {
    "panely":   (175, 56),
    "stridac":  (175, 168),
    "baterie":  (370, 168),
    "rozvadec": (175, 250),
    "sit":      (70, 340),
    "dum":      (300, 340),
}

# Čáry mezi uzly. Body jsou posunuté od středů tak, aby čára začínala
# až za okrajem ikony a nekřížila ji.
#
# Pořadí bodů je "výchozí směr": kterým směrem čára vede, když je hodnota
# kladná. U záporné se body prohodí (viz vysvětlení v úvodu).
SPOJE_BODY = {
    "vyroba":  ((175, 86), (175, 138)),
    "baterie": ((208, 168), (342, 168)),
    "ac":      ((175, 198), (175, 236)),
    "sit":     ((162, 264), (88, 314)),
    "dum":     ((188, 264), (282, 314)),
}

# Pod kolika watty považujeme tok za nulový.
#
# Střídač i v klidu něco málo přehazuje sem a tam a čáry by kvůli tomu
# blikaly a měnily směr. Dvacet wattů je pod rozlišovací schopností
# čehokoliv, co nás zajímá.
KLID = 20


def _vykon(watty):
    """
    Naformátuje výkon pro člověka.

    Do jednoho kilowattu ve wattech (přesnější a kratší: '556 W'),
    od kilowattu výš v kW na dvě desetinná místa ('6,90 kW').
    Znaménko zahazujeme - směr ukazuje šipka, ne mínus u čísla.

    Desetinnou tečku měníme na čárku, protože česky se píše čárka
    a Python ji sám nenapíše.
    """
    w = abs(int(watty))
    if w < 1000:
        return f"{w} W"
    return f"{w / 1000:.2f}".replace(".", ",") + " kW"


def _spoj(klic, hodnota, popis_tam, popis_zpet, popis_klid):
    """
    Připraví jednu čáru: kudy vede, jestli něco teče a co říct v bublině.

    hodnota      - výkon se znaménkem [W]
    popis_tam    - text, když je hodnota kladná (teče po směru čáry)
    popis_zpet   - text, když je záporná (čára se otočí)
    popis_klid   - text, když neteče prakticky nic
    """
    zacatek, konec = SPOJE_BODY[klic]

    if abs(hodnota) < KLID:
        aktivni, popis = False, popis_klid
    elif hodnota > 0:
        aktivni, popis = True, f"{popis_tam} {_vykon(hodnota)}"
    else:
        # Tady se čára otáčí - prohozením bodů. Šipka i animace pak
        # samy ukazují opačným směrem, aniž by to šablona řešila.
        zacatek, konec = konec, zacatek
        aktivni, popis = True, f"{popis_zpet} {_vykon(hodnota)}"

    return {
        "klic": klic,
        "cesta": f"M {zacatek[0]},{zacatek[1]} L {konec[0]},{konec[1]}",
        "aktivni": aktivni,
        "popis": popis,
    }


def priprav(sx):
    """
    Ze stavu soláru udělá vše, co šablona potřebuje k nakreslení diagramu.

    sx - slovník z get_solax_status()

    Vrací slovník s rozměry plátna, uzly (pozice + čísla u nich) a spoji
    (čáry i s určeným směrem). Když se solár nepodařilo přečíst, diagram
    se vůbec nepřipravuje - o to se stará web.py.
    """
    uzly = {}
    for nazev, (x, y) in UZLY_POZICE.items():
        uzly[nazev] = {"x": x, "y": y}

    # Čísla u uzlů. Střídač a rozvaděč schválně žádné nemají - jsou to
    # průchozí body, ne zdroje ani spotřebiče, a číslo u nich by jen
    # opakovalo to, co už je vidět na čarách kolem.
    uzly["panely"]["hodnota"] = _vykon(sx["vykon_panelu"])
    uzly["baterie"]["hodnota"] = _vykon(sx["vykon_baterie"])
    uzly["sit"]["hodnota"] = _vykon(sx["tok_site"])
    uzly["dum"]["hodnota"] = _vykon(sx["spotreba_domu"])

    # Názvy pod ikonami. U baterie a sítě k nim přidáváme, co se zrovna
    # děje - šipka na čáře to sice ukazuje taky, ale slovo se přečte
    # rychleji a hlavně ho uslyší i čtečka obrazovky.
    uzly["panely"]["popisek"] = "Panely"
    uzly["stridac"]["popisek"] = "Střídač"
    uzly["dum"]["popisek"] = "Dům"
    uzly["baterie"]["popisek"] = "Baterie"
    uzly["baterie"]["soc"] = sx["baterie_soc"]

    if sx["tok_site"] > KLID:
        uzly["sit"]["popisek"] = "Síť · dodávka"
    elif sx["tok_site"] < -KLID:
        uzly["sit"]["popisek"] = "Síť · odběr"
    else:
        uzly["sit"]["popisek"] = "Síť"

    spoje = [
        _spoj("vyroba", sx["vykon_panelu"],
              "Panely vyrábějí", "", "Panely nevyrábějí"),
        _spoj("ac", sx["vykon_stridace"],
              "Střídač dodává", "Střídač odebírá", "Střídač stojí"),
        _spoj("baterie", sx["vykon_baterie"],
              "Baterie se nabíjí", "Baterie se vybíjí", "Baterie odpočívá"),
        _spoj("sit", sx["tok_site"],
              "Do sítě dodáváme", "Ze sítě bereme", "Se sítí si nic neměníme"),
        _spoj("dum", sx["spotreba_domu"],
              "Dům spotřebovává", "", "Dům nespotřebovává nic"),
    ]

    return {
        "sirka": SIRKA,
        "vyska": VYSKA,
        "vyrez": VYREZ,
        "uzly": uzly,
        "spoje": spoje,
        # Krátké shrnutí pro čtečky obrazovky. Ty z obrázku nic nepřečtou,
        # takže jim rovnou řekneme, co je na něm vidět.
        "shrnuti": ("Tok energie: " + ", ".join(s["popis"] for s in spoje)
                    + f". Baterie nabitá na {sx['baterie_soc']} %."),
    }
