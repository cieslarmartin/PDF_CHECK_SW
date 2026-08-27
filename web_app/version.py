# version.py
# Jediné místo pro verzi webové aplikace. Formát: w{RR}.{MM}.{XXX}.
# Při každé nasazené změně zvyšte XXX. Zobrazí se v patě webu a v Admin dashboardu.

WEB_VERSION = "w26.08.096"
# Číselný build (zpětná kompatibilita)
WEB_BUILD = 140

# Krátký popis novinek v tomto buildu (zobrazení v „O aplikaci“ a na landingu)
BUILD_NOTES = "Free web kontroly: limit 4 soubory / IP / kalendářní měsíc, počítadlo a paywall (bez e-mailu)."

# Verze / build desktop agenta (zobrazení v sekci Ke stažení). Při vydání nového agenta ručně srovnat s desktop_agent/version.py.
AGENT_BUILD_ID = "57"
AGENT_VERSION_DISPLAY = "v26.02.012"
