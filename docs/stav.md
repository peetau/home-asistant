# Stav projektu

Jediné místo, kde se vede stav. README na tenhle soubor odkazuje a sám ho
neopakuje — jinak by si obojí dřív nebo později začalo protiřečit.

Tenhle soubor je o **přítomnosti**: co je hotové a co aplikace umí. Kam to
míří a v jakém pořadí, je v [`plan.md`](plan.md).

**Kde jsme:** aplikace je nasazená a přihlašuje se do ní odkudkoliv přes
vlastní doménu. Čte soláry i Nanoleaf, kreslí grafy z historie, Nanoleaf umí
i ovládat, drží sdílené nákupní seznamy a spravuje účty a jejich práva.

**Zadání se ale 2. 9. 2026 změnilo.** Z nástěnky jedné domácnosti se stává
**osobní asistent, který se má dát k dispozici i lidem mimo rodinu**.
Soláry a Nanoleaf jsou zařízení jednoho konkrétního domu, takže přestávají
být jádrem a stávají se doplňkem. Jádrem jsou **Přehled** a **Nákup**.
Proč a co z toho plyne, je v [`plan.md`](plan.md).

Taby se tím dělí na dva druhy — ne na dvě poloviny aplikace, ale podle
toho, jestli potřebují hardware:

| druh | taby | kdo | co právo znamená |
|---|---|---|---|
| **dům** | Soláry, Nanoleaf | kdo ta zařízení má | důvěra k naší domácnosti |
| **nástroje** | Přehled, Nákup | kdokoliv | nic citlivého, jen tvoje data |

## Co aplikace umí

**Přehled** — nahoře osobní hlavička s pozdravem podle denní doby, datem se
svátkem a počasím za oknem. Vidí ji **každý bez ohledu na práva**; do té doby
platilo, že kdo má jen Nákup, kouká na jednu kartu, a kdo nemá nic, na větu
„řekni si správci". Pod ní karty se zařízeními a dlaždice nákupních seznamů
s počtem chybějících položek.

**Domácnost** — parta lidí, které patří zařízení: má vlastníka, členy
a **pozvánku kódem**, stejně jako nákupní seznam. Kdo je členem, vidí karty
Solárů a Nanoleafu a v pruhu tabů jejich stránky; kdo v žádné domácnosti
není, dostane místo prázdna nabídku připojit se kódem nebo si založit
vlastní. Práva `solary` a `nanoleaf` tím zanikla — k zařízením se chodí
přes členství.

Dole na stránce je karta **Správa domácnosti**: výpis členů (vlastník první),
vlastníkovi navíc tlačítko Odebrat, kód pozvánky a Nový kód; člen z ní může
odejít, vlastník ne — domácnost musí někomu patřit. Je na ní i **poslední
měření**: když karta Solárů mlčí, tohle řekne, jestli sběrač ještě měří.

**Soláry** — diagram toku energie ve vlastním SVG (šipky podle znaménka,
takže je vidět, kterým směrem energie teče), dnešní bilance včetně
soběstačnosti, proužek s dopadajícím slunečním zářením z předpovědi počasí
a čtyři grafy za 24 hodin. Tok sítě má graf obousměrný — nulu uprostřed,
nad ní dodávku, pod ní odběr.

**Nanoleaf** — stav panelů i ovládání: vypínač, jas, efekty. Obrázek podle
skutečného rozložení panelů a režim návrhu (nejdřív náhled, do panelů se
pošle až po Potvrdit). Jediná stránka s vlastním JavaScriptem.

**Nákup** — **sdílené seznamy**: každý si může založit vlastní a pozvat do
něj kohokoliv **kódem pozvánky**. Vlastník seznam přejmenuje, odebírá členy
a rozhoduje, jestli smí zvát i oni; člen může přidávat a odškrtávat cokoliv,
ale upravit nebo smazat jen to svoje. U koupené položky je vidět, **kdo
koupil komu a za kolik**, a pod seznamem se z toho spočítá **vyúčtování** —
kdo kolik zaplatil a kdo komu co vrátí (vzájemné dluhy se odečítají).

**Správa** — zakládání a mazání účtů, hesla, QR s adresou a **stav
serveru** (záloha, velikost databáze, volné místo). Právo zbylo jediné, na
Správu samotnou.

**Přihlašovací obrazovka** — pozadí podle denní doby, předpověď počasí, datum
se svátkem a indikátory sběru dat a zálohy databáze. Nepřihlášený návštěvník
u indikátorů vidí jen tři stavy (v pořádku / problém / neznámo), žádné časy,
čísla ani chybové hlášky. Formulář má **strop na počet pokusů**: po pěti
chybách z jedné adresy minuta čekání, po deseti pět minut, po patnácti čtvrt
hodiny.

**Napříč aplikací** — tmavý režim s přepínačem, který přežije zavření
prohlížeče. Sběrač `sber.py` plní databázi nezávisle na webu. Zabezpečená
přihlašovací cookie, ProxyFix za Caddy a gunicorn; popsáno
v [`provoz.md`](provoz.md).

## Roadmapa

Číslování je z původního zadání ([`zadani-projektu.md`](zadani-projektu.md)).
Ukazuje pořadí, v jakém dávaly jednotlivé dovednosti smysl se učit — ne pořadí,
v jakém se stihly. **Není to plán projektu**, ten je v [`plan.md`](plan.md).

- [x] **1 — Python a Git** — odbyto rovnou na reálném projektu místo cvičení
- [x] **2 — Web (Flask)** — data dostala stránku v prohlížeči: šablony,
      dědičnost, makra a CSS ve třech vrstvách
- [x] **3 — Databáze (SQLite)** — `sber.py` běží samostatně a plní
      `asistent.db`, stránka z ní kreslí grafy za posledních 24 hodin
- [x] **4 — Přihlašování a rodinné účty** — hashovaná hesla, zamčený
      dashboard, práva na jednotlivé taby a jejich správa přímo v aplikaci
- [x] **5 — Ovládání zařízení** — první zápis do zařízení, dosud se jen
      četlo
- [x] **6 — Hardware naživo na webu** — stránka se sama obnovuje a ukazuje,
      co právě naměřil běžící sběrač
- [x] **7 — Vzdálený přístup / hosting** — běží na vlastní doméně přes HTTPS,
      aplikaci obsluhuje gunicorn za Caddy, k domácím zařízením se server
      dostane přes Tailscale
- [ ] **8 — Rozšíření a hezčí frontend** — dělá se průběžně, ne jako
      samostatná fáze
- [ ] **9 — Rohlík (volitelný capstone)** — nezačato

Roadmapa je tím v podstatě vyčerpaná. Co se dělá dál, už z ní nevyplývá —
vyplývá to ze změny zadání popsané v [`plan.md`](plan.md).
