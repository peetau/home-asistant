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

from functools import wraps

from flask import Flask, render_template, request, redirect, url_for, session

import config
import database
import graf
from devices.nanoleaf import get_nanoleaf_status
from devices.solax import get_solax_status

app = Flask(__name__)

# Tajný klíč, kterým Flask PODEPISUJE přihlašovací cookie. Bez něj by
# session vůbec nefungovala. Obsah cookie je čitelný, ale díky podpisu
# ho uživatel nemůže změnit, aniž by to server nepoznal.
app.secret_key = config.SECRET_KEY


def vyzaduje_prihlaseni(funkce):
    """
    Nálepka pro route, které mají být jen pro přihlášené.

    Použití:
        @app.route("/")
        @vyzaduje_prihlaseni
        def dashboard(): ...

    Je to vlastní DEKORÁTOR - stejný princip jako @app.route, jen si ho
    tentokrát píšeme sami. Obalí původní funkci kontrolou: když v session
    není uživatel, místo stránky pošle přesměrování na přihlášení.

    @wraps(funkce) jen zajistí, že si obalená funkce podrží své jméno -
    bez toho by si Flask myslel, že se všechny route jmenují stejně.
    """
    @wraps(funkce)
    def obalena_funkce(*args, **kwargs):
        if "uzivatel" not in session:
            return redirect(url_for("prihlaseni"))
        return funkce(*args, **kwargs)
    return obalena_funkce


# methods=["GET", "POST"] říká, že tahle adresa umí dvě věci:
#   GET  = "ukaž mi formulář"        (když na stránku přijdeš)
#   POST = "tady máš vyplněné údaje" (když odešleš formulář)
# Bez toho seznamu by Flask POST odmítl.
@app.route("/prihlaseni", methods=["GET", "POST"])
def prihlaseni():
    chyba = None

    if request.method == "POST":
        # request.form je slovník s odeslanými poli. Klíče odpovídají
        # atributům name="..." v HTML formuláři.
        jmeno = request.form.get("jmeno", "").strip()
        heslo = request.form.get("heslo", "")

        uzivatel = database.over_uzivatele(jmeno, heslo)

        if uzivatel:
            # Do session zapíšeme, kdo je přihlášen. Flask to zabalí
            # do podepsané cookie a prohlížeč ji pošle s každým dalším
            # požadavkem - tím si nás server "pamatuje".
            session["uzivatel"] = uzivatel["jmeno"]
            session["uzivatel_id"] = uzivatel["id"]
            return redirect(url_for("dashboard"))

        # Schválně neříkáme, jestli je špatně jméno, nebo heslo. Kdybychom
        # rozlišovali, útočník by si mohl ověřit, která jména existují.
        chyba = "Nesprávné jméno nebo heslo."

    return render_template("prihlaseni.html", chyba=chyba)


@app.route("/odhlaseni")
def odhlaseni():
    # Vyprázdní session -> cookie přestane platit -> uživatel je odhlášen.
    session.clear()
    return redirect(url_for("prihlaseni"))


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
@vyzaduje_prihlaseni
def dashboard():
    # Přečteme obě zařízení. lambda je "funkce na jeden řádek bez jména" -
    # tady jen zabalí volání s parametry, aby ho _bezpecne mohlo spustit.
    nanoleaf, nanoleaf_chyba = _bezpecne(
        lambda: get_nanoleaf_status(config.NANOLEAF_IP, config.NANOLEAF_TOKEN))
    solax, solax_chyba = _bezpecne(
        lambda: get_solax_status(config.SOLAX_DONGLE_IP, config.SOLAX_WIFI_SN))

    # render_template vezme šablonu a doplní do ní pojmenovaná data.
    # Co tady pošleme (nanoleaf=...), tím jménem se to v šabloně objeví.
    # Historie z databáze pro grafy. Sloupce řádku jsou v pořadí, v jakém
    # je vrací nacti_pro_graf(): 0=cas, 1=vykon_panelu, 2=denni_vyroba, 3=soc.
    #
    # Výkon a baterie mají ÚPLNĚ JINOU stupnici (watty vs. procenta), proto
    # dva samostatné grafy pod sebou, ne jeden se dvěma osami. Graf se dvěma
    # osami y je klasická past: dvě křivky v něm jdou libovolně "posunout"
    # vůči sobě jen změnou měřítka, takže svádí vidět souvislost, která tam není.
    historie = _bezpecne(lambda: database.nacti_pro_graf(hodin=24))[0] or []

    graf_vykon = graf.priprav(
        historie, index_hodnoty=1, barva="#eb6834",
        jednotka="kW", delitel=1000, desetin=1)
    graf_baterie = graf.priprav(
        historie, index_hodnoty=3, barva="#2a78d6",
        jednotka="%", desetin=0)

    return render_template(
        "dashboard.html",
        nanoleaf=nanoleaf, nanoleaf_chyba=nanoleaf_chyba,
        solax=solax, solax_chyba=solax_chyba,
        graf_vykon=graf_vykon, graf_baterie=graf_baterie,
        historie=list(reversed(historie))[:20],   # tabulka: nejnovější nahoře
        cas=datetime.now().strftime("%H:%M:%S"),
        uzivatel=session.get("uzivatel"),
    )


if __name__ == "__main__":
    # debug=True = při chybě ukáže podrobnosti a po změně kódu sám restartuje.
    # V ostrém provozu VYPNOUT (přijde na řadu ve fázi hostingu).
    app.run(debug=True)
