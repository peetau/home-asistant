# Stav projektu

Jediné místo, kde se vede stav. README na tenhle soubor odkazuje a sám ho
neopakuje — jinak by si obojí dřív nebo později začalo protiřečit.

**Kde jsme:** aplikace je nasazená a rodina se do ní přihlašuje odkudkoliv
přes vlastní doménu. Čte soláry i Nanoleaf, kreslí grafy z historie, Nanoleaf
umí i ovládat a spravuje účty a jejich práva. Tab Soláry ukazuje diagram toku
energie, dnešní bilanci a čtyři grafy.

**Aplikace se posunula od nástěnky našeho baráku k osobnímu asistentovi.**
Taby se tím rozpadly na dva druhy:

| druh | taby | kdo | co právo znamená |
|---|---|---|---|
| **dům** | Soláry, Nanoleaf | jen rodina | důvěra k naší domácnosti |
| **nástroje** | Nákup | kdokoliv | nic citlivého, jen tvoje data |

Nákup proto umí **sdílené seznamy**: každý si může založit vlastní, pozvat
do něj kohokoliv kódem a k zařízením v domě se ten člověk nedostane.

**Co se dělá teď.** Postupně se prochází taby, každý dostane svoje kolo
práce, a až potom se zamyká přihlášení:

1. ~~tab **Nákup**~~ — hotovo, a v září 2026 celý přestavěný na sdílené
   seznamy (viz níž)
2. ~~tab **Správa**~~ — hotovo
3. ~~tab **Soláry**~~ — hotovo (1. 9. 2026)
4. ~~**Přehled** (dashboard)~~ — dostal dlaždice s nákupními seznamy;
   větší kolo práce ho ještě čeká
5. **registrace** — účty zatím zakládá správce ručně. Až se otevře
   registrace, přestane být limit pokusů odloženou věcí a stane se
   **podmínkou**
6. **limit pokusů o přihlášení** — formulář je veřejně na internetu a nemá
   žádný strop na počet pokusů; podrobnosti a další odložené věci jsou
   v [`dalsi-kroky.md`](dalsi-kroky.md)

## Roadmapa

Číslování je z původního zadání ([`zadani-projektu.md`](zadani-projektu.md)).
Ukazuje pořadí, v jakém dávaly jednotlivé dovednosti smysl se učit — ne pořadí,
v jakém se stihly.

- [x] **1 — Python a Git** — odbyto rovnou na reálném projektu místo cvičení
- [x] **2 — Web (Flask)** — data dostala stránku v prohlížeči: šablony,
      dědičnost, makra a CSS ve třech vrstvách
- [x] **3 — Databáze (SQLite)** — `sber.py` běží samostatně a plní
      `asistent.db`, stránka z ní kreslí grafy za posledních 24 hodin
- [x] **4 — Přihlašování a rodinné účty** — hashovaná hesla, zamčený
      dashboard, práva na jednotlivé taby a jejich správa přímo v aplikaci
- [x] **5 — Ovládání zařízení** — první zápis do zařízení, dosud se jen
      četlo: vypínač, jas a efekty Nanoleaf, obrázek podle skutečného
      rozložení panelů a režim návrhu (nejdřív náhled, do panelů se pošle
      až po Potvrdit)
- [x] **6 — Hardware naživo na webu** — stránka se sama obnovuje a ukazuje,
      co právě naměřil běžící sběrač
- [x] **7 — Vzdálený přístup / hosting** — běží na vlastní doméně přes HTTPS,
      aplikaci obsluhuje gunicorn za Caddy, k domácím zařízením se server
      dostane přes Tailscale
- [ ] **8 — Rozšíření a hezčí frontend** — dělá se průběžně, ne jako
      samostatná fáze
- [ ] **9 — Rohlík (volitelný capstone)** — nezačato

## Co přibylo mimo roadmapu

- **Nákupní seznam** — společný pro rodinu: přidávání, odškrtávání, úklid
- **Správa uživatelů** — zakládání a mazání účtů, práva na jednotlivé taby
- **Tmavý režim** — přepínač motivu, volba přežije zavření prohlížeče
- **Přihlašovací obrazovka** — pozadí podle denní doby, předpověď počasí,
  datum se svátkem a indikátory sběru dat a zálohy databáze. Nepřihlášený
  návštěvník u indikátorů vidí jen tři stavy (v pořádku / problém / neznámo),
  žádné časy, čísla ani chybové hlášky
- **Příprava na produkci** — zabezpečená přihlašovací cookie, ProxyFix za
  Caddy a gunicorn; popsáno v [`provoz.md`](provoz.md)
- **Tab Soláry** — diagram toku energie ve vlastním SVG (šipky podle
  znaménka, takže je vidět, kterým směrem energie teče), dnešní bilance
  včetně soběstačnosti, proužek s dopadajícím slunečním zářením z předpovědi
  počasí a čtyři grafy za 24 hodin. Tok sítě má graf obousměrný — nulu
  uprostřed, nad ní dodávku, pod ní odběr.
- **Sdílené nákupní seznamy** — každý uživatel si může založit vlastní
  seznam a pozvat do něj kohokoliv **kódem pozvánky**. Vlastník seznam
  přejmenuje, odebírá členy a rozhoduje, jestli smí zvát i oni; člen může
  přidávat a odškrtávat cokoliv, ale upravit nebo smazat jen to svoje.
  U koupené položky je vidět, **kdo koupil komu a za kolik**, a pod
  seznamem se z toho spočítá **vyúčtování** — kdo kolik zaplatil a kdo komu
  co vrátí (vzájemné dluhy se odečítají).
