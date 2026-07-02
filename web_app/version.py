# version.py
# Jediné místo pro verzi webové aplikace. Formát: w{RR}.{MM}.{XXX}.
# Při každé nasazené změně zvyšte XXX. Zobrazí se v patě webu a v Admin dashboardu.

WEB_VERSION = "w26.02.079"
# Číselný build (zpětná kompatibilita)
WEB_BUILD = 123

# Krátký popis novinek v tomto buildu (zobrazení v „O aplikaci“ a na landingu)
BUILD_NOTES = "Nový tarif FIREMNÍ (1 licence = 5 zařízení, cena za 4), přidávání vlastních tierů v Adminu."

# Verze / build desktop agenta (zobrazení v sekci Ke stažení). Při vydání nového agenta ručně srovnat s desktop_agent/version.py.
AGENT_BUILD_ID = "55"
AGENT_VERSION_DISPLAY = "v26.02.010"
