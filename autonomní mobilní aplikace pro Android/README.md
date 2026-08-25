# DokuCheck Admin – nativní Android aplikace (Fáze A)

Soukromé APK pro majitele DokuCheck. **Není určené pro Google Play.** Instalace jen sideload (APK).

## TUTO SLOŽKU NECOMMITUJTE

**TUTO SLOŽKU NECOMMITUJTE / NEDÁVEJTE `git add .` Z KOŘENE REPOZITÁŘE.**

Kořenové `.gitignore` se NESMÍ měnit. Soubor `.gitignore` v této složce (hvězdička) **neochrání** rodičovský `git add .`.

Práce je jen na disku. Na GitHub se tato složka **nedává**.

---

## Co to je

Flutter aplikace (jen Android, minSdk 26) pro denní provoz: objednávky, licence, odeslání platby, zapnutí/vypnutí licence, reset zařízení, verze agenta.

Server **se nemění**. Aplikace volá **existující** endpointy na `https://www.dokucheck.cz` (stejné jako webový admin).

Flutter projekt je v podsložce `dokucheck_admin/` (ASCII název – `flutter create` nesnáší mezery a diakritiku).

---

## Přihlášení (Fáze A – záměrně jako na webu)

1. Start aplikace → **zámek s otiskem / biometrií**. Otisk **jen odemkne aplikaci na telefonu**. Neodstraňuje 2FA na serveru.
2. **Jméno + heslo** (stejné jako `/login` na webu).
3. **Šestimístný kód z e-mailu** (stejné jako `/login/verify-code`).
4. Teprve potom dashboard.

**2FA se nepřeskakuje.** Uložená session se nepoužívá k přeskočení hesla a OTP. To je záměr: web se v tomto úkolu nesmí měnit.

Po úspěšném OTP drží aplikace Flask session cookie **v paměti** (běh appky) a posílá ji s CSRF hlavičkou `X-CSRF-Token` na `/admin/api/...`. Po ukončení procesu se musíte znovu přihlásit (heslo + e-mailový kód). Serverová session žije cca 24 hodin; pokud mezitím vyprší, API vrátí přesměrování na `/login` a aplikace vás vrátí na přihlášení.

Zákaznický Bearer `api_key` agenta **není** admin přihlášení – aplikace ho nepoužívá.

`/admin/api/v1/` na serveru **neexistuje**. Klient ho nevymýšlí.

---

## Obrazovky

| Obrazovka | Účel |
|-----------|------|
| Zámek | Otisk / biometrie |
| Přihlášení | Jméno + heslo |
| OTP | 6místný kód z e-mailu |
| Přehled | KPI (summary + health + volitelně stats/kpis), pull-to-refresh |
| Objednávky | Poslední objednávky ze `summary.last_orders`, detail, Odeslat platbu |
| Licence | Výpis všech licencí z `/admin/users-licenses`, filtrování, otevření podle API klíče |
| Verze agenta | POST `/admin/api/mobile/agent-version` |
| Účet | Odhlásit (GET `/logout` + vymazání session v paměti) |

Spodní lišta: **Přehled | Objednávky | Licence | Více**

Žádný WebView na celý `/admin`.

---

## Sideload (instalace APK)

1. Vytvořte release APK (viz níže).
2. Soubor bude v `dist/` (po úspěšném buildu) nebo v `dokucheck_admin/build/app/outputs/flutter-apk/app-release.apk`.
3. Na telefonu povolte instalaci z neznámých zdrojů / z tohoto správce souborů.
4. Otevřete APK a nainstalujte.
5. Spusťte **DokuCheck Admin** → otisk → jméno a heslo admina → kód z e-mailu.

---

## Spuštění ve vývoji

Vyžaduje [Flutter SDK](https://docs.flutter.dev/get-started/install/windows) a Android SDK (cmdline-tools, platform 34+, build-tools).

```powershell
cd "c:\CURSOR_SOUBORY\Claude\PDF_CHECK_SW\autonomní mobilní aplikace pro Android\dokucheck_admin"
flutter pub get
flutter analyze
flutter test
flutter run
```

Produkční base URL: `https://www.dokucheck.cz`

Debug (emulátor → host):

```powershell
flutter run --dart-define=BASE_URL=http://10.0.2.2:8080
```

Nebo upravte `dokucheck_admin/assets/app_config.yaml` (nesahá se do `desktop_agent/config.yaml`).

Release APK:

```powershell
flutter build apk --release
copy build\app\outputs\flutter-apk\app-release.apk "..\dist\DokuCheck-Admin.apk"
```

Pomocný skript: `tools\bootstrap_flutter.ps1` (pokud je Flutter v PATH, doplní Android scaffold a zkusí build).

### Automatický test v Android emulátoru

Emulátor, systémový obraz i AVD jsou lokálně v `_dev/` a na GitHub se neposílají.

```powershell
tools\pripravit_emulator.ps1
tools\spustit_emulator.ps1
tools\testovat_v_emulatoru.ps1
```

E2E test používá lokální testovací server na `http://10.0.2.2:18080` a ověřuje:

- odemčení aplikace,
- heslo a OTP,
- session cookie a CSRF,
- přehled,
- stránku licencí obsahující formulář `email` + `password`,
- načtení všech sedmi testovacích licencí bez falešného odhlášení.

Produkční OTP lze automaticky načíst jen ze samostatné testovací IMAP schránky. Soubor
`tools\e2e_secrets.example.json` zkopírujte jako `tools\e2e_secrets.json` a doplňte
údaje pouze lokálně. Skutečné údaje se nesmějí vložit do README, logů ani Gitu.

Potom lze spustit read-only kontrolu skutečného serveru:

```powershell
tools\testovat_produkci.ps1
```

Test vyvolá produkční OTP, načte ho přes IMAP, otevře dashboard a porovná načtení
licencí. Na produkci nemění licence, objednávky ani verzi agenta.

Pokud `android/` chybí nebo je neúplný (projekt byl založen bez SDK):

```powershell
cd dokucheck_admin
flutter create . --platforms=android --org cz.dokucheck --project-name dokucheck_admin
```

To **nesmí** mazat `lib/`. Potom v `AndroidManifest.xml` ověřte `USE_BIOMETRIC` a v `MainActivity` dědičnost `FlutterFragmentActivity`.

---

## Bezpečnost (klient)

- Heslo, OTP ani session cookie se **nelogují**.
- Session cookie a CSRF token jsou po OTP jen v paměti procesu (CookieJar), ne v plain SharedPreferences.
- README neobsahuje žádná hesla.

---

## GitHub

**Nepoužívá se.** Tuto složku na GitHub nenahrávejte.
