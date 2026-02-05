# Jak spustit PDF DokuCheck Agent

Agent používá **grafiku V3 (Enterprise)** – strom složek, metriky, možnosti odebrání z fronty, spuštění z disku je stejné jako dříve.

## 1. Co je potřeba

- **Python 3.8+** (s tkinter – bývá součástí instalace Pythonu)
- Nainstalované závislosti ze složky `desktop_agent`

## 2. Instalace závislostí (stačí jednou)

V příkazové řádce (PowerShell nebo CMD):

```text
cd C:\Claude\PDF_CHECK_SW\desktop_agent
pip install -r requirements.txt
```

Nebo z kořene projektu:

```text
cd C:\Claude\PDF_CHECK_SW
pip install -r desktop_agent\requirements.txt
```

Nainstaluje se: `requests`, `PyYAML`, `tkinterdnd2`, `customtkinter`.

## 3. Jak agent otevřít (spustit)

### Varianta A – dvojklik na batch soubor

1. Otevřete složku **desktop_agent**:  
   `C:\Claude\PDF_CHECK_SW\desktop_agent`
2. Dvojklik na **SPUSTIT_AGENT.bat**
3. Mělo by se otevřít okno agenta (V3 Enterprise rozhraní).

### Varianta B – z příkazové řádky

1. Spusťte **PowerShell** nebo **CMD**.
2. Přejděte do složky agenta:
   ```text
   cd C:\Claude\PDF_CHECK_SW\desktop_agent
   ```
3. Spusťte:
   ```text
   python pdf_check_agent_main.py
   ```

### Varianta C – z Cursor / VS Code

1. Otevřete složku `PDF_CHECK_SW` v editoru.
2. Otevřete integrovaný terminál (Ctrl+`).
3. Zadejte:
   ```text
   cd desktop_agent
   python pdf_check_agent_main.py
   ```

## 4. Po spuštění

- Při prvním spuštění se může objevit dialog **Přihlášení**. Můžete zvolit **Vyzkoušet zdarma** nebo zadat e-mail a heslo.
- Přidejte **soubory** nebo **složku** s PDF (tlačítka nebo přetažení do zóny).
- Klikněte na **Kontrola**. U více souborů uvidíte progress bar.
- Po dokončení se zeptá: **Chcete poslat na server?** – Ano = odeslání a otevření webu, Ne = jen lokální výsledky.
- **Otevřít web** v hlavičce otevře portál s přihlášením (pokud jste přihlášeni).

## 5. Když to neběží

- **„python není rozpoznán“** – do PATH není přidaný Python; při instalaci Pythonu zaškrtněte **Add Python to PATH**, nebo použijte plnou cestu k `python.exe`.
- **Chyba u importu (customtkinter, tkinterdnd2…)** – v složce `desktop_agent` znovu spusťte:  
  `pip install -r requirements.txt`
- **Žádné okno se neotevře** – v terminálu by měla být chybová hláška; pošlete ji pro diagnostiku.

---

## Rychlé shrnutí – spuštění z disku

| Způsob | Postup |
|--------|--------|
| **Dvojklik** | Složka `desktop_agent` → dvojklik na **SPUSTIT_AGENT.bat** |
| **Příkazová řádka** | `cd C:\Claude\PDF_CHECK_SW\desktop_agent` → `python pdf_check_agent_main.py` |
| **Z kořene projektu** | `python desktop_agent\pdf_check_agent_main.py` (z `C:\Claude\PDF_CHECK_SW`) |

Před prvním spuštěním nainstalujte závislosti:  
`pip install -r desktop_agent\requirements.txt`
