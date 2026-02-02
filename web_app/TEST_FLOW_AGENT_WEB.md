# Jak testovat: Agent → Web přes licenční správu (PythonAnywhere)

Web běží na **https://cieslar.pythonanywhere.com**. Tento návod popisuje, jak otestovat celý tok: admin vytvoří licenci na webu → uživatel dostane klíč → v agentovi aktivuje licenci (bez úprav YAML) → výsledky na webu.

---

## Přehled flow (logika)

1. **Web** – administrátor vytvoří uživatele (licenci): jméno, e-mail, typ licence (Tier), platnost. Systém vygeneruje **licenční klíč** (API klíč).
2. **Uživatel** dostane klíč (e-mailem, z webu po „zakoupení“, nebo od admina).
3. **Uživatel si stáhne agenta**, spustí ho.
4. **V agentovi** – při prvním spuštění (nebo po kliknutí na „Licence / Přihlášení“) se zobrazí dialog **Aktivace licence**. Uživatel **vloží licenční klíč** a klikne **Ověřit a uložit**. Konfigurace (včetně uložení klíče) se upraví **automaticky**, není potřeba editovat YAML ani jiné soubory.
5. Po aktivaci má uživatel přístup k funkcím podle typu licence; výsledky kontrol se odesílají na web a zobrazí se v režimu „Z Agenta“.

**Shrnutí:** Na webu vytvoříte uživatele (licenci) a k němu máte API klíč. Ten uživatel zadá v agentovi v dialogu Aktivace licence. Žádné ruční vypisování do YAML.

---

## Co budete potřebovat

- **Web** – už nasazený na https://cieslar.pythonanywhere.com (nemusíte nic spouštět lokálně).
- **Složka pdfcheck_agent** – desktop agent na vašem PC.
- Python 3.x, nainstalované závislosti v agentovi: `pip install -r requirements.txt`.

---

## Postup testování

### Krok 1: Admin na webu – přihlášení a vytvoření licence

1. V prohlížeči otevřete: **https://cieslar.pythonanywhere.com**

2. **První účet admina** (pokud ještě nemáte):
   - Jděte na: **https://cieslar.pythonanywhere.com/admin/setup**
   - Zadejte email, heslo (2×), uložte.

3. **Přihlášení do adminu:**
   - Jděte na: **https://cieslar.pythonanywhere.com/admin/login**
   - Přihlaste se emailem a heslem.

4. **Vytvoření licence (API klíč pro „uživatele“):**
   - V admin dashboardu klikněte na **„Nová licence“**.
   - Vyplňte:
     - **Jméno uživatele** – např. „Test Uživatel“
     - **Email** – např. „test@example.cz“
     - **Tier** – vyberte **Basic** nebo **Pro**
     - **Platnost (dny)** – např. 365
   - Klikněte **„Vytvořit“**.
   - **Zkopírujte vygenerovaný API klíč** (např. `sk_basic_xxxx...` nebo `sk_pro_xxxx...`).

---

### Krok 2: Aktivace licence v agentovi (bez úprav YAML)

1. Otevřete složku **pdfcheck_agent** a spusťte agenta: `python agent.py`.

2. Při prvním spuštění se zobrazí dialog **„Aktivace licence / Přihlášení“**. Pokud ne, klikněte v dolní liště na **„Licence / Přihlášení“**.

3. V dialogu uvidíte:
   - **Server** – adresa webu (např. https://cieslar.pythonanywhere.com).
   - **Lichenční klíč** – sem vložte klíč z Kroku 1 (admin → Nová licence → zkopírovaný klíč).

4. Klikněte **„Ověřit a uložit“**. Agent ověří klíč na webu a uloží ho do konfigurace. **Nemusíte ručně upravovat config.yaml.**

5. Po úspěšné aktivaci se v dolní liště agenta zobrazí např. **„Přihlášen: user@email.cz (Basic)“**.

---

### Krok 3: Spuštění agenta a kontrola PDF

1. V příkazovém řádku ve složce **pdfcheck_agent** napište:

   ```bash
   python agent.py
   ```

2. V okně agenta:
   - Vyberte složku s PDF nebo jeden soubor (přetáhnutím nebo tlačítkem).
   - Klikněte na **„Zkontrolovat PDF“** (nebo ekvivalent).

3. Agent by měl:
   - Ověřit API klíč na webu (`/api/auth/verify`),
   - Zkontrolovat PDF,
   - Odeslat výsledky na **https://cieslar.pythonanywhere.com** (`/api/batch/upload`).

---

### Krok 4: Kontrola výsledků na webu

1. V prohlížeči otevřete: **https://cieslar.pythonanywhere.com**

2. Přepněte do režimu **„Z Agenta“** (pokud má aplikace přepínač režimů).

3. Měly by se zobrazit výsledky z agenta – batche, složky, soubory.

4. V admin dashboardu (**/admin**) u dané licence uvidíte statistiky (počet kontrol, zařízení atd.).

---

## Rychlý checklist

| Krok | Akce | Ověření |
|------|------|---------|
| 1a | Admin setup (první účet) | https://cieslar.pythonanywhere.com/admin/setup → účet vytvořen |
| 1b | Admin login | https://cieslar.pythonanywhere.com/admin/login → dashboard |
| 1c | Nová licence, zvolit Tier, vytvořit | API klíč zkopírován |
| 2 | V agentu: Licence / Přihlášení → vložit klíč → Ověřit a uložit | Aktivace licence, přehled účtu v dolní liště |
| 3 | Spustit agenta, zkontrolovat PDF | Kontrola proběhne, data se odešlou |
| 4 | Web – režim „Z Agenta“ | Vidíte batch a výsledky z agenta |

---

## Řešení problémů

- **Agent: „Nelze se připojit k serveru“**  
  - Zkontrolujte internet.  
  - V **config.yaml** musí být `api.url: https://cieslar.pythonanywhere.com` (ne 127.0.0.1).

- **Agent: „Neplatný API klíč“ / 401**  
  - Použijte přesně klíč z adminu (Nová licence).  
  - V adminu ověřte, že licence je **Aktivní** a ne vypršená.

- **Na webu nejsou výsledky z agenta**  
  - Ověřte, že agent skutečně odeslal batch (log v terminálu / agent.log).  
  - Na webu jste v režimu „Z Agenta“ a používáte https://cieslar.pythonanywhere.com.

---

*Návod pro PDF DokuCheck na PythonAnywhere. © 2025 Ing. Martin Cieślar*
