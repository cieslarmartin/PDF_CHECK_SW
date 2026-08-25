# Návod: ČSOB příchozí platby (IMAP) na PythonAnywhere

Avíza z banky chodí na **cieslar@dokucheck.cz**. Server je čte přes IMAP, páruje podle **přesného VS + částky na haléř**.

**Automatická aktivace licence je defaultně VYPNUTÁ** – v adminu ji zapnete až po otestování.

---

## 1. Co musí být na PythonAnywhere (env)

**Web → vaše webová app → Environment variables** (pak **Reload**):

| Proměnná | Hodnota |
|----------|---------|
| `IMAP_HOST` | `imap.seznam.cz` |
| `IMAP_PORT` | `993` |
| `IMAP_USER` | `cieslar@dokucheck.cz` |
| `IMAP_PASSWORD` | **Heslo pro aplikace** ze Seznamu (ne běžné heslo k webu) |
| `IMAP_FOLDER` | `INBOX` |

Heslo **nikdy** do gitu ani do DB.

### Jak získat Heslo pro aplikace (Seznam)

1. Přihlaste se na účet `cieslar@dokucheck.cz` (Seznam / Seznam Profi).
2. Nastavení → Hesla aplikací (nebo Bezpečnost) → vytvořit nové heslo pro IMAP.
3. To heslo vložte do `IMAP_PASSWORD` na PA.

Ujistěte se, že je u schránky **zapnutý IMAP**.

---

## 2. Python balíčky na PA

V Bash konzoli (ve virtualenv webu):

```bash
pip install dkimpy dnspython
```

Bez `dkimpy` skončí avíza jako **podezřelé** (bez DKIM se nikdy neaktivuje).

---

## 3. Nasazení kódu

```bash
cd /home/cieslar/...   # složka s web_app
git pull
```

Pak na PA **Web → Reload**.

Admin: **Prodej → Příchozí platby ČSOB**  
URL: `https://www.dokucheck.cz/admin/csob-platby`

---

## 4. Otestování (doporučené pořadí)

1. V adminu nechte **autoaktivaci VYPNUTO**.
2. Sekce **Stav připojení** – musí být zelené „heslo nastaveno“ a „dkimpy OK“.
3. Tlačítko **Ověřit IMAP přihlášení**.
4. **Nahrát .eml** (vzorové avízo) – ověří parser (případně zaškrtnout „Přeskočit DKIM“ jen pro lokální test).
5. **Spustit IMAP** – případně zaškrtnout „Včetně už přečtených od ČSOB“, pokud jste avízo už otevřeli v mailu.
6. Při shodě VS+částka vznikne stav **Shoda** → ručně **Aktivovat**.
7. Až bude vše OK, teprve **Zapnout autoaktivaci**.

---

## 5. Automat každých 5 minut (Always-on)

Na PA (Hacker / placený plán – outbound IMAP):

**Tasks → Always-on**:

```bash
cd /home/cieslar/CESTA_K_WEB_APP && python process_csob_payments.py --loop --interval 300
```

Cestu upravte podle skutečné složky (`web_app` na PA).

Jednorázový běh:

```bash
python process_csob_payments.py
```

---

## 6. Bezpečnost (shrnutí)

- Aktivace **nikdy** bez platného DKIM `d=csob.cz` (automat).
- Párování jen **přesný VS + přesná částka** (haléře).
- Cizí maily ve schránce se **neoznačují** jako přečtené.
- Kill-switch `auto_activate_csob` v adminu – kdykoli vypnout.
