# version.py
# Jediné místo pro verzi webové aplikace. Formát: w{RR}.{MM}.{XXX}.
# Při každé nasazené změně zvyšte XXX. Zobrazí se v patě webu a v Admin dashboardu.

WEB_VERSION = "w26.02.091"
# Číselný build (zpětná kompatibilita)
WEB_BUILD = 135

# Krátký popis novinek v tomto buildu (zobrazení v „O aplikaci“ a na landingu)
BUILD_NOTES = "Portál: správa a přejmenování zařízení; Firemní: filtr dávek podle PC; aktivační e-mail s odkazem na portál."

# Verze / build desktop agenta (zobrazení v sekci Ke stažení). Při vydání nového agenta ručně srovnat s desktop_agent/version.py.
AGENT_BUILD_ID = "56"
AGENT_VERSION_DISPLAY = "v26.02.011"
