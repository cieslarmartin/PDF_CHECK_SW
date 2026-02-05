# ui_2026_v3_enterprise.py – TOP 2026 preview V3: Enterprise / Dashboard. NEMĚŇ produkční ui.py.
# Více panelů, metriky nahoře, vyšší info density, „Jak to funguje“ timeline.
# Optimalizováno pro moderní velké rozlišení (2K/4K): DPI awareness + škálování CTk.

import tkinter as tk
from tkinter import filedialog, messagebox
import threading
import webbrowser
import os
import sys

import customtkinter as ctk

from ui import _count_errors_from_result, _session_summary_text

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")


def _setup_high_dpi_v3():
    """
    Pro V3: nastaví DPI awareness (Windows) a škálování CTk podle šířky obrazovky,
    aby UI bylo čitelné na 2K/4K bez rozmazání.
    Volat PŘED vytvořením root okna.

    Možnosti vylepšení UI / velké rozlišení (bez změny technologie):
    - CustomTkinter: set_widget_scaling() / set_window_scaling() (použito zde),
      automatická DPI awareness na Windows/macOS.
    - Jiné technologie (vyžadují větší refaktor): PyQt6/PySide6 (vektorové, HiDPI),
      web (Electron/Tauri nebo lokální server + prohlížeč), Kivy, Dear PyGui.
    """
    try:
        if sys.platform == "win32":
            try:
                ctypes = __import__("ctypes")
                shcore = getattr(ctypes.windll, "shcore", None)
                if shcore:
                    # PROCESS_PER_MONITOR_DPI_AWARE = 2
                    shcore.SetProcessDpiAwareness(2)
            except Exception:
                try:
                    ctypes = __import__("ctypes")
                    ctypes.windll.user32.SetProcessDPIAware()
                except Exception:
                    pass
    except Exception:
        pass
    # Zjistit šířku obrazovky bez vytvoření CTk okna (pomocí čistého Tk)
    try:
        tmp = tk.Tk()
        tmp.withdraw()
        screen_w = tmp.winfo_screenwidth()
        tmp.destroy()
        # Základ 1920 → scale 1.0; 2560 → ~1.33; 3840 → 2.0 (max)
        scale = min(2.0, max(1.0, screen_w / 1920.0))
        ctk.set_widget_scaling(scale)
        ctk.set_window_scaling(scale)
    except Exception:
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
BORDER = "#1F2937"
TEXT = "#E5E7EB"
TEXT_MUTED = "#94A3B8"
ACCENT = "#0891b2"
SUCCESS = "#22c55e"
WARNING = "#f97316"
ERROR = "#ef4444"
SECONDS_PER_FILE_ETA = 0.4
SIDEBAR_W = 220
ROW_HEIGHT_FOLDER = 22
ROW_HEIGHT_FILE = 26
# Text v pravém panelu – nezobrazujeme detail kontroly jednotlivých PDF (citlivá data)
NO_DETAIL_MSG = "Výsledky kontroly jednotlivých PDF se v této aplikaci nezobrazují.\nStav uvidíte po odeslání na server."


class PDFCheckUI_2026_V3:
    """Preview V3 – enterprise dashboard, metriky nahoře, Jak to funguje, high density."""

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

        self.tasks = []
        self.queue_display = []
        self.session_files_checked = 0
        self.start_time = None
        self.total_files = 0
        self.processed_files = 0
        self.cancel_requested = False
        self.is_running = False
        self.selected_qidx = None

        self.root.title("DokuCheck Agent – Preview V3 Enterprise (2026)")
        self.root.minsize(1100, 700)
        self.root.geometry("1440x900")
        try:
            self.root.configure(fg_color=BG_APP)
        except tk.TclError:
            self.root.configure(bg=BG_APP)
        self._center()
        self._build_layout()
        self._setup_dnd_overlay()
        self._show_session_summary()

    def _center(self):
        self.root.update_idletasks()
        w, h = 1440, 900
        x = (self.root.winfo_screenwidth() // 2) - (w // 2)
        y = (self.root.winfo_screenheight() // 2) - (h // 2)
        self.root.geometry(f"{w}x{h}+{x}+{y}")

    def _build_layout(self):
        self.root.grid_columnconfigure(0, weight=0, minsize=SIDEBAR_W)
        self.root.grid_columnconfigure(1, weight=1)
        self.root.grid_rowconfigure(0, weight=1)

        # Sidebar
        sidebar = ctk.CTkFrame(self.root, fg_color=BG_HEADER, width=SIDEBAR_W, corner_radius=0)
        sidebar.grid(row=0, column=0, sticky="nswe")
        sidebar.grid_propagate(False)
        ctk.CTkLabel(sidebar, text="DokuCheck", font=(FONT_STACK[0], FS_20, "bold"), text_color=TEXT).pack(pady=(16, 0))
        ctk.CTkLabel(sidebar, text="V3 Enterprise", font=(FONT_STACK[0], FS_12), text_color=TEXT_MUTED).pack(pady=(0, 12))
        ctk.CTkLabel(sidebar, text="Účet", font=(FONT_STACK[0], FS_12, "bold"), text_color=TEXT_MUTED).pack(anchor=tk.W, padx=12, pady=(4, 0))
        self.sidebar_account = ctk.CTkLabel(sidebar, text="Nepřihlášen", font=(FONT_STACK[0], FS_12), text_color=TEXT, wraplength=SIDEBAR_W - 24)
        self.sidebar_account.pack(anchor=tk.W, padx=12, pady=(0, 2))
        self.sidebar_daily_limit = ctk.CTkLabel(sidebar, text="Limit: —", font=(FONT_STACK[0], FS_12), text_color=TEXT_MUTED, wraplength=SIDEBAR_W - 24)
        self.sidebar_daily_limit.pack(anchor=tk.W, padx=12, pady=(0, 8))
        ctk.CTkButton(sidebar, text="Web", command=self._open_web, font=(FONT_STACK[0], FS_12), width=160, fg_color=ACCENT).pack(pady=4, padx=12, fill=tk.X)
        self.logout_btn = ctk.CTkButton(sidebar, text="Odhlásit", command=self._do_logout, font=(FONT_STACK[0], FS_12), width=160, fg_color=ERROR)
        self.logout_btn.pack(pady=2, padx=12, fill=tk.X)
        self.logout_btn.pack_forget()
        self.login_btn = ctk.CTkButton(sidebar, text="Přihlásit", command=self.show_api_key_dialog, font=(FONT_STACK[0], FS_12), width=160, fg_color=BORDER)
        self.login_btn.pack(pady=2, padx=12, fill=tk.X)
        self.license_status_label = ctk.CTkLabel(sidebar, text="", font=(FONT_STACK[0], FS_12), text_color=ERROR, wraplength=SIDEBAR_W - 24)
        self.license_status_label.pack(anchor=tk.W, padx=12, pady=(0, 6))
        self.daily_limit_label = self.sidebar_daily_limit

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
        ctk.CTkButton(bar, text="Vymazat vše", command=self.clear_queue, font=(FONT_STACK[0], FS_12), width=72, fg_color=BORDER).pack(side=tk.LEFT, padx=2, pady=4)
        ctk.CTkButton(bar, text="Odebrat vybrané", command=self.remove_checked_from_queue, font=(FONT_STACK[0], FS_12), width=100, fg_color=BORDER).pack(side=tk.LEFT, padx=2, pady=4)
        ctk.CTkButton(bar, text="Odebrat položku", command=self.remove_selected_from_queue, font=(FONT_STACK[0], FS_12), width=96, fg_color=BORDER).pack(side=tk.LEFT, padx=2, pady=4)
        ctk.CTkButton(bar, text="Odebrat složku", command=self.remove_folder_of_selected, font=(FONT_STACK[0], FS_12), width=96, fg_color=BORDER).pack(side=tk.LEFT, padx=2, pady=4)
        self.check_btn = ctk.CTkButton(bar, text="ODESLAT KE KONTROLE", command=self.on_check_clicked, font=(FONT_STACK[0], FS_14, "bold"), fg_color=ACCENT, height=32)
        self.check_btn.pack(side=tk.RIGHT, padx=10, pady=6)

        # Content: queue + detail + "Jak to funguje"
        content = ctk.CTkFrame(main, fg_color="transparent")
        content.grid(row=2, column=0, sticky="nsew", padx=6, pady=4)
        content.grid_columnconfigure(0, weight=2, minsize=340)
        content.grid_columnconfigure(1, weight=1, minsize=260)
        content.grid_columnconfigure(2, weight=0, minsize=180)
        content.grid_rowconfigure(0, weight=1)
        main.grid_rowconfigure(2, weight=1)

        # Queue panel
        left = ctk.CTkFrame(content, fg_color=BG_CARD, corner_radius=6)
        left.grid(row=0, column=0, sticky="nsew", padx=(0, 4))
        left.grid_columnconfigure(0, weight=1)
        left.grid_rowconfigure(1, weight=1)
        ctk.CTkLabel(left, text="Fronta (strom složek)", font=(FONT_STACK[0], FS_14, "bold"), text_color=TEXT).grid(row=0, column=0, sticky="w", padx=10, pady=(10, 4))
        self.queue_scroll = ctk.CTkScrollableFrame(left, fg_color="transparent")
        self.queue_scroll.grid(row=1, column=0, sticky="nsew", padx=6, pady=(0, 6))
        left.grid_columnconfigure(0, weight=1)
        left.grid_rowconfigure(1, weight=1)

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
            "3. Odeslat ke kontrole",
            "4. Prohlédněte výsledky",
            "5. Odeslat na server",
        ]
        for i, s in enumerate(steps):
            ctk.CTkLabel(timeline, text=s, font=(FONT_STACK[0], FS_12), text_color=TEXT_MUTED, anchor="w").grid(row=i + 1, column=0, sticky="w", padx=10, pady=2)
        self.timeline_frame = timeline

        # Progress row
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
        self._progress_row.grid_remove()
        self.eta_label = ctk.CTkLabel(self._progress_row, text="", font=(FONT_STACK[0], FS_12), text_color=TEXT_MUTED)
        self.eta_label.pack(side=tk.RIGHT)
        self.header_status = self.sidebar_account

    def _open_web(self):
        url = None
        if self.on_get_web_login_url:
            try:
                url = self.on_get_web_login_url()
            except Exception:
                pass
        webbrowser.open(url or self.api_url)

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
        for raw in self.root.tk.splitlist(event.data):
            path = (raw.strip() if isinstance(raw, str) else None) or (raw.get("path") or raw.get("full_path") if isinstance(raw, dict) else None)
            if path and isinstance(path, str):
                self.add_path_to_queue(path)
        self.update_queue_display()

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
        for f in files:
            self.add_path_to_queue(f)
        self.update_queue_display()

    def add_folder(self):
        folder = filedialog.askdirectory(title="Vyberte složku s PDF")
        if folder:
            self.add_path_to_queue(folder)
            self.update_queue_display()

    def clear_queue(self):
        self.tasks = []
        self.queue_display = []
        self.update_queue_display()
        self._update_stats()
        self._show_session_summary()

    def _badge_text(self, item):
        r = item.get("result")
        if not r or not isinstance(r, dict):
            return "…", TEXT_MUTED
        if r.get("skipped"):
            return "Přeskočeno", TEXT_MUTED
        if r.get("success"):
            return "OK", SUCCESS
        return "Chyba", ERROR

    def update_queue_display(self):
        for w in self.queue_scroll.winfo_children():
            w.destroy()
        qidx_global = 0
        for task_ix, task in enumerate(self.tasks):
            file_paths = task.get("file_paths", [])
            if not file_paths:
                continue
            is_folder = task.get("type") == "folder"
            name = task.get("name", "")
            if is_folder:
                # Řádek složky (strom)
                row = ctk.CTkFrame(self.queue_scroll, fg_color=BG_HEADER, corner_radius=3, height=ROW_HEIGHT_FOLDER)
                row.pack(fill=tk.X, pady=1)
                row.pack_propagate(False)
                lbl = ctk.CTkLabel(row, text=f"📁 {name}  ({len(file_paths)} souborů)", font=(FONT_STACK[0], FS_12, "bold"), text_color=TEXT, anchor="w")
                lbl.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=8, pady=2)
                lbl.bind("<Button-1>", lambda e, tix=task_ix: self._remove_folder_by_index(tix))
                row.bind("<Button-1>", lambda e, tix=task_ix: self._remove_folder_by_index(tix))
                btn = ctk.CTkButton(row, text="✕", width=24, height=18, font=(FONT_STACK[0], 10), fg_color=ERROR, command=lambda tix=task_ix: self._remove_folder_by_index(tix))
                btn.pack(side=tk.RIGHT, padx=4, pady=2)
            for j in range(len(file_paths)):
                if qidx_global >= len(self.queue_display):
                    break
                item = self.queue_display[qidx_global]
                qidx = qidx_global
                qidx_global += 1
                prefix = "    📄 " if is_folder else "📄 "
                row = ctk.CTkFrame(self.queue_scroll, fg_color=BORDER, corner_radius=3, height=ROW_HEIGHT_FILE)
                row.pack(fill=tk.X, pady=1)
                row.pack_propagate(False)
                chk = "☑" if item.get("checked", True) else "☐"
                badge_text, badge_color = self._badge_text(item)
                cb = ctk.CTkLabel(row, text=chk, font=(FONT_STACK[0], FS_12), text_color=TEXT, width=18, cursor="hand2")
                cb.pack(side=tk.LEFT, padx=4, pady=3)
                cb.bind("<Button-1>", lambda e, i=qidx: self._toggle_checked(i))
                lbl = ctk.CTkLabel(row, text=prefix + item.get("filename", ""), font=(FONT_STACK[0], FS_12), text_color=TEXT, anchor="w")
                lbl.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=2, pady=3)
                lbl.bind("<Button-1>", lambda e, i=qidx: self._select_item(i))
                pill = ctk.CTkLabel(row, text=badge_text, font=(FONT_STACK[0], FS_12), text_color=badge_color, width=44)
                pill.pack(side=tk.RIGHT, padx=4, pady=3)
                row.bind("<Button-1>", lambda e, i=qidx: self._select_item(i))
        self._update_stats()

    def _toggle_checked(self, qidx):
        if 0 <= qidx < len(self.queue_display):
            self.queue_display[qidx]["checked"] = not self.queue_display[qidx].get("checked", True)
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
            messagebox.showinfo("Fronta", "Žádné zaškrtnuté položky k odebrání.")
            return
        self._remove_paths_from_queue(to_remove)

    def remove_selected_from_queue(self):
        """Odebere z fronty aktuálně vybranou položku."""
        if self.selected_qidx is None:
            messagebox.showinfo("Fronta", "Nejdříve vyberte položku (klikněte na řádek).")
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
            messagebox.showinfo("Fronta", "Nejdříve vyberte položku ve složce, kterou chcete odebrat.")
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
        checked = [(q["path"], i) for i, q in enumerate(self.queue_display) if q.get("checked")]
        if not checked:
            messagebox.showwarning("Varování", "Přidejte a zaškrtněte položky ke kontrole.")
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
            all_results = []
            source_folder_for_batch = None
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

    def show_progress(self):
        import time
        self.start_time = time.time()
        self.progress.set(0)
        self.progress_label.configure(text="Zahajuji…", text_color=ACCENT)
        self._progress_row.grid()
        self.cancel_btn.pack(side=tk.RIGHT, padx=6)
        self.check_btn.configure(state="disabled")

    def finish_progress(self):
        self.is_running = False
        self.progress.set(1)
        self.progress_label.configure(text="Hotovo." if not self.cancel_requested else "Zrušeno", text_color=SUCCESS if not self.cancel_requested else WARNING)
        self.cancel_btn.pack_forget()
        self.check_btn.configure(state="normal")
        self.root.after(2500, lambda: self._progress_row.grid_remove())

    def update_progress(self, current, total, filename):
        import time
        if self.cancel_requested:
            return
        if total > 0:
            self.progress.set(current / total)
            remaining = total - current
            if current > 0 and self.start_time:
                eta_seconds = (time.time() - self.start_time) / current * remaining
            else:
                eta_seconds = remaining * SECONDS_PER_FILE_ETA
            mm, ss = int(eta_seconds // 60), int(eta_seconds % 60)
            self.progress_label.configure(text=f"{current}/{total}")
            self.eta_label.configure(text=f"ETA {mm:02d}:{ss:02d}")
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
        self.detail_text.insert("0.0", f"Hotovo: {success_count} souborů | Čas: {time_str}\n\nPo odeslání na server uvidíte stav v portálu.")
        self.detail_text.configure(state="disabled")
        upload_error = result.get("upload_error")
        if self.on_send_batch_callback and results_with_qidx:
            n = len(results_with_qidx)
            if messagebox.askyesno("Odeslat na server", f"Poslat data z {n} souborů na server?", default=messagebox.YES):
                try:
                    results_only = [r for _, r in results_with_qidx]
                    out = self.on_send_batch_callback(results_only, result.get("source_folder_for_batch"))
                    if out and len(out) >= 2 and not out[0]:
                        upload_error = out[1]
                except Exception as e:
                    upload_error = str(e)
                self._open_web()
        if upload_error and ("limit" in upload_error.lower() or "vyčerpán" in upload_error.lower()):
            messagebox.showwarning("Limit", upload_error)

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

    def set_license_display(self, text):
        self.sidebar_account.configure(text=text or "Nepřihlášen", text_color=TEXT if text else TEXT_MUTED)
        if text:
            self.login_btn.pack_forget()
            self.logout_btn.pack(pady=2, padx=12, fill=tk.X)
        else:
            self.logout_btn.pack_forget()
            self.login_btn.pack(pady=2, padx=12, fill=tk.X)

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
                email = DEMO_TRIAL_EMAIL or "free@trial.app"
                password = DEMO_TRIAL_PASSWORD or "free"
            except ImportError:
                email, password = "free@trial.app", "free"
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
        ctk.CTkEntry(dialog, textvariable=email_var, width=300).pack(pady=2, padx=16, fill=tk.X)
        ctk.CTkLabel(dialog, text="Heslo:", text_color=TEXT).pack(anchor=tk.W, padx=16, pady=(4, 0))
        ctk.CTkEntry(dialog, textvariable=pass_var, show="*", width=300).pack(pady=2, padx=16, fill=tk.X)

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
                       on_send_batch_callback=None):
    """Vytvoří a vrátí (root, app) pro preview V3 Enterprise – stejný podpis jako create_app.
    Před vytvořením okna volá _setup_high_dpi_v3() pro DPI awareness a škálování na 2K/4K."""
    _setup_high_dpi_v3()
    if TKINTERDND_AVAILABLE:
        try:
            root = TkinterDnD.Tk()
            root.configure(bg=BG_APP)
        except Exception:
            root = ctk.CTk()
    else:
        root = ctk.CTk()
    app = PDFCheckUI_2026_V3(
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
