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
    heslo = getpass("  Heslo: ")
    if len(heslo) < 6:
        print("  Heslo je moc krátké (aspoň 6 znaků).")
        return

    if heslo != getpass("  Heslo znovu: "):
        print("  Hesla se neshodují.")
        return

    if database.vytvor_uzivatele(jmeno, heslo):
        print(f"  Účet '{jmeno}' vytvořen.")
    else:
        print(f"  Účet '{jmeno}' už existuje.")


def smaz_ucet():
    jmeno = input("  Jméno účtu ke smazání: ").strip()
    with database._spojeni() as db:
        kurzor = db.execute("DELETE FROM uzivatele WHERE jmeno = ?", (jmeno,))
        # rowcount říká, kolik řádků příkaz opravdu změnil
        if kurzor.rowcount:
            print(f"  Účet '{jmeno}' smazán.")
        else:
            print(f"  Účet '{jmeno}' neexistuje.")


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
