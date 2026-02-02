# NÁVOD - Jak vytvořit APK soubor a nainstalovat na Samsung S24

## METODA 1: Použití Android Studio (Doporučeno)

### Krok 1: Instalace Android Studio
1. Stáhněte Android Studio z: https://developer.android.com/studio
2. Nainstalujte Android Studio
3. Při první instalaci nechte stáhnout Android SDK

### Krok 2: Otevření projektu
1. Spusťte Android Studio
2. Klikněte na "Open" (nebo File → Open)
3. Najděte složku `TetrisGame` a otevřete ji
4. Počkejte, než se projekt načte a stáhnou se potřebné závislosti (může trvat několik minut)

### Krok 3: Vytvoření APK
1. V horním menu klikněte na **Build** → **Build Bundle(s) / APK(s)** → **Build APK(s)**
2. Počkejte na dokončení buildu (dole vpravo uvidíte progress)
3. Po dokončení se zobrazí notifikace s odkazem "locate" - klikněte na něj
4. APK soubor najdete v: `TetrisGame/app/build/outputs/apk/debug/app-debug.apk`

### Krok 4: Přenos do Samsung S24

**Varianta A - USB kabel:**
1. Připojte Samsung S24 k počítači přes USB
2. Na telefonu povolte "Přenos souborů" (File Transfer)
3. Zkopírujte `app-debug.apk` do telefonu (například do složky Downloads)

**Varianta B - Email/Cloud:**
1. Pošlete APK sobě emailem nebo nahrajte do Google Drive/Dropbox
2. Na telefonu si stáhněte APK soubor

### Krok 5: Instalace na telefonu
1. Na Samsung S24 otevřete **Nastavení** → **Zabezpečení a soukromí** → **Další nastavení zabezpečení**
2. Povolte "Instalovat neznámé aplikace" pro aplikaci, kterou použijete k instalaci (např. Moje soubory, Chrome)
3. Otevřete stažený APK soubor v telefonu
4. Potvrďte instalaci
5. Aplikace "Tetris" se objeví v menu aplikací

---

## METODA 2: Použití příkazové řádky (Pro pokročilé)

### Předpoklady:
- Nainstalovaný JDK 17 nebo novější
- Nainstalovaný Android SDK

### Postup:
1. Otevřete příkazovou řádku (CMD) ve složce `TetrisGame`
2. Spusťte:
```
gradlew.bat assembleDebug
```
3. APK najdete v: `app\build\outputs\apk\debug\app-debug.apk`
4. Pokračujte krokem 4 z Metody 1

---

## METODA 3: Použití online builderů (Nejjednodušší, ale méně bezpečné)

Můžete použít online služby jako:
- **AppGyver** (vyžaduje registraci)
- **AppsGeyser** (jednodušší, ale omezené)

**POZNÁMKA:** Pro vlastní Java kód ale většinou potřebujete Android Studio.

---

## OVLÁDÁNÍ HRY

**Tlačítka:**
- **◄** - Pohyb doleva
- **►** - Pohyb doprava
- **▼** - Rychlý pád dolů
- **↻** - Rotace dílku

**Úrovně obtížnosti:**
- Tlačítka 1-11 v dolní části
- Čím vyšší úroveň, tím rychlejší pád dílků
- Úroveň 1 = nejpomalejší (pro začátečníky)
- Úroveň 11 = nejrychlejší (pro experty)

**Skóre:**
- Za každou vyčištěnou řadu získáte 100 bodů × aktuální úroveň
- Například na úrovni 5 = 500 bodů za řadu

**Nová hra:**
- Tlačítko "Nová hra" restartuje hru

---

## ŘEŠENÍ PROBLÉMŮ

**Problém: "Instalace blokována"**
- Řešení: Povolte instalaci z neznámých zdrojů v Nastavení → Zabezpečení

**Problém: "Aplikace není kompatibilní"**
- Řešení: Samsung S24 by měl podporovat aplikaci bez problémů (minSDK 21)

**Problém: Gradle build selhává**
- Řešení: Zkontrolujte internetové připojení, Gradle stahuje závislosti

**Problém: Android Studio je pomalé**
- Řešení: Zavřete ostatní aplikace, Android Studio potřebuje hodně RAM

---

## POZNÁMKY

- APK je v DEBUG režimu, vhodné pro osobní použití
- Pro publikování na Google Play by bylo potřeba vytvořit RELEASE build s podpisem
- Aplikace funguje offline, nepotřebuje internet
- Černobílé grafické rozhraní pro úsporu baterie a retro vzhled
- Hra ukládá stav automaticky při pozastavení (minimalizace aplikace)

---

## SPECIFIKACE HRY

- **Platforma:** Android 5.0 (API 21) a novější
- **Grafika:** Černobílá
- **Rozlišení:** Adaptivní (přizpůsobí se displeji)
- **Orientace:** Pouze na výšku (portrait)
- **Velikost APK:** Cca 1-2 MB
- **Herní pole:** 10 × 20 buněk
- **Typy dílků:** 7 standardních tetromino (I, O, T, L, J, S, Z)
- **Úrovně obtížnosti:** 11 (od nejpomalejší po nejrychlejší)

Přeji hodně zábavy s Tetris hrou! 🎮
