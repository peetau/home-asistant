# Struktura projektu

Mapa souborů — co je kde a proč. Když hledáš, kam sáhnout, začni tady.

```
web.py              webový server (Flask): adresy stránek, přihlášení, práva
database.py         práce s databází (SQLite) — měření, účty, práva, nákup
sber.py             sběrač měření: běží pořád a plní databázi
main.py             vstupní bod konzolové verze (rychlý výpis stavu)
graf.py             převod naměřených dat na souřadnice pro SVG graf
diagram.py          rozvržení a směry šipek pro diagram toku energie
pocasi.py           počasí z Open-Meteo: předpověď i současné slunce
svatky.py           datum, jmeniny a státní svátky (tabulka přímo v souboru)
sprava_uctu.py      zakládání a mazání rodinných účtů z příkazové řádky
ziskej_token.py     jednorázový pomocník na vygenerování Nanoleaf tokenu

devices/
  nanoleaf.py       Nanoleaf panely: čtení stavu i ovládání
  solax.py          čtení stavu solární elektrárny

static/
  style.css         vzhled (barvy jako proměnné, světlý i tmavý motiv)
  motiv.js          přepínač motivu (systém / světlý / tmavý)

templates/
  zaklad.html       společná kostra všech stránek (hlavička, navigace)
  motiv_skript.html nastavení motivu před vykreslením (proti bliknutí)
  makra.html        znovupoužitelné kousky: nakresli_graf,
                    nakresli_diagram, napoveda, tabulka_mereni
  prehled.html      tab Přehled
  solary.html       tab Soláry
  nanoleaf.html     tab Nanoleaf (jediná stránka s vlastním JavaScriptem)
  nakup.html        tab Nákup
  sprava.html       tab Správa (účty a práva)
  prihlaseni.html   přihlašovací stránka

docs/
  stav.md             kde projekt je + roadmapa
  struktura.md        tenhle soubor
  provoz.md           jak to spustit doma i na serveru
  dalsi-kroky.md      věci, na které jsme narazili a odložili je
  zadani-projektu.md  původní zadání (historický dokument)

config.py           REÁLNÉ tokeny a souřadnice — není v Gitu!
config.example.py   šablona configu — je v Gitu
requirements.txt    seznam potřebných knihoven
asistent.db         databáze měření — vzniká za běhu, není v Gitu
```

## Co stojí za zmínku

**`devices/nanoleaf.py` už nejen čte.** Vedle `get_nanoleaf_status()` umí
i zapisovat: `set_nanoleaf_on()`, `set_nanoleaf_brightness()`,
`set_nanoleaf_effect()`. `get_nanoleaf_detail()` vytáhne stav, seznam efektů
i rozložení panelů jedním dotazem (zařízení to stejně vrací naráz),
`get_nanoleaf_paleta()` přinese barvy efektu pro náhled a
`_rozlozeni_na_svg()` spočítá z pozic a natočení panelů vrcholy pro obrázek.

**JavaScript je v projektu jen na dvou místech.** `static/motiv.js` přepíná
motiv a `templates/nanoleaf.html` má vlastní skript pro režim návrhu. Obojí
je záměrně navíc, ne základ: bez JavaScriptu zůstanou stránky funkční, jen
bez náhledu a bez ručního přepnutí motivu.

**`config.py` drží víc než tokeny.** Kromě přístupů k Nanoleafu a SolaXu i
`SECRET_KEY` (podpis přihlašovací cookie), `ZALOHY_SLOZKA` a souřadnice pro
počasí. Co který údaj znamená, je vysvětlené přímo v `config.example.py`,
provozní souvislosti v [`provoz.md`](provoz.md).

**Dva procesy, ne jeden.** `web.py` obsluhuje stránky, `sber.py` nezávisle
na něm zapisuje měření do databáze. Potkávají se jen přes `asistent.db`,
takže když jeden spadne, druhý běží dál.

**Migrace, která něco ZAKLÁDÁ, si to musí zamknout.** Gunicorn spouští dva
workery naráz. Když se migrace hlídá jen dotazem „už je to hotové?", oba se
zeptají dřív, než kterýkoliv stihne zapsat, oba dostanou „ještě ne" a oba ji
provedou — takhle na serveru vznikly dva stejné seznamy. Od té doby je
v databázi tabulka `migrace` a funkce `_migrace_zabrana()`; o tom, kdo
migraci provede, rozhoduje databáze, ne načasování. Přidání sloupce se
hlídat nemusí, to se buď povede, nebo skončí chybou „sloupec už je".

**U nákupu vede každý přístup jednou brankou.** `polozka_pro_uzivatele()`
a `seznam_pro_uzivatele()` vrátí data jen tomu, kdo na ně má právo, a rovnou
v SQL spočítají, jestli je smí i měnit. Route pak jen zavolá branku a při
`None` vrátí **404, ne 403** — kdo na cizí seznam nemá právo, nemá se ani
dozvědět, že existuje. Kód pozvánky se stejným způsobem vůbec nedostane do
šablony tomu, kdo ho vidět nesmí.

**Čeština nezná rod uživatele.** „Hana koupil" praští do očí, takže se
u položky píše „koupil(a)" a ve vyúčtování sloveso není vůbec — říká ho
jednou nadpis. Kdyby přibývaly další věty o lidech, počítej s tím.

**`devices/solax.py` je naše mapa, ne dokumentace.** Dongle posílá pole tří
set čísel bez jakéhokoliv popisu; co které znamená, jsme museli odvodit.
Vršek souboru je proto tabulka indexů a je na ní postavené všechno ostatní.
Dvě věci se z ní vyplatí pamatovat: záporná čísla chodí jako 16bitová
odspodu (hodnota nad 32767 znamená `hodnota − 65536`) a právě znaménko
určuje SMĚR toku, a denní spotřebu domu dongle neposílá vůbec — dopočítává
se jako `odběr + výstup střídače − dodávka`, stejně jako to dělá SolaX
aplikace.

**Když budeš dohledávat další index, nehádej ho.** Metoda je popsaná
v komentáři `solax.py`: porovnat živá data se snímkem obrazovky ze SolaX
aplikace a ověřit součtem. Pozor, aplikace čte z cloudu a opožďuje se
o několik minut, takže čísla nesmí sedět na jednotku — musí odpovídat
tomu, co bylo před chvílí.
