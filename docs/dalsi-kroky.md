# Další kroky

Seznam věcí, na které jsme narazili a odložili je. Není to plán, jen ať
nezapadnou.

## Bezpečnost

### Limit pokusů o přihlášení
**Priorita: vysoká.** Přihlašovací formulář je veřejně na internetu
a nemá žádný strop na počet pokusů — kdokoliv může zkoušet hesla
donekonečna. Hashování hesel je schválně pomalé, takže útok není snadný,
ale bránit se tomu nijak nebráníme.

Co s tím:
- počítat neúspěšné pokusy podle jména i podle IP adresy
- po několika pokusech krátká prodleva, po dalších delší
- pozor, ať se tím nedá vyřadit z provozu poctivý uživatel (útočník by
  mohl schválně zkoušet cizí jméno, aby ho zablokoval)
- za Caddy je skutečná IP v hlavičce, kterou už čte ProxyFix

## Provoz

### Y520 místo domácího PC jako Tailscale průchod
Teď drží spojku k zařízením hlavní počítač. Y520 by bral míň proudu
a nerestartoval se při práci. Postup je stejný jako u desktopu.

### Druhá adresa `asistent.` (bez překlepu)
Doména běží na `asistant.pepacodes.cz`. Kdyby vadilo, dá se přidat
`A` záznam pro `asistent.` a v Caddy nechat obojí.

## Rozvoj

- portfolio na `pepacodes.cz` — přidá se jako další blok v Caddy
- e-shop — dostane vlastní server
- další zařízení = další tab (viz `VSECHNY_TABY` v `database.py`)
