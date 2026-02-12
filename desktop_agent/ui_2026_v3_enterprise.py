# ui_2026_v3_enterprise.py – TOP 2026 preview V3: Enterprise / Dashboard. NEMĚŇ produkční ui.py.
# Více panelů, metriky nahoře, vyšší info density, „Jak to funguje“ timeline.
# Optimalizováno pro moderní velké rozlišení (2K/4K): DPI awareness + škálování CTk.

import tkinter as tk
from tkinter import filedialog, messagebox
from tkinter import ttk
import threading
import webbrowser
import os
import sys
import time

import customtkinter as ctk

from ui import _count_errors_from_result, _session_summary_text
from version import BUILD_VERSION, AGENT_VERSION

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")


def _setup_high_dpi_v3():
    """
    DPI Awareness (Windows) – okno se při přetažení na jiný monitor správně překreslí a nezprůhlední.
    Volat PŘED vytvořením root okna. SetProcessDpiAwareness(1) = system DPI.
    """
    try:
        if sys.platform == "win32":
            try:
                ctypes = __import__("ctypes")
                shcore = getattr(ctypes.windll, "shcore", None)
                if shcore:
                    shcore.SetProcessDpiAwareness(1)
            except Exception:
                try:
                    ctypes = __import__("ctypes")
                    ctypes.windll.user32.SetProcessDPIAware()
                except Exception:
                    pass
    except Exception:
        pass
    ctk.set_widget_scaling(1.0)
    ctk.set_window_scaling(1.0)

try:
    from tkinterdnd2 import DND_FILES, TkinterDnD
    TKINTERDND_AVAILABLE = True
except ImportError:
    TKINTERDND_AVAILABLE = False

FONT_STACK = ("Segoe UI Variable", "Segoe UI", "Inter")
FS_12 = 12
FS_14 = 14
FS_16 = 16
FS_20 = 20
FS_24 = 24
FS_32 = 32

BG_APP = "#0B0F14"
BG_CARD = "#0B1220"
BG_HEADER = "#0F172A"
# Barvy pro ttk Treeview (theme clam) – musí být konzistentní s aplikací, žádná bílá
TREEVIEW_BG = "#1a1a1a"
TREEVIEW_FG = "#ffffff"
BORDER = "#1F2937"
TEXT = "#E5E7EB"
TEXT_MUTED = "#94A3B8"
ACCENT = "#0891b2"
SUCCESS = "#22c55e"
WARNING = "#f97316"
ERROR = "#ef4444"
SECONDS_PER_FILE_ETA = 0.4
SIDEBAR_W = 220
# Strom – rowheight 38 px (vzdušnost)
TREE_ROWHEIGHT = 38
# Logo – vyměnitelné. Při běhu z exe (PyInstaller) jsou data v sys._MEIPASS.
if getattr(sys, 'frozen', False):
    _AGENT_DIR = getattr(sys, '_MEIPASS', os.path.dirname(os.path.abspath(__file__)))
else:
    _AGENT_DIR = os.path.dirname(os.path.abspath(__file__))
LOGO_PATH = os.path.join(_AGENT_DIR, "logo", "logo.png")
LOGO_ICO_PATH = os.path.join(_AGENT_DIR, "logo", "logo.ico")
NO_DETAIL_MSG = "Výsledky kontroly jednotlivých PDF se v této aplikaci nezobrazují.\nStav uvidíte po odeslání na server."

SPLASH_DURATION_MS = 3000


def _create_splash(master):
    """Vytvoří dočasné okno bez okrajů (splash): logo, verze, copyright. Trvá SPLASH_DURATION_MS ms."""
    splash = ctk.CTkToplevel(master)
    splash.overrideredirect(True)
    splash.configure(fg_color=BG_APP)
    splash.attributes("-topmost", True)
    w, h = 420, 300
    splash.geometry(f"{w}x{h}")
    splash.update_idletasks()
    sw = splash.winfo_screenwidth()
    sh = splash.winfo_screenheight()
    x = (sw - w) // 2
    y = (sh - h) // 2
    splash.geometry(f"{w}x{h}+{x}+{y}")
    try:
        logo_img = ctk.CTkImage(light_image=LOGO_PATH, dark_image=LOGO_PATH, size=(200, 100))
        ctk.CTkLabel(splash, text="", image=logo_img).pack(pady=(32, 16))
    except Exception:
        ctk.CTkLabel(splash, text="DokuCheck Agent", font=(FONT_STACK[0], FS_20, "bold"), text_color=TEXT).pack(pady=(32, 16))
    ctk.CTkLabel(splash, text=AGENT_VERSION, font=(FONT_STACK[0], FS_16), text_color=TEXT).pack(pady=4)
    ctk.CTkLabel(splash, text="© 2026 Ing. Martin Cieślar", font=(FONT_STACK[0], 10), text_color=TEXT_MUTED).pack(pady=(0, 24))
    splash.update()
    return splash


def _close_splash_and_show_main(splash, root):
    """Zavře splash a zobrazí hlavní okno (už maximalizované)."""
    try:
        splash.destroy()
    except Exception:
        pass
    try:
        root.deiconify()
    except Exception:
        pass


class PDFCheckUI_2026_V3:
    """Preview V3 – enterprise dashboard, metriky nahoře, Jak to funguje, high density."""

    def __init__(self, root, on_check_callback, on_api_key_callback, api_url="",
                 on_login_password_callback=None, on_logout_callback=None, on_get_max_files=None,
                 on_after_login_callback=None, on_after_logout_callback=None, on_get_web_login_url=None,
                 on_get_remote_config=None,
                 on_get_legal_config=None,
                 on_send_batch_callback=None, on_has_login=None):
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
        self.on_has_login = on_has_login  # callable() -> bool; bez přihlášení nelze analyzovat ani odesílat
        self.on_get_remote_config = on_get_remote_config  # callable() -> dict s disclaimer, vop_link, update_msg
        self.on_get_legal_config = on_get_legal_config  # callable() -> dict s disclaimer, vop_url, gdpr_url
        self.api_url = api_url or "https://www.dokucheck.cz"

        self.tasks = []
        self.queue_display = []
        self.batches = []  # [{"label": "Dávka - HH:MM", "qidx_start": int, "qidx_end": int, "root_iid": str|None}, ...]
        self.session_files_checked = 0
        self.start_time = None
        self.total_files = 0
        self.processed_files = 0
        self.cancel_requested = False
        self.is_running = False
        self.selected_qidx = None

        self.root.title("DokuCheck Agent")
        self.root.minsize(1200, 750)
        self.root.geometry("1680x1000")
        try:
            self.root.configure(fg_color=BG_APP)
        except tk.TclError:
            self.root.configure(bg=BG_APP)
        self._center()
        self._build_layout()
        self._setup_dnd_overlay()
        self._apply_dark_title_bar()
        self._setup_logo()
        self._show_session_summary()
        # Maximalizace se provádí v create_app před deiconify() – zde už ne, aby neprobliklo
        self.root.after(250, self._update_analyze_send_state)

    def _center(self):
        self.root.update_idletasks()
        w, h = 1680, 1000
        x = (self.root.winfo_screenwidth() // 2) - (w // 2)
        y = (self.root.winfo_screenheight() // 2) - (h // 2)
        self.root.geometry(f"{w}x{h}+{x}+{y}")

    def _apply_dark_title_bar(self):
        """Tmavý title bar na Windows 10/11 (DWM)."""
        if sys.platform != "win32":
            return
        try:
            ct = __import__("ctypes")
            hwnd = ct.windll.user32.GetParent(self.root.winfo_id())
            if not hwnd:
                return
            DWMWA_USE_IMMERSIVE_DARK_MODE = 20
            val = ct.c_int(1)
            ct.windll.dwmapi.DwmSetWindowAttribute(hwnd, DWMWA_USE_IMMERSIVE_DARK_MODE, ct.byref(val), ct.sizeof(val))
        except Exception:
            pass

    def _setup_logo(self):
        """Ikona okna: logo/logo.ico (Windows), jinak logo/logo.png přes iconphoto."""
        try:
            if os.path.isfile(LOGO_ICO_PATH):
                self.root.iconbitmap(LOGO_ICO_PATH)
                return
        except Exception:
            pass
        try:
            if os.path.isfile(LOGO_PATH):
                # Fallback: PNG jako ikona okna (taskbar, titulní lišta)
                img = tk.PhotoImage(file=LOGO_PATH)
                self.root.iconphoto(True, img)
        except Exception:
            pass

    def _build_layout(self):
        self.root.grid_columnconfigure(0, weight=0, minsize=SIDEBAR_W)
        self.root.grid_columnconfigure(1, weight=1)
        self.root.grid_rowconfigure(0, weight=1)

        # Sidebar
        sidebar = ctk.CTkFrame(self.root, fg_color=BG_HEADER, width=SIDEBAR_W, corner_radius=0)
        sidebar.grid(row=0, column=0, sticky="nswe")
        sidebar.grid_propagate(False)
        # Logo (vyměnitelné – nahraďte soubor desktop_agent/logo/logo.png)
        self._logo_container = ctk.CTkFrame(sidebar, fg_color="transparent")
        self._logo_container.pack(pady=(16, 0))
        if os.path.isfile(LOGO_PATH):
            try:
                logo_img = ctk.CTkImage(light_image=LOGO_PATH, dark_image=LOGO_PATH, size=(140, 36))
                ctk.CTkLabel(self._logo_container, text="", image=logo_img).pack()
            except Exception:
                ctk.CTkLabel(self._logo_container, text="DokuCheck", font=(FONT_STACK[0], FS_20, "bold"), text_color=TEXT).pack()
        else:
            ctk.CTkLabel(self._logo_container, text="DokuCheck", font=(FONT_STACK[0], FS_20, "bold"), text_color=TEXT).pack()
        # Blok „Účet“ – zobrazen když přihlášen
        self._account_frame = ctk.CTkFrame(sidebar, fg_color="transparent")
        self._account_frame.pack(fill=tk.X, pady=(0, 4))
        ctk.CTkLabel(self._account_frame, text="Účet", font=(FONT_STACK[0], FS_12, "bold"), text_color=TEXT_MUTED).pack(anchor=tk.W, padx=12, pady=(0, 0))
        self.sidebar_account = ctk.CTkLabel(self._account_frame, text="Nepřihlášen", font=(FONT_STACK[0], FS_12), text_color=TEXT, wraplength=SIDEBAR_W - 24)
        self.sidebar_account.pack(anchor=tk.W, padx=12, pady=(0, 2))
        self.sidebar_daily_limit = ctk.CTkLabel(self._account_frame, text="Limit: —", font=(FONT_STACK[0], FS_12), text_color=TEXT_MUTED, wraplength=SIDEBAR_W - 24)
        self.sidebar_daily_limit.pack(anchor=tk.W, padx=12, pady=(0, 6))
        ctk.CTkButton(sidebar, text="Web", command=self._open_web, font=(FONT_STACK[0], FS_12), width=160, fg_color=ACCENT).pack(pady=4, padx=12, fill=tk.X)
        self.logout_btn = ctk.CTkButton(sidebar, text="Odhlásit", command=self._do_logout, font=(FONT_STACK[0], FS_12), width=160, fg_color=ERROR)
        self.logout_btn.pack(pady=2, padx=12, fill=tk.X)
        self.logout_btn.pack_forget()
        # Přihlášení přímo v sidebaru (ne vyskakovací okno)
        self._login_frame = ctk.CTkFrame(sidebar, fg_color="transparent")
        self._login_frame.pack(fill=tk.X, pady=(0, 4))
        ctk.CTkLabel(self._login_frame, text="Přihlášení", font=(FONT_STACK[0], FS_12, "bold"), text_color=TEXT_MUTED).pack(anchor=tk.W, padx=12, pady=(4, 2))
        self._login_status = ctk.CTkLabel(self._login_frame, text="", font=(FONT_STACK[0], FS_12), text_color=ERROR, wraplength=SIDEBAR_W - 24)
        self._login_status.pack(anchor=tk.W, padx=12, pady=(0, 2))
        ctk.CTkButton(self._login_frame, text="Vyzkoušet zdarma", command=self._do_trial_login, font=(FONT_STACK[0], FS_12), width=160, fg_color=ACCENT).pack(pady=2, padx=12, fill=tk.X)
        self._login_email = ctk.CTkEntry(self._login_frame, placeholder_text="jmeno@firma.cz", width=160, height=28, font=(FONT_STACK[0], FS_12))
        self._login_email.pack(pady=2, padx=12, fill=tk.X)
        self._login_email.bind("<Return>", lambda e: self._do_email_login())
        self._login_pass = ctk.CTkEntry(self._login_frame, placeholder_text="Heslo", width=160, height=28, show="*", font=(FONT_STACK[0], FS_12))
        self._login_pass.pack(pady=2, padx=12, fill=tk.X)
        self._login_pass.bind("<Return>", lambda e: self._do_email_login())
        ctk.CTkButton(self._login_frame, text="Přihlásit se", command=self._do_email_login, font=(FONT_STACK[0], FS_12), width=160, fg_color=BORDER).pack(pady=2, padx=12, fill=tk.X)
        self.license_status_label = ctk.CTkLabel(sidebar, text="", font=(FONT_STACK[0], FS_12), text_color=ERROR, wraplength=SIDEBAR_W - 24)
        self.license_status_label.pack(anchor=tk.W, padx=12, pady=(0, 6))
        self.daily_limit_label = self.sidebar_daily_limit
        # Patička sidebaru (footer_frame): dynamické právní informace – disclaimer + odkazy VOP, GDPR
        self._remote_footer = ctk.CTkFrame(sidebar, fg_color="transparent")
        self._remote_footer.pack(side=tk.BOTTOM, fill=tk.X, padx=12, pady=(8, 12))
        legal = self._get_legal_config()
        FOOTER_FONT = (FONT_STACK[0], 10)
        self._disclaimer_label = ctk.CTkLabel(
            self._remote_footer,
            text=legal.get("disclaimer", "Výsledek kontroly je informativní. Za finální správnost dokumentace odpovídá autorizovaná osoba dle platných norem."),
            font=FOOTER_FONT,
            text_color=TEXT_MUTED,
            wraplength=SIDEBAR_W - 24,
            justify=tk.LEFT,
        )
        self._disclaimer_label.pack(anchor=tk.W)
        links_row = ctk.CTkFrame(self._remote_footer, fg_color="transparent")
        links_row.pack(anchor=tk.W, pady=(4, 0))
        vop_url = legal.get("vop_url", "")
        gdpr_url = legal.get("gdpr_url", "")
        if vop_url:
            ctk.CTkButton(links_row, text="VOP", command=lambda: webbrowser.open(vop_url), font=FOOTER_FONT, fg_color="transparent", text_color=ACCENT, width=36, height=18, anchor="w").pack(side=tk.LEFT, padx=(0, 8))
        if gdpr_url:
            ctk.CTkButton(links_row, text="GDPR", command=lambda: webbrowser.open(gdpr_url), font=FOOTER_FONT, fg_color="transparent", text_color=ACCENT, width=40, height=18, anchor="w").pack(side=tk.LEFT)
        rc = self._get_remote_config()
        self._update_msg_label = ctk.CTkLabel(self._remote_footer, text=rc.get("update_msg", "Používáte aktuální verzi."), font=FOOTER_FONT, text_color=TEXT_MUTED, wraplength=SIDEBAR_W - 24)
        self._update_msg_label.pack(anchor=tk.W, pady=(4, 0))
        about_row = ctk.CTkFrame(self._remote_footer, fg_color="transparent")
        about_row.pack(anchor=tk.W, pady=(2, 0))
        ctk.CTkLabel(about_row, text=f"Build {BUILD_VERSION}", font=(FONT_STACK[0], 9), text_color=TEXT_MUTED).pack(side=tk.LEFT)
        ctk.CTkButton(about_row, text="ⓘ", command=self._show_about, font=(FONT_STACK[0], 11), fg_color="transparent", text_color=ACCENT, width=28, height=22, anchor="center").pack(side=tk.LEFT, padx=(8, 0))

        main = ctk.CTkFrame(self.root, fg_color="transparent")
        main.grid(row=0, column=1, sticky="nsew", padx=0, pady=0)
        main.grid_columnconfigure(0, weight=1)
        main.grid_rowconfigure(1, weight=1)

        # Metrics row – 4 mini cards
        metrics_row = ctk.CTkFrame(main, fg_color="transparent")
        metrics_row.grid(row=0, column=0, sticky="ew", padx=8, pady=(8, 4))
        metrics_row.grid_columnconfigure(0, weight=1)
        metrics_row.grid_columnconfigure(1, weight=1)
        metrics_row.grid_columnconfigure(2, weight=1)
        metrics_row.grid_columnconfigure(3, weight=1)
        self.metric_dnes = ctk.CTkLabel(metrics_row, text="Dnes: 0", font=(FONT_STACK[0], FS_14, "bold"), text_color=TEXT)
        self.metric_dnes.grid(row=0, column=0, sticky="w", padx=8, pady=6)
        self.metric_ok = ctk.CTkLabel(metrics_row, text="Úspěšnost: —", font=(FONT_STACK[0], FS_14, "bold"), text_color=SUCCESS)
        self.metric_ok.grid(row=0, column=1, sticky="w", padx=8, pady=6)
        self.metric_chyby = ctk.CTkLabel(metrics_row, text="Chyby: 0", font=(FONT_STACK[0], FS_14, "bold"), text_color=ERROR)
        self.metric_chyby.grid(row=0, column=2, sticky="w", padx=8, pady=6)
        self.metric_pdfa = ctk.CTkLabel(metrics_row, text="PDF/A-3 OK: 0", font=(FONT_STACK[0], FS_14, "bold"), text_color=TEXT_MUTED)
        self.metric_pdfa.grid(row=0, column=3, sticky="w", padx=8, pady=6)

        # Command bar
        bar = ctk.CTkFrame(main, fg_color=BG_CARD, height=44, corner_radius=0)
        bar.grid(row=1, column=0, sticky="ew")
        bar.grid_propagate(False)
        main.grid_rowconfigure(1, weight=0)
        ctk.CTkButton(bar, text="Přidat soubory", command=self.add_files, font=(FONT_STACK[0], FS_12), width=100, fg_color=ACCENT).pack(side=tk.LEFT, padx=6, pady=4)
        ctk.CTkButton(bar, text="+ Složka", command=self.add_folder, font=(FONT_STACK[0], FS_12), width=72, fg_color=ACCENT).pack(side=tk.LEFT, padx=2, pady=4)
        ctk.CTkButton(bar, text="VYMAZAT VŠE", command=self.clear_queue, font=(FONT_STACK[0], FS_12), width=100, fg_color=BORDER).pack(side=tk.LEFT, padx=2, pady=4)
        self.check_btn = ctk.CTkButton(bar, text="Analyzovat PDF", command=self.on_check_clicked, font=(FONT_STACK[0], FS_14, "bold"), fg_color=ACCENT, height=32)
        self.check_btn.pack(side=tk.RIGHT, padx=4, pady=6)
        self.send_btn = ctk.CTkButton(bar, text="Odeslat metadata na server", command=self._on_send_metadata_clicked, font=(FONT_STACK[0], FS_12, "bold"), fg_color=SUCCESS, height=28)
        self.send_btn.pack(side=tk.RIGHT, padx=4, pady=6)
        self.send_btn.pack_forget()

        # Content: queue širší + detail + "Jak to funguje"
        content = ctk.CTkFrame(main, fg_color="transparent")
        content.grid(row=2, column=0, sticky="nsew", padx=6, pady=4)
        content.grid_columnconfigure(0, weight=3, minsize=440)
        content.grid_columnconfigure(1, weight=1, minsize=260)
        content.grid_columnconfigure(2, weight=0, minsize=180)
        content.grid_rowconfigure(0, weight=1)
        main.grid_rowconfigure(2, weight=1)

        # Queue panel – strom (Treeview) + toolbar
        left = ctk.CTkFrame(content, fg_color=BG_CARD, corner_radius=6)
        left.grid(row=0, column=0, sticky="nsew", padx=(0, 4))
        left.grid_columnconfigure(0, weight=1)
        left.grid_rowconfigure(2, weight=1)
        ctk.CTkLabel(left, text="Fronta (strom složek)", font=(FONT_STACK[0], FS_14, "bold"), text_color=TEXT).grid(row=0, column=0, sticky="w", padx=10, pady=(10, 4))
        # Toolbar nad stromem: Rozbalit / Sbalit (tlačítka filtru Vše/Chyby/PDF/A-3 OK odstraněna)
        self._queue_filter = "all"
        toolbar = ctk.CTkFrame(left, fg_color="transparent")
        toolbar.grid(row=1, column=0, sticky="ew", padx=6, pady=(0, 4))
        toolbar.grid_columnconfigure(0, weight=1)
        ctk.CTkButton(toolbar, text="Rozbalit vše", command=self._tree_expand_all, font=(FONT_STACK[0], FS_12), width=90).grid(row=0, column=0, padx=4, pady=2)
        ctk.CTkButton(toolbar, text="Sbalit vše", command=self._tree_collapse_all, font=(FONT_STACK[0], FS_12), width=90).grid(row=0, column=1, padx=4, pady=2)
        # Kontejner pro tk Treeview (ttk potřebuje tk rodiče) – bez rámečku, barva jako aplikace
        self._tree_container = tk.Frame(left, bg=TREEVIEW_BG, highlightthickness=0)
        self._tree_container.grid(row=2, column=0, sticky="nsew", padx=6, pady=(0, 6))
        self._tree_container.grid_columnconfigure(0, weight=1)
        self._tree_container.grid_rowconfigure(0, weight=1)
        self._queue_tree_style = ttk.Style()
        try:
            self._queue_tree_style.theme_use("clam")
        except tk.TclError:
            pass
        self._queue_tree_style.configure(
            "Queue.Treeview",
            rowheight=TREE_ROWHEIGHT,
            background=TREEVIEW_BG,
            foreground=TREEVIEW_FG,
            fieldbackground=TREEVIEW_BG,
        )
        self._queue_tree_style.configure("Queue.Treeview.Heading", background=BG_HEADER, foreground=TREEVIEW_FG)
        self._queue_tree_style.map(
            "Queue.Treeview",
            background=[("selected", BORDER), ("!selected", TREEVIEW_BG)],
            foreground=[("selected", TREEVIEW_FG), ("!selected", TREEVIEW_FG)],
            fieldbackground=[("selected", BORDER), ("!selected", TREEVIEW_BG)],
        )
        self.queue_tree = ttk.Treeview(
            self._tree_container, columns=("status",), show="tree headings", height=18,
            style="Queue.Treeview", selectmode="browse",
        )
        self.queue_tree.heading("#0", text="Položka")
        self.queue_tree.heading("status", text="Stav")
        self.queue_tree.column("#0", minwidth=200, stretch=True)
        self.queue_tree.column("status", width=52, minwidth=52)
        self.queue_tree.tag_configure("ok", foreground=SUCCESS)
        self.queue_tree.tag_configure("error", foreground=ERROR)
        self.queue_tree.tag_configure("pending", foreground=TEXT_MUTED)
        scroll = tk.Scrollbar(self._tree_container, command=self.queue_tree.yview, bg=TREEVIEW_BG, troughcolor=TREEVIEW_BG, activebackground=BORDER)
        self.queue_tree.configure(yscrollcommand=scroll.set)
        self.queue_tree.grid(row=0, column=0, sticky="nsew")
        scroll.grid(row=0, column=1, sticky="ns")
        self.queue_tree.bind("<<TreeviewSelect>>", self._on_tree_select)
        self.queue_tree.bind("<Button-1>", self._on_tree_click)
        self._dnd_hint_label = ctk.CTkLabel(
            self._tree_container, text="Zde přetáhněte soubory nebo složky k analýze",
            text_color=TEXT_MUTED, font=(FONT_STACK[0], FS_14),
        )
        self._dnd_hint_label.place(relx=0.5, rely=0.5, anchor=tk.CENTER)
        self._tree_iid_to_qidx = {}
        self._tree_iid_to_task_ix = {}
        self._qidx_to_tree_iid = {}
        self._last_display_result = None
        self.queue_scroll = None

        # Pravý panel – bez detailu kontroly jednotlivých PDF (citlivá data)
        right = ctk.CTkFrame(content, fg_color=BG_CARD, corner_radius=6)
        right.grid(row=0, column=1, sticky="nsew", padx=4)
        right.grid_columnconfigure(0, weight=1)
        right.grid_rowconfigure(1, weight=1)
        ctk.CTkLabel(right, text="Informace", font=(FONT_STACK[0], FS_14, "bold"), text_color=TEXT).grid(row=0, column=0, sticky="w", padx=10, pady=(10, 4))
        self.detail_text = ctk.CTkTextbox(right, font=(FONT_STACK[0], FS_12), fg_color=BG_APP, text_color=TEXT, wrap="word")
        self.detail_text.grid(row=1, column=0, sticky="nsew", padx=8, pady=(0, 8))
        self.results_text = self.detail_text

        # Jak to funguje – timeline
        timeline = ctk.CTkFrame(content, fg_color=BG_CARD, corner_radius=6, width=180)
        timeline.grid(row=0, column=2, sticky="nsew", padx=(4, 0))
        timeline.grid_propagate(False)
        ctk.CTkLabel(timeline, text="Jak to funguje", font=(FONT_STACK[0], FS_12, "bold"), text_color=TEXT_MUTED).grid(row=0, column=0, sticky="w", padx=10, pady=(10, 6))
        steps = [
            "1. Přidejte PDF",
            "2. Zaškrtněte položky",
            "3. Analyzovat PDF",
            "4. Prohlédněte výsledky",
            "5. Odeslat metadata na server",
        ]
        for i, s in enumerate(steps):
            ctk.CTkLabel(timeline, text=s, font=(FONT_STACK[0], FS_12), text_color=TEXT_MUTED, anchor="w").grid(row=i + 1, column=0, sticky="w", padx=10, pady=2)
        ctk.CTkButton(timeline, text="Nápověda", command=self._show_help_modal, font=(FONT_STACK[0], FS_12), fg_color="transparent", width=120).grid(row=len(steps) + 1, column=0, padx=10, pady=(12, 8))
        self.timeline_frame = timeline

        # Progress row – Počet X/Y, ETA, Rychlost (při běhu); Připraveno: N souborů, M složek (v klidu)
        self._progress_row = ctk.CTkFrame(main, fg_color="transparent")
        self._progress_row.grid(row=3, column=0, sticky="ew", padx=8, pady=4)
        main.grid_rowconfigure(3, weight=0)
        self.progress_label = ctk.CTkLabel(self._progress_row, text="Připraveno", font=(FONT_STACK[0], FS_12), text_color=TEXT_MUTED)
        self.progress_label.pack(side=tk.LEFT)
        self.cancel_btn = ctk.CTkButton(self._progress_row, text="Zrušit", command=self.cancel_check, font=(FONT_STACK[0], FS_12), width=60, fg_color=ERROR)
        self.cancel_btn.pack(side=tk.RIGHT, padx=6)
        self.cancel_btn.pack_forget()
        self.progress = ctk.CTkProgressBar(self._progress_row, height=6, progress_color=ACCENT)
        self.progress.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=6)
        self.progress.set(0)
        self._progress_speed_label = ctk.CTkLabel(self._progress_row, text="", font=(FONT_STACK[0], FS_12), text_color=TEXT_MUTED)
        self._progress_speed_label.pack(side=tk.RIGHT, padx=(0, 8))
        self.eta_label = ctk.CTkLabel(self._progress_row, text="", font=(FONT_STACK[0], FS_12), text_color=TEXT_MUTED)
        self.eta_label.pack(side=tk.RIGHT)
        self._progress_row.grid_remove()
        # Panel zpráv v hlavním okně (bez vyskakovacích oken)
        self._msg_row = ctk.CTkFrame(main, fg_color=BG_CARD, corner_radius=4, height=44)
        self._msg_row.grid(row=4, column=0, sticky="ew", padx=8, pady=4)
        self._msg_row.grid_propagate(False)
        main.grid_rowconfigure(4, weight=0)
        self._msg_label = ctk.CTkLabel(self._msg_row, text="—", font=(FONT_STACK[0], FS_12), text_color=TEXT_MUTED, anchor="w")
        self._msg_label.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=10, pady=8)
        self._msg_btn_frame = ctk.CTkFrame(self._msg_row, fg_color="transparent")
        self._msg_btn_frame.pack(side=tk.RIGHT, padx=8, pady=4)
        self._msg_pending_callback = None  # pro Ano/Ne v panelu zpráv
        # Tlačítko O programu (i) v pravém dolním rohu hlavní aplikace
        about_footer = ctk.CTkFrame(main, fg_color="transparent")
        about_footer.grid(row=5, column=0, sticky="e", padx=8, pady=2)
        main.grid_rowconfigure(5, weight=0)
        ctk.CTkButton(about_footer, text="ⓘ", command=self._show_about, font=(FONT_STACK[0], 12), fg_color="transparent", text_color=ACCENT, width=32, height=24).pack(side=tk.RIGHT)
        self.header_status = self.sidebar_account

    def show_message(self, text, msg_type="info", buttons=None, callback=None):
        """Zobrazí zprávu v panelu v hlavním okně. buttons: [(label, value), ...]; callback(value) po kliknutí."""
        color = TEXT_MUTED
        if msg_type == "warning":
            color = WARNING
        elif msg_type == "error":
            color = ERROR
        self._msg_label.configure(text=text, text_color=color)
        for w in self._msg_btn_frame.winfo_children():
            w.destroy()
        self._msg_pending_callback = None
        if buttons and callback:
            self._msg_pending_callback = (buttons, callback)
            for label, value in buttons:
                btn = ctk.CTkButton(
                    self._msg_btn_frame, text=label, width=70,
                    command=lambda v=value: self._on_msg_button(v)
                )
                btn.pack(side=tk.LEFT, padx=4)

    def _on_msg_button(self, value):
        if self._msg_pending_callback:
            _, callback = self._msg_pending_callback
            self._msg_pending_callback = None
            self.clear_message()
            try:
                callback(value)
            except Exception:
                pass

    def clear_message(self):
        """Smaže zprávu a tlačítka v panelu zpráv."""
        self._msg_label.configure(text="—", text_color=TEXT_MUTED)
        for w in self._msg_btn_frame.winfo_children():
            w.destroy()
        self._msg_pending_callback = None

    def _do_trial_login(self):
        self._login_status.configure(text="")
        try:
            from license import DEMO_TRIAL_EMAIL, DEMO_TRIAL_PASSWORD
            email = DEMO_TRIAL_EMAIL or "zdarma@trial.verze"
            password = DEMO_TRIAL_PASSWORD or "free"
        except ImportError:
            email, password = "zdarma@trial.verze", "free"
        if self.on_login_password_callback:
            result = self.on_login_password_callback(email, password)
            if result and result[0]:
                self.set_license_display("Režim: Zkušební verze (Trial)")
                if self.on_after_login_callback:
                    self.on_after_login_callback()
            else:
                self._login_status.configure(text=result[1] if result and len(result) > 1 else "Chyba", text_color=ERROR)

    def _do_email_login(self):
        self._login_status.configure(text="")
        email = self._login_email.get().strip()
        password = self._login_pass.get()
        if not email or not password:
            self._login_status.configure(text="Zadejte e-mail a heslo.", text_color=ERROR)
            return
        if self.on_login_password_callback:
            result = self.on_login_password_callback(email, password)
            if result and result[0]:
                display_text = result[2] if len(result) > 2 else None
                self.set_license_display(display_text or ("Přihlášen: " + email))
                if self.on_after_login_callback:
                    self.on_after_login_callback()
            else:
                self._login_status.configure(text=result[1] if result and len(result) > 1 else "Chyba", text_color=ERROR)

    def _open_web(self):
        url = None
        if self.on_get_web_login_url:
            try:
                url = self.on_get_web_login_url()
            except Exception:
                pass
        # Přihlášený: url = odkaz s tokenem -> přihlášení a rovnou webová aplikace (/app). Nepřihlášený: otevřít /app (kontrola PDF), ne landing.
        base = (self.api_url or "").rstrip("/")
        fallback = (base + "/app") if base else self.api_url
        webbrowser.open(url or fallback)

    def _setup_dnd_overlay(self):
        if not TKINTERDND_AVAILABLE:
            return
        try:
            overlay = tk.Frame(self.root, bg=BG_APP)
            overlay.place(relx=0, rely=0, relwidth=1, relheight=1)
            overlay.place_forget()
            card = tk.Frame(overlay, bg=BORDER)
            card.place(relx=0.5, rely=0.5, anchor=tk.CENTER, width=300, height=100)
            tk.Label(card, text="↓ Pustit soubory", font=(FONT_STACK[0], FS_20, "bold"), fg=TEXT, bg=BORDER).pack(expand=True)
            overlay.drop_target_register(DND_FILES)
            overlay.dnd_bind("<<Drop>>", self._on_drop)
            overlay.dnd_bind("<<DragEnter>>", lambda e: overlay.place(relx=0, rely=0, relwidth=1, relheight=1))
            overlay.dnd_bind("<<DragLeave>>", lambda e: overlay.place_forget())
            self.root.drop_target_register(DND_FILES)
            self.root.dnd_bind("<<DragEnter>>", lambda e: overlay.place(relx=0, rely=0, relwidth=1, relheight=1))
            self.root.dnd_bind("<<DragLeave>>", lambda e: overlay.place_forget())
            self.root.dnd_bind("<<Drop>>", self._on_drop)
            self._dnd_overlay = overlay
        except Exception:
            self._dnd_overlay = None

    def _on_drop(self, event):
        if getattr(self, "_dnd_overlay", None):
            self._dnd_overlay.place_forget()
        start = len(self.queue_display)
        for raw in self.root.tk.splitlist(event.data):
            path = (raw.strip() if isinstance(raw, str) else None) or (raw.get("path") or raw.get("full_path") if isinstance(raw, dict) else None)
            if path and isinstance(path, str):
                self.add_path_to_queue(path)
        if len(self.queue_display) > start:
            self.batches.append({
                "label": "Dávka - " + time.strftime("%d.%m. %H:%M"),
                "qidx_start": start,
                "qidx_end": len(self.queue_display),
                "root_iid": None,
            })
        self.update_queue_display()
        self._update_progress_idle()

    @staticmethod
    def _normalize_path(item):
        if item is None:
            return None
        if isinstance(item, str) and item.strip():
            return item.strip()
        if isinstance(item, dict):
            p = item.get("path") or item.get("full_path")
            if p and isinstance(p, str):
                return p.strip()
        return None

    @staticmethod
    def _path_to_filename(x):
        if x is None:
            return ""
        if isinstance(x, str):
            return os.path.basename(x)
        if isinstance(x, dict):
            return x.get("filename") or os.path.basename(x.get("path") or x.get("full_path") or "")
        return ""

    def _get_queue_totals(self):
        """Vrátí (počet PDF souborů, počet složek) – okamžitý předpočet z fronty."""
        n_files = len(self.queue_display)
        n_folders = sum(1 for t in self.tasks if t.get("type") == "folder")
        return n_files, n_folders

    def _update_progress_idle(self):
        """Pre-flight: Vybráno X souborů v Y složkách | Předpokládaný čas ~MM:SS."""
        if self.is_running:
            return
        n_files, n_folders = self._get_queue_totals()
        checked = len([q for q in self.queue_display if q.get("checked", True)])
        processed = len([q for q in self.queue_display if q.get("result")])
        sent = len([q for q in self.queue_display if q.get("sent")])
        new_count = n_files - processed
        if n_files > 0:
            self._progress_row.grid()
            eta_sec = checked * SECONDS_PER_FILE_ETA
            mm, ss = int(eta_sec // 60), int(eta_sec % 60)
            eta_str = f"{mm}:{ss:02d}" if mm > 0 else f"0:{ss:02d}"
            stav = f"Nové: {new_count} | Zpracované: {processed} | Odeslané: {sent}"
            self.progress_label.configure(
                text=f"Vybráno: {checked} souborů v {n_folders} složkách | {stav} | Předpokládaný čas: ~{eta_str}",
                text_color=TEXT_MUTED,
            )
            self.eta_label.configure(text="")
            self._progress_speed_label.configure(text="")
            self.progress.set(0)
        else:
            self._progress_row.grid_remove()

    def add_path_to_queue(self, path):
        path = self._normalize_path(path)
        if not path:
            return
        if os.path.isdir(path):
            from pdf_checker import find_all_pdfs
            pdfs = find_all_pdfs(path)
            if pdfs:
                name = os.path.basename(path)
                file_paths = []
                for fp in pdfs:
                    p = (fp.get("full_path") or fp.get("path")) if isinstance(fp, dict) else (fp if isinstance(fp, str) else None)
                    if not p:
                        continue
                    file_paths.append(p)
                    self.queue_display.append({"path": p, "filename": (fp.get("filename") or os.path.basename(p)) if isinstance(fp, dict) else os.path.basename(p), "status": "pending", "result": None, "checked": True})
                if file_paths:
                    self.tasks.append({"type": "folder", "path": path, "name": name, "file_paths": file_paths})
        elif path.lower().endswith(".pdf"):
            name = os.path.basename(path)
            self.tasks.append({"type": "file", "path": path, "name": name, "file_paths": [path]})
            self.queue_display.append({"path": path, "filename": name, "status": "pending", "result": None, "checked": True})

    def add_files(self):
        files = filedialog.askopenfilenames(title="Vyberte PDF", filetypes=[("PDF", "*.pdf")])
        start = len(self.queue_display)
        for f in files:
            self.add_path_to_queue(f)
        if len(self.queue_display) > start:
            self.batches.append({
                "label": "Dávka - " + time.strftime("%d.%m. %H:%M"),
                "qidx_start": start,
                "qidx_end": len(self.queue_display),
                "root_iid": None,
            })
        self.update_queue_display()
        self._update_progress_idle()

    def add_folder(self):
        folder = filedialog.askdirectory(title="Vyberte složku s PDF")
        if folder:
            start = len(self.queue_display)
            self.add_path_to_queue(folder)
            if len(self.queue_display) > start:
                self.batches.append({
                    "label": "Dávka - " + time.strftime("%d.%m. %H:%M"),
                    "qidx_start": start,
                    "qidx_end": len(self.queue_display),
                    "root_iid": None,
                })
            self.update_queue_display()
            self._update_progress_idle()

    def clear_queue(self):
        """Jediné místo, kde smí být voláno tree.delete – VYMAZAT VŠE."""
        self.tasks = []
        self.queue_display = []
        self.batches = []
        for iid in self.queue_tree.get_children(""):
            self.queue_tree.delete(iid)
        self._tree_iid_to_qidx.clear()
        self._tree_iid_to_task_ix.clear()
        self._qidx_to_tree_iid.clear()
        self._update_stats()
        self._show_session_summary()
        self._update_progress_idle()

    def _badge_text(self, item):
        """Vrátí (text pro pilulku, barva). Pilulky: ✓ zelená / ✗ červená."""
        r = item.get("result")
        if not r or not isinstance(r, dict):
            return "…", TEXT_MUTED
        if r.get("skipped"):
            return "…", TEXT_MUTED
        if r.get("success"):
            return "✓", SUCCESS
        return "✗", ERROR

    def _item_passes_filter(self, item):
        if self._queue_filter == "all":
            return True
        if self._queue_filter == "errors":
            r = item.get("result")
            return r and isinstance(r, dict) and not r.get("success") and not r.get("skipped")
        if self._queue_filter == "pdfa_ok":
            r = item.get("result")
            if not r or not isinstance(r, dict):
                return False
            return (r.get("results") or {}).get("pdf_format", {}).get("is_pdf_a3") is True
        return True

    def _on_queue_filter(self, value):
        if value == "Vše":
            self._queue_filter = "all"
        elif value == "Chyby":
            self._queue_filter = "errors"
        elif value == "PDF/A-3 OK":
            self._queue_filter = "pdfa_ok"
        self.update_queue_display()

    def _tree_expand_all(self):
        def _expand(iid):
            self.queue_tree.item(iid, open=True)
            for c in self.queue_tree.get_children(iid):
                _expand(c)
        for iid in self.queue_tree.get_children(""):
            _expand(iid)

    def _tree_collapse_all(self):
        def _collapse(iid):
            for c in self.queue_tree.get_children(iid):
                _collapse(c)
            self.queue_tree.item(iid, open=False)
        for iid in self.queue_tree.get_children(""):
            _collapse(iid)

    def _on_tree_select(self, event):
        sel = self.queue_tree.selection()
        if not sel:
            return
        iid = sel[0]
        qidx = self._tree_iid_to_qidx.get(iid)
        if qidx is not None:
            self._select_item(qidx)

    def _collect_file_qindices_under(self, parent_iid):
        """Rekurzivně vrátí set qidx všech souborů pod daným uzlem (složka/dávka)."""
        out = set()
        for c in self.queue_tree.get_children(parent_iid):
            qidx = self._tree_iid_to_qidx.get(c)
            if qidx is not None:
                out.add(qidx)
            else:
                out.update(self._collect_file_qindices_under(c))
        return out

    def _on_tree_click(self, event):
        region = self.queue_tree.identify_region(event.x, event.y)
        if region != "cell" and region != "tree":
            return
        iid = self.queue_tree.identify_row(event.y)
        if not iid:
            return
        qidx = self._tree_iid_to_qidx.get(iid)
        if qidx is not None:
            self._toggle_checked(qidx)
            return
        iid_str = str(iid) if iid else ""
        if iid_str.startswith("path-") or iid_str.startswith("batch-"):
            qindices = self._collect_file_qindices_under(iid)
            if not qindices:
                return
            items = [self.queue_display[i] for i in qindices if 0 <= i < len(self.queue_display)]
            all_checked = all(item.get("checked", True) for item in items)
            new_val = not all_checked
            for i in qindices:
                if 0 <= i < len(self.queue_display):
                    self.queue_display[i]["checked"] = new_val
            for i in qindices:
                fiid = self._qidx_to_tree_iid.get(i)
                if fiid and self.queue_tree.exists(fiid):
                    chk = "☑" if new_val else "☐"
                    name = self.queue_display[i].get("filename", "")
                    self.queue_tree.item(fiid, text=f"{chk}  📄 {name}")
            self._update_stats()
            if not self.is_running:
                self._update_progress_idle()
            return

    def _get_remote_config(self):
        """Vrátí slovník z serveru (disclaimer, vop_link, update_msg) nebo výchozí."""
        if callable(getattr(self, "on_get_remote_config", None)):
            try:
                return self.on_get_remote_config() or {}
            except Exception:
                pass
        return {"disclaimer": "Výsledek je informativní. Za správnost odpovídá projektant.", "vop_link": "https://www.dokucheck.cz/vop", "update_msg": "Používáte aktuální verzi."}

    def _get_legal_config(self):
        """Vrátí právní konfiguraci (disclaimer, vop_url, gdpr_url) z fetch_legal_config() nebo výchozí."""
        if callable(getattr(self, "on_get_legal_config", None)):
            try:
                return self.on_get_legal_config() or {}
            except Exception:
                pass
        return {
            "disclaimer": "Výsledek kontroly je informativní. Za finální správnost dokumentace odpovídá autorizovaná osoba dle platných norem.",
"vop_url": "https://www.dokucheck.cz/vop",
                "gdpr_url": "https://www.dokucheck.cz/gdpr",
        }

    def _show_about(self):
        """O programu – styl PDF-XChange: záhlaví (logo, verze), popis, právní doložka, komponenty, spodní banner. Modální."""
        from datetime import datetime
        top = ctk.CTkToplevel(self.root)
        top.title("O programu DokuCheck PRO")
        top.geometry("650x500")
        top.configure(fg_color=BG_APP)
        top.transient(self.root)
        top.grab_set()
        top.resizable(False, False)
        TEXT_MAIN = TEXT

        def _center_on_app():
            top.update_idletasks()
            w, h = 650, 500
            rx = self.root.winfo_x()
            ry = self.root.winfo_y()
            rw = self.root.winfo_width()
            rh = self.root.winfo_height()
            if rw > 1 and rh > 1:
                x = rx + (rw - w) // 2
                y = ry + (rh - h) // 2
            else:
                x = (top.winfo_screenwidth() - w) // 2
                y = (top.winfo_screenheight() - h) // 2
            top.geometry(f"{w}x{h}+{max(0, x)}+{max(0, y)}")
        top.after(50, _center_on_app)

        main = ctk.CTkFrame(top, fg_color=BG_APP)
        main.pack(fill=tk.BOTH, expand=True, padx=12, pady=12)

        # —— 1. Záhlaví: logo vlevo, název + verze + datum vpravo ——
        header = ctk.CTkFrame(main, fg_color="transparent")
        header.pack(fill=tk.X, pady=(0, 12))
        if os.path.isfile(LOGO_PATH):
            try:
                logo_img = ctk.CTkImage(light_image=LOGO_PATH, dark_image=LOGO_PATH, size=(140, 72))
                ctk.CTkLabel(header, text="", image=logo_img).pack(side=tk.LEFT, padx=(0, 20))
            except Exception:
                pass
        header_right = ctk.CTkFrame(header, fg_color="transparent")
        header_right.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        ctk.CTkLabel(header_right, text="DokuCheck PRO", font=(FONT_STACK[0], FS_20, "bold"), text_color=TEXT_MAIN).pack(anchor=tk.W)
        ctk.CTkLabel(header_right, text=f"Verze: {AGENT_VERSION} (Enterprise Edition)", font=(FONT_STACK[0], FS_12), text_color=TEXT_MAIN).pack(anchor=tk.W)

        # —— 2. Střed: účel aplikace ——
        desc = (
            "Automatizovaná kontrola PDF/A-3, autorizací a razítek pro Portál stavebníka. "
            "Aplikace zajišťuje integritu souborů, kontrolu metadat a soulad se standardy pro digitální podání. "
            "Soubory zůstávají na vašem disku, na server odcházejí pouze nezbytná metadata."
        )
        ctk.CTkLabel(main, text=desc, font=(FONT_STACK[0], FS_12), text_color=TEXT_MAIN, justify=tk.LEFT, wraplength=610).pack(anchor=tk.W, pady=(0, 8))
        info_row = ctk.CTkFrame(main, fg_color="transparent")
        info_row.pack(fill=tk.X, pady=(0, 12))
        ctk.CTkLabel(info_row, text="Více informací o tomto produktu a našich dalších službách naleznete na webu ", font=(FONT_STACK[0], FS_12), text_color=TEXT_MAIN).pack(side=tk.LEFT)
        link_style = (FONT_STACK[0], FS_12)
        b_web = ctk.CTkButton(info_row, text="www.dokucheck.cz", command=lambda: webbrowser.open("https://www.dokucheck.cz"), font=link_style, fg_color="transparent", text_color=ACCENT)
        b_web.pack(side=tk.LEFT)
        ctk.CTkLabel(info_row, text=" nebo e-mailová podpora ", font=(FONT_STACK[0], FS_12), text_color=TEXT_MAIN).pack(side=tk.LEFT)
        b_mail = ctk.CTkButton(info_row, text="podpora@dokucheck.cz", command=lambda: webbrowser.open("mailto:podpora@dokucheck.cz"), font=link_style, fg_color="transparent", text_color=ACCENT)
        b_mail.pack(side=tk.LEFT)
        ctk.CTkLabel(info_row, text=".", font=(FONT_STACK[0], FS_12), text_color=TEXT_MAIN).pack(side=tk.LEFT)

        # —— 3. Právní doložka a scrollable technologie ——
        ctk.CTkLabel(main, text="Copyright © 2026 Ing. Martin Cieślar. Všechna práva vyhrazena.", font=(FONT_STACK[0], FS_12), text_color=TEXT_MAIN).pack(anchor=tk.W, pady=(0, 6))
        components = (
            "Python 3.12\n"
            "PyMuPDF / MuPDF\n"
            "CustomTkinter"
        )
        comp_text = ctk.CTkTextbox(main, font=(FONT_STACK[0], 10), fg_color=BG_CARD, text_color=TEXT_MUTED, height=72, wrap="word")
        comp_text.pack(fill=tk.X, pady=(0, 12))
        comp_text.insert("1.0", components)
        comp_text.configure(state="disabled")

        # —— 4. Spodní banner ——
        banner = ctk.CTkFrame(main, fg_color=BORDER, corner_radius=6)
        banner.pack(fill=tk.X, side=tk.BOTTOM, pady=(12, 0))
        banner_inner = ctk.CTkFrame(banner, fg_color="transparent")
        banner_inner.pack(fill=tk.X, padx=12, pady=10)
        ctk.CTkLabel(banner_inner, text="Software pro kontrolu, validaci a přípravu inženýrské dokumentace.", font=(FONT_STACK[0], FS_12), text_color=TEXT_MAIN).pack(side=tk.LEFT)
        ctk.CTkLabel(banner_inner, text="CIESLAR Group", font=(FONT_STACK[0], 10), text_color=TEXT_MUTED).pack(side=tk.RIGHT)

        ctk.CTkButton(top, text="Zavřít", command=lambda: (top.grab_release(), top.destroy()), font=(FONT_STACK[0], FS_12), width=100, fg_color=ACCENT).pack(pady=(0, 12))
        top.protocol("WM_DELETE_WINDOW", lambda: (top.grab_release(), top.destroy()))

    def _show_help_modal(self):
        """Nápověda – terminologie: serverová / cloudová kontrola + disclaimer a VOP ze serveru."""
        dialog = ctk.CTkToplevel(self.root)
        dialog.title("Nápověda")
        dialog.geometry("420x320")
        dialog.configure(fg_color=BG_CARD)
        dialog.transient(self.root)
        ctk.CTkLabel(dialog, text="Nápověda", font=(FONT_STACK[0], FS_16, "bold"), text_color=TEXT).pack(pady=(14, 8))
        help_text = (
            "Kontroly v tomto režimu jsou serverová / cloudová kontrola.\n\n"
            "1. Přidejte PDF (soubory nebo složku)\n"
            "2. Zaškrtněte položky ke kontrole\n"
            "3. Klikněte na „Analyzovat PDF“ (lokální kontrola)\n"
            "4. Po dokončení můžete kliknout na „Odeslat metadata na server“\n\n"
            "Bezpečnost: V režimu Agent jsou na server odesílána pouze technická metadata "
            "o struktuře PDF a elektronických podpisech. Samotný obsah vašich výkresů a dokumentů "
            "nikdy neopouští váš počítač."
        )
        lbl = ctk.CTkLabel(dialog, text=help_text, font=(FONT_STACK[0], FS_12), text_color=TEXT_MUTED, justify=tk.LEFT, wraplength=380)
        lbl.pack(padx=20, pady=(0, 8), fill=tk.BOTH, expand=True)
        rc = self._get_remote_config()
        ctk.CTkLabel(dialog, text=rc.get("disclaimer", "Výsledek je informativní."), font=(FONT_STACK[0], FS_12 - 1), text_color=TEXT_MUTED, justify=tk.LEFT, wraplength=380).pack(padx=20, pady=(0, 4), anchor="w")
        vop = rc.get("vop_link", "")
        if vop:
            ctk.CTkButton(dialog, text="VOP (obchodní podmínky)", command=lambda: webbrowser.open(vop), font=(FONT_STACK[0], FS_12 - 1), fg_color="transparent", text_color=ACCENT).pack(pady=(0, 8))
        ctk.CTkButton(dialog, text="Zavřít", command=dialog.destroy, font=(FONT_STACK[0], FS_12), width=100).pack(pady=(0, 14))

    def _root_for_qidx(self, qidx):
        """Vrátí kořenovou cestu (složku výběru) pro daný qidx – od ní se zobrazuje strom níže."""
        qidx_start = 0
        for task in self.tasks:
            file_paths = task.get("file_paths", [])
            if not file_paths:
                continue
            if qidx_start <= qidx < qidx_start + len(file_paths):
                if task.get("type") == "folder":
                    return (task.get("path") or "").strip()
                return (os.path.dirname(file_paths[0]) or "").strip()
            qidx_start += len(file_paths)
        return ""

    def _path_to_folder_prefixes(self, path, root):
        """Z cesty souboru vrátí relativní prefixy složek vůči root (od vybrané složky níže)."""
        if not path or not path.strip():
            return []
        full = os.path.normpath(path).replace("\\", "/")
        root_n = (os.path.normpath(root).replace("\\", "/").rstrip("/") + "/") if root else ""
        if root_n and not full.startswith(root_n):
            rel = full
        else:
            rel = full[len(root_n):] if root_n else full
        rel = rel.lstrip("/")
        dirname = os.path.dirname(rel)
        if not dirname:
            return []
        parts = [p for p in dirname.replace("\\", "/").split("/") if p]
        if not parts:
            return []
        return ["/".join(parts[:i]) for i in range(1, len(parts) + 1)]

    def _append_to_tree(self, batch):
        """Přidá jednu dávku do stromu bez mazání: kořen 📦 Dávka - [čas], pod ním hloubková struktura složek a souborů."""
        root_iid = batch.get("root_iid")
        if root_iid and self.queue_tree.exists(root_iid):
            return
        qidx_start = batch["qidx_start"]
        qidx_end = batch["qidx_end"]
        root_iid = "batch-%d-%d" % (qidx_start, qidx_end)
        batch["root_iid"] = root_iid
        self.queue_tree.insert("", "end", iid=root_iid, text="📦 " + batch["label"], values=("",))
        self._tree_iid_to_task_ix[root_iid] = None

        path_to_iid = {}  # relativní prefix (v rámci dávky) -> iid, aby se složky neduplikovaly
        for qidx in range(qidx_start, qidx_end):
            item = self.queue_display[qidx]
            path = item.get("path") or ""
            if not path:
                continue
            root = self._root_for_qidx(qidx)
            full = os.path.normpath(path).replace("\\", "/")
            root_n = (os.path.normpath(root).replace("\\", "/").rstrip("/") + "/") if root else ""
            if root_n and full.startswith(root_n):
                rel = full[len(root_n):].lstrip("/")
            else:
                rel = full
            dirname = os.path.dirname(rel)
            for prefix in self._path_to_folder_prefixes(path, root):
                if prefix in path_to_iid:
                    continue
                parts = [p for p in prefix.split("/") if p]
                parent_prefix = "/".join(parts[:-1]) if len(parts) > 1 else None
                parent_iid = path_to_iid.get(parent_prefix, root_iid) if parent_prefix else root_iid
                safe = (root_iid + "-" + prefix).replace("/", "_").replace(":", "_").replace("\\", "_")
                folder_iid = "path-" + safe
                path_to_iid[prefix] = folder_iid
                display_name = parts[-1] if parts else prefix
                self.queue_tree.insert(parent_iid, "end", iid=folder_iid, text="📁 " + display_name, values=("",))
            parent_iid = path_to_iid.get(dirname, root_iid) if dirname else root_iid
            chk = "☑" if item.get("checked", True) else "☐"
            badge_text, _ = self._badge_text(item)
            display_name = "%s  📄 %s" % (chk, item.get("filename", ""))
            file_iid = "file-%d" % qidx
            self.queue_tree.insert(parent_iid, "end", iid=file_iid, text=display_name, values=(badge_text,))
            self._tree_iid_to_qidx[file_iid] = qidx
            self._qidx_to_tree_iid[qidx] = file_iid
            if badge_text == "✓":
                self.queue_tree.item(file_iid, tags=("ok",))
            elif badge_text == "✗":
                self.queue_tree.item(file_iid, tags=("error",))
            else:
                self.queue_tree.item(file_iid, tags=("pending",))

        def _expand(iid):
            self.queue_tree.item(iid, open=True)
            for c in self.queue_tree.get_children(iid):
                _expand(c)
        _expand(root_iid)

    def update_queue_display(self):
        """Žádné mazání stromu – pouze přidání nových dávkových uzlů a aktualizace textu/tagů u existujících."""
        for batch in self.batches:
            self._append_to_tree(batch)
        for qidx, item in enumerate(self.queue_display):
            file_iid = self._qidx_to_tree_iid.get(qidx)
            if not file_iid or not self.queue_tree.exists(file_iid):
                continue
            chk = "☑" if item.get("checked", True) else "☐"
            badge_text, _ = self._badge_text(item)
            name = item.get("filename", "")
            self.queue_tree.item(file_iid, text="%s  📄 %s" % (chk, name), values=(badge_text,))
            if badge_text == "✓":
                self.queue_tree.item(file_iid, tags=("ok",))
            elif badge_text == "✗":
                self.queue_tree.item(file_iid, tags=("error",))
            else:
                self.queue_tree.item(file_iid, tags=("pending",))
        self._queue_tree_style.configure(
            "Queue.Treeview",
            rowheight=TREE_ROWHEIGHT,
            background=TREEVIEW_BG,
            foreground=TREEVIEW_FG,
            fieldbackground=TREEVIEW_BG,
        )
        self._queue_tree_style.map(
            "Queue.Treeview",
            foreground=[("selected", TREEVIEW_FG), ("!selected", TREEVIEW_FG)],
            background=[("selected", BORDER), ("!selected", TREEVIEW_BG)],
            fieldbackground=[("selected", BORDER), ("!selected", TREEVIEW_BG)],
        )
        if getattr(self, "_dnd_hint_label", None):
            if not self.queue_display:
                self._dnd_hint_label.place(relx=0.5, rely=0.5, anchor=tk.CENTER)
            else:
                self._dnd_hint_label.place_forget()
        self._update_stats()
        if not self.is_running:
            self._update_progress_idle()

    def _toggle_checked(self, qidx):
        if 0 <= qidx < len(self.queue_display):
            self.queue_display[qidx]["checked"] = not self.queue_display[qidx].get("checked", True)
            iid = self._qidx_to_tree_iid.get(qidx)
            if iid and self.queue_tree.exists(iid):
                chk = "☑" if self.queue_display[qidx].get("checked", True) else "☐"
                name = self.queue_display[qidx].get("filename", "")
                self.queue_tree.item(iid, text=f"{chk}  📄 {name}")
            else:
                self.update_queue_display()

    def _select_item(self, qidx):
        if 0 <= qidx < len(self.queue_display):
            self.selected_qidx = qidx
            self.detail_text.configure(state="normal")
            self.detail_text.delete("0.0", "end")
            self.detail_text.insert("0.0", NO_DETAIL_MSG)
            self.detail_text.configure(state="disabled")

    def remove_checked_from_queue(self):
        """Odebere z fronty všechny zaškrtnuté položky."""
        to_remove = set()
        for qidx, item in enumerate(self.queue_display):
            if item.get("checked", True):
                to_remove.add(item.get("path"))
        if not to_remove:
            self.show_message("Žádné zaškrtnuté položky k odebrání.")
            return
        self._remove_paths_from_queue(to_remove)

    def remove_selected_from_queue(self):
        """Odebere z fronty aktuálně vybranou položku."""
        if self.selected_qidx is None:
            self.show_message("Nejdříve vyberte položku (klikněte na řádek).")
            return
        if 0 <= self.selected_qidx < len(self.queue_display):
            path = self.queue_display[self.selected_qidx].get("path")
            if path:
                self._remove_paths_from_queue({path})
        self.selected_qidx = None

    def _remove_folder_by_index(self, task_ix):
        """Odebere celou složku (úlohu) z fronty."""
        if 0 <= task_ix < len(self.tasks):
            task = self.tasks[task_ix]
            paths = set(task.get("file_paths", []))
            if paths:
                self._remove_paths_from_queue(paths)
        self.selected_qidx = None

    def remove_folder_of_selected(self):
        """Odebere z fronty celou složku, do které patří vybraná položka."""
        if self.selected_qidx is None:
            self.show_message("Nejdříve vyberte položku ve složce, kterou chcete odebrat.")
            return
        for task_ix, task in enumerate(self.tasks):
            file_paths = task.get("file_paths", [])
            qidx_start = sum(len(self.tasks[i].get("file_paths", [])) for i in range(task_ix))
            if qidx_start <= self.selected_qidx < qidx_start + len(file_paths):
                self._remove_folder_by_index(task_ix)
                return
        self.selected_qidx = None

    def _remove_paths_from_queue(self, paths_to_remove):
        """Odstraní z tasks a queue_display všechny položky s path v paths_to_remove."""
        paths_to_remove = set(paths_to_remove)
        new_tasks = []
        new_queue_display = []
        for task in self.tasks:
            kept_paths = [p for p in task.get("file_paths", []) if p not in paths_to_remove]
            if not kept_paths:
                continue
            for p in kept_paths:
                item = next((q for q in self.queue_display if q.get("path") == p), None)
                if item is not None:
                    new_queue_display.append(item)
            new_tasks.append({**task, "file_paths": kept_paths})
        self.tasks = new_tasks
        self.queue_display = new_queue_display
        self.batches = []  # po změně obsahu fronty jsou qidx neplatné
        self.selected_qidx = None
        self.update_queue_display()
        self._show_session_summary()

    def _show_session_summary(self):
        self.detail_text.configure(state="normal")
        self.detail_text.delete("0.0", "end")
        self.detail_text.insert("0.0", _session_summary_text(self.tasks, self.queue_display, self.session_files_checked))
        self.detail_text.configure(state="disabled")

    def _update_stats(self):
        total = len([q for q in self.queue_display if q.get("status") not in ("pending", None)])
        ok = len([q for q in self.queue_display if q.get("status") == "success"])
        pct = int(round(100 * ok / total)) if total else 0
        errs = sum(_count_errors_from_result(q.get("result")) for q in self.queue_display)
        pdfa_ok = sum(1 for q in self.queue_display if q.get("result") and isinstance(q.get("result"), dict) and (q.get("result").get("results") or {}).get("pdf_format", {}).get("is_pdf_a3"))
        self.metric_dnes.configure(text=f"Dnes: {self.session_files_checked}")
        self.metric_ok.configure(text=f"Úspěšnost: {pct}%" if total else "Úspěšnost: —")
        self.metric_chyby.configure(text=f"Chyby: {errs}")
        self.metric_pdfa.configure(text=f"PDF/A-3 OK: {pdfa_ok}")

    def on_check_clicked(self):
        if self.on_has_login and callable(self.on_has_login) and not self.on_has_login():
            self.show_message("Pro analýzu a odeslání na server se nejprve přihlaste („Vyzkoušet zdarma“ nebo e-mail v sidebaru).", msg_type="warning")
            return
        checked = [(q["path"], i) for i, q in enumerate(self.queue_display) if q.get("checked")]
        if not checked:
            self.show_message("Přidejte a zaškrtněte položky ke kontrole.", msg_type="warning")
            return
        if self.is_running:
            return
        self.cancel_requested = False
        self.is_running = True
        self.show_progress()
        threading.Thread(target=self._check_thread, args=(checked,), daemon=True).start()

    def _check_thread(self, checked_paths_qidx):
        import time
        try:
            max_files = 99999
            if self.on_get_max_files:
                try:
                    max_files = self.on_get_max_files()
                except Exception:
                    max_files = 5
            if max_files < 0:
                max_files = 99999
            all_results = []
            source_folder_for_batch = None

            if max_files < 99999:
                # Limitovaný účet (trial/zdarma): analyzovat jen prvních max_files souborů po jednom
                to_process = checked_paths_qidx[:max_files]
                total_files_to_process = len(to_process)
                for path, qidx in to_process:
                    if self.cancel_requested:
                        break
                    processed = len(all_results)
                    self.root.after(0, lambda c=processed + 1, t=total_files_to_process, f=os.path.basename(path): self.update_progress(c, t, f))
                    result = self.on_check_callback(path, mode="single", auto_send=False)
                    all_results.append((qidx, result))
                if all_results and to_process:
                    source_folder_for_batch = os.path.dirname(to_process[0][0])
            else:
                # Neomezený účet: složky po složce, soubory po jednom
                task_checked = []
                qidx_used = set()
                for path, qidx in checked_paths_qidx:
                    if qidx in qidx_used:
                        continue
                    for task_ix, task in enumerate(self.tasks):
                        file_paths = task.get("file_paths", [])
                        if not file_paths:
                            continue
                        qidx_start = sum(len(self.tasks[i].get("file_paths", [])) for i in range(task_ix))
                        if qidx_start <= qidx < qidx_start + len(file_paths):
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
                total_files_to_process = min(sum(len(items) for _, _, items in task_checked), max_files)
                processed = 0
                for task_ix, task, items in task_checked:
                    if self.cancel_requested or processed >= max_files:
                        break
                    is_folder = task.get("type") == "folder"
                    task_path = task.get("path", "")
                    if is_folder and task_path:
                        self.root.after(0, lambda p=processed, t=total_files_to_process: self.update_progress(p, t, os.path.basename(task_path)))
                        folder_result = self.on_check_callback(task_path, mode="folder", auto_send=False)
                        results_list = folder_result.get("results", []) if isinstance(folder_result, dict) else []
                        qidx_start = sum(len(self.tasks[i].get("file_paths", [])) for i in range(task_ix))
                        checked_qidx_in_task = {q for _, q in items}
                        for j, res in enumerate(results_list):
                            if processed >= max_files:
                                break
                            qidx = qidx_start + j
                            if qidx in checked_qidx_in_task:
                                all_results.append((qidx, res))
                                processed += 1
                        if all_results and source_folder_for_batch is None:
                            source_folder_for_batch = task_path
                    else:
                        for path, qidx in items:
                            if self.cancel_requested or processed >= max_files:
                                break
                            processed += 1
                            self.root.after(0, lambda c=processed, t=total_files_to_process, f=os.path.basename(path): self.update_progress(c, t, f))
                            result = self.on_check_callback(path, mode="single", auto_send=False)
                            all_results.append((qidx, result))

            if not all_results:
                self.root.after(0, lambda: self.display_error("Žádné PDF ke kontrole."))
            else:
                self.root.after(0, lambda: self.display_results({
                    "results_with_qidx": all_results,
                    "response_data": None,
                    "upload_error": None,
                    "source_folder_for_batch": source_folder_for_batch,
                }))
        except Exception as e:
            self.root.after(0, lambda: self.display_error(str(e)))
        finally:
            self.root.after(0, self.finish_progress)

    def cancel_check(self):
        self.cancel_requested = True
        self.progress_label.configure(text="Ruším…", text_color=WARNING)

    def _on_send_metadata_clicked(self):
        """Tlačítko „Odeslat metadata na server“ – zobrazí se po dokončení lokální analýzy."""
        if self._last_display_result:
            self._on_send_confirm(True, self._last_display_result)
            self.send_btn.pack_forget()
            self._last_display_result = None

    def show_progress(self):
        import time
        self.start_time = time.time()
        self.progress.set(0)
        total = len([q for q in self.queue_display if q.get("checked")])
        self.progress_label.configure(text=f"Zpracováno: 0/{total} | Zbývá: --:-- (ETA) | Rychlost: — soub/s", text_color=ACCENT)
        self.eta_label.configure(text="")
        self._progress_speed_label.configure(text="")
        self._progress_row.grid()
        self.cancel_btn.pack(side=tk.RIGHT, padx=6)
        self.check_btn.configure(state="disabled")
        if getattr(self, "send_btn", None):
            self.send_btn.pack_forget()

    def finish_progress(self):
        self.is_running = False
        self.progress.set(1)
        self.progress_label.configure(text="Hotovo." if not self.cancel_requested else "Zrušeno", text_color=SUCCESS if not self.cancel_requested else WARNING)
        self.eta_label.configure(text="")
        self._progress_speed_label.configure(text="")
        self.cancel_btn.pack_forget()
        self.check_btn.configure(state="normal")
        def _hide_or_idle():
            if self.tasks and not self.is_running:
                self._update_progress_idle()
            else:
                self._progress_row.grid_remove()
        self.root.after(2500, _hide_or_idle)

    def update_progress(self, current, total, filename):
        import time
        if self.cancel_requested:
            return
        if total > 0:
            self.progress.set(current / total)
            remaining = total - current
            if current > 0 and self.start_time:
                elapsed = time.time() - self.start_time
                eta_seconds = elapsed / current * remaining
                speed = current / elapsed if elapsed > 0 else 0
                speed_str = f"{speed:.1f}"
            else:
                eta_seconds = remaining * SECONDS_PER_FILE_ETA
                speed_str = "—"
            mm, ss = int(eta_seconds // 60), int(eta_seconds % 60)
            self.progress_label.configure(
                text=f"Zpracováno: {current}/{total} | Zbývá: {mm:02d}:{ss:02d} (ETA) | Rychlost: {speed_str} soub/s",
                text_color=ACCENT,
            )
            self.eta_label.configure(text="")
            self._progress_speed_label.configure(text="")
        self.root.update_idletasks()

    def display_results(self, result):
        import time
        results_with_qidx = result.get("results_with_qidx", [])
        for qidx, res in results_with_qidx:
            if 0 <= qidx < len(self.queue_display):
                self.queue_display[qidx]["result"] = res
                self.queue_display[qidx]["status"] = "success" if res.get("success") else "error"
                self.queue_display[qidx]["checked"] = not res.get("success")
        self.update_queue_display()
        self._update_stats()
        success_count = sum(1 for _, r in results_with_qidx if r.get("success"))
        self.session_files_checked += success_count
        total_time = time.time() - self.start_time if self.start_time else 0
        time_str = f"{int(total_time)}s" if total_time < 60 else f"{int(total_time / 60)}m {int(total_time % 60)}s"
        self.detail_text.configure(state="normal")
        self.detail_text.delete("0.0", "end")
        self.detail_text.configure(state="disabled")
        upload_error = result.get("upload_error")
        can_send = self.on_has_login and callable(self.on_has_login) and self.on_has_login()
        if can_send and self.on_send_batch_callback and results_with_qidx:
            self.detail_text.configure(state="normal")
            self.detail_text.insert("0.0", f"Hotovo: {success_count} souborů | Čas: {time_str}\n\nKlikněte na „Odeslat metadata na server“ pro odeslání výsledků do portálu.")
            self.detail_text.configure(state="disabled")
            self._last_display_result = result
            self.send_btn.pack(side=tk.RIGHT, padx=4, pady=6)
            return
        self.detail_text.configure(state="normal")
        self.detail_text.insert("0.0", f"Hotovo: {success_count} souborů | Čas: {time_str}\n\n" + (
            "Klikněte na „Odeslat metadata na server“ pro odeslání výsledků do portálu." if can_send else
            "Pro odeslání na server se přihlaste („Vyzkoušet zdarma“ nebo e-mail v sidebaru)."
        ))
        self.detail_text.configure(state="disabled")
        if upload_error and ("limit" in upload_error.lower() or "vyčerpán" in upload_error.lower()):
            self.show_message(upload_error, msg_type="warning")

    def _on_send_confirm(self, send_yes, result):
        """Callback po kliknutí Ano/Ne u odeslání na server."""
        self.clear_message()
        results_with_qidx = result.get("results_with_qidx", [])
        upload_error = result.get("upload_error")
        if send_yes and results_with_qidx and self.on_send_batch_callback:
            try:
                results_only = [r for _, r in results_with_qidx]
                out = self.on_send_batch_callback(results_only, result.get("source_folder_for_batch"))
                if out and len(out) >= 2 and not out[0]:
                    upload_error = out[1]
                elif out and len(out) >= 1 and out[0]:
                    for qidx, _ in results_with_qidx:
                        if 0 <= qidx < len(self.queue_display):
                            self.queue_display[qidx]["sent"] = True
                    if not self.is_running:
                        self._update_progress_idle()
            except Exception as e:
                upload_error = str(e)
            self._open_web()
        if upload_error and ("limit" in upload_error.lower() or "vyčerpán" in upload_error.lower()):
            self.show_message(upload_error, msg_type="warning")

    def display_error(self, msg):
        self.detail_text.configure(state="normal")
        self.detail_text.delete("0.0", "end")
        self.detail_text.insert("0.0", f"CHYBA:\n{msg}")
        self.detail_text.configure(state="disabled")

    def set_export_xls_enabled(self, enabled):
        pass

    def set_daily_limit_display(self, used, limit):
        if limit is None or (isinstance(limit, int) and limit < 0):
            self.sidebar_daily_limit.configure(text="Limit: neomezeno")
        else:
            self.sidebar_daily_limit.configure(text=f"Limit: {used or 0}/{limit}")

    def _update_analyze_send_state(self):
        """Zapne nebo vypne „Analyzovat PDF“ podle toho, zda je uživatel přihlášen (Vyzkoušet zdarma nebo e-mail)."""
        can = self.on_has_login() if (self.on_has_login and callable(self.on_has_login)) else True
        if getattr(self, "check_btn", None):
            self.check_btn.configure(state=tk.NORMAL if can else tk.DISABLED)
            if not can:
                self.send_btn.pack_forget()

    def set_license_display(self, text):
        self.sidebar_account.configure(text=text or "Nepřihlášen", text_color=TEXT if text else TEXT_MUTED)
        if text:
            self._login_frame.pack_forget()
            self._account_frame.pack(fill=tk.X, pady=(0, 4))
            self.logout_btn.pack(pady=2, padx=12, fill=tk.X)
        else:
            self._account_frame.pack_forget()
            self._login_frame.pack(fill=tk.X, pady=(0, 4))
            self.logout_btn.pack_forget()
        self._update_analyze_send_state()

    def clear_results_and_queue(self):
        self.tasks = []
        self.queue_display = []
        self.session_files_checked = 0
        self.update_queue_display()
        self._show_session_summary()

    def open_web_after_check(self):
        self._open_web()

    def _do_logout(self):
        if getattr(self, "on_after_logout_callback", None):
            self.on_after_logout_callback()
        if self.on_logout_callback:
            self.on_logout_callback()

    def show_api_key_dialog(self):
        dialog = ctk.CTkToplevel(self.root)
        dialog.title("Přihlášení")
        dialog.geometry("400x320")
        dialog.configure(fg_color=BG_CARD)
        dialog.transient(self.root)
        dialog.grab_set()
        ctk.CTkLabel(dialog, text="Přihlášení", font=(FONT_STACK[0], FS_14, "bold"), text_color=TEXT).pack(pady=(12, 6))
        status_label = ctk.CTkLabel(dialog, text="", text_color=TEXT_MUTED)
        status_label.pack(pady=2)

        def do_trial():
            try:
                from license import DEMO_TRIAL_EMAIL, DEMO_TRIAL_PASSWORD
                email = DEMO_TRIAL_EMAIL or "zdarma@trial.verze"
                password = DEMO_TRIAL_PASSWORD or "free"
            except ImportError:
                email, password = "zdarma@trial.verze", "free"
            if self.on_login_password_callback:
                result = self.on_login_password_callback(email, password)
                if result and result[0]:
                    self.set_license_display("Režim: Zkušební verze (Trial)")
                    if self.on_after_login_callback:
                        self.on_after_login_callback()
                    dialog.after(600, dialog.destroy)
                else:
                    status_label.configure(text=result[1] if result and len(result) > 1 else "Chyba", text_color=ERROR)

        ctk.CTkButton(dialog, text="Vyzkoušet zdarma", command=do_trial, font=(FONT_STACK[0], FS_12), fg_color=ACCENT).pack(pady=6)
        email_var = ctk.StringVar()
        pass_var = ctk.StringVar()
        ctk.CTkLabel(dialog, text="E-mail:", text_color=TEXT).pack(anchor=tk.W, padx=16, pady=(4, 0))
        email_entry = ctk.CTkEntry(dialog, textvariable=email_var, width=300, placeholder_text="jmeno@firma.cz")
        email_entry.pack(pady=2, padx=16, fill=tk.X)
        ctk.CTkLabel(dialog, text="Heslo:", text_color=TEXT).pack(anchor=tk.W, padx=16, pady=(4, 0))
        pass_entry = ctk.CTkEntry(dialog, textvariable=pass_var, show="*", width=300)
        pass_entry.pack(pady=2, padx=16, fill=tk.X)
        email_entry.bind("<Return>", lambda e: do_login())
        pass_entry.bind("<Return>", lambda e: do_login())

        def do_login():
            email = email_var.get().strip()
            password = pass_var.get()
            if email and password and self.on_login_password_callback:
                result = self.on_login_password_callback(email, password)
                if result and result[0]:
                    display_text = result[2] if len(result) > 2 else None
                    self.set_license_display(display_text or ("Přihlášen: " + email))
                    if self.on_after_login_callback:
                        self.on_after_login_callback()
                    dialog.after(600, dialog.destroy)
                else:
                    status_label.configure(text=result[1] if result and len(result) > 1 else "Chyba", text_color=ERROR)
            else:
                status_label.configure(text="Zadejte e-mail a heslo.", text_color=ERROR)

        ctk.CTkButton(dialog, text="Přihlásit se", command=do_login, font=(FONT_STACK[0], FS_12), fg_color=ACCENT).pack(pady=10)


def create_app_2026_v3(on_check_callback, on_api_key_callback, api_url="",
                       on_login_password_callback=None, on_logout_callback=None, on_get_max_files=None,
                       on_after_login_callback=None, on_after_logout_callback=None, on_get_web_login_url=None,
                       on_send_batch_callback=None, on_has_login=None, on_get_remote_config=None, on_get_legal_config=None):
    """Vytvoří a vrátí (root, app) pro preview V3 Enterprise.
    Okno je během inicializace skryté (withdraw), po dokončení nastavení se zobrazí již maximalizované (bez probliknutí).
    on_has_login: callable() -> bool; bez přihlášení nelze analyzovat ani odesílat.
    on_get_remote_config: callable() -> dict; on_get_legal_config: callable() -> dict."""
    _setup_high_dpi_v3()
    if TKINTERDND_AVAILABLE:
        try:
            root = TkinterDnD.Tk()
            root.configure(bg=BG_APP)
        except Exception:
            root = ctk.CTk()
    else:
        root = ctk.CTk()
    # Skrýt okno během celé inicializace (barvy, logo, layout) – zabrání probliknutí
    root.withdraw()
    # Průhlednost vždy 1.0; žádné měnění -alpha při pohybu okna (zákaz zprůhlednění na jiném monitoru)
    try:
        root.attributes("-alpha", 1.0)
    except tk.TclError:
        pass
    app = PDFCheckUI_2026_V3(
        root, on_check_callback, on_api_key_callback, api_url=api_url,
        on_login_password_callback=on_login_password_callback,
        on_logout_callback=on_logout_callback,
        on_get_max_files=on_get_max_files,
        on_after_login_callback=on_after_login_callback,
        on_after_logout_callback=on_after_logout_callback,
        on_get_web_login_url=on_get_web_login_url,
        on_send_batch_callback=on_send_batch_callback,
        on_has_login=on_has_login,
        on_get_remote_config=on_get_remote_config,
        on_get_legal_config=on_get_legal_config,
    )
    # Maximalizace před zobrazením – hlavní okno se zobrazí až po splashi
    try:
        if sys.platform == "win32":
            root.state("zoomed")
        elif sys.platform == "darwin":
            root.attributes("-zoomed", True)
        else:
            root.state("zoomed")
    except tk.TclError:
        pass
    # Splash 3 s: logo, verze, copyright; pak zavřít splash a zobrazit hlavní okno (maximalizované)
    splash = _create_splash(root)
    root.after(SPLASH_DURATION_MS, lambda: _close_splash_and_show_main(splash, root))
    return root, app
