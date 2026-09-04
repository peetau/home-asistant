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
  asistent.html     půlka Asistent (hlavička, nákupní seznamy)
  domacnost.html    půlka Domácnost (zařízení, nebo pozvánka)
  solary.html       tab Soláry
  nanoleaf.html     tab Nanoleaf (jediná stránka s vlastním JavaScriptem)
  nakup.html        tab Nákup
  sprava.html       tab Správa (účty a právo na Správu)
  prihlaseni.html   přihlašovací stránka

testy/
  spust.py           pustí všechny testy a vypíše souhrn
  spolecne.py        zázemí testů: dočasná databáze, účet, spouštěč
  test_spojeni.py    spojení s databází se zavírají
  test_prihlaseni.py strop na počet přihlašovacích pokusů
  test_stranky.py    stránky odpovídají a nenechávají viset spojení
  README.md          jak se testy pouštějí a jak přidat další

docs/
  stav.md             kde projekt je + roadmapa
  plan.md             kam projekt miri a v jakem poradi
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

**Osobní hlavička patří Asistentovi a vidí ji každý.** Pozdrav, datum se
svátkem a počasí se vykreslí v `asistent.html` bez ohledu na cokoliv. Je to
schválně: kdo má jen Nákup, měl dřív Přehled prakticky prázdný. Zařízení
jsou na druhé půlce, v `domacnost.html`, a ta se řídí členstvím v domácnosti
(viz níž). Data pro hlavičku skládá
route `dashboard()` z `pozdrav()`, `svatky.popis_dne()` a `pocasi.ted()`
plus prvního dne z `pocasi.predpoved()`.

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

**`with sqlite3.connect(...)` spojení NEZAVÍRÁ.** Potvrdí transakci, ale
soubor nechá otevřený — zavře ho až uklízeč paměti, a ten se v dlouho
běžícím gunicornu spouští jen občas. Než se na to přišlo, nasbíral každý
worker za patnáct hodin přes tisíc otevřených kopií `asistent.db`, došly
systémové deskriptory (strop je 1024) a aplikace přestala umět databázi
otevřít vůbec — stránka spadla na `unable to open database file`. Proto je
`_spojeni()` správce kontextu, který zavírá v `finally`, a proto se spojení
nikde nesmí otevírat přímo přes `sqlite3.connect()`. Sběrače se to netýkalo:
jedno spojení za pět minut uklízeč vždycky stihl uklidit.

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

**K zařízením se nechodí přes právo, ale přes členství v domácnosti.**
Práva `solary` a `nanoleaf` byla 4. 9. 2026 zrušená stejně jako předtím
`nakup`; `VSECHNY_TABY` zbylo jediné, `sprava`. Domácnost je věc v databázi
s vlastníkem, členy a pozvánkou kódem — tedy přesně to, co už umí nákupní
seznam, jen podruhé.

⚠️ **Sloupec `ma_zarizeni` není ozdoba.** Zařízení jsou pořád v `config.py`,
tedy společná pro celý server. Kdyby se podmínka ptala jen „jsi člen nějaké
domácnosti", stačilo by si jednu založit a člověk by viděl cizí SolaX.
Podmínka proto zní „jsi člen TÉ domácnosti, které patří zařízení z configu".
Že takovou domácnost může být nejvýš jedna, hlídá **částečný unikátní index**
(`WHERE ma_zarizeni = 1`) — tedy databáze, ne Python; dva workery zakládající
naráz si dvě hlavní domácnosti udělat nemůžou.

Podmínka je napsaná na **jednom místě**, v `uzivatel_a_prava()`, protože je
bezpečnostní: `domacnost_uzivatele()` z ní jen bere výsledek. Dvě kopie by
znamenaly, že se jednou opraví jen jedna.

**Pruh tabů se filtruje podle půlky.** V Domácnosti svítí Soláry a Nanoleaf
(jen členovi), v Asistentovi Nákup a Správa. Přepínač se tím stal jedinou
cestou mezi půlkami a lišta na telefonu se zkrátila z pěti položek na tři.
Schování tabu je ale **pohodlí, ne ochrana** — tu dělá `vyzaduje_domacnost`
na routách. Ten vrací **302 na Asistenta, ne 404**: pravidlo „404 místo 403"
platí u Nákupu, kde by odpověď prozradila, že cizí seznam existuje, ale
u tabu není co prozradit.

**Strop na přihlašování počítá adresy, ne jména.** Pět chybných pokusů
z jedné IP znamená minutu čekání, deset pět minut, patnáct čtvrt hodiny;
úspěšné přihlášení počítadlo smaže. Kdyby se počítala jména, stačilo by
útočníkovi zkoušet cizí jméno a majitele účtu tím vyřadit z provozu —
zamknout někoho by bylo snazší než se k němu vloupat. Zablokované adrese se
heslo vůbec neověřuje: hashování je záměrně pomalé, takže by se opakovanými
pokusy dal vytížit procesor i bez naděje na uhodnutí. Počítadlo je v tabulce
`pokusy_prihlaseni`, ne v paměti procesu — gunicorn má dva workery a každý by
měl vlastní.

**Čeština nezná rod uživatele.** „Hana koupil" praští do očí, takže se
u položky píše „koupil(a)" a ve vyúčtování sloveso není vůbec — říká ho
jednou nadpis. Kdyby přibývaly další věty o lidech, počítej s tím.

Stejný problém má **pátý pád**: „Dobré ráno, Petře" chce skloňování, které
se z uloženého jména odvodit nedá — závisí na rodu, o kterém nic nevíme,
a výjimek je spousta (Marek → Marku, Jana → Jano). Proto `pozdrav()`
ve `web.py` zdraví **bez oslovení jménem**. Jméno má člověk vedle sebe
v hlavičce stránky, tak ať radši chybí, než aby bylo zkomolené —
a u cizích jmen by komolení bylo pravidlo, ne výjimka.

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
