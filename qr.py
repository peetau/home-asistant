"""
QR kód pro sdílení adresy aplikace.

Knihovna segno spočítá matici čtverečků; SVG si z ní kreslíme sami -
stejně jako u grafu a rozložení panelů. Díky tomu se barva řídí motivem
(currentColor), což hotový obrázek z knihovny neumí.
"""

import segno

# Bílý rám kolem kódu. Čtečky ho potřebují, aby kód našly v okolí.
# Norma doporučuje 4 moduly, 2 stačí a šetří místo.
OKRAJ = 2


def qr_pro_svg(text):
    """
    Vrátí obdélníky pro nakreslení QR kódu v SVG.

    Sousední tmavé čtverečky v řádku slučujeme do jednoho obdélníku -
    místo ~700 samostatných čtverců jich pak stačí zhruba polovina
    a stránka je menší.

    Vrací:
        {"strana": 41, "obdelniky": [{"x": 2, "y": 2, "sirka": 7}, ...]}
    """
    matice = list(segno.make(text, error="m").matrix)
    velikost = len(matice)

    obdelniky = []
    for y, radek in enumerate(matice):
        x = 0
        while x < velikost:
            if not radek[x]:
                x += 1
                continue
            # Našli jsme tmavý čtvereček - najdeme, kam až souvislý pruh sahá
            zacatek = x
            while x < velikost and radek[x]:
                x += 1
            obdelniky.append({
                "x": zacatek + OKRAJ,
                "y": y + OKRAJ,
                "sirka": x - zacatek,
            })

    return {"strana": velikost + 2 * OKRAJ, "obdelniky": obdelniky}
