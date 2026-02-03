# ui.py
# GUI pro PDF DokuCheck Agent
# Build 42 - Treeview hierarchy, checkboxes, safe result summary (no raw JSON)

import tkinter as tk
from tkinter import ttk, filedialog, messagebox, scrolledtext
import threading
import webbrowser
import os

# Zkus importovat TkinterDnD
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
    # Header: Filename, Status Icon (Large), Time Processed
    status_icons = {'pending': '⏳', 'success': '✅', 'error': '❌', 'skipped': '⚠️'}
    icon = status_icons.get(status, '⏳')
    lines.append(f"{icon}  {filename}")
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


def _session_summary_text(tasks, queue_display, session_files_checked):
    """Text pro pravý panel když nic není vybráno (souhrn relace)."""
    n_tasks = len(tasks)
    n_checked = sum(1 for q in queue_display if q.get('checked'))
    return (
        f"Fronta: {n_tasks} úkolů ({n_checked} vybráno)\n"
        f"Dnes zkontrolováno: {session_files_checked} souborů"
    )


class PDFCheckUI:
    """Hlavní GUI aplikace – moderní modré rozhraní"""

    # Paleta – modrá úroveň (inspirace: OneDrive, Dropbox, moderní nástroje)
    BG_APP = "#f0f4f8"
    BG_WHITE = "#ffffff"
    BG_LIGHT = "#e8eef4"
    BG_CARD = "#ffffff"
    BG_HEADER = "#1a365d"
    BG_HEADER_LIGHT = "#2c5282"
    TEXT_DARK = "#2d3748"
    TEXT_MUTED = "#718096"
    ACCENT = "#3182ce"
    ACCENT_HOVER = "#2b6cb0"
    SUCCESS_GREEN = "#38a169"
    ERROR_RED = "#e53e3e"
    WARNING_ORANGE = "#dd6b20"
    BORDER = "#e2e8f0"
    DROP_HOVER = "#dde4ec"
    BUTTON_TEXT = "#ffffff"

    # Primary button color (Modern Corporate)
    ACCENT_BTN = "#007ACC"

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
        self.api_url = api_url or "https://cieslar.pythonanywhere.com"

        # Tasks: list of {type: 'folder'|'file', path, name, file_paths: [str]}
        self.tasks = []
        # Flat file list in task order: [{'path', 'filename', 'status', 'result', 'checked'}, ...]
        self.queue_display = []
        # Map tree iid (task_i_file_j) -> queue_display index
        self._iid_to_qidx = {}

        # Session: počet zkontrolovaných souborů v této relaci (pro souhrn)
        self.session_files_checked = 0

        # Tracking pro progress
        self.start_time = None
        self.total_files = 0
        self.processed_files = 0
        self.cancel_requested = False
        self.is_running = False

        # Okno – výchozí velikost 1000x700 (WINDOW SIZE)
        self.root.title("PDF DokuCheck Agent")
        self.root.geometry("1000x700")
        self.root.minsize(800, 600)
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
        webbrowser.open(url or self.api_url or "https://cieslar.pythonanywhere.com")

    def _on_export_xls_click(self):
        """Otevře web (kde je export do Excelu). Tlačítko je aktivní jen u PRO verze."""
        if self.on_get_web_login_url:
            try:
                url = self.on_get_web_login_url()
                if url:
                    webbrowser.open(url)
                    return
            except Exception:
                pass
        webbrowser.open(self.api_url or "https://cieslar.pythonanywhere.com")

    def set_export_xls_enabled(self, enabled):
        """Aktivuje nebo deaktivuje tlačítko Export do XLS (PRO = aktivní, Basic/Trial = disabled)."""
        if getattr(self, 'export_xls_btn', None) is None:
            return
        if enabled:
            self.export_xls_btn.config(state=tk.NORMAL, bg=self.ACCENT_BTN, fg=self.BUTTON_TEXT, text="Export do XLS")
        else:
            self.export_xls_btn.config(state=tk.DISABLED, bg=self.BG_LIGHT, fg=self.TEXT_MUTED, text="Export do XLS (jen PRO)")

    def create_widgets(self):
        """Pevný layout: Header, Toolbar s akcemi, obsah (strom + detail), Action bar (Spustit vždy vidět), Footer."""
        # --- Treeview styl ---
        _tree_style = ttk.Style()
        _tree_style.theme_use("clam")
        _tree_style.configure(
            "Treeview",
            rowheight=32,
            font=("Segoe UI", 9),
            background="#ffffff",
            fieldbackground="#ffffff",
            foreground="#1a202c",
        )
        _tree_style.configure(
            "Treeview.Heading",
            font=("Segoe UI", 9, "bold"),
            background="#f1f5f9",
            foreground="#334155",
        )
        _tree_style.map("Treeview", background=[("selected", self.ACCENT_BTN)], foreground=[("selected", "#ffffff")])

        # 1) FOOTER – vždy dole
        bottom_frame = tk.Frame(self.root, bg="#e2e8f0", height=36)
        bottom_frame.pack(side=tk.BOTTOM, fill=tk.X)
        bottom_frame.pack_propagate(False)
        self.license_status_label = tk.Label(bottom_frame, text="", font=("Segoe UI", 9), bg="#e2e8f0", fg=self.TEXT_DARK)
        self.license_status_label.pack(side=tk.LEFT, padx=16, pady=6)
        version_label = tk.Label(bottom_frame, text="Build 42", font=("Segoe UI", 9), bg="#e2e8f0", fg=self.TEXT_MUTED)
        version_label.pack(side=tk.RIGHT, padx=16, pady=6)

        # 2) ACTION BAR – vždy viditelné nad footerem: Přidat / Vyprazdnit / Stats / SPUSTIT KONTROLU (+ řádek progress při běhu)
        action_bar = tk.Frame(self.root, bg="#ffffff", height=88, highlightbackground="#cbd5e0", highlightthickness=1)
        action_bar.pack(side=tk.BOTTOM, fill=tk.X)
        action_bar.pack_propagate(False)
        btn_style = {"font": ("Segoe UI", 9), "bg": self.ACCENT_BTN, "fg": self.BUTTON_TEXT, "relief": tk.FLAT,
                     "padx": 12, "pady": 6, "cursor": "hand2", "highlightthickness": 0}
        tk.Button(action_bar, text="Přidat soubory", command=self.add_files, **btn_style).pack(side=tk.LEFT, padx=(12, 6), pady=10)
        tk.Button(action_bar, text="+ Složka", command=self.add_folder, **btn_style).pack(side=tk.LEFT, padx=6, pady=10)
        tk.Button(action_bar, text="Vyprazdnit", command=self.clear_queue,
                  font=("Segoe UI", 9), bg=self.BG_LIGHT, fg=self.TEXT_DARK, relief=tk.FLAT,
                  padx=10, pady=6, cursor="hand2").pack(side=tk.LEFT, padx=6, pady=10)
        self.export_xls_btn = tk.Button(
            action_bar, text="Export do XLS",
            font=("Segoe UI", 9), bg=self.BG_LIGHT, fg=self.TEXT_DARK, relief=tk.FLAT,
            padx=10, pady=6, cursor="hand2", state=tk.DISABLED,
            command=self._on_export_xls_click
        )
        self.export_xls_btn.pack(side=tk.LEFT, padx=6, pady=10)
        self.stats_label = tk.Label(
            action_bar, text="Soubory: 0 | Složky: 0 | Odhad: 0s",
            font=("Segoe UI", 9), bg="#ffffff", fg=self.TEXT_MUTED
        )
        self.stats_label.pack(side=tk.LEFT, padx=16, pady=10)
        self.check_btn = tk.Button(
            action_bar, text="▶  Kontrola", font=("Segoe UI", 10, "bold"),
            bg=self.ACCENT_BTN, fg=self.BUTTON_TEXT, relief=tk.FLAT,
            padx=24, pady=8, cursor="hand2", command=self.on_check_clicked,
            activebackground="#2980b9", activeforeground=self.BUTTON_TEXT
        )
        self.check_btn.pack(side=tk.RIGHT, padx=12, pady=10)
        # Progress řádek v action bar (zobrazí se při běhu)
        progress_row = tk.Frame(action_bar, bg="#ffffff")
        progress_row.pack(side=tk.BOTTOM, fill=tk.X, padx=12, pady=(0, 4))
        self.progress_label = tk.Label(progress_row, text="Připraveno", font=("Segoe UI", 9),
                                       bg="#ffffff", fg=self.TEXT_MUTED, anchor="w")
        self.progress_label.pack(side=tk.LEFT, fill=tk.X, expand=True)
        self.cancel_btn = tk.Button(progress_row, text="Zrušit", font=("Segoe UI", 9),
                                    bg=self.ERROR_RED, fg=self.BUTTON_TEXT, relief=tk.FLAT,
                                    padx=10, pady=4, cursor="hand2", command=self.cancel_check,
                                    activebackground="#c53030", activeforeground=self.BUTTON_TEXT)
        self.cancel_btn.pack(side=tk.RIGHT, padx=4)
        self.cancel_btn.pack_forget()
        style = ttk.Style()
        style.theme_use("clam")
        style.configure("Blue.Horizontal.TProgressbar", troughcolor=self.BG_LIGHT, background=self.ACCENT_BTN, thickness=10)
        self.progress = ttk.Progressbar(progress_row, style="Blue.Horizontal.TProgressbar", mode='determinate', length=280)
        self.progress.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 8))
        progress_row.pack_forget()  # zobrazí show_progress()

        # 3) HEADER
        header_frame = tk.Frame(self.root, bg=self.BG_HEADER, height=52)
        header_frame.pack(fill=tk.X)
        header_frame.pack_propagate(False)
        title_label = tk.Label(header_frame, text="PDF DokuCheck Agent", font=("Segoe UI", 14, "bold"),
                               bg=self.BG_HEADER, fg=self.BUTTON_TEXT)
        title_label.pack(side=tk.LEFT, padx=16, pady=10)
        subtitle = tk.Label(header_frame, text="Kontrola PDF a odeslání na server", font=("Segoe UI", 9),
                            bg=self.BG_HEADER, fg="#a0aec0")
        subtitle.pack(side=tk.LEFT, padx=(0, 16))
        self.header_status = tk.Label(header_frame, text="", font=("Segoe UI", 9), bg=self.BG_HEADER, fg="#a0aec0")
        self.header_status.pack(side=tk.RIGHT, padx=6, pady=10)
        self.logout_btn_header = tk.Button(header_frame, text="Odhlásit", font=("Segoe UI", 9),
            bg="#c53030", fg=self.BUTTON_TEXT, relief=tk.FLAT, padx=10, pady=4, cursor="hand2", command=self._do_logout,
            activebackground="#9b2c2c", activeforeground=self.BUTTON_TEXT)
        self.logout_btn_header.pack(side=tk.RIGHT, padx=4, pady=8)
        self.logout_btn_header.pack_forget()
        self.login_btn_header = tk.Button(header_frame, text="Přihlásit", font=("Segoe UI", 9),
            bg=self.BG_HEADER_LIGHT, fg=self.BUTTON_TEXT, relief=tk.FLAT, padx=10, pady=4, cursor="hand2",
            command=self.show_api_key_dialog, activebackground=self.ACCENT, activeforeground=self.BUTTON_TEXT)
        self.login_btn_header.pack(side=tk.RIGHT, padx=4, pady=8)
        def _open_web():
            url = None
            if self.on_get_web_login_url:
                try: url = self.on_get_web_login_url()
                except Exception: pass
            webbrowser.open(url or self.api_url or "https://cieslar.pythonanywhere.com")
        web_btn = tk.Button(header_frame, text="Otevřít web", font=("Segoe UI", 9),
            bg=self.BG_HEADER_LIGHT, fg=self.BUTTON_TEXT, relief=tk.FLAT, padx=10, pady=4, cursor="hand2",
            command=_open_web, activebackground=self.ACCENT, activeforeground=self.BUTTON_TEXT)
        web_btn.pack(side=tk.RIGHT, padx=6, pady=8)

        # 4) OBSAH – paned (levý: drop + strom, pravý: detail)
        paned = tk.PanedWindow(self.root, orient=tk.HORIZONTAL, bg=self.BG_APP, sashwidth=5)
        paned.pack(fill=tk.BOTH, expand=True, padx=10, pady=8)

        left_panel = tk.Frame(paned, bg=self.BG_WHITE, padx=10, pady=10)
        right_panel = tk.Frame(paned, bg="#F4F7F9", padx=10, pady=10)
        paned.add(left_panel, minsize=260)
        paned.add(right_panel, minsize=320)

        # Levý panel: jen drop zóna + strom (žádné tlačítko dole)
        tk.Label(left_panel, text="Přidat ke kontrole", font=("Segoe UI", 9, "bold"),
                 bg=self.BG_WHITE, fg=self.TEXT_DARK).pack(anchor=tk.W)
        self.create_drop_zone(left_panel)
        tk.Label(left_panel, text="Fronta úkolů (zaškrtněte položky)", font=("Segoe UI", 9, "bold"),
                 bg=self.BG_WHITE, fg=self.TEXT_DARK).pack(anchor=tk.W, pady=(8, 4))
        tree_frame = tk.Frame(left_panel, bg=self.BG_WHITE)
        tree_frame.pack(fill=tk.BOTH, expand=True)
        tree_scroll = ttk.Scrollbar(tree_frame)
        self.queue_tree = ttk.Treeview(tree_frame, columns=("name",), show="tree headings", height=14,
                                       yscrollcommand=tree_scroll.set, selectmode="browse")
        tree_scroll.config(command=self.queue_tree.yview)
        self.queue_tree.heading("#0", text=" ")
        self.queue_tree.heading("name", text="Úkol / Soubor")
        self.queue_tree.column("#0", width=28)
        self.queue_tree.column("name", width=200)
        self.queue_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        tree_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        self.queue_tree.bind("<<TreeviewSelect>>", self._on_queue_select)
        self.queue_tree.bind("<Button-1>", self._on_tree_click)

        # Pravý panel: souhrn / výsledek
        tk.Label(right_panel, text="Souhrn / výsledek vybraného souboru", font=("Segoe UI", 9, "bold"),
                 bg="#F4F7F9", fg=self.TEXT_DARK).pack(anchor=tk.W)
        self.detail_text = scrolledtext.ScrolledText(
            right_panel, font=("Segoe UI", 9), bg="#ffffff", fg=self.TEXT_DARK,
            relief=tk.FLAT, wrap=tk.WORD, padx=10, pady=10
        )
        self.detail_text.pack(fill=tk.BOTH, expand=True)
        self._show_session_summary()

        self.results_text = self.detail_text
        self.logout_btn = self.logout_btn_header
        self._progress_row = progress_row  # pro show_progress / finish_progress

    def create_drop_zone(self, parent):
        """Vytvoří drag & drop zónu"""
        self.drop_frame = tk.Frame(parent, bg=self.BG_LIGHT, relief=tk.GROOVE, borderwidth=2, height=70)
        self.drop_frame.pack(fill=tk.X, pady=8)
        self.drop_frame.pack_propagate(False)

        self.drop_label = tk.Label(
            self.drop_frame,
            text="Přetáhněte složky nebo PDF soubory sem",
            font=("Segoe UI", 11),
            bg=self.BG_LIGHT,
            fg=self.TEXT_MUTED,
            cursor="hand2"
        )
        self.drop_label.pack(expand=True, fill=tk.BOTH, pady=(12, 2))
        self.drop_hint = tk.Label(
            self.drop_frame,
            text="nebo klikněte pro výběr složky",
            font=("Segoe UI", 9),
            bg=self.BG_LIGHT,
            fg=self.TEXT_MUTED,
            cursor="hand2"
        )
        self.drop_hint.pack(pady=(0, 12))

        # Kliknutí = přidat složku
        self.drop_frame.bind("<Button-1>", lambda e: self.add_folder())
        self.drop_label.bind("<Button-1>", lambda e: self.add_folder())
        self.drop_hint.bind("<Button-1>", lambda e: self.add_folder())
        for el in (self.drop_frame, self.drop_label, self.drop_hint):
            el.bind("<Enter>", lambda e, f=self.drop_frame, l=self.drop_label, h=self.drop_hint: (f.config(bg=self.DROP_HOVER), l.config(bg=self.DROP_HOVER), h.config(bg=self.DROP_HOVER)))
            el.bind("<Leave>", lambda e, f=self.drop_frame, l=self.drop_label, h=self.drop_hint: (f.config(bg=self.BG_LIGHT), l.config(bg=self.BG_LIGHT), h.config(bg=self.BG_LIGHT)))

        # Drag & Drop
        if TKINTERDND_AVAILABLE:
            try:
                self.drop_frame.drop_target_register(DND_FILES)
                self.drop_frame.dnd_bind('<<Drop>>', self.on_drop)
            except:
                pass

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
        """Aktualizuje stats bar nad treeview (live): Soubory: X | Složky: Y | Odhad: Zs."""
        if not hasattr(self, 'stats_label'):
            return
        n_files = sum(len(t.get('file_paths', [])) for t in self.tasks)
        n_folders = sum(1 for t in self.tasks if t.get('type') == 'folder')
        est_s = str(max(0, n_files * 5)) if n_files else "0"
        text = f"Soubory: {n_files} | Složky: {n_folders} | Odhad: {est_s}s"
        self.stats_label.config(text=text)

    def _show_session_summary(self):
        """Zobrazí v pravém panelu souhrn relace (když nic není vybráno)."""
        self.detail_text.config(state=tk.NORMAL)
        self.detail_text.delete(1.0, tk.END)
        self.detail_text.insert(tk.END, _session_summary_text(self.tasks, self.queue_display, self.session_files_checked))
        self.detail_text.config(state=tk.DISABLED)

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
                self.detail_text.config(state=tk.NORMAL)
                self.detail_text.delete(1.0, tk.END)
                text = _format_result_summary(
                    item.get('filename', ''),
                    item.get('status', 'pending'),
                    item.get('result')
                )
                self.detail_text.insert(tk.END, text)
                self.detail_text.config(state=tk.DISABLED)
                return
            # Root node (task): show task summary
            if iid.startswith("task_") and "_file_" not in iid:
                try:
                    task_ix = int(iid.replace("task_", ""))
                    if 0 <= task_ix < len(self.tasks):
                        task = self.tasks[task_ix]
                        name = task.get('name', '')
                        paths = task.get('file_paths', [])
                        self.detail_text.config(state=tk.NORMAL)
                        self.detail_text.delete(1.0, tk.END)
                        icon = "📁" if task.get('type') == 'folder' else "📄"
                        self.detail_text.insert(tk.END, f"{icon}  {name}\n\nPočet souborů: {len(paths)}")
                        self.detail_text.config(state=tk.DISABLED)
                        return
                except (ValueError, IndexError):
                    pass
            self._show_session_summary()
        except Exception:
            self._show_session_summary()

    def _on_tree_click(self, event):
        """Při kliknutí na sloupec checkbox (☐/☑) přepne výběr položky."""
        region = self.queue_tree.identify_region(event.x, event.y)
        if region != "cell":
            return
        col = self.queue_tree.identify_column(event.x)
        if col != "#0":
            return
        iid = self.queue_tree.identify_row(event.y)
        if not iid:
            return
        qidx = self._iid_to_qidx.get(iid)
        if qidx is not None:
            # File node: toggle this file
            if 0 <= qidx < len(self.queue_display):
                self.queue_display[qidx]['checked'] = not self.queue_display[qidx].get('checked', True)
                self.update_queue_display()
                self.queue_tree.selection_set(iid)
            return
        # Root node (task): toggle all children (if all checked -> uncheck all; else check all)
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

    def update_queue_display(self):
        """Aktualizuje hierarchický Treeview: úkoly (složka/soubor) a děti (soubory), se sloupcem checkbox. Auto-expand složek."""
        for row in self.queue_tree.get_children():
            self.queue_tree.delete(row)
        self._iid_to_qidx.clear()
        status_icons = {'pending': '⏳', 'success': '✅', 'error': '❌', 'skipped': '⚠️'}
        qidx = 0
        for task_ix, task in enumerate(self.tasks):
            file_paths = task.get('file_paths', [])
            children_checked = [self.queue_display[qidx + j].get('checked', True) for j in range(len(file_paths)) if qidx + j < len(self.queue_display)]
            all_checked = len(children_checked) > 0 and all(children_checked)
            root_check = "☑" if all_checked else "☐"
            icon = "📁" if task.get('type') == 'folder' else "📄"
            name = task.get('name', '')
            iid_task = f"task_{task_ix}"
            tag = "odd" if task_ix % 2 == 0 else "even"
            self.queue_tree.insert("", tk.END, iid=iid_task, values=(f"{icon} {name}",), text=root_check, tags=(tag,))
            for j, _ in enumerate(file_paths):
                if qidx >= len(self.queue_display):
                    break
                item = self.queue_display[qidx]
                chk = "☑" if item.get('checked', True) else "☐"
                st_icon = status_icons.get(item.get('status', 'pending'), '⏳')
                iid_file = f"task_{task_ix}_file_{j}"
                child_tag = "odd" if (task_ix + j) % 2 == 0 else "even"
                self.queue_tree.insert(iid_task, tk.END, iid=iid_file, values=(f"  {st_icon} {item.get('filename', '')}",), text=chk, tags=(child_tag,))
                self._iid_to_qidx[iid_file] = qidx
                qidx += 1
            self.queue_tree.item(iid_task, open=True)
        # Auto-expand ALL nodes (každý uzel s dětmi rozbalen)
        def _open_all(parent=""):
            for iid in self.queue_tree.get_children(parent):
                self.queue_tree.item(iid, open=True)
                _open_all(iid)
        _open_all("")
        self._update_header_stats()

    def on_check_clicked(self):
        """Handler pro tlačítko Spustit kontrolu – zpracují se pouze zaškrtnuté položky (☑)."""
        checked_paths_qidx = [(q['path'], i) for i, q in enumerate(self.queue_display) if q.get('checked')]
        if not checked_paths_qidx:
            messagebox.showwarning("Varování", "Přidejte položky ke kontrole a zaškrtněte je (☑), nebo přidejte složky/soubory.")
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
        Vlákno pro kontrolu. Zpracuje pouze zaškrtnuté položky (cesty z checked_paths_qidx).
        checked_paths_qidx: list of (path, queue_display_index).
        Po zpracování: úspěšné odškrtne (☐), neúspěšné nechá zaškrtnuté (☑).
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

            # Omezit na max_files (první N zaškrtnutých)
            to_process = checked_paths_qidx[:max_files]
            truncated = len(checked_paths_qidx) > max_files
            if truncated:
                self.root.after(0, lambda: messagebox.showinfo(
                    "Limit",
                    f"Kontrola bude provedena jen u {max_files} souborů. Zbytek byl vynechán."
                ))

            all_results = []
            for path, qidx in to_process:
                if self.cancel_requested:
                    break
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
            }
            self.root.after(0, lambda: self.display_results(summary))

        except Exception as e:
            self.root.after(0, lambda: self.display_error(str(e)))
        finally:
            self.root.after(0, self.finish_progress)

    def cancel_check(self):
        """Zruší probíhající kontrolu"""
        self.cancel_requested = True
        self.progress_label.config(text="Ruším…", fg=self.WARNING_ORANGE)

    def show_progress(self):
        """Zobrazí řádek s progress barem v action bar a zakáže Spustit."""
        import time
        self.start_time = time.time()
        self.processed_files = 0
        self.progress['value'] = 0
        self.progress_label.config(text="Zahajuji zpracování…", fg=self.ACCENT)
        if getattr(self, '_progress_row', None):
            self._progress_row.pack(side=tk.BOTTOM, fill=tk.X, padx=12, pady=(0, 6))
        self.cancel_btn.pack(side=tk.RIGHT)
        self.check_btn.config(state=tk.DISABLED, bg="#9ca3af")

    def finish_progress(self):
        """Skryje progress řádek a znovu povolí Spustit."""
        self.is_running = False
        self.progress['value'] = 100

        if self.cancel_requested:
            self.progress_label.config(text="Zrušeno", fg=self.WARNING_ORANGE)
        else:
            self.progress_label.config(text="Hotovo! Otevřete web pro zobrazení výsledků.", fg=self.SUCCESS_GREEN)
            self.root.after(1000, self.open_web_after_check)

        self.cancel_btn.pack_forget()
        self.check_btn.config(state=tk.NORMAL, bg=self.ACCENT_BTN)
        def _hide_progress_row():
            if getattr(self, '_progress_row', None):
                self._progress_row.pack_forget()
        self.root.after(2500, _hide_progress_row)

    def update_progress(self, current, total, filename):
        """Aktualizuje progress bar s ETA"""
        import time

        if self.cancel_requested:
            return

        if total > 0:
            self.processed_files = current
            self.total_files = total

            percent = (current / total) * 100
            self.progress['value'] = percent

            remaining = total - current

            if current > 0 and self.start_time:
                elapsed = time.time() - self.start_time
                avg_time = elapsed / current
                eta_seconds = avg_time * remaining

                if eta_seconds < 60:
                    eta_str = f"{int(eta_seconds)}s"
                else:
                    eta_str = f"{int(eta_seconds / 60)}m {int(eta_seconds % 60)}s"

                short_name = filename if len(filename) < 35 else "..." + filename[-32:]
                text = f"{current}/{total} ({int(percent)}%) | ETA: {eta_str} | {short_name}"
            else:
                text = f"{current}/{total} ({int(percent)}%)"

            self.progress_label.config(text=text, fg=self.ACCENT)
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

        total_time = time.time() - self.start_time if self.start_time else 0
        time_str = f"{int(total_time)}s" if total_time < 60 else f"{int(total_time / 60)}m {int(total_time % 60)}s"
        results_only = [r for _, r in results_with_qidx]
        success_count = sum(1 for r in results_only if r.get('success'))
        self.session_files_checked += success_count

        pdf_a3_count = sum(1 for r in results_only if r.get('success') and r.get('display', {}).get('is_pdf_a3'))
        signed_count = sum(1 for r in results_only if r.get('success') and r.get('display', {}).get('signature_count', 0) > 0)

        self.results_text.config(state=tk.NORMAL)
        self.results_text.delete(1.0, tk.END)
        self.results_text.insert(tk.END, "KONTROLA DOKONČENA\n")
        self.results_text.insert(tk.END, f"Celkem souborů: {success_count}\n")
        self.results_text.insert(tk.END, f"Formát PDF/A-3: {pdf_a3_count}\n")
        self.results_text.insert(tk.END, f"S podpisem: {signed_count}\n")
        self.results_text.insert(tk.END, f"Čas: {time_str}\n")
        if response_data and response_data.get('status') == 'partial':
            self.results_text.insert(tk.END, f"\n{response_data.get('message', '')}\n")
        self.results_text.insert(tk.END, "\nKlikněte na řádek ve frontě pro detail souboru.\n")
        if upload_error:
            self.results_text.insert(tk.END, f"\n⚠ Odeslání na server: {upload_error}\n")
            if "Zkušební limit" in upload_error or "vyčerpán" in upload_error:
                messagebox.showwarning("Zkušební limit", upload_error)
                self.license_status_label.config(text=upload_error[:60] + ("…" if len(upload_error) > 60 else ""), fg=self.ERROR_RED)
        self.results_text.config(state=tk.DISABLED)

        # Dialog: chcete poslat na server k vyhodnocení?
        if self.on_send_batch_callback and results_with_qidx:
            n = len(results_with_qidx)
            msg = "Načetlo data z {} souborů. Chcete poslat na server k vyhodnocení?".format(n)
            if messagebox.askyesno("Odeslat na server", msg, default=messagebox.YES):
                try:
                    results_only = [r for _, r in results_with_qidx]
                    out = self.on_send_batch_callback(results_only, None)
                    if out and len(out) >= 2 and not out[0]:
                        upload_error = out[1] or "Chyba odeslání na server"
                        self.results_text.config(state=tk.NORMAL)
                        self.results_text.insert(tk.END, "\n⚠ Odeslání na server: " + upload_error + "\n")
                        self.results_text.config(state=tk.DISABLED)
                        if "Zkušební limit" in upload_error or "vyčerpán" in upload_error:
                            messagebox.showwarning("Zkušební limit", upload_error)
                            self.license_status_label.config(text=upload_error[:60] + ("…" if len(upload_error) > 60 else ""), fg=self.ERROR_RED)
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
                except Exception as e:
                    self.results_text.config(state=tk.NORMAL)
                    self.results_text.insert(tk.END, "\n⚠ Odeslání na server: " + str(e) + "\n")
                    self.results_text.config(state=tk.DISABLED)

    def display_error(self, error_msg):
        """Zobrazí chybovou hlášku"""
        self.results_text.config(state=tk.NORMAL)
        self.results_text.delete(1.0, tk.END)
        self.results_text.insert(tk.END, f"CHYBA:\n{error_msg}\n")
        self.results_text.config(state=tk.DISABLED)

    def clear_results_and_queue(self):
        """Vymaže frontu úkolů a zobrazené výsledky (po přihlášení/odhlášení)."""
        self.tasks = []
        self.queue_display = []
        self._iid_to_qidx.clear()
        self.session_files_checked = 0
        self.update_queue_display()
        self._show_session_summary()

    def set_license_display(self, text):
        """Aktualizuje zobrazení stavu licence – v hlavičce Přihlásit/Odhlásit."""
        if text:
            short = (text[:28] + "…") if len(text) > 28 else text
            self.header_status.config(text=short)
            self.license_status_label.config(text=text, fg=self.TEXT_DARK)
            self.login_btn_header.pack_forget()
            self.logout_btn_header.pack(side=tk.RIGHT, padx=2, pady=10)
        else:
            self.header_status.config(text="")
            self.license_status_label.config(text="", fg=self.TEXT_DARK)
            self.logout_btn_header.pack_forget()
            self.login_btn_header.pack(side=tk.RIGHT, padx=2, pady=10)
            self.set_export_xls_enabled(False)

    def _do_logout(self):
        """Odhlášení – vymaže zobrazení, pak klíč a zobrazí dialog přihlášení."""
        if getattr(self, 'on_after_logout_callback', None):
            self.on_after_logout_callback()
        if self.on_logout_callback:
            self.on_logout_callback()

    def show_api_key_dialog(self):
        """Dialog přihlášení: Vyzkoušet zdarma (Trial) nebo e-mail + heslo pro placené účty."""
        dialog = tk.Toplevel(self.root)
        dialog.title("Přihlášení")
        dialog.geometry("480x380")
        dialog.configure(bg=self.BG_WHITE)
        dialog.transient(self.root)
        dialog.grab_set()

        dialog.update_idletasks()
        x = self.root.winfo_x() + (self.root.winfo_width() // 2) - 240
        y = self.root.winfo_y() + (self.root.winfo_height() // 2) - 190
        dialog.geometry(f"+{x}+{y}")

        title = tk.Label(dialog, text="Přihlášení k účtu", font=("Segoe UI", 12, "bold"),
                         bg=self.BG_WHITE, fg=self.TEXT_DARK)
        title.pack(pady=(16, 8))
        # Adresa serveru (self.api_url) zůstává v kódu, v UI se nezobrazuje.

        status_label = tk.Label(dialog, text="", font=("Segoe UI", 9), bg=self.BG_WHITE)
        status_label.pack(pady=8)

        def do_trial():
            status_label.config(text="Režim: Zkušební verze (Trial)", fg=self.ACCENT)
            dialog.update()
            try:
                from license import DEMO_TRIAL_EMAIL, DEMO_TRIAL_PASSWORD
                email, password = DEMO_TRIAL_EMAIL or "demo_trial@dokucheck.app", DEMO_TRIAL_PASSWORD or "demo123"
            except ImportError:
                email, password = "demo_trial@dokucheck.app", "demo123"
            if self.on_login_password_callback:
                result = self.on_login_password_callback(email, password)
                success = result[0] if result else False
                message = result[1] if len(result) > 1 else ""
                display_text = result[2] if len(result) > 2 else None
                if success:
                    status_label.config(text="Režim: Zkušební verze (Trial)", fg=self.SUCCESS_GREEN)
                    self.set_license_display("Režim: Zkušební verze (Trial)")
                    if self.on_after_login_callback:
                        self.on_after_login_callback()
                    dialog.after(800, dialog.destroy)
                else:
                    status_label.config(text=message or "Chyba přihlášení", fg=self.ERROR_RED)
            else:
                status_label.config(text="Chyba: chybí callback", fg=self.ERROR_RED)

        btn_trial = tk.Button(dialog, text="Vyzkoušet zdarma", font=("Segoe UI", 10, "bold"),
                              bg=self.ACCENT_BTN, fg=self.BUTTON_TEXT, relief=tk.FLAT,
                              padx=20, pady=10, cursor="hand2", command=do_trial)
        btn_trial.pack(pady=(8, 16))

        tk.Label(dialog, text="Přihlásit se (e-mail + heslo – placený účet):",
                 font=("Segoe UI", 9, "bold"), bg=self.BG_WHITE, fg=self.TEXT_DARK).pack(anchor=tk.W, padx=20, pady=(8, 4))
        email_var = tk.StringVar()
        pass_var = tk.StringVar()
        tk.Label(dialog, text="E-mail:", font=("Segoe UI", 9), bg=self.BG_WHITE, fg=self.TEXT_DARK).pack(anchor=tk.W, padx=20, pady=(2, 0))
        email_entry = tk.Entry(dialog, textvariable=email_var, font=("Consolas", 11), width=42)
        email_entry.pack(pady=2, padx=20, fill=tk.X)
        tk.Label(dialog, text="Heslo:", font=("Segoe UI", 9), bg=self.BG_WHITE, fg=self.TEXT_DARK).pack(anchor=tk.W, padx=20, pady=(6, 0))
        pass_entry = tk.Entry(dialog, textvariable=pass_var, font=("Consolas", 11), width=42, show="*")
        pass_entry.pack(pady=2, padx=20, fill=tk.X)
        email_entry.focus()

        def do_login():
            email = email_var.get().strip()
            password = pass_var.get()

            if email and password and self.on_login_password_callback:
                status_label.config(text="Ověřuji e-mail a heslo…", fg=self.WARNING_ORANGE)
                dialog.update()
                result = self.on_login_password_callback(email, password)
                success = result[0] if result else False
                message = result[1] if len(result) > 1 else ""
                display_text = result[2] if len(result) > 2 else None
                if success:
                    status_label.config(text=message or "Přihlášeno.", fg=self.SUCCESS_GREEN)
                    if display_text:
                        self.set_license_display(display_text if str(display_text).strip().startswith("Režim:") else "Přihlášen: " + display_text)
                    if self.on_after_login_callback:
                        self.on_after_login_callback()
                    dialog.after(1200, dialog.destroy)
                else:
                    status_label.config(text=message or "Chyba přihlášení", fg=self.ERROR_RED)
                return

            status_label.config(text="Zadejte e-mail a heslo.", fg=self.ERROR_RED)

        btn = tk.Button(dialog, text="Přihlásit se", font=("Segoe UI", 10, "bold"),
                        bg=self.ACCENT, fg=self.BUTTON_TEXT, relief=tk.FLAT,
                        padx=20, pady=8, cursor="hand2", command=do_login)
        btn.pack(pady=10)

        pass_entry.bind("<Return>", lambda e: do_login())
        email_entry.bind("<Return>", lambda e: do_login())


def create_app(on_check_callback, on_api_key_callback, api_url="",
              on_login_password_callback=None, on_logout_callback=None, on_get_max_files=None,
              on_after_login_callback=None, on_after_logout_callback=None, on_get_web_login_url=None,
              on_send_batch_callback=None):
    """Vytvoří a vrátí GUI aplikaci. on_send_batch_callback(results, source_folder) -> (success, msg, batch_id, response_data)."""
    if TKINTERDND_AVAILABLE:
        try:
            root = TkinterDnD.Tk()
        except:
            root = tk.Tk()
    else:
        root = tk.Tk()

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
