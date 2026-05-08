# version.py
# Jediné místo pro verzi webové aplikace. Formát: w{RR}.{MM}.{XXX}.
# Při každé nasazené změně zvyšte XXX. Zobrazí se v patě webu a v Admin dashboardu.

WEB_VERSION = "w26.02.062"
# Číselný build (zpětná kompatibilita)
WEB_BUILD = 106

# Krátký popis novinek v tomto buildu (zobrazení v „O aplikaci“ a na landingu)
BUILD_NOTES = "Produkční landing přepnut na landing_preview variantu H; přepínač variant zůstává jen na /landing-preview."

# Verze / build desktop agenta (zobrazení v sekci Ke stažení). Při vydání nového agenta ručně srovnat s desktop_agent/version.py.
# TEST: build 54 pro ověření update notifieru (pak vrátit na 53).
AGENT_BUILD_ID = "54"
AGENT_VERSION_DISPLAY = "v26.02.008"
