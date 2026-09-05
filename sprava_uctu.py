r"""
Správa rodinných účtů.

Spuštění:
    .venv\Scripts\python.exe sprava_uctu.py

Nabídne jednoduché menu: vypsat účty, přidat nový, smazat.
Hesla se při psaní nezobrazují a ukládají se jen jako hash.
"""

from getpass import getpass

import database


def vypis_ucty():
    ucty = database.seznam_uzivatelu()
    if not ucty:
        print("  (zatím žádné účty)")
        return
    print(f"  {'id':>3}  {'jméno':<16} vytvořen")
    for id_u, jmeno, vytvoren in ucty:
        print(f"  {id_u:>3}  {jmeno:<16} {vytvoren}")


def pridej_ucet():
    jmeno = input("  Jméno (např. petr, mama): ").strip()
    if not jmeno:
        print("  Jméno nesmí být prázdné.")
        return

    # getpass čte heslo, ale NEZOBRAZUJE ho - nikdo ti ho nepřečte přes rameno
    # a nezůstane v historii terminálu.
    # E-mail je od 5. 9. 2026 přihlašovací údaj, takže účet bez něj by se
    # dovnitř nedostal.
    email = input("  E-mail: ").strip()
    if not email:
        print("  E-mail nesmí být prázdný.")
        return

    heslo = getpass("  Heslo: ")
    if len(heslo) < 6:
        print("  Heslo je moc krátké (aspoň 6 znaků).")
        return

    if heslo != getpass("  Heslo znovu: "):
        print("  Hesla se neshodují.")
        return

    if database.vytvor_uzivatele(jmeno, email, heslo):
        print(f"  Účet '{jmeno}' vytvořen.")
    else:
        print("  Účet se nezaložil: e-mail už někdo používá, "
              "nebo to není adresa.")


def smaz_ucet():
    """
    Maže podle ID, ne podle jména.

    ⚠️ Do 5. 9. 2026 se mazalo podle jména a bylo to bezpečné, protože
    jména byla jedinečná. Od chvíle, kdy jedinečná nejsou, by
    `DELETE ... WHERE jmeno = ?` smazal VŠECHNY účty toho jména naraz.
    Id je vypsané v seznamu účtů o kus výš.

    Kontroly (poslední správce, vlastník seznamu nebo domácnosti) dělá
    database.smaz_uzivatele() - proto se volá ona, a ne holý DELETE.
    """
    zadano = input("  ID účtu ke smazání: ").strip()
    if not zadano.isdigit():
        print("  Zadej číslo ze sloupce id.")
        return

    ok, duvod = database.smaz_uzivatele(int(zadano))
    print("  Účet smazán." if ok else "  " + duvod)


def main():
    database.init_db()

    while True:
        print()
        print("=== Správa rodinných účtů ===")
        vypis_ucty()
        print()
        print("  [p] přidat účet   [s] smazat účet   [k] konec")
        volba = input("  Volba: ").strip().lower()

        if volba == "p":
            pridej_ucet()
        elif volba == "s":
            smaz_ucet()
        elif volba in ("k", "q", ""):
            print("  Konec.")
            break
        else:
            print("  Neznámá volba.")


if __name__ == "__main__":
    main()
