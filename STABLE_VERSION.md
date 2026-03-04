# Stabilní verze (restore point)

Tento soubor označuje **verzi, na kterou se lze vrátit**, když později zasahujete do kódu a chcete mít jistotu „čistého“ stavu.

## Aktuální stabilní verze

- **Agent:** v26.02.006 (BUILD 51)
- **Web:** w26.02.015 (WEB_BUILD 59)
- **Datum označení:** 2026-02-24

## Návrat na tuto verzi

1. **Označení v Gitu (doporučeno)**  
   Jednorázově vytvořte tag (v kořeni repozitáře):
   ```bash
   git tag v26.02.006
   ```
   Případně s popisem:
   ```bash
   git tag -a v26.02.006 -m "Stabilní verze: podpisy přes pypdf, batch podle složek, lokální test"
   ```
   Tag lze později pushnout: `git push origin v26.02.006`.

2. **Vrácení kódu na tuto verzi**  
   - Podle tagu: `git checkout v26.02.006`  
   - Podle commitu: `git checkout <hash>` (hash commitu, který odpovídá této verzi)

3. **V chatu (Cursor)**  
   Můžete napsat: *„Vrať změny k verzi v26.02.006“* nebo *„Návrat na stabilní verzi podle STABLE_VERSION.md“*. Asistent pak použije `git checkout v26.02.006` (nebo daný commit).

## Kdy aktualizovat tento soubor

Při každém „uzavření“ verze, ke které chcete mít možnost návratu, upravte datum a čísla verzí v tomto souboru a případně vytvořte nový tag (např. `v26.03.001`).
