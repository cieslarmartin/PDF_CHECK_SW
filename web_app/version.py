# version.py
# Jediné místo pro verzi webové aplikace. Formát: w{RR}.{MM}.{XXX}.
# Při každé nasazené změně zvyšte XXX. Zobrazí se v patě webu a v Admin dashboardu.

WEB_VERSION = "w26.02.047"
# Číselný build (zpětná kompatibilita)
WEB_BUILD = 91

# Krátký popis novinek v tomto buildu (zobrazení v „O aplikaci“ a na landingu)
BUILD_NOTES = "Oprava cloudové kontroly PDF: web znovu vidí sdílený engine desktop_agent/pdf_checker.py (sys.path)."

# Verze / build desktop agenta (zobrazení v sekci Ke stažení). Při vydání nového agenta ručně srovnat s desktop_agent/version.py.
# TEST: build 54 pro ověření update notifieru (pak vrátit na 53).
AGENT_BUILD_ID = "54"
AGENT_VERSION_DISPLAY = "v26.02.008"
