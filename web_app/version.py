# version.py
# Jediné místo pro verzi webové aplikace. Formát: w{RR}.{MM}.{XXX}.
# Při každé nasazené změně zvyšte XXX. Zobrazí se v patě webu a v Admin dashboardu.

WEB_VERSION = "w26.02.069"
# Číselný build (zpětná kompatibilita)
WEB_BUILD = 113

# Krátký popis novinek v tomto buildu (zobrazení v „O aplikaci“ a na landingu)
BUILD_NOTES = "Admin: reálné přihlášení (bez obcházení session), heslo admin + druhý kód e-mailem na otp_email (výchozě cieslar@dokucheck.cz). SESSION_COOKIE_SECURE z env. Tabulka admin_login_challenges."

# Verze / build desktop agenta (zobrazení v sekci Ke stažení). Při vydání nového agenta ručně srovnat s desktop_agent/version.py.
# TEST: build 54 pro ověření update notifieru (pak vrátit na 53).
AGENT_BUILD_ID = "54"
AGENT_VERSION_DISPLAY = "v26.02.008"
