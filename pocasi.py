"""
Předpověď počasí pro přihlašovací stránku.

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

# Jak dlouho platí uložená odpověď
PLATNOST_MINUT = 30

# Kolik dní dopředu
DNI = 3

# Mezipaměť žije v paměti procesu. Gunicorn má na serveru dva workery,
# takže vzniknou dvě nezávislé - to je v pořádku, jsou to čtyři dotazy
# za hodinu místo dvou. Open-Meteo to nezaznamená.
_ulozeno = {"kdy": None, "data": None}


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
    # Máme uloženou odpověď a je ještě čerstvá?
    if _ulozeno["kdy"] is not None:
        stari = datetime.now() - _ulozeno["kdy"]
        if stari < timedelta(minutes=PLATNOST_MINUT):
            return _ulozeno["data"]

    try:
        odpoved = requests.get(ADRESA, params={
            "latitude": lat,
            "longitude": lon,
            "daily": "weather_code,temperature_2m_max,temperature_2m_min",
            "timezone": "Europe/Prague",
            "forecast_days": DNI,
        }, timeout=5)
        odpoved.raise_for_status()
        denni = odpoved.json()["daily"]
    except Exception:
        # Nepovedlo se. Když máme něco staršího uloženého, radši to -
        # včerejší předpověď je pořád lepší než prázdné místo.
        return _ulozeno["data"]

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

    _ulozeno["kdy"] = datetime.now()
    _ulozeno["data"] = vysledek
    return vysledek
