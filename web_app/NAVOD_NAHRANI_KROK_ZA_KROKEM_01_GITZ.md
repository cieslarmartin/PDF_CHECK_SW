# Nahrazení na web (PythonAnywhere) – krok za krokem pro začátečníky

Tento návod vás provede od nuly: co je Git, co nastavit na PythonAnywhere a jak pak nahrávat na web automaticky místo ručního kopírování.

---

## Část 1: Co je Git a proč ho použít

**Git** je nástroj na správu verzí kódu. Pro vás znamená hlavně toto:

- Na **disku** máte složku s projektem (např. `c:\Claude\41`).
- **Git** v té složce sleduje změny v souborech (co jste přidali, upravili, smazali).
- Můžete tyto změny **odeslat** na internet (na službu jako **GitHub**) – tomu se říká **push**.
- Na **PythonAnywhere** pak stejný projekt **stáhnete** z internetu jedním příkazem (**pull**) – nemusíte nic kopírovat ručně.

**Zjednodušeně:**  
Na PC uděláte změny → řeknete Gitu „ulož to a pošli na GitHub“. Na PythonAnywhere otevřete konzoli a řeknete „stáhni novou verzi z GitHubu“. Tím nahradíte ruční nahrávání souborů.

---

## Část 2: Co budete potřebovat

1. **Účet na PythonAnywhere** – ten už máte (https://www.pythonanywhere.com/).
2. **Účet na GitHubu** (zdarma) – na https://github.com/ si vytvořte účet, pokud ho nemáte.
3. **Git na vašem PC** – program, který budete spouštět v příkazové řádce. Nainstalujte ho (viz krok 3 níže).

---

## Část 3: Nainstalovat Git na váš počítač

1. Otevřete v prohlížeči: **https://git-scm.com/download/win**
2. Stáhněte instalační soubor (např. „Click here to download“).
3. Spusťte instalaci. Většinou stačí nechat výchozí volby – jen klikat „Next“, na konci „Finish“.
4. **Restartujte počítač** (nebo alespoň zavřete a znovu otevřete příkazový řádek / PowerShell).
5. Ověření: otevřete **PowerShell** nebo **CMD** (vyhledat „cmd“ nebo „PowerShell“ v menu Start) a napište:
   ```bash
   git --version
   ```
   Mělo by se zobrazit něco jako `git version 2.43...`. Pokud ano, Git je nainstalovaný.

---

## Část 4: Vytvořit repozitář na GitHubu

1. Přihlaste se na **https://github.com/**.
2. Vpravo nahoře klikněte na **„+“** → **„New repository“**.
3. **Repository name:** napište např. `pdf-dokucheck-web` (bez mezer, malými písmeny).
4. **Public** nechte zaškrtnuté.
5. **Nevyplňujte** „Add a README“ ani další volby – nechte prázdné.
6. Klikněte **„Create repository“**.
7. Na další stránce uvidíte adresu repozitáře. Bude vypadat takto (s vaším jménem a názvem):
   ```text
   https://github.com/VASE_GITHUB_JMENO/pdf-dokucheck-web.git
   ```
   Tuto adresu si **zkopírujte** (budete ji potřebovat později). Můžete ji napsat i na papír.

--- https://github.com/cieslarmartin/pdf-dokucheck-web.git

## Část 5: Připojit váš projekt (složka 41) k Gitu na PC

1. Na disku otevřete složku, kde máte projekt. Např. **`c:\Claude`** (tedy složka, ve které je podsložka **41**).
2. V té složce (`c:\Claude`) otevřete **PowerShell** nebo **CMD**:
   - Ve složce v Průzkumníku klikněte do řádku s cestou nahoře, smažte text a napište `powershell` a Enter,  
   **nebo**
   - Menu Start → vyhledat „PowerShell“ → spustit → v okně napsat:
     ```bash
     cd c:\Claude
     ```
     a Enter.
3. V příkazové řádce (v `c:\Claude`) zadejte po řádcích tyto příkazy. Po každém zmáčkněte Enter.

   **a) Inicializace Gitu v této složce:**
   ```bash
   git init
   ```
   Mělo by se objevit: „Initialized empty Git repository...“.

   **b) Připojení k vašemu repozitáři na GitHubu** (nahraďte adresu tou, co jste si zkopírovali v kroku 4):
   ```bash
   git remote add origin https://github.com/VASE_GITHUB_JMENO/pdf-dokucheck-web.git
   ```

   **c) Přidání souborů ze složky 41 do Gitu:**
   ```bash
   git add 41
   ```

   **d) První „zápis“ verze (commit):**
   ```bash
   git commit -m "Prvni verze webu v41"
   ```

   **e) Odeslání na GitHub (push):**
   ```bash
   git branch -M main
   git push -u origin main
   ```
   Po `git push` se může zeptat na **přihlášení do GitHubu**. Pokud máte dvoufázové ověření, použijte **Personal Access Token** místo hesla (GitHub vám ukáže odkaz, kde token vytvořit – v Settings → Developer settings → Personal access tokens).

Až příkaz doběhne bez chyby, vaše složka `41` je na GitHubu. Můžete to zkontrolovat – obnovte stránku vašeho repozitáře v prohlížeči, měla by tam být složka `41` se soubory.

---

## Část 6: Nastavení na PythonAnywhere (jednou)

1. Přihlaste se na **https://www.pythonanywhere.com/**.
2. Otevřete záložku **„Consoles“** (Konzole). Klikněte na **„Bash“** (nebo „$ Bash“) – otevře se černé okno (konzole).
3. V konzoli napište (nahraďte adresu vaším repozitářem z kroku 4):
   ```bash
   cd ~
   git clone https://github.com/VASE_GITHUB_JMENO/pdf-dokucheck-web.git mujweb
   ```
   Místo `mujweb` můžete použít název složky, který už na PythonAnywhere máte pro web (např. `cieslar.pythonanywhere.com`). Pokud tam už něco máte, raději použijte nový název (např. `mujweb`) a pak v záložce Web změníte cestu k projektu.
4. Po dokončení příkazu (`git clone`) se vytvoří složka `mujweb` (nebo jak jste ji pojmenovali) a v ní váš projekt včetně složky `41`.
5. **Záložka Web:**
   - Klikněte na **„Web“** v horní liště.
   - U **„Source code“** nastavte cestu tak, aby ukazovala na váš projekt. Např.:
     ```text
     /home/VASE_PA_JMENO/mujweb/41
     ```
     (VASE_PA_JMENO = vaše přihlašovací jméno na PythonAnywhere.)
   - U **„WSGI configuration file“** nastavte cestu k WSGI souboru, např.:
     ```text
     /home/VASE_PA_JMENO/mujweb/41/cieslar_pythonanywhere_com_wsgi.py
     ```
   - Klikněte na zelené tlačítko **„Reload“** (načíst znovu web).
6. Otestujte v prohlížeči vaši adresu (např. `https://cieslar.pythonanywhere.com/`). Měla by běžet aktuální verze z Gitu.

Tím máte na PythonAnywhere projekt napojený na GitHub. Od teď stačí na serveru stahovat nové verze (viz část 7).

---

## Část 7: Jak od teď „nahrávat“ na web (už ne ručně)

Kdykoli na **PC** něco v projektu (ve složce 41) změníte a chcete to mít na webu:

### Na vašem počítači (v `c:\Claude`)

1. Otevřete **PowerShell** nebo **CMD** a přejděte do složky projektu:
   ```bash
   cd c:\Claude
   ```
2. Pošlete změny do Gitu a na GitHub:
   ```bash
   git add 41
   git commit -m "Aktualizace webu"
   git push
   ```
   (Zpráva u `commit` může být cokoli, např. „Oprava adminu“ nebo „Nova verze“.)

### Na PythonAnywhere

1. Přihlaste se na **https://www.pythonanywhere.com/**.
2. Záložka **„Consoles“** → **„Bash“** (nebo otevřete už existující Bash).
3. V konzoli:
   ```bash
   cd ~/mujweb
   git pull
   ```
   (Pokud jste složku pojmenovali jinak, napište `cd ~/nazev_slozky`.)
4. Záložka **„Web“** → klikněte na zelené tlačítko **„Reload“**.

Tím je na webu nová verze. Ručně už nic nekopírujete – jen `git add`, `commit`, `push` na PC a na PythonAnywhere `git pull` + Reload.

---

## Část 8: (Volitelně) Automatický reload po „push“

Pokud nechcete na PythonAnywhere ručně klikat na **Reload**, můžete použít skript, který reload udělá za vás přes PythonAnywhere API.

1. Na PythonAnywhere: **Account** (ikona uživatele vpravo nahoře) → **„API Token“**. Klikněte na **„Create new API token“** a token si **zkopírujte** (ukáže se jen jednou).
2. Na PC ve složce **41**:
   - Je tam soubor **`deploy_config.example.env`**. Zkopírujte ho a přejmenujte na **`deploy_config.env`**.
   - Do **`deploy_config.env`** napište (bez uvozovek, nahraďte svými údaji):
     ```text
     PA_USERNAME=vase_pythonanywhere_jmeno
     PA_API_TOKEN=vase_api_token_zkopirovany_z_kroku_1
     PA_DOMAIN=cieslar.pythonanywhere.com
     ```
3. Při nasazení pak na PC stačí spustit:
   ```bash
   cd c:\Claude\41
   python deploy_to_pythonanywhere.py
   ```
   Skript udělá commit + push a přes API znovu načte web (Reload). Na PythonAnywhere stále musíte v Bash jednou spustit **`git pull`** (nebo si nastavit SSH a doplnit ho do skriptu – to je pokročilejší).

---

## Shrnutí – co kdy děláte

| Kde | Co děláte |
|-----|------------|
| **Jednou** | Nainstalujete Git, vytvoříte repozitář na GitHubu, v `c:\Claude` spustíte `git init`, `remote add`, `add 41`, `commit`, `push`. |
| **Jednou** | Na PythonAnywhere v Bash: `git clone` vašeho repozitáře, v záložce Web nastavíte cestu a WSGI, Reload. |
| **Při každé aktualizaci** | Na PC: `git add 41`, `git commit -m "popis"`, `git push`. Na PythonAnywhere: v Bash `cd ~/mujweb`, `git pull`, v záložce Web **Reload**. |
| **Volitelně** | Do `deploy_config.env` dáte API token a doménu; při nasazení spustíte `python deploy_to_pythonanywhere.py` – push + automatický Reload. |

Pokud nějaký krok nevyjde (napíše to chybu), pošlete přesnou zprávu z příkazové řádky nebo screenshot a dá se podle toho doplnit konkrétní řešení.
