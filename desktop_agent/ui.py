# ui.py
# PDF DokuCheck Agent – Dashboard layout, Sidebar + Main, celoplošný DnD, moderní Treeview.

import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import threading
import webbrowser
import os

import customtkinter as ctk

from version import BUILD_VERSION

# Téma
ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

# Globální font a Treeview
FONT_FAMILY = "Segoe UI"
FONT_SIZE = 14
FONT_SIZE_TITLE = 15
FONT_SIZE_HEADER = 17
TREEVIEW_BG = "#1e1e1e"
TREEVIEW_FG = "#e5e7eb"
TREEVIEW_ROWHEIGHT = 38
TREEVIEW_SELECT = "#0891b2"
SIDEBAR_WIDTH = 260

# Zkus importovat TkinterDnD (s CTk root může být nefunkční – drop zóna pak jen klik)
try:
    from tkinterdnd2 import DND_FILES, TkinterDnD
    TKINTERDND_AVAILABLE = True
except ImportError:
    TKINTERDND_AVAILABLE = False


def _format_result_summary(filename, status, result):
    """
    Vytvoří uživatelsky přívětivý souhrn výsledku. NIKDY nevrací raw JSON.
    result: dict z analyze_pdf_file nebo None (pending/skipped).
    """
    lines = []
    status_labels = {'pending': '...', 'success': 'OK', 'error': 'CHYBA', 'skipped': 'Přeskočeno'}
    label = status_labels.get(status, '...')
    lines.append(f"[{label}]  {filename}")
    lines.append("")

    if result is None:
        if status == 'skipped':
            lines.append("Přeskočeno z důvodu limitu licence.")
        else:
            lines.append("Čeká na zpracování.")
        return "\n".join(lines)

    if not isinstance(result, dict):
        if isinstance(result, str) and result.strip().startswith("{"):
            try:
                import json
                result = json.loads(result)
            except Exception:
                result = None
        if not isinstance(result, dict):
            lines.append("Žádná data k zobrazení.")
            return "\n".join(lines)

    # Skipped / limit reached
    if result.get('skipped') or (result.get('success') is False and 'limit' in str(result.get('error', '')).lower()):
        lines.append("Přeskočeno z důvodu limitu licence.")
        return "\n".join(lines)

    # Time processed
    processed_at = result.get('processed_at') or ''
    if processed_at:
        try:
            from datetime import datetime
            dt = datetime.fromisoformat(processed_at.replace('Z', '+00:00'))
            time_str = dt.strftime('%d.%m.%Y %H:%M')
        except Exception:
            time_str = processed_at[:19] if len(processed_at) > 19 else processed_at
        lines.append(f"Zpracováno: {time_str}")
    lines.append("")

    # Details table (plain language)
    display = result.get('display') or {}
    results_inner = result.get('results') or {}
    pdf_format = results_inner.get('pdf_format') or {}

    pdfa_version = display.get('pdf_version') or pdf_format.get('exact_version') or "—"
    lines.append(f"PDF/A verze: {pdfa_version}")

    sig_count = display.get('signature_count', 0)
    signatures = display.get('signatures') or results_inner.get('signatures') or []
    valid_sig = sum(1 for s in signatures if s.get('valid'))
    invalid_sig = len(signatures) - valid_sig
    if sig_count == 0:
        lines.append("Podpisy: 0")
    else:
        lines.append(f"Podpisy: {valid_sig} platných, {invalid_sig} neplatných")

    # Validation errors as bullet points
    errors = []
    if not result.get('success'):
        err = result.get('error')
        if err:
            errors.append(err)
    if pdf_format.get('exact_version') and 'ne PDF/A' in str(pdf_format.get('exact_version', '')):
        errors.append("Dokument není ve formátu PDF/A.")
    for s in signatures:
        if not s.get('valid'):
            name = s.get('name') or s.get('signer', '—') if isinstance(s, dict) else '—'
            errors.append(f"Neplatný podpis: {name}")
    if errors:
        lines.append("")
        lines.append("Chyby validace:")
        for e in errors:
            lines.append(f"  • {e}")
    else:
        if result.get('success'):
            lines.append("")
            lines.append("Dokument je v pořádku.")

    return "\n".join(lines)


def _result_cell_pdfa(result):
    """Pilulka: ✓ (zelená) / ✗ (červená) pro sloupec PDF/A."""
    if not result or not isinstance(result, dict):
        return "—", "muted"
    inner = result.get("results") or {}
    pdf_format = inner.get("pdf_format") or {}
    if result.get("skipped"):
        return "Přeskočeno", "muted"
    is_a3 = pdf_format.get("is_pdf_a3") or result.get("display", {}).get("is_pdf_a3")
    return (" ✓ ", "ok") if is_a3 else (" ✗ ", "fail")


def _result_cell_podpis(result):
    """Pilulka ✓/✗ pro sloupec Podpis."""
    if not result or not isinstance(result, dict):
        return "—", "muted"
    if result.get("skipped"):
        return "Přeskočeno", "muted"
    sigs = (result.get("results") or {}).get("signatures") or []
    valid = sum(1 for s in sigs if s.get("valid"))
    if not sigs:
        return " ✗ ", "fail"
    return (" ✓ ", "ok") if valid == len(sigs) else (f" ✗ {len(sigs)-valid}", "fail")


def _result_cell_razitko(result):
    """Pilulka ✓/✗ pro sloupec Čas. razítko (VČR/LOK)."""
    if not result or not isinstance(result, dict):
        return "—", "muted"
    if result.get("skipped"):
        return "Přeskočeno", "muted"
    sigs = (result.get("results") or {}).get("signatures") or []
    has_tsa = any(s.get("timestamp_valid") for s in sigs)
    if not sigs:
        return "—", "muted"
    return (" ✓ ", "ok") if has_tsa else (" ✗ ", "fail")


def _count_errors_from_result(result):
    """Z výsledku kontroly vrátí počet chyb (0 = OK). Stejná logika jako v _format_result_summary."""
    if not result or not isinstance(result, dict):
        return 0
    if result.get('skipped'):
        return 0
    errors = 0
    if not result.get('success') and result.get('error'):
        errors += 1
    results_inner = result.get('results') or {}
    pdf_format = results_inner.get('pdf_format') or {}
    if pdf_format.get('exact_version') and 'ne PDF/A' in str(pdf_format.get('exact_version', '')):
        errors += 1
    for s in (results_inner.get('signatures') or []):
        if not s.get('valid'):
            errors += 1
    return errors


def _session_summary_text(tasks, queue_display, session_files_checked):
    """Text pro pravý panel když nic není vybráno (souhrn relace)."""
    n_tasks = len(tasks)
    n_checked = sum(1 for q in queue_display if q.get('checked'))
    return (
        f"Fronta: {n_tasks} úkolů ({n_checked} vybráno)\n"
        f"Dnes zkontrolováno: {session_files_checked} souborů"
    )


class PDFCheckUI:
    """Hlavní GUI – Modern Dark UI, fronta úkolů."""

    # Barevné schéma sjednocené s webem: tmavé pozadí, akcent modrá/tyrkys z pdf_check_web_main
    BG_APP = "#121212"
    BG_CARD = "#1e1e1e"
    BG_HEADER = "#1a1a2e"
    BG_HEADER_LIGHT = "#16213e"
    TEXT_DARK = "#e5e7eb"
    TEXT_MUTED = "#9ca3af"
    ACCENT = "#0891b2"           # tyrkys/cyan jako na webu (btn-cyan)
    ACCENT_BLUE = "#1e5a8a"      # modrá jako header na webu
    SUCCESS_GREEN = "#22c55e"
    ERROR_RED = "#ef4444"
    WARNING_ORANGE = "#f97316"
    BORDER = "#2d2d2d"
    DROP_HOVER = "#2d2d2d"
    BUTTON_TEXT = "#ffffff"
    ACCENT_BTN = "#0891b2"
    SECONDS_PER_FILE_ETA = 0.4   # odhad času na 1 soubor (s)

    def __init__(self, root, on_check_callback, on_api_key_callback, api_url="",
                 on_login_password_callback=None, on_logout_callback=None, on_get_max_files=None,
                 on_after_login_callback=None, on_after_logout_callback=None, on_get_web_login_url=None,
                 on_send_batch_callback=None):
        self.root = root
        self.on_check_callback = on_check_callback
        self.on_api_key_callback = on_api_key_callback
        self.on_login_password_callback = on_login_password_callback
        self.on_logout_callback = on_logout_callback
        self.on_get_max_files = on_get_max_files
        self.on_after_login_callback = on_after_login_callback
        self.on_after_logout_callback = on_after_logout_callback
        self.on_get_web_login_url = on_get_web_login_url
        self.on_send_batch_callback = on_send_batch_callback
        self.api_url = api_url or "https://www.dokucheck.cz"

        # Tasks: list of {type: 'folder'|'file', path, name, file_paths: [str]}
        self.tasks = []
        # Flat file list in task order: [{'path', 'filename', 'status', 'result', 'checked'}, ...]
        self.queue_display = []
        # Map tree iid (task_i_file_j) -> queue_display index
        self._iid_to_qidx = {}
        # Map results_tree iid -> queue_display index (pro detail při výběru)
        self._results_iid_to_qidx = {}

        # Session: počet zkontrolovaných souborů v této relaci (pro souhrn)
        self.session_files_checked = 0

        # Tracking pro progress
        self.start_time = None
        self.total_files = 0
        self.processed_files = 0
        self.cancel_requested = False
        self.is_running = False

        self.root.title("PDF DokuCheck Agent")
        self.root.geometry("1000x700")
        self.root.minsize(800, 600)
        try:
            self.root.configure(fg_color=self.BG_APP)
        except tk.TclError:
            self.root.configure(bg=self.BG_APP)

        self.center_window()
        self.create_widgets()

    def center_window(self):
        """Vycentruje okno na obrazovce"""
        self.root.update_idletasks()
        width = 1000
        height = 700
        x = (self.root.winfo_screenwidth() // 2) - (width // 2)
        y = (self.root.winfo_screenheight() // 2) - (height // 2)
        self.root.geometry(f'{width}x{height}+{x}+{y}')

    def open_web_after_check(self):
        """Otevře web dashboard po dokončení kontroly (s automatickým přihlášením, pokud je agent přihlášen)"""
        url = None
        if self.on_get_web_login_url:
            try:
                url = self.on_get_web_login_url()
            except Exception:
                pass
        webbrowser.open(url or self.api_url or "https://www.dokucheck.cz")

    def set_export_xls_enabled(self, enabled):
        """Žádné tlačítko Export Excel v agentovi – metoda ponechána kvůli kompatibilitě s pdf_check_agent_main."""
        pass

    def create_widgets(self):
        """UI 2025: sidebar_frame (260px) + main_frame. Modern.Treeview, celoplošný DnD, CTkSegmentedButton filtry."""
        # Styl "Modern.Treeview" – rowheight 38, Segoe UI 14
        _tree_style = ttk.Style()
        _tree_style.theme_use("clam")
        _tree_style.configure(
            "Modern.Treeview",
            rowheight=38,
            font=(FONT_FAMILY, FONT_SIZE),
            background=TREEVIEW_BG,
            fieldbackground=TREEVIEW_BG,
            foreground=TREEVIEW_FG,
        )
        _tree_style.configure(
            "Modern.Treeview.Heading",
            font=(FONT_FAMILY, 15, "bold"),
            background=self.BORDER,
            foreground=TREEVIEW_FG,
        )
        _tree_style.map("Modern.Treeview", background=[("selected", TREEVIEW_SELECT)], foreground=[("selected", self.BUTTON_TEXT)])
        _tree_style.configure("Modern.Treeview", borderwidth=0)
        _tree_style.configure("Modern.Treeview.Heading", borderwidth=0)

        self.root.grid_columnconfigure(0, weight=0, minsize=SIDEBAR_WIDTH)
        self.root.grid_columnconfigure(1, weight=1)
        self.root.grid_rowconfigure(0, weight=1)

        # ——— sidebar_frame (levý, 260px, tmavší) ———
        sidebar_frame = ctk.CTkFrame(self.root, fg_color=self.BG_HEADER, width=SIDEBAR_WIDTH, corner_radius=0)
        sidebar_frame.grid(row=0, column=0, sticky="nswe", padx=0, pady=0)
        sidebar_frame.grid_propagate(False)
        # Account Info
        ctk.CTkLabel(sidebar_frame, text="DokuCheck", font=(FONT_FAMILY, 20, "bold"), text_color=self.BUTTON_TEXT).pack(pady=(20, 0))
        ctk.CTkLabel(sidebar_frame, text=f"Build {BUILD_VERSION}", font=(FONT_FAMILY, FONT_SIZE - 2), text_color=self.TEXT_MUTED).pack(pady=(0, 16))
        ctk.CTkLabel(sidebar_frame, text="Můj účet", font=(FONT_FAMILY, FONT_SIZE, "bold"), text_color=self.TEXT_DARK).pack(anchor=tk.W, padx=16, pady=(8, 4))
        self.sidebar_account = ctk.CTkLabel(sidebar_frame, text="Nepřihlášen", font=(FONT_FAMILY, FONT_SIZE - 1), text_color=self.TEXT_MUTED, wraplength=SIDEBAR_WIDTH - 32)
        self.sidebar_account.pack(anchor=tk.W, padx=16, pady=(0, 4))
        self.sidebar_tier = ctk.CTkLabel(sidebar_frame, text="Tier: —", font=(FONT_FAMILY, FONT_SIZE - 2), text_color=self.TEXT_MUTED, wraplength=SIDEBAR_WIDTH - 32)
        self.sidebar_tier.pack(anchor=tk.W, padx=16, pady=(0, 2))
        self.sidebar_daily_limit = ctk.CTkLabel(sidebar_frame, text="Denní limit: —", font=(FONT_FAMILY, FONT_SIZE - 2), text_color=self.TEXT_MUTED, wraplength=SIDEBAR_WIDTH - 32)
        self.sidebar_daily_limit.pack(anchor=tk.W, padx=16, pady=(0, 12))
        self.sidebar_stats = ctk.CTkLabel(sidebar_frame, text="Zkontrolováno: 0 | Úspěšnost: —", font=(FONT_FAMILY, FONT_SIZE - 2), text_color=self.TEXT_MUTED, wraplength=SIDEBAR_WIDTH - 32)
        self.sidebar_stats.pack(anchor=tk.W, padx=16, pady=(0, 16))
        def _open_web():
            try:
                url = self.on_get_web_login_url() if self.on_get_web_login_url else None
            except Exception:
                url = None
            webbrowser.open(url or self.api_url or "https://www.dokucheck.cz")
        ctk.CTkButton(sidebar_frame, text="Otevřít Web", command=_open_web, corner_radius=8, fg_color=self.ACCENT, width=200, font=(FONT_FAMILY, FONT_SIZE)).pack(pady=6, padx=16, fill=tk.X)
        # Spodní sekce: Admin, Log out
        self.sidebar_settings_btn = ctk.CTkButton(sidebar_frame, text="Admin", command=self._show_settings, corner_radius=8, fg_color=self.BORDER, width=200, font=(FONT_FAMILY, FONT_SIZE))
        self.sidebar_settings_btn.pack(pady=6, padx=16, fill=tk.X)
        self.logout_btn_header = ctk.CTkButton(sidebar_frame, text="Odhlásit", command=self._do_logout, corner_radius=8, fg_color=self.ERROR_RED, width=200, font=(FONT_FAMILY, FONT_SIZE))
        self.logout_btn_header.pack(pady=6, padx=16, fill=tk.X)
        self.logout_btn_header.pack_forget()
        self.login_btn_header = ctk.CTkButton(sidebar_frame, text="Přihlásit", command=self.show_api_key_dialog, corner_radius=8, fg_color=self.BG_HEADER_LIGHT, width=200, font=(FONT_FAMILY, FONT_SIZE))
        self.login_btn_header.pack(pady=6, padx=16, fill=tk.X)
        self.daily_limit_label = self.sidebar_daily_limit
        self.license_status_label = ctk.CTkLabel(sidebar_frame, text="", font=(FONT_FAMILY, FONT_SIZE - 2), text_color=self.ERROR_RED, wraplength=SIDEBAR_WIDTH - 32)
        self.license_status_label.pack(anchor=tk.W, padx=16, pady=(0, 8))

        # ——— main_frame (pravý, dynamický) ———
        main_frame = ctk.CTkFrame(self.root, fg_color="transparent")
        main_frame.grid(row=0, column=1, sticky="nsew", padx=0, pady=0)
        main_frame.grid_rowconfigure(1, weight=1)
        main_frame.grid_columnconfigure(0, weight=1)

        # Header: VYMAZAT VŠE (tlačítka filtru Vše/Chyby/PDF/A-3 OK odstraněna)
        header_dash = ctk.CTkFrame(main_frame, fg_color=self.BG_CARD, height=52, corner_radius=0)
        header_dash.grid(row=0, column=0, sticky="ew")
        header_dash.grid_propagate(False)
        main_frame.grid_columnconfigure(0, weight=1)
        self.results_filter = tk.StringVar(value="VŠE")
        ctk.CTkButton(header_dash, text="VYMAZAT VŠE", command=self.clear_queue, corner_radius=8, fg_color=self.ERROR_RED, width=120, height=32, font=(FONT_FAMILY, FONT_SIZE - 1, "bold")).pack(side=tk.RIGHT, padx=12, pady=10)

        # Content: strom + detail vlevo, fronta úkolů vpravo (bez malé drop zóny)
        content = ctk.CTkFrame(main_frame, fg_color="transparent")
        content.grid(row=1, column=0, sticky="nsew", padx=10, pady=6)
        content.grid_columnconfigure(0, weight=1, minsize=260)
        content.grid_columnconfigure(1, weight=1, minsize=320)
        content.grid_rowconfigure(0, weight=1)

        # Levý blok – Projektový strom (Modern.Treeview + status pilulky)
        left_panel = ctk.CTkFrame(content, fg_color=self.BG_CARD, corner_radius=10)
        left_panel.grid(row=0, column=0, sticky="nsew", padx=(0, 5))
        left_panel.grid_rowconfigure(2, weight=1)
        left_panel.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(left_panel, text="Projektový strom", font=(FONT_FAMILY, FONT_SIZE_TITLE, "bold"), text_color=self.TEXT_DARK).grid(row=0, column=0, sticky="w", padx=12, pady=(12, 4))
        results_tree_frame = tk.Frame(left_panel, bg=self.BG_CARD)
        results_tree_frame.grid(row=2, column=0, sticky="nsew", padx=12, pady=(0, 8))
        rtree_scroll = ttk.Scrollbar(results_tree_frame)
        self.results_tree = ttk.Treeview(results_tree_frame, columns=("pdfa", "podpis", "razitko"), show="tree headings", height=14, yscrollcommand=rtree_scroll.set, selectmode="browse", style="Modern.Treeview")
        self.results_tree.heading("#0", text="Soubor")
        self.results_tree.heading("pdfa", text="PDF/A")
        self.results_tree.heading("podpis", text="Podpis")
        self.results_tree.heading("razitko", text="Čas. razítko")
        self.results_tree.column("#0", width=200)
        self.results_tree.column("pdfa", width=72)
        self.results_tree.column("podpis", width=80)
        self.results_tree.column("razitko", width=72)
        rtree_scroll.config(command=self.results_tree.yview)
        self.results_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        rtree_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        # Status pilulky: status_ok (#22c55e, bílý text), status_error (#ef4444, bílý text)
        self.results_tree.tag_configure("status_ok", foreground="white", background="#22c55e")
        self.results_tree.tag_configure("status_error", foreground="white", background="#ef4444")
        self.results_tree.tag_configure("muted", foreground=self.TEXT_MUTED)
        self.results_tree.tag_configure("folder", font=(FONT_FAMILY, FONT_SIZE, "bold"))
        self.results_tree.bind("<<TreeviewSelect>>", self._on_results_tree_select)
        self.detail_text = ctk.CTkTextbox(left_panel, font=(FONT_FAMILY, FONT_SIZE - 1), fg_color=self.BG_APP, text_color=self.TEXT_DARK, corner_radius=8, wrap="word", height=72)
        self.detail_text.grid(row=3, column=0, sticky="ew", padx=12, pady=(0, 12))
        self.results_text = self.detail_text
        self._show_session_summary()

        # Pravý blok – pouze fronta úkolů (malá drop zóna odstraněna; DnD celé okno)
        right_panel = ctk.CTkFrame(content, fg_color=self.BG_CARD, corner_radius=10)
        right_panel.grid(row=0, column=1, sticky="nsew", padx=(5, 0))
        right_panel.grid_rowconfigure(2, weight=1)
        right_panel.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(right_panel, text="Fronta úkolů", font=(FONT_FAMILY, FONT_SIZE_TITLE, "bold"), text_color=self.TEXT_DARK).grid(row=0, column=0, sticky="w", padx=12, pady=(12, 4))
        btn_row = ctk.CTkFrame(right_panel, fg_color="transparent")
        btn_row.grid(row=1, column=0, sticky="nw", padx=12, pady=(0, 4))
        ctk.CTkButton(btn_row, text="Přidat soubory", command=self.add_files, corner_radius=8, fg_color=self.ACCENT, width=110, font=(FONT_FAMILY, FONT_SIZE - 1)).pack(side=tk.LEFT, padx=(0, 4))
        ctk.CTkButton(btn_row, text="+ Složka", command=self.add_folder, corner_radius=8, fg_color=self.ACCENT, width=90, font=(FONT_FAMILY, FONT_SIZE - 1)).pack(side=tk.LEFT, padx=4)
        ctk.CTkButton(btn_row, text="Vymazat historii", command=self.clear_queue, corner_radius=8, fg_color=self.BORDER, width=110, font=(FONT_FAMILY, FONT_SIZE - 1)).pack(side=tk.LEFT, padx=4)
        tree_frame = tk.Frame(right_panel, bg=self.BG_CARD)
        tree_frame.grid(row=2, column=0, sticky="nsew", padx=12, pady=(0, 12))
        right_panel.grid_rowconfigure(2, weight=1)
        tree_scroll = ttk.Scrollbar(tree_frame)
        self.queue_tree = ttk.Treeview(tree_frame, columns=("name", "status", "errors", "action"), show="tree headings", height=12, yscrollcommand=tree_scroll.set, selectmode="browse")
        tree_scroll.config(command=self.queue_tree.yview)
        self.queue_tree.heading("#0", text=" ")
        self.queue_tree.heading("name", text="Úkol / Soubor")
        self.queue_tree.heading("status", text="Stav")
        self.queue_tree.heading("errors", text="Chyby")
        self.queue_tree.heading("action", text="Smazat")
        self.queue_tree.column("#0", width=32)
        self.queue_tree.column("name", width=200)
        self.queue_tree.column("status", width=70)
        self.queue_tree.column("errors", width=70)
        self.queue_tree.column("action", width=56)
        self.queue_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        tree_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        self.queue_tree.bind("<<TreeviewSelect>>", self._on_queue_select)
        self.queue_tree.bind("<Button-1>", self._on_tree_click)
        self.queue_tree.tag_configure("task_row", background=TREEVIEW_BG, foreground=TREEVIEW_FG)

        # Footer: progress + status (štíhlý) – progress_row se zobrazí při běhu kontroly
        footer = ctk.CTkFrame(main_frame, fg_color=self.BORDER, height=44, corner_radius=0)
        footer.grid(row=2, column=0, sticky="ew")
        footer.grid_propagate(False)
        progress_row = ctk.CTkFrame(footer, fg_color="transparent")
        progress_row.pack(fill=tk.X, padx=12, pady=(6, 2))
        self.progress_label = ctk.CTkLabel(progress_row, text="Připraveno", text_color=self.TEXT_MUTED, anchor="w", font=(FONT_FAMILY, FONT_SIZE - 1))
        self.progress_label.pack(side=tk.LEFT, fill=tk.X, expand=True)
        self.cancel_btn = ctk.CTkButton(progress_row, text="Zrušit", command=self.cancel_check, corner_radius=6, fg_color=self.ERROR_RED, width=60, height=24, font=(FONT_FAMILY, FONT_SIZE - 2))
        self.cancel_btn.pack(side=tk.RIGHT, padx=4)
        self.cancel_btn.pack_forget()
        self.progress = ctk.CTkProgressBar(progress_row, height=10, corner_radius=5, progress_color=self.ACCENT)
        self.progress.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 8))
        self.progress.set(0)
        progress_row.pack_forget()
        self._progress_row = progress_row
        footer_inner = ctk.CTkFrame(footer, fg_color="transparent")
        footer_inner.pack(fill=tk.X, padx=12, pady=4)
        self.stats_label = ctk.CTkLabel(footer_inner, text="Načteno: 0 souborů", text_color=self.TEXT_MUTED, font=(FONT_FAMILY, FONT_SIZE - 2))
        self.stats_label.pack(side=tk.LEFT)
        self.eta_label = ctk.CTkLabel(footer_inner, text="Odhad: —", text_color=self.TEXT_MUTED, font=(FONT_FAMILY, FONT_SIZE - 2))
        self.eta_label.pack(side=tk.RIGHT)
        ctk.CTkLabel(footer_inner, text=f"Build {BUILD_VERSION}", font=(FONT_FAMILY, FONT_SIZE - 2), text_color=self.TEXT_MUTED).pack(side=tk.RIGHT, padx=12)

        self._check_btn_anchor = ctk.CTkFrame(content, fg_color="transparent")
        self._check_btn_anchor.grid(row=4, column=0, columnspan=2, pady=8)
        self.check_btn = ctk.CTkButton(self._check_btn_anchor, text="ODESLAT KE KONTROLE", font=(FONT_FAMILY, FONT_SIZE, "bold"), corner_radius=10, fg_color=self.ACCENT_BTN, height=42, command=self.on_check_clicked)
        self.check_btn.pack(pady=4)

        self.header_status = self.sidebar_account
        self.logout_btn = self.logout_btn_header

        # Celoplošný DnD: overlay přes celé okno, root jako drop target
        self._dnd_overlay_main = None
        self._setup_global_dnd()

    def _on_filter_segment(self, value):
        """Callback CTkSegmentedButton: mapuje Vše/Chyby/PDF/A-3 OK na filtr a překreslí strom."""
        m = {"Vše": "VŠE", "Chyby": "POUZE CHYBY", "PDF/A-3 OK": "PDF/A-3 OK"}
        self.results_filter.set(m.get(value, "VŠE"))
        self.update_results_tree()

    def _show_settings(self):
        """Placeholder pro Nastavení (Build 46)."""
        messagebox.showinfo("Nastavení", "Nastavení aplikace připravujeme.\nPro konfiguraci serveru a klíče použijte config.yaml ve složce agenta.")

    def _setup_global_dnd(self):
        """Celé okno přijímá soubory. dnd_overlay (modrý) se zobrazí při drag_enter, skryje při drop/leave."""
        if not TKINTERDND_AVAILABLE:
            return
        try:
            # Overlay přes celé root okno (tk.Frame – TkinterDnD2 vyžaduje tk widget)
            overlay = tk.Frame(self.root, bg=self.ACCENT)
            overlay.place(relx=0, rely=0, relwidth=1, relheight=1)
            overlay.place_forget()
            label = tk.Label(overlay, text="Pustit soubory k analýze", font=(FONT_FAMILY, 18, "bold"), fg="white", bg=self.ACCENT)
            label.place(relx=0.5, rely=0.5, anchor=tk.CENTER)
            overlay.drop_target_register(DND_FILES)
            overlay.dnd_bind("<<Drop>>", self._on_global_drop)
            overlay.dnd_bind("<<DragEnter>>", lambda e: overlay.place(relx=0, rely=0, relwidth=1, relheight=1))
            overlay.dnd_bind("<<DragLeave>>", lambda e: overlay.place_forget())
            self._dnd_overlay_main = overlay
            # Root také jako drop target, aby drag nad celým oknem zobrazil overlay
            self.root.drop_target_register(DND_FILES)
            self.root.dnd_bind("<<DragEnter>>", lambda e: overlay.place(relx=0, rely=0, relwidth=1, relheight=1))
            self.root.dnd_bind("<<DragLeave>>", lambda e: overlay.place_forget())
            self.root.dnd_bind("<<Drop>>", self._on_global_drop)
        except Exception:
            self._dnd_overlay_main = None

    def _on_global_drop(self, event):
        """Zpracuje drop na celoplošný overlay a skryje overlay."""
        if getattr(self, "_dnd_overlay_main", None):
            self._dnd_overlay_main.place_forget()
        paths = self.root.tk.splitlist(event.data)
        for raw in paths:
            path = self._normalize_path(raw)
            if path:
                self.add_path_to_queue(path)
        self.update_queue_display()

    @staticmethod
    def _normalize_path(item):
        """
        Normalizuje vstup na řetězec cesty.
        - str -> použije se jako cesta
        - dict s klíčem 'path' -> vrátí item['path']
        - dict s klíčem 'full_path' -> vrátí item['full_path']
        - jinak -> vrátí None
        """
        if item is None:
            return None
        if isinstance(item, str) and item.strip():
            return item.strip()
        if isinstance(item, dict):
            path = item.get('path') or item.get('full_path')
            if path and isinstance(path, str) and path.strip():
                return path.strip()
        return None

    @staticmethod
    def _path_to_filename(path_or_dict):
        """Z cesty (str) nebo dict s 'filename'/'path'/'full_path' vrátí jméno souboru."""
        if path_or_dict is None:
            return ''
        if isinstance(path_or_dict, str):
            return os.path.basename(path_or_dict)
        if isinstance(path_or_dict, dict):
            name = path_or_dict.get('filename')
            if name:
                return name
            p = path_or_dict.get('full_path') or path_or_dict.get('path')
            if p and isinstance(p, str):
                return os.path.basename(p)
        return ''

    def on_drop(self, event):
        """Handler pro drag & drop - podporuje složky i soubory"""
        paths = self.root.tk.splitlist(event.data)
        for raw in paths:
            path = self._normalize_path(raw)
            if path:
                self.add_path_to_queue(path)
            elif raw is not None:
                try:
                    logger = __import__('logging').getLogger(__name__)
                    logger.warning("on_drop: nelze použít položku (neplatná cesta): %s", type(raw).__name__)
                except Exception:
                    pass
        self.update_queue_display()

    def _update_header_stats(self):
        """Aktualizuje stats v patičce a v sidebaru."""
        if hasattr(self, 'stats_label'):
            n_files = sum(len(t.get('file_paths', [])) for t in self.tasks)
            n_folders = sum(1 for t in self.tasks if t.get('type') == 'folder')
            self.stats_label.configure(text=f"Načteno: {n_files} souborů" + (f" v {n_folders} složkách" if n_folders else ""))
        self._update_sidebar_stats()

    def _update_sidebar_stats(self):
        """Sidebar: Zkontrolováno: X | Úspěšnost: Y%."""
        if not getattr(self, 'sidebar_stats', None):
            return
        total = len([q for q in self.queue_display if q.get('status') not in ('pending', None)])
        ok = len([q for q in self.queue_display if q.get('status') == 'success'])
        if total == 0:
            self.sidebar_stats.configure(text="Zkontrolováno: 0 | Úspěšnost: —")
        else:
            pct = int(round(100 * ok / total)) if total else 0
            self.sidebar_stats.configure(text=f"Zkontrolováno: {total} | Úspěšnost: {pct}%")

    def _set_results_filter(self, value):
        """Nastaví filtr a překreslí strom. Synchronizuje CTkSegmentedButton."""
        self.results_filter.set(value)
        seg = getattr(self, "filter_segmented", None)
        if seg:
            m = {"VŠE": "Vše", "POUZE CHYBY": "Chyby", "PDF/A-3 OK": "PDF/A-3 OK"}
            seg.set(m.get(value, "Vše"))
        self.update_results_tree()

    def _include_by_filter(self, item):
        """True pokud má být položka zobrazena podle aktuálního filtru."""
        f = self.results_filter.get()
        if f == "VŠE":
            return True
        result = item.get("result")
        if not result or not isinstance(result, dict):
            return f == "POUZE CHYBY"  # pending – zobraz jen u CHYBY
        if result.get("skipped"):
            return f != "PDF/A-3 OK"
        if f == "POUZE CHYBY":
            return _count_errors_from_result(result) > 0
        if f == "PDF/A-3 OK":
            inner = result.get("results") or {}
            pdf_format = inner.get("pdf_format") or {}
            return pdf_format.get("is_pdf_a3") or result.get("display", {}).get("is_pdf_a3")
        return True

    def update_results_tree(self):
        """Naplní Projektový strom z tasks + queue_display (složka → soubory, sloupce PDF/A, Podpis, Čas. razítko)."""
        if not getattr(self, "results_tree", None):
            return
        self._results_iid_to_qidx.clear()
        for iid in self.results_tree.get_children():
            self.results_tree.delete(iid)
        qidx = 0
        for task_ix, task in enumerate(self.tasks):
            file_paths = task.get("file_paths", [])
            name = task.get("name", "")
            iid_task = f"rtask_{task_ix}"
            self.results_tree.insert("", tk.END, iid=iid_task, values=("", "", ""), text=f"📁 {name}", tags=("folder",))
            for j in range(len(file_paths)):
                if qidx >= len(self.queue_display):
                    break
                item = self.queue_display[qidx]
                if not self._include_by_filter(item):
                    qidx += 1
                    continue
                fn = item.get("filename", "")
                result = item.get("result")
                pdfa_txt, pdfa_tag = _result_cell_pdfa(result)
                podpis_txt, podpis_tag = _result_cell_podpis(result)
                razitko_txt, razitko_tag = _result_cell_razitko(result)
                row_tag = "status_error" if "fail" in (pdfa_tag, podpis_tag, razitko_tag) else ("status_ok" if "ok" in (pdfa_tag, podpis_tag, razitko_tag) else "muted")
                iid_file = f"rtask_{task_ix}_f_{qidx}"
                self.results_tree.insert(iid_task, tk.END, iid=iid_file, values=(pdfa_txt, podpis_txt, razitko_txt), text=f"📄 {fn}", tags=(row_tag,))
                self._results_iid_to_qidx[iid_file] = qidx
                qidx += 1
            self.results_tree.item(iid_task, open=True)

    def _on_results_tree_select(self, event):
        """Při výběru v Projektovém stromu zobrazí detail v detail_text (pokud je to soubor s výsledkem)."""
        sel = self.results_tree.selection()
        if not sel:
            return
        iid = sel[0]
        qidx = self._results_iid_to_qidx.get(iid)
        if qidx is not None and 0 <= qidx < len(self.queue_display):
            item = self.queue_display[qidx]
            text = _format_result_summary(item.get("filename", ""), item.get("status", "pending"), item.get("result"))
            self.detail_text.configure(state="normal")
            self.detail_text.delete("0.0", "end")
            self.detail_text.insert("0.0", text)
            self.detail_text.configure(state="disabled")

    def _show_session_summary(self):
        """Zobrazí v pravém panelu souhrn relace (když nic není vybráno)."""
        self.detail_text.configure(state="normal")
        self.detail_text.delete("0.0", "end")
        self.detail_text.insert("0.0", _session_summary_text(self.tasks, self.queue_display, self.session_files_checked))
        self.detail_text.configure(state="disabled")

    def add_path_to_queue(self, path):
        """Přidá cestu (soubor nebo složka) jako úkol. Složka = 1 úkol s dětmi (soubory)."""
        path = self._normalize_path(path)
        if not path:
            try:
                logger = __import__('logging').getLogger(__name__)
                logger.warning("add_path_to_queue: vynechána neplatná cesta (není str ani dict s path)")
            except Exception:
                pass
            return
        if os.path.isdir(path):
            from pdf_checker import find_all_pdfs
            pdfs = find_all_pdfs(path)
            if pdfs:
                name = os.path.basename(path)
                file_paths = []
                for fp in pdfs:
                    file_path = self._normalize_path(fp) if isinstance(fp, dict) else (fp if isinstance(fp, str) else None)
                    if not file_path:
                        try:
                            logger = __import__('logging').getLogger(__name__)
                            logger.warning("add_path_to_queue: vynechán záznam bez cesty: %s", type(fp).__name__)
                        except Exception:
                            pass
                        continue
                    file_paths.append(file_path)
                    self.queue_display.append({
                        'path': file_path,
                        'filename': self._path_to_filename(fp),
                        'status': 'pending', 'result': None, 'checked': True
                    })
                if file_paths:
                    self.tasks.append({'type': 'folder', 'path': path, 'name': name, 'file_paths': file_paths})
        elif path.lower().endswith('.pdf'):
            name = os.path.basename(path)
            self.tasks.append({'type': 'file', 'path': path, 'name': name, 'file_paths': [path]})
            self.queue_display.append({'path': path, 'filename': name, 'status': 'pending', 'result': None, 'checked': True})

    def add_folder(self):
        """Dialog pro přidání složky"""
        folder = filedialog.askdirectory(title="Vyberte složku s PDF")
        if folder:
            self.add_path_to_queue(folder)
            self.update_queue_display()

    def add_files(self):
        """Dialog pro přidání souborů"""
        files = filedialog.askopenfilenames(
            title="Vyberte PDF soubory",
            filetypes=[("PDF soubory", "*.pdf")]
        )
        for f in files:
            self.add_path_to_queue(f)
        self.update_queue_display()

    def clear_queue(self):
        """Vyčistí úkoly a frontu."""
        self.tasks = []
        self.queue_display = []
        self._iid_to_qidx.clear()
        self.update_queue_display()
        self._update_header_stats()
        self._show_session_summary()

    def remove_from_queue(self, index):
        """Odstraní úkol z fronty (index do tasks)."""
        if 0 <= index < len(self.tasks):
            task = self.tasks[index]
            paths = set(task.get('file_paths', []))
            self.queue_display = [q for q in self.queue_display if q.get('path') not in paths]
            del self.tasks[index]
            self.update_queue_display()
            self._show_session_summary()

    def _on_queue_select(self, event):
        """Zobrazí v pravém panelu souhrn vybraného souboru/úkolu (nikdy raw JSON). Při prázdném výběru souhrn relace."""
        sel = self.queue_tree.selection()
        if not sel:
            self._show_session_summary()
            return
        try:
            iid = sel[0]
            qidx = self._iid_to_qidx.get(iid)
            if qidx is not None and 0 <= qidx < len(self.queue_display):
                item = self.queue_display[qidx]
                self.detail_text.configure(state="normal")
                self.detail_text.delete("0.0", "end")
                text = _format_result_summary(
                    item.get('filename', ''),
                    item.get('status', 'pending'),
                    item.get('result')
                )
                self.detail_text.insert("0.0", text)
                self.detail_text.configure(state="disabled")
                return
            if iid.startswith("task_") and "_file_" not in iid:
                try:
                    task_ix = int(iid.replace("task_", ""))
                    if 0 <= task_ix < len(self.tasks):
                        task = self.tasks[task_ix]
                        name = task.get('name', '')
                        paths = task.get('file_paths', [])
                        self.detail_text.configure(state="normal")
                        self.detail_text.delete("0.0", "end")
                        kind = "Složka" if task.get('type') == 'folder' else "Soubor"
                        self.detail_text.insert("0.0", f"{kind}  {name}\n\nPočet souborů: {len(paths)}")
                        self.detail_text.configure(state="disabled")
                        return
                except (ValueError, IndexError):
                    pass
            self._show_session_summary()
        except Exception:
            self._show_session_summary()

    def _on_tree_click(self, event):
        """Klik: checkbox (#0) = přepnutí výběru; sloupec Smazat (#4) u tasku = smazat úkol."""
        region = self.queue_tree.identify_region(event.x, event.y)
        if region != "cell":
            return
        col = self.queue_tree.identify_column(event.x)
        iid = self.queue_tree.identify_row(event.y)
        if not iid:
            return
        # Klik na "Smazat" (sloupec action) u tasku = odstranit úkol
        if col == "#4" and iid.startswith("task_") and "_file_" not in iid:
            try:
                task_ix = int(iid.replace("task_", ""))
                if 0 <= task_ix < len(self.tasks):
                    self.remove_from_queue(task_ix)
            except (ValueError, IndexError):
                pass
            return
        if col != "#0":
            return
        qidx = self._iid_to_qidx.get(iid)
        if qidx is not None:
            if 0 <= qidx < len(self.queue_display):
                self.queue_display[qidx]['checked'] = not self.queue_display[qidx].get('checked', True)
                self.update_queue_display()
                self.queue_tree.selection_set(iid)
            return
        if iid.startswith("task_") and "_file_" not in iid:
            try:
                task_ix = int(iid.replace("task_", ""))
                if 0 <= task_ix < len(self.tasks):
                    task = self.tasks[task_ix]
                    start = sum(len(self.tasks[i].get('file_paths', [])) for i in range(task_ix))
                    count = len(task.get('file_paths', []))
                    children_checked = [self.queue_display[start + j].get('checked') for j in range(count) if start + j < len(self.queue_display)]
                    all_checked = len(children_checked) > 0 and all(children_checked)
                    new_val = not all_checked
                    for j in range(count):
                        if start + j < len(self.queue_display):
                            self.queue_display[start + j]['checked'] = new_val
                    self.update_queue_display()
                    self.queue_tree.selection_set(iid)
            except (ValueError, IndexError):
                pass

    def _task_status(self, task_ix):
        """Vrátí 'Odesláno' pokud byl úkol alespoň jednou zpracován, jinak 'Nový'."""
        start = sum(len(self.tasks[i].get('file_paths', [])) for i in range(task_ix))
        count = len(self.tasks[task_ix].get('file_paths', []))
        for j in range(count):
            if start + j < len(self.queue_display) and self.queue_display[start + j].get('status') not in ('pending', None):
                return "Odesláno"
        return "Nový"

    def _file_error_summary(self, item):
        """Pro položku fronty vrátí text chyb: OK, 1 chyba, 2 chyby, 5 chyb … (jako na webu)."""
        n = _count_errors_from_result(item.get('result'))
        if n == 0:
            return "OK"
        if n == 1:
            return "1 chyba"
        if 2 <= n <= 4:
            return f"{n} chyby"
        return f"{n} chyb"

    def _task_error_summary(self, task_ix):
        """Pro úkol (složka/soubor) vrátí souhrn chyb potomků: — nebo např. 3 chyby."""
        start = sum(len(self.tasks[i].get('file_paths', [])) for i in range(task_ix))
        count = len(self.tasks[task_ix].get('file_paths', []))
        total = 0
        for j in range(count):
            if start + j < len(self.queue_display):
                total += _count_errors_from_result(self.queue_display[start + j].get('result'))
        if total == 0:
            return "—"
        if total == 1:
            return "1 chyba"
        if 2 <= total <= 4:
            return f"{total} chyby"
        return f"{total} chyb"

    def update_queue_display(self):
        """Aktualizuje Treeview: úkoly s checkboxem, stavem, chybami a výrazným tlačítkem Smazat."""
        for row in self.queue_tree.get_children():
            self.queue_tree.delete(row)
        self._iid_to_qidx.clear()
        status_labels = {'pending': '...', 'success': 'OK', 'error': 'CHYBA', 'skipped': 'Presk'}
        qidx = 0
        for task_ix, task in enumerate(self.tasks):
            file_paths = task.get('file_paths', [])
            children_checked = [self.queue_display[qidx + j].get('checked', True) for j in range(len(file_paths)) if qidx + j < len(self.queue_display)]
            all_checked = len(children_checked) > 0 and all(children_checked)
            root_check = "[x]" if all_checked else "[ ]"
            kind = "Dir" if task.get('type') == 'folder' else "File"
            name = task.get('name', '')
            task_status = self._task_status(task_ix)
            task_errors = self._task_error_summary(task_ix)
            iid_task = f"task_{task_ix}"
            tag = "task_row"  # výraznější řádek pro úkol (Smazat je v tomto řádku)
            self.queue_tree.insert("", tk.END, iid=iid_task, values=(f"{kind}  {name}", task_status, task_errors, "🗑 Smazat"), text=root_check, tags=(tag,))
            for j, _ in enumerate(file_paths):
                if qidx >= len(self.queue_display):
                    break
                item = self.queue_display[qidx]
                chk = "[x]" if item.get('checked', True) else "[ ]"
                st = status_labels.get(item.get('status', 'pending'), '...')
                err_text = self._file_error_summary(item)
                iid_file = f"task_{task_ix}_file_{j}"
                child_tag = "odd" if (task_ix + j) % 2 == 0 else "even"
                self.queue_tree.insert(iid_task, tk.END, iid=iid_file, values=(f"  [{st}] {item.get('filename', '')}", "", err_text, ""), text=chk, tags=(child_tag,))
                self._iid_to_qidx[iid_file] = qidx
                qidx += 1
            self.queue_tree.item(iid_task, open=True)
        def _open_all(parent=""):
            for iid in self.queue_tree.get_children(parent):
                self.queue_tree.item(iid, open=True)
                _open_all(iid)
        _open_all("")
        self._update_header_stats()
        self.update_results_tree()

    def on_check_clicked(self):
        """Handler pro tlačítko Spustit kontrolu – zpracují se pouze zaškrtnuté položky (☑)."""
        checked_paths_qidx = [(q['path'], i) for i, q in enumerate(self.queue_display) if q.get('checked')]
        if not checked_paths_qidx:
            messagebox.showwarning("Varování", "Přidejte položky ke kontrole a zaškrtněte je, nebo přidejte složky/soubory.")
            return
        if self.is_running:
            return
        self.cancel_requested = False
        self.is_running = True
        self.show_progress()
        thread = threading.Thread(target=self._check_thread, args=(checked_paths_qidx,), daemon=True)
        thread.start()

    def _check_thread(self, checked_paths_qidx):
        """
        Vlákno pro kontrolu. Seskupuje zaškrtnuté položky podle úkolu (task):
        - úkol typu složka: jedno volání mode='folder' (zachová folder/relative_path pro strom na webu),
        - úkol typu soubor: volání mode='single'.
        checked_paths_qidx: list of (path, queue_display_index).
        """
        try:
            max_files = 99999
            if self.on_get_max_files:
                try:
                    max_files = self.on_get_max_files()
                except Exception:
                    max_files = 5
            if max_files < 0:
                max_files = 99999

            # Seskupit (path, qidx) podle tasku: pro každý task mít seznam (path, qidx) zaškrtnutých
            task_checked = []  # [(task_ix, task, [(path, qidx), ...]), ...]
            qidx_used = set()
            for path, qidx in checked_paths_qidx:
                if qidx in qidx_used:
                    continue
                for task_ix, task in enumerate(self.tasks):
                    file_paths = task.get('file_paths', [])
                    if not file_paths:
                        continue
                    # qidx pro tento task začíná na sum předchozích
                    qidx_start = sum(len(self.tasks[i].get('file_paths', [])) for i in range(task_ix))
                    if qidx_start <= qidx < qidx_start + len(file_paths):
                        # Najít nebo vytvořit záznam pro tento task
                        found = False
                        for tc in task_checked:
                            if tc[0] == task_ix:
                                tc[2].append((path, qidx))
                                found = True
                                break
                        if not found:
                            task_checked.append((task_ix, task, [(path, qidx)]))
                        qidx_used.add(qidx)
                        break

            all_results = []
            source_folder_for_batch = None
            total_files_to_process = sum(len(items) for _, _, items in task_checked)
            total_files_to_process = min(total_files_to_process, max_files)
            truncated = sum(len(items) for _, _, items in task_checked) > max_files
            if truncated:
                self.root.after(0, lambda: messagebox.showinfo(
                    "Limit",
                    f"Kontrola bude provedena jen u {max_files} souborů. Zbytek byl vynechán."
                ))

            processed = 0
            for task_ix, task, items in task_checked:
                if self.cancel_requested:
                    break
                remaining = max_files - processed
                if remaining <= 0:
                    break
                is_folder = task.get('type') == 'folder'
                task_path = task.get('path', '')
                if is_folder and task_path:
                    # Jedno volání pro celou složku – výsledky mají folder/relative_path pro strom na webu
                    self.root.after(0, lambda p=processed, t=total_files_to_process: self.update_progress(p, t, os.path.basename(task_path)))
                    folder_result = self.on_check_callback(task_path, mode='folder', auto_send=False)
                    results_list = folder_result.get('results', []) if isinstance(folder_result, dict) else []
                    qidx_start = sum(len(self.tasks[i].get('file_paths', [])) for i in range(task_ix))
                    checked_qidx_in_task = {q for _, q in items}
                    for j, res in enumerate(results_list):
                        if processed >= max_files:
                            break
                        qidx = qidx_start + j
                        if qidx not in checked_qidx_in_task:
                            continue
                        all_results.append((qidx, res))
                        processed += 1
                        if processed % 5 == 0 or processed == total_files_to_process:
                            self.root.after(0, lambda cur=processed, tot=total_files_to_process: self.update_progress(cur, tot, os.path.basename(task_path)))
                    if len(all_results) > 0 and source_folder_for_batch is None:
                        source_folder_for_batch = task_path
                else:
                    # Jednotlivé soubory (task typu file nebo fallback)
                    for path, qidx in items:
                        if self.cancel_requested or processed >= max_files:
                            break
                        processed += 1
                        fn = os.path.basename(path)
                        self.root.after(0, lambda c=processed, t=total_files_to_process, f=fn: self.update_progress(c, t, f))
                        result = self.on_check_callback(path, mode='single', auto_send=False)
                        all_results.append((qidx, result))

            if not all_results:
                self.root.after(0, lambda: self.display_error("Žádné PDF soubory ke kontrole."))
                self.root.after(0, self.finish_progress)
                return

            summary = {
                'results_with_qidx': all_results,
                'response_data': None,
                'truncated': truncated,
                'max_files': max_files,
                'upload_error': None,
                'source_folder_for_batch': source_folder_for_batch,
            }
            self.root.after(0, lambda: self.display_results(summary))

        except Exception as e:
            self.root.after(0, lambda: self.display_error(str(e)))
        finally:
            self.root.after(0, self.finish_progress)

    def cancel_check(self):
        """Zruší probíhající kontrolu"""
        self.cancel_requested = True
        self.progress_label.configure(text="Ruším…", text_color=self.WARNING_ORANGE)

    def show_progress(self):
        """Zobrazí řádek s progress barem v action bar a zakáže Kontrola."""
        import time
        self.start_time = time.time()
        self.processed_files = 0
        self.progress.set(0)
        self.progress_label.configure(text="Zahajuji zpracování…", text_color=self.ACCENT)
        if getattr(self, 'eta_label', None):
            self.eta_label.configure(text="Odhadovaný čas: —")
        if getattr(self, '_progress_row', None):
            self._progress_row.pack(fill=tk.X, padx=12, pady=(0, 4))
        self.cancel_btn.pack(side=tk.RIGHT)
        self.check_btn.configure(state="disabled")

    def finish_progress(self):
        """Skryje progress řádek a znovu povolí Kontrola."""
        self.is_running = False
        self.progress.set(1)

        if self.cancel_requested:
            self.progress_label.configure(text="Zrušeno", text_color=self.WARNING_ORANGE)
        else:
            self.progress_label.configure(text="Hotovo.", text_color=self.SUCCESS_GREEN)
        if getattr(self, 'eta_label', None):
            self.eta_label.configure(text="Odhadovaný čas: —")

        self.cancel_btn.pack_forget()
        self.check_btn.configure(state="normal")
        def _hide_progress_row():
            if getattr(self, '_progress_row', None):
                self._progress_row.pack_forget()
        self.root.after(2500, _hide_progress_row)

    def update_progress(self, current, total, filename):
        """Progress: progress_label a eta_label (Odhadovaný čas: MM:SS)."""
        import time

        if self.cancel_requested:
            return

        if total > 0:
            self.processed_files = current
            self.total_files = total
            self.progress.set(current / total)
            remaining = total - current
            if current > 0 and self.start_time:
                elapsed = time.time() - self.start_time
                avg_time = elapsed / current
                eta_seconds = avg_time * remaining
            else:
                eta_seconds = remaining * self.SECONDS_PER_FILE_ETA
            mm = int(eta_seconds // 60)
            ss = int(eta_seconds % 60)
            eta_str = f"{mm:02d}:{ss:02d}" if mm > 0 else f"00:{ss:02d}"
            self.progress_label.configure(text=f"Zpracovávání: {current}/{total}", text_color=self.ACCENT)
            if getattr(self, 'eta_label', None):
                self.eta_label.configure(text=f"Odhadovaný čas: {eta_str}")
            self.root.update_idletasks()

    def display_results(self, result):
        """
        Aktualizuje stav ve frontě podle (qidx, result). Úspěšné odškrtne (☐), neúspěšné/skipped nechá zaškrtnuté (☑).
        Zvýší session_files_checked o počet úspěšných.
        Při upload_error (např. Zkušební limit vyčerpán) zobrazí popup a status bar.
        """
        import time
        results_with_qidx = result.get('results_with_qidx', [])
        response_data = result.get('response_data')
        upload_error = result.get('upload_error')

        for qidx, res in results_with_qidx:
            if 0 <= qidx < len(self.queue_display):
                self.queue_display[qidx]['result'] = res
                self.queue_display[qidx]['status'] = 'success' if res.get('success') else 'error'
                # Po kontrole: úspěšné odškrtnout, neúspěšné nechat zaškrtnuté (možnost znovu spustit)
                self.queue_display[qidx]['checked'] = not res.get('success')

        if response_data and response_data.get('status') == 'partial':
            processed_count = response_data.get('processed_count', len(results_with_qidx))
            for i in range(processed_count, len(results_with_qidx)):
                qidx = results_with_qidx[i][0]
                if 0 <= qidx < len(self.queue_display):
                    self.queue_display[qidx]['status'] = 'skipped'
                    self.queue_display[qidx]['checked'] = True
                    self.queue_display[qidx]['result'] = None

        self.update_queue_display()
        self.update_results_tree()
        self._update_sidebar_stats()

        total_time = time.time() - self.start_time if self.start_time else 0
        time_str = f"{int(total_time)}s" if total_time < 60 else f"{int(total_time / 60)}m {int(total_time % 60)}s"
        results_only = [r for _, r in results_with_qidx]
        success_count = sum(1 for r in results_only if r.get('success'))
        self.session_files_checked += success_count

        pdf_a3_count = sum(1 for r in results_only if r.get('success') and r.get('display', {}).get('is_pdf_a3'))
        signed_count = sum(1 for r in results_only if r.get('success') and r.get('display', {}).get('signature_count', 0) > 0)

        self.results_text.configure(state="normal")
        self.results_text.delete("0.0", "end")
        self.results_text.insert("0.0", "KONTROLA DOKONČENA\n"
            f"Celkem souborů: {success_count}\n"
            f"Formát PDF/A-3: {pdf_a3_count}\n"
            f"S podpisem: {signed_count}\n"
            f"Čas: {time_str}\n"
            + (f"\n{response_data.get('message', '')}\n" if response_data and response_data.get('status') == 'partial' else "")
            + "\nKlikněte na řádek ve frontě pro detail souboru.\n"
            + (f"\nOdeslání na server: {upload_error}\n" if upload_error else ""))
        self.results_text.configure(state="disabled")
        if upload_error and ("Zkušební limit" in upload_error or "vyčerpán" in upload_error):
            messagebox.showwarning("Zkušební limit", upload_error)
            self.license_status_label.configure(text=upload_error[:60] + ("…" if len(upload_error) > 60 else ""), text_color=self.ERROR_RED)

        # Dialog: chcete poslat na server? Web se otevře až po kliknutí na Ano (po odeslání).
        if self.on_send_batch_callback and results_with_qidx:
            n = len(results_with_qidx)
            msg = "Načetlo data z {} souborů. Chcete poslat na server k vyhodnocení?".format(n)
            if messagebox.askyesno("Odeslat na server", msg, default=messagebox.YES):
                try:
                    results_only = [r for _, r in results_with_qidx]
                    source_folder = result.get('source_folder_for_batch') if isinstance(result, dict) else None
                    out = self.on_send_batch_callback(results_only, source_folder)
                    if out and len(out) >= 2 and not out[0]:
                        upload_error = out[1] or "Chyba odeslání na server"
                        self.results_text.configure(state="normal")
                        self.results_text.insert("end", "\nOdeslání na server: " + upload_error + "\n")
                        self.results_text.configure(state="disabled")
                        if "Zkušební limit" in upload_error or "vyčerpán" in upload_error:
                            messagebox.showwarning("Zkušební limit", upload_error)
                            self.license_status_label.configure(text=upload_error[:60] + ("…" if len(upload_error) > 60 else ""), text_color=self.ERROR_RED)
                    if out and len(out) >= 4 and out[3]:
                        response_data = out[3]
                        if response_data and response_data.get('status') == 'partial':
                            processed_count = response_data.get('processed_count', len(results_with_qidx))
                            for i in range(processed_count, len(results_with_qidx)):
                                qidx = results_with_qidx[i][0]
                                if 0 <= qidx < len(self.queue_display):
                                    self.queue_display[qidx]['status'] = 'skipped'
                                    self.queue_display[qidx]['checked'] = True
                                    self.queue_display[qidx]['result'] = None
                            self.update_queue_display()
                    # Otevřít web až po potvrzení a odeslání (ne před dialogem)
                    self.open_web_after_check()
                except Exception as e:
                    self.results_text.configure(state="normal")
                    self.results_text.insert("end", "\nOdeslání na server: " + str(e) + "\n")
                    self.results_text.configure(state="disabled")

    def display_error(self, error_msg):
        """Zobrazí chybovou hlášku"""
        self.results_text.configure(state="normal")
        self.results_text.delete("0.0", "end")
        self.results_text.insert("0.0", f"CHYBA:\n{error_msg}\n")
        self.results_text.configure(state="disabled")

    def clear_results_and_queue(self):
        """Vymaže frontu úkolů a zobrazené výsledky (po přihlášení/odhlášení)."""
        self.tasks = []
        self.queue_display = []
        self._iid_to_qidx.clear()
        self.session_files_checked = 0
        self.update_queue_display()
        self._show_session_summary()

    def set_daily_limit_display(self, used, limit):
        """Aktualizuje text denního limitu v action bar. limit None nebo -1 = neomezeno."""
        if not getattr(self, 'daily_limit_label', None):
            return
        if limit is None or (isinstance(limit, int) and limit < 0):
            self.daily_limit_label.configure(text="Váš denní limit: neomezeno (Reset o půlnoci).")
        else:
            self.daily_limit_label.configure(text=f"Váš denní limit: {used or 0} / {limit} souborů (Reset o půlnoci).")

    def set_license_display(self, text):
        """Aktualizuje zobrazení stavu licence – sidebar Můj účet a Přihlásit/Odhlásit."""
        if not text and getattr(self, 'daily_limit_label', None):
            self.daily_limit_label.configure(text="Denní limit: —")
        if getattr(self, 'sidebar_account', None):
            self.sidebar_account.configure(text=text or "Nepřihlášen", text_color=self.TEXT_DARK if text else self.TEXT_MUTED)
        if getattr(self, 'sidebar_tier', None):
            tier = "—"
            if text and "(" in text:
                tier = text.split("(")[-1].rstrip(")")
            self.sidebar_tier.configure(text=f"Tier: {tier}")
        if text:
            self.license_status_label.configure(text="", text_color=self.TEXT_DARK)
            self.login_btn_header.pack_forget()
            self.logout_btn_header.pack(pady=6, padx=16, fill=tk.X)
        else:
            self.license_status_label.configure(text="", text_color=self.TEXT_DARK)
            self.logout_btn_header.pack_forget()
            self.login_btn_header.pack(pady=6, padx=16, fill=tk.X)
            if hasattr(self, 'set_export_xls_enabled'):
                self.set_export_xls_enabled(False)

    def _do_logout(self):
        """Odhlášení – vymaže zobrazení, pak klíč a zobrazí dialog přihlášení."""
        if getattr(self, 'on_after_logout_callback', None):
            self.on_after_logout_callback()
        if self.on_logout_callback:
            self.on_logout_callback()

    def show_api_key_dialog(self):
        """Dialog přihlášení: Vyzkoušet zdarma (Trial) nebo e-mail + heslo pro placené účty. Dark theme."""
        dialog = ctk.CTkToplevel(self.root)
        dialog.title("Přihlášení")
        dialog.geometry("480x380")
        dialog.configure(fg_color=self.BG_CARD)
        dialog.transient(self.root)
        dialog.grab_set()
        dialog.update_idletasks()
        x = self.root.winfo_x() + (self.root.winfo_width() // 2) - 240
        y = self.root.winfo_y() + (self.root.winfo_height() // 2) - 190
        dialog.geometry(f"+{x}+{y}")

        ctk.CTkLabel(dialog, text="Přihlášení k účtu", font=("Segoe UI", 12, "bold"), text_color=self.TEXT_DARK).pack(pady=(16, 8))
        status_label = ctk.CTkLabel(dialog, text="", text_color=self.TEXT_MUTED)
        status_label.pack(pady=8)

        def do_trial():
            status_label.configure(text="Režim: Zkušební verze (Trial)", text_color=self.ACCENT)
            dialog.update()
            try:
                from license import DEMO_TRIAL_EMAIL, DEMO_TRIAL_PASSWORD
                email = DEMO_TRIAL_EMAIL or "free@trial.app"
                password = DEMO_TRIAL_PASSWORD or "free"
            except ImportError:
                email, password = "free@trial.app", "free"
            if self.on_login_password_callback:
                result = self.on_login_password_callback(email, password)
                success = result[0] if result else False
                message = result[1] if len(result) > 1 else ""
                if success:
                    status_label.configure(text="Režim: Zkušební verze (Trial)", text_color=self.SUCCESS_GREEN)
                    self.set_license_display("Režim: Zkušební verze (Trial)")
                    if self.on_after_login_callback:
                        self.on_after_login_callback()
                    dialog.after(800, dialog.destroy)
                else:
                    status_label.configure(text=message or "Chyba přihlášení", text_color=self.ERROR_RED)
            else:
                status_label.configure(text="Chyba: chybí callback", text_color=self.ERROR_RED)

        ctk.CTkButton(dialog, text="Vyzkoušet zdarma", font=("Segoe UI", 10, "bold"), corner_radius=10,
                      fg_color=self.ACCENT_BTN, command=do_trial).pack(pady=(8, 16))

        ctk.CTkLabel(dialog, text="Přihlásit se (e-mail + heslo – placený účet):", font=("Segoe UI", 9, "bold"), text_color=self.TEXT_DARK).pack(anchor=tk.W, padx=20, pady=(8, 4))
        email_var = ctk.StringVar()
        pass_var = ctk.StringVar()
        ctk.CTkLabel(dialog, text="E-mail:", text_color=self.TEXT_DARK).pack(anchor=tk.W, padx=20, pady=(2, 0))
        email_entry = ctk.CTkEntry(dialog, textvariable=email_var, font=("Consolas", 11), width=400, corner_radius=8)
        email_entry.pack(pady=2, padx=20, fill=tk.X)
        ctk.CTkLabel(dialog, text="Heslo:", text_color=self.TEXT_DARK).pack(anchor=tk.W, padx=20, pady=(6, 0))
        pass_entry = ctk.CTkEntry(dialog, textvariable=pass_var, font=("Consolas", 11), width=400, corner_radius=8, show="*")
        pass_entry.pack(pady=2, padx=20, fill=tk.X)
        email_entry.focus()

        def do_login():
            email = email_var.get().strip()
            password = pass_var.get()
            if email and password and self.on_login_password_callback:
                status_label.configure(text="Ověřuji e-mail a heslo…", text_color=self.WARNING_ORANGE)
                dialog.update()
                result = self.on_login_password_callback(email, password)
                success = result[0] if result else False
                message = result[1] if len(result) > 1 else ""
                display_text = result[2] if len(result) > 2 else None
                if success:
                    status_label.configure(text=message or "Přihlášeno.", text_color=self.SUCCESS_GREEN)
                    if display_text:
                        self.set_license_display(display_text if str(display_text).strip().startswith("Režim:") else "Přihlášen: " + display_text)
                    if self.on_after_login_callback:
                        self.on_after_login_callback()
                    dialog.after(1200, dialog.destroy)
                else:
                    status_label.configure(text=message or "Chyba přihlášení", text_color=self.ERROR_RED)
                return
            status_label.configure(text="Zadejte e-mail a heslo.", text_color=self.ERROR_RED)

        ctk.CTkButton(dialog, text="Přihlásit se", font=("Segoe UI", 10, "bold"), corner_radius=10, fg_color=self.ACCENT, command=do_login).pack(pady=10)
        pass_entry.bind("<Return>", lambda e: do_login())
        email_entry.bind("<Return>", lambda e: do_login())


def create_app(on_check_callback, on_api_key_callback, api_url="",
              on_login_password_callback=None, on_logout_callback=None, on_get_max_files=None,
              on_after_login_callback=None, on_after_logout_callback=None, on_get_web_login_url=None,
              on_send_batch_callback=None):
    """Vytvoří a vrátí GUI aplikaci (CustomTkinter, Dark). Pro DnD se použije TkinterDnD.Tk() jako root."""
    if TKINTERDND_AVAILABLE:
        try:
            root = TkinterDnD.Tk()
            root.configure(bg="#1a1a1a")
        except Exception:
            root = ctk.CTk()
    else:
        root = ctk.CTk()

    app = PDFCheckUI(
        root, on_check_callback, on_api_key_callback, api_url=api_url,
        on_login_password_callback=on_login_password_callback,
        on_logout_callback=on_logout_callback,
        on_get_max_files=on_get_max_files,
        on_after_login_callback=on_after_login_callback,
        on_after_logout_callback=on_after_logout_callback,
        on_get_web_login_url=on_get_web_login_url,
        on_send_batch_callback=on_send_batch_callback,
    )
    return root, app
