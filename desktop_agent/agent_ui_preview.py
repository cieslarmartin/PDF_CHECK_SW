# agent_ui_preview.py
# Spouští 3 vizuální varianty UI (2026) jako preview – bez zásahu do ui.py a pdf_check_agent_main.py.
# Použití: python agent_ui_preview.py --ui v1  |  python agent_ui_preview.py --ui v2  |  python agent_ui_preview.py --ui v3

import sys
import argparse
import logging

# Nastavení logování (stejně jako v pdf_check_agent_main)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler()],
)
logger = logging.getLogger(__name__)


def main():
    parser = argparse.ArgumentParser(description="DokuCheck Agent – preview UI variant V1/V2/V3")
    parser.add_argument("--ui", choices=["v1", "v2", "v3"], default="v1", help="Variant: v1 (minimal), v2 (glass), v3 (enterprise)")
    args = parser.parse_args()

    # Import skutečné logiky agenta (kontrola, licence, API)
    from pdf_check_agent_main import PDFCheckAgent

    # Výběr UI modulu podle --ui
    if args.ui == "v1":
        from ui_2026_v1_minimal import create_app_2026_v1 as create_app_preview
    elif args.ui == "v2":
        from ui_2026_v2_glass import create_app_2026_v2 as create_app_preview
    else:
        from ui_2026_v3_enterprise import create_app_2026_v3 as create_app_preview

    agent = PDFCheckAgent()
    # Stejné callbacky jako v agent.run() – vytvoříme preview UI místo produkčního
    agent.root, agent.app = create_app_preview(
        on_check_callback=agent.check_pdf,
        on_api_key_callback=agent.verify_api_key,
        api_url=agent.license_manager.api_url,
        on_login_password_callback=agent.login_with_password,
        on_logout_callback=agent.logout,
        on_get_max_files=agent.get_max_files_for_batch,
        on_after_login_callback=agent._clear_view,
        on_after_logout_callback=agent._clear_view,
        on_get_web_login_url=lambda: agent._get_web_login_url(),
        on_send_batch_callback=lambda results, src=None: agent.send_batch_results_to_api(results, src),
    )
    agent.check_first_run()
    agent._refresh_license_display()
    logger.info("Preview UI %s – spuštěno", args.ui)
    agent.root.mainloop()
    logger.info("Preview ukončen")


if __name__ == "__main__":
    main()
    sys.exit(0)
