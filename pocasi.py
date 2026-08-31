"""
Počasí: předpověď pro přihlašovací stránku a současný stav pro Soláry.

Zdroj: Open-Meteo (https://open-meteo.com) - zdarma, bez registrace
a bez API klíče. Nemusíme tedy nic tajného řešit v configu.

MEZIPAMĚŤ JE TU POVINNÁ, ne jako optimalizace. Přihlašovací stránku
vidí kdokoliv na internetu; kdyby na ni bušil robot, bušili bychom
i my do Open-Meteo a stránka by se plazila. Proto se ptáme nejvýš
jednou za půl hodiny a mezitím vracíme uloženou odpověď.
"""

from datetime import datetime, timedelta

import requests

ADRESA = "https://api.open-meteo.com/v1/forecast"

# Jak dlouho platí uložená odpověď. Každý dotaz má svou platnost:
# předpověď na tři dny se za půl hodiny nezmění, kdežto sluneční záření
# Open-Meteo přepočítává po čtvrthodině.
PLATNOST_MINUT = 30
PLATNOST_TED_MINUT = 10

# Kolik dní dopředu
DNI = 3

# S čím porovnáváme sluneční záření, aby se dalo ukázat proužkem.
#
# 1000 W/m² je hodnota daná normou, při které se měří výkon panelů -
# těch "9,9 kWp" na štítku. V Česku takhle silně slunce nesvítí ani
# v poledne v červnu, takže proužek v praxi plný nebude. Je to schválně:
# ukazuje, jak daleko je dnešek od ideálních podmínek.
ZARENI_MAXIMUM = 1000

# Mezipaměť žije v paměti procesu. Gunicorn má na serveru dva workery,
# takže vzniknou dvě nezávislé - to je v pořádku, jsou to čtyři dotazy
# za hodinu místo dvou. Open-Meteo to nezaznamená.
#
# POVINNÁ je hlavně kvůli stránce Soláry: ta se sama obnovuje každých
# 30 sekund, takže bez mezipaměti by jeden otevřený prohlížeč znamenal
# 120 dotazů za hodinu.
_ulozeno = {
    "predpoved": {"kdy": None, "data": None},
    "ted": {"kdy": None, "data": None},
}


def _z_mezipameti(klic, platnost_minut, ziskej):
    """
    Vrátí uloženou odpověď, a když je stará, řekne si o novou.

    ziskej je FUNKCE, ne hotová data - kdyby to byla data, musela by se
    stáhnout pokaždé a mezipaměť by nic neušetřila. Takhle se zavolá jen
    tehdy, když je opravdu potřeba.

    Když stahování selže, vrátíme to poslední, co máme (klidně staré).
    Půlhodinu stará předpověď je pořád lepší než prázdné místo.
    """
    schranka = _ulozeno[klic]

    if schranka["kdy"] is not None:
        if datetime.now() - schranka["kdy"] < timedelta(minutes=platnost_minut):
            return schranka["data"]

    try:
        data = ziskej()
    except Exception:
        return schranka["data"]

    schranka["kdy"] = datetime.now()
    schranka["data"] = data
    return data


# Open-Meteo vrací číselné kódy počasí podle normy WMO.
# Nemá smysl rozlišovat všech ~30 hodnot, stačí skupiny.
_KODY = {
    0: ("☀️", "jasno"),
    1: ("🌤️", "skoro jasno"),
    2: ("⛅", "polojasno"),
    3: ("☁️", "zataženo"),
    45: ("🌫️", "mlha"),
    48: ("🌫️", "námraza"),
    51: ("🌦️", "mrholení"),
    53: ("🌦️", "mrholení"),
    55: ("🌦️", "mrholení"),
    61: ("🌧️", "déšť"),
    63: ("🌧️", "déšť"),
    65: ("🌧️", "silný déšť"),
    66: ("🌧️", "mrznoucí déšť"),
    67: ("🌧️", "mrznoucí déšť"),
    71: ("🌨️", "sněžení"),
    73: ("🌨️", "sněžení"),
    75: ("❄️", "silné sněžení"),
    77: ("🌨️", "sněhové krupky"),
    80: ("🌦️", "přeháňky"),
    81: ("🌦️", "přeháňky"),
    82: ("⛈️", "silné přeháňky"),
    85: ("🌨️", "sněhové přeháňky"),
    86: ("🌨️", "sněhové přeháňky"),
    95: ("⛈️", "bouřky"),
    96: ("⛈️", "bouřky s kroupami"),
    99: ("⛈️", "bouřky s kroupami"),
}

_DNY_ZKRATKY = ("po", "út", "st", "čt", "pá", "so", "ne")

# Co k dnešnímu slunci říct lidsky. Hranice jsou ve W/m² a hledá se
# odshora dolů - platí první, na kterou hodnota dosáhne.
_HLASKY = (
    (750, "Slunce jede naplno."),
    (500, "Slunce svítí, jak má."),
    (250, "Slunce se schovává za mraky."),
    (80, "Zataženo, panely sotva mrknou."),
    (0, "Skoro tma, panely mají volno."),
)


def _hlaska(zareni, je_den):
    """Vybere větu, která odpovídá tomu, jak zrovna svítí."""
    if not je_den:
        return "Slunce je pod obzorem."
    for hranice, text in _HLASKY:
        if zareni >= hranice:
            return text
    return _HLASKY[-1][1]


def _popis_dne(index, datum):
    """První dva dny pojmenujeme slovně, dál stačí zkratka dne."""
    if index == 0:
        return "dnes"
    if index == 1:
        return "zítra"
    return _DNY_ZKRATKY[datum.weekday()]


def predpoved(lat, lon):
    """
    Vrátí předpověď na tři dny, nebo None když se ji nepodařilo získat.

    Formát:
        [{"den": "dnes", "ikona": "🌦️", "popis": "přeháňky",
          "max": 27, "min": 18}, ...]

    None se vrací záměrně místo výjimky: přihlašovací stránka se musí
    vykreslit i tehdy, když je Open-Meteo nedostupné - jen se blok
    s počasím neukáže.
    """
    def stahni():
        odpoved = requests.get(ADRESA, params={
            "latitude": lat,
            "longitude": lon,
            "daily": "weather_code,temperature_2m_max,temperature_2m_min",
            "timezone": "Europe/Prague",
            "forecast_days": DNI,
        }, timeout=5)
        odpoved.raise_for_status()
        denni = odpoved.json()["daily"]

        vysledek = []
        for i in range(len(denni["time"])):
            datum = datetime.strptime(denni["time"][i], "%Y-%m-%d")
            ikona, popis = _KODY.get(denni["weather_code"][i], ("🌡️", "—"))
            vysledek.append({
                "den": _popis_dne(i, datum),
                "ikona": ikona,
                "popis": popis,
                "max": round(denni["temperature_2m_max"][i]),
                "min": round(denni["temperature_2m_min"][i]),
            })
        return vysledek

    return _z_mezipameti("predpoved", PLATNOST_MINUT, stahni)


def ted(lat, lon):
    """
    Vrátí, co je za oknem právě teď, nebo None když se to nepovedlo.

    Formát:
        {"ikona": "⛅", "popis": "polojasno", "teplota": 23,
         "zareni": 345, "podil": 35, "je_den": True,
         "hlaska": "Slunce se schovává za mraky."}

    'zareni' je sluneční záření dopadající na metr čtvereční [W/m²].
    Je to údaj z předpovědi počasí, NE měření z našich panelů - proto se
    na stránce ukazuje nad výrobou: nejdřív co je v nabídce, teprve pak
    kolik jsme z toho vzali.
    """
    def stahni():
        odpoved = requests.get(ADRESA, params={
            "latitude": lat,
            "longitude": lon,
            "current": "temperature_2m,weather_code,shortwave_radiation,is_day",
            "timezone": "Europe/Prague",
        }, timeout=5)
        odpoved.raise_for_status()
        ted_ = odpoved.json()["current"]

        zareni = round(ted_["shortwave_radiation"])
        je_den = bool(ted_["is_day"])
        ikona, popis = _KODY.get(ted_["weather_code"], ("🌡️", "—"))

        # V noci by kód 0 ("jasno") vrátil sluníčko, což je nesmysl.
        if not je_den:
            ikona = "🌙"

        return {
            "ikona": ikona,
            "popis": popis,
            "teplota": round(ted_["temperature_2m"]),
            "zareni": zareni,
            # Na proužek stačí celá procenta a nikdy víc než sto.
            "podil": min(100, round(100 * zareni / ZARENI_MAXIMUM)),
            "je_den": je_den,
            "hlaska": _hlaska(zareni, je_den),
        }

    return _z_mezipameti("ted", PLATNOST_TED_MINUT, stahni)
