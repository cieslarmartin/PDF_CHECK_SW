# ui_2026_v1_minimal.py – TOP 2026 preview V1: Minimal clean. NEMĚŇ produkční ui.py.
# Layout: command bar, sidebar 230px, queue jako card list, results detail panel.

import tkinter as tk
from tkinter import filedialog, messagebox
import threading
import webbrowser
import os

import customtkinter as ctk

from ui import _format_result_summary, _count_errors_from_result, _session_summary_text

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

try:
    from tkinterdnd2 import DND_FILES, TkinterDnD
    TKINTERDND_AVAILABLE = True
except ImportError:
    TKINTERDND_AVAILABLE = False

# Typografie 12/14/16/20/24/32
FONT_STACK = ("Segoe UI Variable", "Segoe UI", "Inter")
FS_12 = 12
FS_14 = 14
FS_16 = 16
FS_20 = 20
FS_24 = 24
FS_32 = 32

# Barvy 2026
BG_APP = "#0B0F14"
BG_CARD = "#111827"
BG_HEADER = "#0F172A"
BORDER = "#1F2937"
TEXT = "#E5E7EB"
TEXT_MUTED = "#94A3B8"
ACCENT = "#0891b2"
SUCCESS = "#22c55e"
WARNING = "#f97316"
ERROR = "#ef4444"
SECONDS_PER_FILE_ETA = 0.4
SIDEBAR_W = 230


class PDFCheckUI_2026_V1:
    """Preview V1 – minimal clean, flat card rows, bez Treeview."""

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

        self.tasks = []
        self.queue_display = []
        self.session_files_checked = 0
        self.start_time = None
        self.total_files = 0
        self.processed_files = 0
        self.cancel_requested = False
        self.is_running = False

        self.root.title("DokuCheck Agent – Preview V1 (2026)")
        self.root.minsize(900, 620)
        self.root.geometry("1100x680")
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
        w, h = 1100, 680
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
        ctk.CTkLabel(sidebar, text="DokuCheck", font=(FONT_STACK[0], FS_20, "bold"), text_color=TEXT).pack(pady=(20, 0))
        ctk.CTkLabel(sidebar, text="Preview V1", font=(FONT_STACK[0], FS_12), text_color=TEXT_MUTED).pack(pady=(0, 16))
        ctk.CTkLabel(sidebar, text="Účet", font=(FONT_STACK[0], FS_14, "bold"), text_color=TEXT).pack(anchor=tk.W, padx=16, pady=(8, 4))
        self.sidebar_account = ctk.CTkLabel(sidebar, text="Nepřihlášen", font=(FONT_STACK[0], FS_12), text_color=TEXT_MUTED, wraplength=SIDEBAR_W - 32)
        self.sidebar_account.pack(anchor=tk.W, padx=16, pady=(0, 4))
        self.sidebar_daily_limit = ctk.CTkLabel(sidebar, text="Denní limit: —", font=(FONT_STACK[0], FS_12), text_color=TEXT_MUTED, wraplength=SIDEBAR_W - 32)
        self.sidebar_daily_limit.pack(anchor=tk.W, padx=16, pady=(0, 12))
        # Mini stats
        self.stat_dnes = ctk.CTkLabel(sidebar, text="Dnes: 0", font=(FONT_STACK[0], FS_12), text_color=TEXT_MUTED)
        self.stat_dnes.pack(anchor=tk.W, padx=16, pady=2)
        self.stat_ok = ctk.CTkLabel(sidebar, text="Úspěšnost: —", font=(FONT_STACK[0], FS_12), text_color=TEXT_MUTED)
        self.stat_ok.pack(anchor=tk.W, padx=16, pady=2)
        ctk.CTkButton(sidebar, text="Otevřít Web", command=self._open_web, font=(FONT_STACK[0], FS_14), width=180, fg_color=ACCENT).pack(pady=8, padx=16, fill=tk.X)
        self.logout_btn = ctk.CTkButton(sidebar, text="Odhlásit", command=self._do_logout, font=(FONT_STACK[0], FS_14), width=180, fg_color=ERROR)
        self.logout_btn.pack(pady=4, padx=16, fill=tk.X)
        self.logout_btn.pack_forget()
        self.login_btn = ctk.CTkButton(sidebar, text="Přihlásit", command=self.show_api_key_dialog, font=(FONT_STACK[0], FS_14), width=180, fg_color=BORDER)
        self.login_btn.pack(pady=4, padx=16, fill=tk.X)
        self.daily_limit_label = self.sidebar_daily_limit
        self.license_status_label = ctk.CTkLabel(sidebar, text="", font=(FONT_STACK[0], FS_12), text_color=ERROR, wraplength=SIDEBAR_W - 32)
        self.license_status_label.pack(anchor=tk.W, padx=16, pady=(0, 8))

        # Main
        main = ctk.CTkFrame(self.root, fg_color="transparent")
        main.grid(row=0, column=1, sticky="nsew", padx=0, pady=0)
        main.grid_columnconfigure(0, weight=1)
        main.grid_rowconfigure(1, weight=1)

        # Command bar
        bar = ctk.CTkFrame(main, fg_color=BG_CARD, height=48, corner_radius=0)
        bar.grid(row=0, column=0, sticky="ew")
        bar.grid_propagate(False)
        main.grid_columnconfigure(0, weight=1)
        ctk.CTkButton(bar, text="Přidat soubory", command=self.add_files, font=(FONT_STACK[0], FS_14), width=120, fg_color=ACCENT).pack(side=tk.LEFT, padx=8, pady=6)
        ctk.CTkButton(bar, text="+ Složka", command=self.add_folder, font=(FONT_STACK[0], FS_14), width=90, fg_color=ACCENT).pack(side=tk.LEFT, padx=4, pady=6)
        ctk.CTkButton(bar, text="Vymazat", command=self.clear_queue, font=(FONT_STACK[0], FS_14), width=80, fg_color=BORDER).pack(side=tk.LEFT, padx=4, pady=6)
        self.check_btn = ctk.CTkButton(bar, text="ODESLAT KE KONTROLE", command=self.on_check_clicked, font=(FONT_STACK[0], FS_16, "bold"), fg_color=ACCENT, height=36)
        self.check_btn.pack(side=tk.RIGHT, padx=12, pady=6)

        # Content: queue list + detail
        content = ctk.CTkFrame(main, fg_color="transparent")
        content.grid(row=1, column=0, sticky="nsew", padx=8, pady=8)
        content.grid_columnconfigure(0, weight=1, minsize=320)
        content.grid_columnconfigure(1, weight=1, minsize=280)
        content.grid_rowconfigure(0, weight=1)

        # Queue – scrollable card list
        left = ctk.CTkFrame(content, fg_color=BG_CARD, corner_radius=8)
        left.grid(row=0, column=0, sticky="nsew", padx=(0, 4))
        left.grid_columnconfigure(0, weight=1)
        left.grid_rowconfigure(1, weight=1)
        ctk.CTkLabel(left, text="Fronta", font=(FONT_STACK[0], FS_16, "bold"), text_color=TEXT).grid(row=0, column=0, sticky="w", padx=12, pady=(12, 6))
        self.queue_scroll = ctk.CTkScrollableFrame(left, fg_color="transparent")
        self.queue_scroll.grid(row=1, column=0, sticky="nsew", padx=8, pady=(0, 8))
        left.grid_columnconfigure(0, weight=1)
        left.grid_rowconfigure(1, weight=1)

        # Results detail
        right = ctk.CTkFrame(content, fg_color=BG_CARD, corner_radius=8)
        right.grid(row=0, column=1, sticky="nsew", padx=(4, 0))
        right.grid_columnconfigure(0, weight=1)
        right.grid_rowconfigure(1, weight=1)
        ctk.CTkLabel(right, text="Detail výsledku", font=(FONT_STACK[0], FS_16, "bold"), text_color=TEXT).grid(row=0, column=0, sticky="w", padx=12, pady=(12, 6))
        self.detail_text = ctk.CTkTextbox(right, font=(FONT_STACK[0], FS_14), fg_color=BG_APP, text_color=TEXT, wrap="word")
        self.detail_text.grid(row=1, column=0, sticky="nsew", padx=12, pady=(0, 12))
        self.results_text = self.detail_text

        # Progress row (skrytý)
        self._progress_row = ctk.CTkFrame(main, fg_color="transparent")
        self._progress_row.grid(row=2, column=0, sticky="ew", padx=8, pady=4)
        main.grid_rowconfigure(2, weight=0)
        self.progress_label = ctk.CTkLabel(self._progress_row, text="Připraveno", font=(FONT_STACK[0], FS_14), text_color=TEXT_MUTED)
        self.progress_label.pack(side=tk.LEFT)
        self.cancel_btn = ctk.CTkButton(self._progress_row, text="Zrušit", command=self.cancel_check, font=(FONT_STACK[0], FS_12), width=70, fg_color=ERROR)
        self.cancel_btn.pack(side=tk.RIGHT, padx=8)
        self.cancel_btn.pack_forget()
        self.progress = ctk.CTkProgressBar(self._progress_row, height=8, progress_color=ACCENT)
        self.progress.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=8)
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
            overlay = tk.Frame(self.root, bg=ACCENT)
            overlay.place(relx=0, rely=0, relwidth=1, relheight=1)
            overlay.place_forget()
            lbl = tk.Label(overlay, text="Pustit soubory k analýze", font=(FONT_STACK[0], FS_20, "bold"), fg="white", bg=ACCENT)
            lbl.place(relx=0.5, rely=0.5, anchor=tk.CENTER)
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

    def _pill(self, text, ok=True):
        color = SUCCESS if ok else ERROR
        return (text, color)

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
        for qidx, item in enumerate(self.queue_display):
            row = ctk.CTkFrame(self.queue_scroll, fg_color=BORDER, corner_radius=6, height=44)
            row.pack(fill=tk.X, pady=2)
            row.pack_propagate(False)
            chk = "☑" if item.get("checked", True) else "☐"
            badge_text, badge_color = self._badge_text(item)
            cb = ctk.CTkLabel(row, text=chk, font=(FONT_STACK[0], FS_14), text_color=TEXT, width=24, cursor="hand2")
            cb.pack(side=tk.LEFT, padx=8, pady=8)
            cb.bind("<Button-1>", lambda e, i=qidx: self._toggle_checked(i))
            lbl = ctk.CTkLabel(row, text=item.get("filename", ""), font=(FONT_STACK[0], FS_14), text_color=TEXT, anchor="w")
            lbl.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=4, pady=8)
            lbl.bind("<Button-1>", lambda e, i=qidx: self._select_item(i))
            pill = ctk.CTkLabel(row, text=badge_text, font=(FONT_STACK[0], FS_12), text_color=badge_color, width=56)
            pill.pack(side=tk.RIGHT, padx=8, pady=8)
            row.bind("<Button-1>", lambda e, i=qidx: self._select_item(i))
        self._update_stats()

    def _toggle_checked(self, qidx):
        if 0 <= qidx < len(self.queue_display):
            self.queue_display[qidx]["checked"] = not self.queue_display[qidx].get("checked", True)
            self.update_queue_display()

    def _select_item(self, qidx):
        if 0 <= qidx < len(self.queue_display):
            item = self.queue_display[qidx]
            text = _format_result_summary(item.get("filename", ""), item.get("status", "pending"), item.get("result"))
            self.detail_text.configure(state="normal")
            self.detail_text.delete("0.0", "end")
            self.detail_text.insert("0.0", text)
            self.detail_text.configure(state="disabled")

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
        self.stat_dnes.configure(text=f"Dnes: {self.session_files_checked}")
        self.stat_ok.configure(text=f"Úspěšnost: {pct}%" if total else "Úspěšnost: —")

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
        self.cancel_btn.pack(side=tk.RIGHT, padx=8)
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
            self.progress_label.configure(text=f"Zpracovávám: {current}/{total}")
            self.eta_label.configure(text=f"{mm:02d}:{ss:02d}")
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
        self.detail_text.insert("0.0", f"KONTROLA DOKONČENA\nCelkem: {success_count}\nČas: {time_str}\n\nKlikněte na řádek pro detail.")
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
            self.sidebar_daily_limit.configure(text="Denní limit: neomezeno")
        else:
            self.sidebar_daily_limit.configure(text=f"Denní limit: {used or 0} / {limit}")

    def set_license_display(self, text):
        self.sidebar_account.configure(text=text or "Nepřihlášen", text_color=TEXT if text else TEXT_MUTED)
        if text:
            self.login_btn.pack_forget()
            self.logout_btn.pack(pady=4, padx=16, fill=tk.X)
        else:
            self.logout_btn.pack_forget()
            self.login_btn.pack(pady=4, padx=16, fill=tk.X)

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
        dialog.geometry("420x360")
        dialog.configure(fg_color=BG_CARD)
        dialog.transient(self.root)
        dialog.grab_set()
        ctk.CTkLabel(dialog, text="Přihlášení", font=(FONT_STACK[0], FS_16, "bold"), text_color=TEXT).pack(pady=(16, 8))
        status_label = ctk.CTkLabel(dialog, text="", text_color=TEXT_MUTED)
        status_label.pack(pady=4)

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

        ctk.CTkButton(dialog, text="Vyzkoušet zdarma", command=do_trial, font=(FONT_STACK[0], FS_14), fg_color=ACCENT).pack(pady=8)
        email_var = ctk.StringVar()
        pass_var = ctk.StringVar()
        ctk.CTkLabel(dialog, text="E-mail:", text_color=TEXT).pack(anchor=tk.W, padx=20, pady=(8, 0))
        ctk.CTkEntry(dialog, textvariable=email_var, width=320).pack(pady=2, padx=20, fill=tk.X)
        ctk.CTkLabel(dialog, text="Heslo:", text_color=TEXT).pack(anchor=tk.W, padx=20, pady=(6, 0))
        ctk.CTkEntry(dialog, textvariable=pass_var, show="*", width=320).pack(pady=2, padx=20, fill=tk.X)

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

        ctk.CTkButton(dialog, text="Přihlásit se", command=do_login, font=(FONT_STACK[0], FS_14), fg_color=ACCENT).pack(pady=12)


def create_app_2026_v1(on_check_callback, on_api_key_callback, api_url="",
                       on_login_password_callback=None, on_logout_callback=None, on_get_max_files=None,
                       on_after_login_callback=None, on_after_logout_callback=None, on_get_web_login_url=None,
                       on_send_batch_callback=None):
    """Vytvoří a vrátí (root, app) pro preview V1 – stejný podpis jako create_app."""
    if TKINTERDND_AVAILABLE:
        try:
            root = TkinterDnD.Tk()
            root.configure(bg=BG_APP)
        except Exception:
            root = ctk.CTk()
    else:
        root = ctk.CTk()
    app = PDFCheckUI_2026_V1(
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
