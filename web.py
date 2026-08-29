r"""
Webové rozhraní domácího asistenta (Flask).

Na rozdíl od main.py, který proběhne a skončí, tenhle soubor spustí
SERVER, který běží pořád a čeká, až si prohlížeč řekne o stránku.

Spuštění (cmd):
    .venv\Scripts\python.exe web.py
pak v prohlížeči:  127.0.0.1:5000

Vzhled stránky je oddělený v souboru templates/dashboard.html (šablona).
Tenhle soubor řeší jen LOGIKU: přečti zařízení a předej data šabloně.
"""

from datetime import datetime

from flask import Flask, render_template

import config
from devices.nanoleaf import get_nanoleaf_status
from devices.solax import get_solax_status

app = Flask(__name__)


def _bezpecne(nacti):
    """
    Zavolá zadanou funkci a vrátí dvojici (data, chyba).

    Když čtení projde:   vrátí (slovník_dat, None)
    Když spadne:         vrátí (None, "text chyby")

    Díky tomu se o try/except staráme na jednom místě a route dole
    zůstane přehledná. Předání funkce jako parametru (nacti) je
    pythonovský zvyk - funkce se dá poslat dál stejně jako číslo.
    """
    try:
        return nacti(), None
    except Exception as chyba:
        return None, str(chyba)


@app.route("/")
def dashboard():
    # Přečteme obě zařízení. lambda je "funkce na jeden řádek bez jména" -
    # tady jen zabalí volání s parametry, aby ho _bezpecne mohlo spustit.
    nanoleaf, nanoleaf_chyba = _bezpecne(
        lambda: get_nanoleaf_status(config.NANOLEAF_IP, config.NANOLEAF_TOKEN))
    solax, solax_chyba = _bezpecne(
        lambda: get_solax_status(config.SOLAX_DONGLE_IP, config.SOLAX_WIFI_SN))

    # render_template vezme šablonu a doplní do ní pojmenovaná data.
    # Co tady pošleme (nanoleaf=...), tím jménem se to v šabloně objeví.
    return render_template(
        "dashboard.html",
        nanoleaf=nanoleaf, nanoleaf_chyba=nanoleaf_chyba,
        solax=solax, solax_chyba=solax_chyba,
        cas=datetime.now().strftime("%H:%M:%S"),
    )


if __name__ == "__main__":
    # debug=True = při chybě ukáže podrobnosti a po změně kódu sám restartuje.
    # V ostrém provozu VYPNOUT (přijde na řadu ve fázi hostingu).
    app.run(debug=True)
