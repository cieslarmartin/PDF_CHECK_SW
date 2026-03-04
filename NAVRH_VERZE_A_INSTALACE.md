# Návrh: chování instalace na Windows a verze v agentu

## 1. Jak to je teď (bez změn)

### Instalátor (Inno Setup)

- V `desktop_agent/install/installer_config.iss` je **pevné AppId**: `B8E7F2A3-4C1D-4E56-9A0B-3F2C8D1E5A6B`.
- **DefaultDirName** = `{autopf}\DokuCheckPRO` (typicky `C:\Program Files\DokuCheckPRO`).

**Důsledek:**  
Windows považuje všechny instalace s tímto AppId za **stejnou aplikaci**. Když spustíte nový instalátor (novější verze), **přepíše starou instalaci** – nebude vedle sebe dva „DokuCheck PRO“, ale jeden, aktualizovaný. To je žádoucí chování.

### Verze v instalátoru

- `build_installer.py` bere **BUILD_VERSION** z `desktop_agent/version.py` (např. 51) a vloží ho do .iss jako **MyAppVersion**.
- Inno nastaví **VersionInfoVersion** v .exe na tuto verzi, takže ve Vlastnostech souboru a v Přidat/odebrat programy Windows vidíte číslo verze.

**Shrnutí:**  
Jedna instalace, upgrade přepisem, verze se zobrazuje v systému. Není potřeba měnit instalátor kvůli „jedné vs. dvě instalace“.

---

## 2. Co doplnit do agenta (až schválíte)

Aby bylo „upořádáno na verzi, kterou instaluji“ přímo v aplikaci:

### 2a) Zobrazení verze v agentu (doporučeno)

- V hlavním okně (např. v titulku nebo v patičce) zobrazit text typu: **DokuCheck PRO v26.02.006 (build 51)**.
- Případně položka menu **O aplikaci** s plnou verzí (AGENT_VERSION + BUILD_VERSION) a odkazem na web.

Zdroj verzí: `desktop_agent/version.py` (AGENT_VERSION, BUILD_VERSION) – už tam je.

### 2b) Kontrola novější verze (volitelně)

- Při startu (nebo z menu) agent zavolá API na serveru (např. endpoint z Admin nastavení) a zjistí „doporučenou“ nebo „nejnovější“ verzi.
- Pokud je na serveru vyšší build než aktuální, zobrazit např.:  
  *„K dispozici je nová verze v26.02.007. Stáhnout: [odkaz].“*

To vyžaduje:
- Na webu endpoint nebo veřejný soubor s číslem aktuální doporučené verze (např. z `web_app/version.py` nebo z DB).
- V agentovi načtení této hodnoty a porovnání s lokální BUILD_VERSION.

---

## 3. Doporučený postup

1. **Teď:**  
   Nic neměnit na instalátoru – chování (jedna aplikace, přepsání staré verze) je v pořádku.

2. **Implementovat po schválení:**  
   - **2a)** Zobrazení verze v agentu (titulek nebo „O aplikaci“).  
   - **2b)** Až budete chtít – kontrola novější verze a odkaz na stažení.

Až mi napíšete, že to má být takto (případně jen 2a, nebo 2a+2b), můžu navrhnout konkrétní úpravy v kódu agenta (kde přidat verzi do titulku, jak načíst z version.py, a pokud ano – jak volat API pro novější verzi).
