r"""
Webové rozhraní domácího asistenta (Flask).

Na rozdíl od main.py, který proběhne a skončí, tenhle soubor spustí
SERVER, který běží pořád a čeká, až si prohlížeč řekne o stránku.

Spuštění (cmd):
    .venv\Scripts\python.exe web.py
pak v prohlížeči:  127.0.0.1:5000

Vzhled je oddělený v templates/ - společnou kostru drží zaklad.html,
jednotlivé stránky ji dědí. Tenhle soubor řeší jen LOGIKU:
přečti data a předej je šabloně.
"""

import os
import shutil
from datetime import datetime
from functools import wraps
from pathlib import Path

from flask import (Flask, render_template, request, redirect, url_for,
                   session, g, jsonify)
from werkzeug.middleware.proxy_fix import ProxyFix

import config
import database
import graf
import pocasi
import qr
import svatky
from devices.nanoleaf import (get_nanoleaf_status, get_nanoleaf_detail,
                             set_nanoleaf_on, set_nanoleaf_brightness,
                             set_nanoleaf_effect, get_nanoleaf_paleta)
from devices.solax import get_solax_status

# Běžíme na serveru, nebo doma při vývoji?
#
# Ten samý kód se chová na dvou místech trochu jinak. Rozhoduje o tom
# proměnná prostředí - nastavení, které kód dostane zvenku od systému,
# místo aby ho měl napsané v sobě. Na serveru ji nastaví systemd,
# doma není nastavená vůbec, takže tam vyjde False.
PRODUKCE = os.environ.get("ASISTENT_PRODUKCE") == "1"

# Připravit databázi (vytvořit chybějící tabulky, doplnit nové sloupce).
# Volá to i sber.py; je to bezpečné volat opakovaně a díky tomu se migrace
# spustí i tehdy, když se restartuje jen web.
database.init_db()

app = Flask(__name__)

# Tajný klíč, kterým Flask PODEPISUJE přihlašovací cookie. Bez něj by
# session vůbec nefungovala. Obsah cookie je čitelný, ale díky podpisu
# ho uživatel nemůže změnit, aniž by to server nepoznal.
app.secret_key = config.SECRET_KEY

# --- Zabezpečení přihlašovací cookie ---
app.config.update(
    # Cookie se nesmí odeslat po nešifrovaném spojení. Bez toho by ji
    # šlo na cizí Wi-Fi odposlechnout a přihlásit se jako někdo jiný.
    # Doma to musí zůstat vypnuté, jinak by se přes http:// nedalo
    # přihlásit vůbec.
    SESSION_COOKIE_SECURE=PRODUKCE,

    # JavaScript na stránce se k cookie nedostane. Kdyby se někdy povedlo
    # propašovat na web cizí skript, přihlášení rodiny mu zůstane skryté.
    SESSION_COOKIE_HTTPONLY=True,

    # Cookie se nepošle, když na náš web někdo odkáže z cizí stránky
    # formulářem. Ochrana proti tomu, aby tě podvržený odkaz odhlásil
    # nebo něco provedl tvým jménem.
    SESSION_COOKIE_SAMESITE="Lax",
)

if PRODUKCE:
    # Na serveru stojí před aplikací Caddy (reverzní proxy). Aplikace by
    # tedy každý požadavek viděla jako "HTTP z adresy 127.0.0.1" - Caddy
    # je totiž její jediný soused.
    #
    # ProxyFix ji naučí číst hlavičky, které Caddy přidává: skutečnou
    # adresu návštěvníka a to, že spojení bylo HTTPS. Bez toho by
    # url_for() skládal odkazy s http:// a cookie s příznakem Secure
    # by se nikdy neodeslala.
    #
    # x_for/x_proto=1 znamená "věř přesně jedné proxy před sebou" -
    # tolik jich tam je. Vyšší číslo by dovolilo hlavičky podvrhnout.
    app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1)

# Lidské názvy tabů pro Správu. Klíče musí sedět na database.VSECHNY_TABY.
POPISY_TABU = {
    "solary": "☀️ Soláry",
    "nanoleaf": "💡 Nanoleaf",
    "nakup": "🛒 Nákup",
    "sprava": "⚙️ Správa",
}


# Jak staré smí být, aby to ještě bylo "v pořádku".
# Sběrač měří po 5 minutách, takže dvě zmeškaná kola ještě nejsou porucha.
# Záloha běží denně, jeden vynechaný běh taky ne.
LIMIT_MERENI_MINUT = 15
LIMIT_ZALOHY_HODIN = 48


def podrobny_stav():
    """
    Podrobnosti o běhu systému pro tab Správa.

    Tohle je to, co jsme na přihlašovací obrazovce ZÁMĚRNĚ nezobrazili -
    tam jsou jen barevné tečky. Tady je to v pořádku: je to po přihlášení
    a jen pro správce.
    """
    def zjisti():
        udaje = {}

        minuty = database.stari_posledniho_mereni()
        udaje["mereni_minut"] = None if minuty is None else round(minuty)

        with database._spojeni() as db:
            udaje["mereni_pocet"] = db.execute(
                "SELECT COUNT(*) FROM mereni").fetchone()[0]
            udaje["mereni_od"] = db.execute(
                "SELECT MIN(cas) FROM mereni").fetchone()[0]

        # Velikost databáze a volné místo na disku
        udaje["db_mb"] = round(os.path.getsize(database.DB_SOUBOR) / 1048576, 1)
        volno = shutil.disk_usage(os.path.dirname(database.DB_SOUBOR) or ".")
        udaje["disk_volno_gb"] = round(volno.free / 1073741824, 1)
        udaje["disk_celkem_gb"] = round(volno.total / 1073741824, 1)

        # Stáří zálohy v hodinách
        slozka = os.path.expanduser(getattr(config, "ZALOHY_SLOZKA", "~/zalohy"))
        zalohy = []
        if os.path.isdir(slozka):
            zalohy = [os.path.join(slozka, f) for f in os.listdir(slozka)
                      if f.endswith(".db.gz")]
        if zalohy:
            nejnovejsi = max(os.path.getmtime(z) for z in zalohy)
            udaje["zaloha_hodin"] = round(
                (datetime.now().timestamp() - nejnovejsi) / 3600, 1)
            udaje["zaloha_pocet"] = len(zalohy)
        else:
            udaje["zaloha_hodin"] = None
            udaje["zaloha_pocet"] = 0

        return udaje

    return _bezpecne(zjisti)[0]


def denni_nalada():
    """
    Podle hodiny vrátí náladu pro pozadí přihlašovací stránky.

    Rozhoduje SERVER, ne JavaScript - pozadí je tak správné hned
    při prvním vykreslení a neprobliká se. Stejný důvod jako u motivu.
    """
    hodina = datetime.now().hour
    if hodina < 6:
        return "noc"
    if hodina < 10:
        return "rano"
    if hodina < 18:
        return "den"
    if hodina < 22:
        return "vecer"
    return "noc"


def stav_sberu():
    """
    Běží sběr měření? Vrací jen "ok" / "problem" / "nezname".

    Schválně nevrací žádné číslo ani čas: tenhle údaj se ukazuje
    PŘED přihlášením, takže ho vidí kdokoliv na internetu. Barevná
    tečka majiteli stačí, kolemjdoucímu neřekne nic použitelného.
    """
    minuty, chyba = _bezpecne(database.stari_posledniho_mereni)
    if chyba is not None or minuty is None:
        return "nezname"
    return "ok" if minuty <= LIMIT_MERENI_MINUT else "problem"


def stav_zalohy():
    """
    Je záloha databáze čerstvá? Zase jen "ok" / "problem" / "nezname".

    Dívá se na stáří nejnovějšího souboru ve složce záloh. Doma složka
    neexistuje, takže vyjde "nezname" - a to je správně, doma se
    nezálohuje.
    """
    def zjisti():
        slozka = Path(os.path.expanduser(
            getattr(config, "ZALOHY_SLOZKA", "~/zalohy")))
        zalohy = list(slozka.glob("*.db.gz"))
        if not zalohy:
            return None
        nejnovejsi = max(z.stat().st_mtime for z in zalohy)
        return (datetime.now().timestamp() - nejnovejsi) / 3600

    hodiny, chyba = _bezpecne(zjisti)
    if chyba is not None or hodiny is None:
        return "nezname"
    return "ok" if hodiny <= LIMIT_ZALOHY_HODIN else "problem"


def aktualni_prava():
    """
    Práva přihlášeného uživatele, čtená z DATABÁZE - ne ze session.

    Proč z databáze: session vzniká při přihlášení a pak se nemění. Když
    správce někomu přidá právo, ten člověk by o tom nevěděl, dokud by se
    neodhlásil a nepřihlásil - reload stránky nepomůže, protože prohlížeč
    posílá pořád tu samou cookie.

    Je to jeden malý dotaz navíc při každém požadavku. Výsledek si uložíme
    do g, což je úložiště platné po dobu JEDNOHO požadavku - takže i když
    se na práva zeptáme na pěti místech, do databáze se sáhne jednou.

    Když už uživatel neexistuje (správce mu smazal účet), session se
    vyprázdní a pošleme ho na přihlášení.
    """
    if "prava" in g:
        return g.prava

    if "uzivatel_id" not in session:
        g.prava = set()
        return g.prava

    zaznam = database.uzivatel_a_prava(session["uzivatel_id"])
    if zaznam is None:
        session.clear()
        g.prava = set()
    else:
        g.prava = zaznam[1]
    return g.prava


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


def vyzaduje_pravo(tab):
    """
    Nálepka pro route, které smí jen uživatel s právem na daný tab.

        @app.route("/solary")
        @vyzaduje_pravo("solary")
        def solary(): ...

    Oproti vyzaduje_prihlaseni je to o patro výš: dekorátor S PARAMETREM.
    Funguje tak, že vyzaduje_pravo("solary") nejdřív VYROBÍ dekorátor
    (funkci dekorator níž) a teprve ten se přilepí na route. Proto jsou
    tu tři vnořené funkce místo dvou.

    DŮLEŽITÉ: tahle kontrola je ta skutečná ochrana. Skrytí tabu v menu
    je jen pohodlí - kdo zná adresu, může požadavek poslat i tak.
    """
    def dekorator(funkce):
        @wraps(funkce)
        def obalena_funkce(*args, **kwargs):
            if "uzivatel" not in session:
                return redirect(url_for("prihlaseni"))
            if tab not in aktualni_prava():
                # Bez práva pošleme na Přehled - ten má každý přihlášený.
                return redirect(url_for("dashboard"))
            return funkce(*args, **kwargs)
        return obalena_funkce
    return dekorator


@app.context_processor
def spolecna_data():
    """
    Data, která dostane KAŽDÁ šablona automaticky.

    Dřív každá route posílala uzivatel=session.get("uzivatel") zvlášť -
    pětkrát to samé. Context processor to řeší na jednom místě: co vrátí
    tenhle slovník, je vidět ve všech šablonách.

    Práva bereme z aktualni_prava(), tedy z databáze - viz vysvětlení tam.
    """
    return {
        "uzivatel": session.get("uzivatel"),
        "prava": aktualni_prava(),
    }


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
            _bezpecne(lambda: database.zaznamenej_prihlaseni(uzivatel["id"]))
            return redirect(url_for("dashboard"))

        # Schválně neříkáme, jestli je špatně jméno, nebo heslo. Kdybychom
        # rozlišovali, útočník by si mohl ověřit, která jména existují.
        chyba = "Nesprávné jméno nebo heslo."

    return render_template(
        "prihlaseni.html",
        chyba=chyba,
        nalada=denni_nalada(),
        datum_svatek=_bezpecne(svatky.popis_dne)[0],
        pocasi=_bezpecne(lambda: pocasi.predpoved(
            config.POCASI_LAT, config.POCASI_LON))[0],
        misto=getattr(config, "POCASI_MISTO", ""),
        stav_sber=stav_sberu(),
        stav_zaloha=stav_zalohy(),
    )


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


def _stav_nanoleaf():
    """Přečte Nanoleaf. Vrací (data, chyba) - jedno z toho je vždy None."""
    return _bezpecne(
        lambda: get_nanoleaf_status(config.NANOLEAF_IP, config.NANOLEAF_TOKEN))


def _stav_solax():
    """Přečte soláry. Vrací (data, chyba)."""
    return _bezpecne(
        lambda: get_solax_status(config.SOLAX_DONGLE_IP, config.SOLAX_WIFI_SN))


@app.route("/")
@vyzaduje_prihlaseni
def dashboard():
    """Přehled - od každého zařízení to nejdůležitější."""
    # Čteme jen zařízení, na která má uživatel právo. Nejde jen o úsporu:
    # každé čtení je volání po síti, takže bez téhle podmínky by se čekalo
    # i na data, která se stejně nezobrazí.
    prava = aktualni_prava()

    nanoleaf, nanoleaf_chyba = (
        _stav_nanoleaf() if "nanoleaf" in prava else (None, None))
    solax, solax_chyba = (
        _stav_solax() if "solary" in prava else (None, None))

    return render_template(
        "prehled.html", aktivni="prehled",
        nanoleaf=nanoleaf, nanoleaf_chyba=nanoleaf_chyba,
        solax=solax, solax_chyba=solax_chyba,
    )


@app.route("/solary")
@vyzaduje_pravo("solary")
def solary():
    """Detail solární elektrárny: aktuální stav, grafy, historie."""
    solax, solax_chyba = _stav_solax()

    # Historie z databáze pro grafy. Sloupce řádku jsou v pořadí, v jakém
    # je vrací nacti_pro_graf(): 0=cas, 1=vykon_panelu, 2=denni_vyroba, 3=soc.
    #
    # Výkon a baterie mají ÚPLNĚ JINOU stupnici (watty vs. procenta), proto
    # dva samostatné grafy pod sebou, ne jeden se dvěma osami. Graf se dvěma
    # osami y je klasická past: dvě křivky v něm jdou libovolně "posunout"
    # vůči sobě jen změnou měřítka, takže svádí vidět souvislost, která tam není.
    historie = _bezpecne(lambda: database.nacti_pro_graf(hodin=24))[0] or []

    graf_vykon = graf.priprav(
        historie, index_hodnoty=1, barva="var(--serie-vykon)",
        jednotka="kW", delitel=1000, desetin=1)
    graf_baterie = graf.priprav(
        historie, index_hodnoty=3, barva="var(--serie-baterie)",
        jednotka="%", desetin=0)

    return render_template(
        "solary.html", aktivni="solary",
        solax=solax, solax_chyba=solax_chyba,
        graf_vykon=graf_vykon, graf_baterie=graf_baterie,
        historie=list(reversed(historie))[:20],   # tabulka: nejnovější nahoře
    )


@app.route("/nanoleaf")
@vyzaduje_pravo("nanoleaf")
def nanoleaf():
    """Detail Nanoleaf: stav, rozložení panelů, ovládání."""
    stav, chyba = _bezpecne(lambda: get_nanoleaf_detail(
        config.NANOLEAF_IP, config.NANOLEAF_TOKEN))
    return render_template(
        "nanoleaf.html", aktivni="nanoleaf",
        nanoleaf=stav, nanoleaf_chyba=chyba,
    )


# ---------------------------------------------------------------------------
# Ovládání Nanoleaf.
#
# Zápis do zařízení je POST + redirect, stejně jako u nákupu: GET musí
# zůstat bezpečný. Kdyby zhasnutí světla bylo obyčejný odkaz, stačilo by,
# aby ho prohlížeč načetl na pozadí, a světlo by zhaslo samo od sebe.
# ---------------------------------------------------------------------------

@app.route("/nanoleaf/prepnout", methods=["POST"])
@vyzaduje_pravo("nanoleaf")
def nanoleaf_prepnout():
    """Zapne nebo vypne panely - podle toho, jak svítí teď."""
    stav, chyba = _stav_nanoleaf()
    if stav is not None:
        _bezpecne(lambda: set_nanoleaf_on(
            config.NANOLEAF_IP, config.NANOLEAF_TOKEN, not stav["on"]))
    return redirect(url_for("nanoleaf"))


@app.route("/nanoleaf/jas", methods=["POST"])
@vyzaduje_pravo("nanoleaf")
def nanoleaf_jas():
    """
    Nastaví jas podle posuvníku.

    Umí odpovědět dvěma způsoby:
      - obyčejné odeslání formuláře -> přesměrování zpět na stránku
      - volání z JavaScriptu        -> jen data, stránka se nenačítá znovu

    To druhé je potřeba kvůli náhledu efektu: kdyby se stránka překreslila,
    rozpracovaný náhled by zmizel.
    """
    z_javascriptu = request.headers.get("X-Pozadavek") == "fetch"

    try:
        jas = int(request.form.get("jas", 0))
    except ValueError:
        return (jsonify({"chyba": "neplatná hodnota"}), 400) if z_javascriptu             else redirect(url_for("nanoleaf"))

    nastaveno, chyba = _bezpecne(lambda: set_nanoleaf_brightness(
        config.NANOLEAF_IP, config.NANOLEAF_TOKEN, jas))

    if z_javascriptu:
        if nastaveno is None:
            return jsonify({"chyba": chyba}), 502
        return jsonify({"jas": nastaveno})
    return redirect(url_for("nanoleaf"))


@app.route("/nanoleaf/efekt", methods=["POST"])
@vyzaduje_pravo("nanoleaf")
def nanoleaf_efekt():
    """
    Potvrzení návrhu: přepne efekt a zároveň nastaví jas.

    Obojí naráz proto, že v režimu návrhu se ani jedno do panelů neposílá -
    uživatel si to skládá v prohlížeči a odešle to jedním tlačítkem.

    Pořadí není náhodné: nejdřív efekt, pak jas. Některé efekty si totiž
    jas přenastavují samy, takže kdyby šel jas první, efekt by ho přepsal.
    """
    nazev = request.form.get("efekt", "")
    if nazev:
        _bezpecne(lambda: set_nanoleaf_effect(
            config.NANOLEAF_IP, config.NANOLEAF_TOKEN, nazev))

    if request.form.get("jas"):
        try:
            jas = int(request.form["jas"])
        except ValueError:
            jas = None
        if jas is not None:
            _bezpecne(lambda: set_nanoleaf_brightness(
                config.NANOLEAF_IP, config.NANOLEAF_TOKEN, jas))

    return redirect(url_for("nanoleaf"))


@app.route("/nanoleaf/paleta")
@vyzaduje_pravo("nanoleaf")
def nanoleaf_paleta():
    """
    Vrátí barvy zvoleného efektu jako JSON - pro náhled v prohlížeči.

    Tohle je první adresa, která nevrací STRÁNKU, ale DATA. Používá ji
    JavaScript: uživatel vybere efekt, prohlížeč si sem řekne o barvy
    a nakreslí náhled - a to všechno bez znovunačtení stránky
    a bez jediného příkazu do panelů.

    Je to GET a je to v pořádku: nic se tím nemění, jen se čte.
    """
    nazev = request.args.get("efekt", "")
    if not nazev:
        return jsonify({"chyba": "chybí jméno efektu"}), 400

    paleta, chyba = _bezpecne(lambda: get_nanoleaf_paleta(
        config.NANOLEAF_IP, config.NANOLEAF_TOKEN, nazev))

    if paleta is None:
        return jsonify({"chyba": chyba}), 502
    return jsonify(paleta)


@app.route("/nakup")
@vyzaduje_pravo("nakup")
def nakup():
    """Nákupní seznam - společný pro celou rodinu."""
    polozky = database.seznam_nakupu()

    # Rozdělíme rovnou tady, ať to šablona nemusí filtrovat dvakrát.
    # Index 2 je sloupec 'koupeno'.
    chybejici = [p for p in polozky if not p[2]]
    koupene = [p for p in polozky if p[2]]

    return render_template(
        "nakup.html", aktivni="nakup",
        chybejici=chybejici, koupene=koupene,
        caste=_bezpecne(database.caste_polozky)[0] or [],
    )


# ---------------------------------------------------------------------------
# Akce nad seznamem.
#
# Všechny jsou POST, ne GET - a je to důležité pravidlo, ne formalita:
# GET musí být "bezpečný", tedy nic neměnit. Kdyby odškrtnutí položky bylo
# GET, stačilo by, aby prohlížeč (nebo jeho přednačítání, nebo antivirus)
# ten odkaz otevřel na pozadí, a položka by se odškrtla sama od sebe.
#
# Každá akce končí redirectem zpátky na seznam. Tomu se říká vzorec
# POST -> redirect -> GET a řeší otravný problém: kdyby route po POSTu
# rovnou vykreslila stránku, tak by po stisku F5 prohlížeč nabídl
# "odeslat formulář znovu" a položka by se přidala podruhé.
# ---------------------------------------------------------------------------

@app.route("/nakup/pridat", methods=["POST"])
@vyzaduje_pravo("nakup")
def nakup_pridat():
    database.pridej_polozku(
        request.form.get("text", ""),
        session.get("uzivatel"),
        request.form.get("mnozstvi", ""),
    )
    return redirect(url_for("nakup"))


# <int:id_polozky> je proměnná část adresy. Flask z /nakup/7/prepnout
# vytáhne sedmičku a předá ji funkci jako parametr. To "int:" navíc hlídá,
# že to je opravdu číslo - když někdo zkusí /nakup/abc/prepnout,
# Flask vrátí 404 a naše funkce se vůbec nespustí.
@app.route("/nakup/<int:id_polozky>/prepnout", methods=["POST"])
@vyzaduje_pravo("nakup")
def nakup_prepnout(id_polozky):
    database.prepni_koupeno(id_polozky, session.get("uzivatel"))
    return redirect(url_for("nakup"))


@app.route("/nakup/<int:id_polozky>/upravit", methods=["POST"])
@vyzaduje_pravo("nakup")
def nakup_upravit(id_polozky):
    database.uprav_polozku(
        id_polozky,
        request.form.get("text", ""),
        request.form.get("mnozstvi", ""),
    )
    return redirect(url_for("nakup"))


@app.route("/nakup/<int:id_polozky>/smazat", methods=["POST"])
@vyzaduje_pravo("nakup")
def nakup_smazat(id_polozky):
    database.smaz_polozku(id_polozky)
    return redirect(url_for("nakup"))


@app.route("/nakup/uklidit", methods=["POST"])
@vyzaduje_pravo("nakup")
def nakup_uklidit():
    """Smaže všechny odškrtnuté položky naráz."""
    database.smaz_koupene()
    return redirect(url_for("nakup"))


# ===========================================================================
# Správa uživatelů
#
# Kdo má právo "sprava", spravuje ostatní. Žádné zvláštní role - Správa
# je prostě další tab jako Soláry nebo Nákup.
#
# Hlášky (chyba/zprava) se předávají přes query parametr v adrese. Je to
# nejjednodušší způsob, jak přežít redirect po POSTu; Flask má na tohle
# i hezčí nástroj (flash zprávy), ale ten by sem přinesl nový koncept.
# ===========================================================================

@app.route("/profil", methods=["GET", "POST"])
@vyzaduje_prihlaseni
def profil():
    """
    Můj profil - vlastní údaje a změna hesla.

    Chrání ho JEN přihlášení, ne právo na tab. Kdyby vyžadoval právo,
    běžný uživatel by si heslo zase nezměnil a přesně to tu řešíme.
    """
    chyba = zprava = None

    if request.method == "POST":
        nove = request.form.get("nove", "")

        # Shodu obou nových hesel zkontrolovat DŘÍV, než se cokoliv změní -
        # jinak by se při překlepu heslo stejně přepsalo.
        if nove != request.form.get("nove2", ""):
            chyba = "Nová hesla se neshodují."
        else:
            ok, duvod = database.zmen_heslo_s_overenim(
                session["uzivatel_id"], request.form.get("stare", ""), nove)
            chyba, zprava = (None, "Heslo změněno.") if ok else (duvod, None)

    return render_template(
        "profil.html", aktivni="profil",
        udaje=_bezpecne(lambda: database.udaje_uzivatele(
            session["uzivatel_id"]))[0],
        chyba=chyba, zprava=zprava,
        popisy_tabu=POPISY_TABU,
    )


@app.route("/sprava")
@vyzaduje_pravo("sprava")
def sprava():
    """Seznam účtů, jejich práva a zakládání nových."""
    return render_template(
        "sprava.html", aktivni="sprava",
        ucty=database.uzivatele_s_pravy(),
        vsechny_taby=database.VSECHNY_TABY,
        popisy_tabu=POPISY_TABU,
        muj_id=session.get("uzivatel_id"),
        stav=podrobny_stav(),
        # Adresu bereme z požadavku, ne z configu - Flask ji zná a díky
        # ProxyFixu je i za Caddy správná (https, skutečná doména).
        adresa=request.url_root.rstrip("/"),
        qr_kod=_bezpecne(lambda: qr.qr_pro_svg(request.url_root.rstrip("/")))[0],
        chyba=request.args.get("chyba"),
        zprava=request.args.get("zprava"),
    )


@app.route("/sprava/pridat", methods=["POST"])
@vyzaduje_pravo("sprava")
def sprava_pridat():
    jmeno = request.form.get("jmeno", "").strip()
    heslo = request.form.get("heslo", "")

    if not jmeno:
        return redirect(url_for("sprava", chyba="Jméno nesmí být prázdné."))
    if len(heslo) < 6:
        return redirect(url_for("sprava", chyba="Heslo musí mít aspoň 6 znaků."))

    if database.vytvor_uzivatele(jmeno, heslo):
        return redirect(url_for(
            "sprava", zprava=f"Účet {jmeno} vytvořen (zatím jen Nákup)."))
    return redirect(url_for("sprava", chyba=f"Účet {jmeno} už existuje."))


@app.route("/sprava/<int:id_uzivatele>/prava", methods=["POST"])
@vyzaduje_pravo("sprava")
def sprava_prava(id_uzivatele):
    # getlist, ne get: zaškrtávátek se stejným name je víc a chceme
    # VŠECHNA zaškrtnutá. Nezaškrtnutá se neodešlou vůbec - proto stačí
    # vzít, co přišlo, a zbytek se odebere.
    taby = request.form.getlist("tab")

    ok, chyba = database.nastav_prava(id_uzivatele, taby)
    if not ok:
        return redirect(url_for("sprava", chyba=chyba))
    return redirect(url_for("sprava", zprava="Práva uložena."))


@app.route("/sprava/<int:id_uzivatele>/heslo", methods=["POST"])
@vyzaduje_pravo("sprava")
def sprava_heslo(id_uzivatele):
    ok, chyba = database.zmen_heslo(id_uzivatele, request.form.get("heslo", ""))
    if not ok:
        return redirect(url_for("sprava", chyba=chyba))
    return redirect(url_for("sprava", zprava="Heslo změněno."))


@app.route("/sprava/<int:id_uzivatele>/smazat", methods=["POST"])
@vyzaduje_pravo("sprava")
def sprava_smazat(id_uzivatele):
    # Pojistka proti sebevraždě. Databáze hlídá "poslední správce",
    # tohle navíc brání i tomu, aby ses smazal, když jsou správci dva.
    if id_uzivatele == session.get("uzivatel_id"):
        return redirect(url_for("sprava", chyba="Sám sebe smazat nemůžeš."))

    ok, chyba = database.smaz_uzivatele(id_uzivatele)
    if not ok:
        return redirect(url_for("sprava", chyba=chyba))
    return redirect(url_for("sprava", zprava="Účet smazán."))


if __name__ == "__main__":
    # debug=True = při chybě ukáže podrobnosti a po změně kódu sám restartuje.
    # V ostrém provozu VYPNOUT (přijde na řadu ve fázi hostingu).
    app.run(debug=True)
