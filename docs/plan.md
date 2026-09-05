# Plán

Kam projekt míří a v jakém pořadí. **Stav** (co už je hotové) je
v [`stav.md`](stav.md), tenhle soubor je o budoucnosti.

Zapsáno 2. 9. 2026, kdy se změnilo zadání.

## Změna směru: z baráku ven

Projekt vznikl jako nástěnka jedné domácnosti — soláry, Nanoleaf, nákupní
seznam pro rodinu. Ukázalo se ale, že **soláry a Nanoleaf jsou moc
konkrétní věc**: jsou to zařízení jednoho konkrétního domu a nikomu jinému
k ničemu nejsou.

Nový cíl je **osobní asistent, který se dá dát k dispozici i lidem mimo
rodinu**. Tím se mění, co je v aplikaci hlavní a co vedlejší:

| dřív | teď |
|---|---|
| jádro = zařízení v domě | jádro = **Přehled** a **Nákup** |
| zařízení jsou důvod, proč aplikace existuje | zařízení jsou **doplněk pro toho, kdo je má** |
| uživatel = člen rodiny | uživatel = **kdokoliv** |

Rozdělení tabů na *dům* a *nástroje*, které popisuje `stav.md`, tím
přestává být rozdělení aplikace na dvě poloviny. Je z něj jen poznámka
o tom, že některé taby potřebují hardware.

## Napětí, které z toho plyne

Přehled má být „vše na jednom místě". Jenže když zařízení odejdou, to
„vše" je **jedna věc** — Nákup. Přehled by se scvrknul na dlaždice
seznamů, což je skoro totéž, co je dneska nahoře na Nákupu.

Z toho plyne pravidlo, které stojí za zapamatování:

> **Přehled nemůže být „vše na jednom místě", dokud to „vše" nemá aspoň
> dvě nebo tři položky.** Otázka „jak má Přehled vypadat" je ve
> skutečnosti otázka „co ten asistent umí".

Proto se Přehled nedá navrhnout jednou a mít hotovo. Poroste s tím, co
do asistenta přibude — a co přibude, se rozhoduje za pochodu.

První krok už hotový je: Přehled dostal **osobní hlavičku** (pozdrav podle
denní doby, datum se svátkem, počasí), kterou vidí každý bez ohledu na
práva. Do té doby platilo, že kdo má jen Nákup, kouká na jednu kartu —
a kdo nemá nic, na větu „řekni si správci".

## Co musí platit, než se to otevře cizím lidem

Tohle není seznam nápadů, ale **podmínek**. Dokud neplatí, nemá smysl
komukoliv mimo rodinu dávat adresu.

### 1. Registrace
Účty dnes zakládá správce ručně přes Správu nebo `sprava_uctu.py`. To
u cizích lidí nejde — musí si účet založit sami.

### 2. ~~Limit pokusů o přihlášení~~ — hotovo 4. 9. 2026
Přihlašovací formulář je veřejně na internetu a neměl žádný strop na počet
pokusů. Od 4. 9. 2026 se počítají chybné pokusy z jedné IP adresy: po pěti
minuta čekání, po deseti pět minut, po patnácti čtvrt hodiny. Počítá se
adresa, ne jméno — jinak by stačilo zkoušet cizí jméno a majitele účtu tím
vyřadit z provozu. Podrobnosti v [`struktura.md`](struktura.md).

### 3. Zapomenuté heslo
Kdo dnes zapomene heslo, nemá žádnou cestu zpátky — musí napsat správci,
který mu ho v aplikaci přepíše. Cizí člověk nikoho takového nemá.

### 4. Smazání účtu
Kdo svěří svoje data cizímu serveru, musí je umět i odnést. Souvisí to
s nákupními seznamy: co se stane se sdíleným seznamem, jehož vlastník
si smaže účet?

### 5. Přehodnocení Správy
„Správce vidí všechny uživatele, mění jim práva a hesla" je rodinný
koncept. U cizích lidí je to něco jiného a je potřeba rozmyslet co.

### 6. ~~Zásada 404 místo 403 platí všude~~ — ověřeno 5. 9. 2026
Platí. **Auditem se změřilo všech 20 adres, které berou `id`** něčeho
cizího, a odpovídají **stejně, ať ta věc existuje nebo ne** — u Nákupu
i u domácností 404, u Správy shodné přesměrování. Domácnosti pravidlo
zdědily, protože se u nich opisoval vzor seznamů i s brankou v SQL.

Výsledky a metoda jsou v `poznamky/audit-404.md` (mimo Git), včetně toho,
co se liší a přesto to leak není: člen na akci jen pro vlastníka dostane
302 místo 404, ale svůj seznam už vidí, takže se nic nedozvídá.

## Co bude se zařízeními

**Zatím se neruší.** Soláry jsou pořád funkční a používají se. Rozhodnutí,
které padnout musí, je jiné: jestli zařízení **zmizí**, nebo se z nich
stane **volitelná část pro toho, kdo je má**.

Kdyby odešla, odejde s nimi zhruba tisíc řádků: `devices/` (482),
`diagram.py` (175), `sber.py` (86), `ziskej_token.py` (66), šablony
`solary.html` a `nanoleaf.html`, kus `graf.py` a 61 zmínek ve `web.py`.

Zůstane ale **větší půlka a je celá obecná**: `svatky.py` (440 řádků),
`pocasi.py` (221), přihlašování a účty, motiv, `_bezpecne()`,
`_migrace_zabrana()`, makra šablon. Nic z toho není o baráku.

## Pořadí práce

1. ~~**Přehled: osobní hlavička**~~ — hotovo 2. 9. 2026
2. ~~**Přehled: obnovování**~~ — vyřešilo se samo rozdělením na Domácnost
   a Asistenta (3. 9. 2026): obnovuje se jen Domácnost, kde běží živá data
   ze zařízení, a od 4. 9. ani ta, když do domácnosti nepatříš. Zbývá
   velikost stránky Soláry v [`dalsi-kroky.md`](dalsi-kroky.md).
3. **Přehled: prázdný stav** — hláška „Zatím ti nikdo nepřidělil přístup,
   řekni si správci" je psaná pro člena rodiny, ne pro cizího člověka.
4. **Registrace** — a s ní podmínky 2 až 6 výš.
5. **Další věci do „vše"** — co asistent bude umět kromě nákupu. Zatím
   otevřené, viz níž.

## Co ještě není rozhodnuté

Tyhle otázky nejsou opomenutí — jsou zapsané schválně, aby bylo vidět,
že na ně odpověď zatím není.

- **Co asistent umí kromě Nákupu?** Nápady vznikají za pochodu. Dokud
  nebudou aspoň dva nebo tři, Přehled nemá co skládat dohromady.
- **Zůstanou zařízení, nebo odejdou?** Padlo, že ovládání Nanoleafu by
  mohlo dávat smysl i obecněji — rozmyslí se.
- **Jak se aplikace bude jmenovat?** „Domácí asistent" přestává sedět,
  když nejde o dům. Není to jen titulek: slovo *rodina* je zapsané
  i v kódu — `sprava_uctu.py` se hlásí jako „Správa rodinných účtů",
  v `database.py` to stojí u tabulky uživatelů a v `sprava.html` je
  na obrazovce nadpis „📱 Adresa pro rodinu". Přejmenování je proto
  vlastní úkol, ne kosmetika.
- **Kdo bude platit provoz a kolik lidí to unese?** Běží to na jednom
  vlastním serveru; podrobnosti v `poznamky/infrastruktura.md` (mimo Git).
