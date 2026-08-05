# version.py
# Jediné místo pro verzi webové aplikace. Formát: w{RR}.{MM}.{XXX}.
# Při každé nasazené změně zvyšte XXX. Zobrazí se v patě webu a v Admin dashboardu.

WEB_VERSION = "w26.02.090"
# Číselný build (zpětná kompatibilita)
WEB_BUILD = 134

# Krátký popis novinek v tomto buildu (zobrazení v „O aplikaci“ a na landingu)
BUILD_NOTES = "Admin: Web kontroly (IP) – limit souborů zdarma/24 h s auto-blokací IP, detail IP a detail uživatele se statistikami."

# Verze / build desktop agenta (zobrazení v sekci Ke stažení). Při vydání nového agenta ručně srovnat s desktop_agent/version.py.
AGENT_BUILD_ID = "56"
AGENT_VERSION_DISPLAY = "v26.02.011"
