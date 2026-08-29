"""
Webové rozhraní domácího asistenta (Flask).

Na rozdíl od main.py, který proběhne a skončí, tenhle soubor spustí
SERVER, který běží pořád a čeká, až si prohlížeč řekne o stránku.

Spuštění:
    python web.py

Pak otevři v prohlížeči:
    http://127.0.0.1:5000

(127.0.0.1 = "tenhle počítač", 5000 = číslo dveří, na kterých Flask
ve výchozím stavu poslouchá. Prohlížeč zaklepe sem.)
"""

from flask import Flask

import config
from devices.nanoleaf import get_nanoleaf_status
from devices.solax import get_solax_status

# Tímhle řádkem vznikne aplikace. __name__ Flasku říká, kde je "doma"
# (podle toho pak hledá šablony a soubory). Ber to zatím jako rituál.
app = Flask(__name__)


# @app.route("/") je "dekorátor" - nálepka nad funkcí, která Flasku říká:
# "když někdo přijde na adresu /, zavolej tuhle funkci". Cokoliv funkce
# vrátí (text/HTML), pošle Flask prohlížeči jako stránku.
#
# Dekorátor je pro tebe nový, tak jen tolik: je to způsob, jak funkci
# něco "přilepit", aniž bys měnil její tělo. Tady tím lepíme adresu.
@app.route("/")
def dashboard():
    # Čtení zařízení může selhat (zařízení offline, jiná Wi-Fi...).
    # Na webu je to o to důležitější: nechceme prohlížeči poslat ošklivou
    # chybovou stránku, jen napíšeme, že se stav nepovedlo načíst.
    # Proto každé čtení zabalíme a případnou chybu si schováme do textu.
    try:
        nl = get_nanoleaf_status(config.NANOLEAF_IP, config.NANOLEAF_TOKEN)
        nanoleaf_html = f"""
            <p>Stav: {"zapnuto" if nl["on"] else "vypnuto"}</p>
            <p>Jas: {nl["brightness"]} %</p>
            <p>Efekt: {nl["effect"]}</p>
        """
    except Exception as chyba:
        nanoleaf_html = f"<p>Nepodařilo se načíst: {chyba}</p>"

    try:
        sx = get_solax_status(config.SOLAX_DONGLE_IP, config.SOLAX_WIFI_SN)
        solax_html = f"""
            <p>Výkon panelů: {sx["vykon_panelu"]} W</p>
            <p>Do sítě/domu: {sx["vykon_do_site"]} W</p>
            <p>Dnešní výroba: {sx["denni_vyroba"]} kWh</p>
            <p>Baterie: {sx["baterie_soc"]} % ({sx["baterie_zbyva"]} kWh)</p>
        """
    except Exception as chyba:
        solax_html = f"<p>Nepodařilo se načíst: {chyba}</p>"

    # Sestavíme celou stránku jako jeden kus HTML. Zatím "ručně" v Pythonu -
    # ve větším projektu by tohle patřilo do zvláštního souboru (šablony),
    # k tomu se dostaneme jako k dalšímu kroku.
    return f"""
    <!doctype html>
    <html lang="cs">
    <head>
        <meta charset="utf-8">
        <title>Domácí asistent</title>
    </head>
    <body>
        <h1>Domácí asistent</h1>

        <h2>Nanoleaf</h2>
        {nanoleaf_html}

        <h2>Solární elektrárna</h2>
        {solax_html}
    </body>
    </html>
    """


if __name__ == "__main__":
    # debug=True = při chybě ukáže podrobnosti přímo v prohlížeči a po každé
    # změně kódu server sám restartuje. Skvělé při vývoji, VYPNOUT v ostrém
    # provozu (prozrazuje vnitřnosti aplikace).
    app.run(debug=True)
