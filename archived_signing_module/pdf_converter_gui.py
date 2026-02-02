# pdf_converter_gui.py
# Samostatné GUI pro PDF Converter s drag & drop
# Build 1.1 | © 2025 Ing. Martin Cieślar

import os
import sys
import tkinter as tk
from tkinter import ttk, filedialog, messagebox, scrolledtext, simpledialog
from pathlib import Path
import threading
from datetime import datetime

# Kontrola pikepdf (není kritická pro spuštění aplikace)
try:
    import pikepdf
    PIKEPDF_AVAILABLE = True
except ImportError:
    PIKEPDF_AVAILABLE = False

# Import PDF converter modulu
from pdf_converter import process_pdf_batch, ProcessingOptions
from pdf_converter.pdfa_converter import find_ghostscript
from pdf_converter.signer import (
    sign_pdf, SigningOptions, find_pkcs11_library, find_all_pkcs11_libraries,
    list_certificates_from_token, PYHANKO_AVAILABLE, PKCS11_AVAILABLE
)
from pdf_converter.config_manager import get_config_manager

# Drag & drop podpora
try:
    from tkinterdnd2 import DND_FILES, TkinterDnD
    DND_AVAILABLE = True
except ImportError:
    DND_AVAILABLE = False
    print("POZOR: tkinterdnd2 není nainstalován. Drag & drop nebude fungovat.")
    print("Instalujte: pip install tkinterdnd2")


class PDFConverterApp:
    """GUI pro PDF Converter s drag & drop"""

    def __init__(self, root):
        self.root = root
        self.root.title("PDF Converter - Odstranění podpisů + PDF/A konverze")
        self.root.geometry("900x900")  # Větší výchozí velikost pro pohodlné zobrazení
        self.root.minsize(800, 700)    # Minimální velikost
        self.root.resizable(True, True)  # Povolíme změnu velikosti

        # Styl
        self.style = ttk.Style()
        self.style.configure("Title.TLabel", font=("Segoe UI", 14, "bold"))
        self.style.configure("Status.TLabel", font=("Segoe UI", 9))
        self.style.configure("Warning.TLabel", foreground="orange")
        self.style.configure("Error.TLabel", foreground="red")

        # Proměnné
        self.files_to_process = []
        self.output_dir = tk.StringVar()
        self.filename_prefix = tk.StringVar()  # Prefix pro název souboru
        self.filename_suffix = tk.StringVar(value="signed")  # Suffix pro název souboru (výchozí: "signed")
        self.use_custom_suffix = tk.BooleanVar(value=False)  # Použít vlastní suffix místo automatického
        self.use_signed_subfolder = tk.BooleanVar(value=True)  # Ukládat do podsložky "Signed" (výchozí: True)
        self.last_input_dir = None  # Sledování poslední vstupní složky pro automatické nastavení
        self.remove_signatures = tk.BooleanVar(value=True)
        self.convert_pdfa = tk.BooleanVar(value=False)  # Výchozí False, uživatel si vybere
        self.sign_after = tk.BooleanVar(value=False)    # Podepisování
        self.pdfa_version = tk.StringVar(value="3")
        self.pdfa_conformance = tk.StringVar(value="A")  # Výchozí 3A
        self.overwrite = tk.BooleanVar(value=False)
        self.filename_prefix = tk.StringVar()  # Prefix pro název souboru
        self.filename_suffix = tk.StringVar(value="signed")  # Suffix pro název souboru (výchozí: "signed")
        self.use_custom_suffix = tk.BooleanVar(value=False)  # Použít vlastní suffix místo automatického
        self.is_processing = False
        
        # Podepisování - proměnné
        self.use_token = tk.BooleanVar(value=True)       # Použít token (True) nebo .pfx (False)
        self.token_pin = tk.StringVar()                  # PIN pro token
        self.certificate_path = tk.StringVar()           # Cesta k .pfx souboru
        self.certificate_label = tk.StringVar()          # Label certifikátu na tokenu
        self.signature_type = tk.StringVar(value="podpis")  # Typ: "podpis" nebo "razitko"
        self.use_tsa = tk.BooleanVar(value=False)         # Použít TSA (výchozí: vypnuto)
        self.tsa_url = tk.StringVar(value="http://tsa.postsignum.cz/tsp")  # TSA URL
        self.tsa_username = tk.StringVar()               # TSA uživatelské jméno
        self.tsa_password = tk.StringVar()               # TSA heslo
        self.visual_signature = tk.BooleanVar(value=True) # Čárové razítko
        self.signing_reason = tk.StringVar(value="Elektronický podpis")
        self.signing_location = tk.StringVar(value="Česká republika")
        self.verified_signer = None                      # Ověřený signer objekt (pro batch)
        self.certificate_info = None                     # Informace o certifikátu
        self._profile_password = None                     # Heslo z profilu (pro PFX)
        
        # PKCS#11 knihovna a tokeny
        self.pkcs11_lib = find_pkcs11_library()
        self.available_pkcs11_libs = find_all_pkcs11_libraries()  # Všechny dostupné knihovny
        self.available_certificates = []
        self.selected_token_type = tk.StringVar(value="auto")  # auto, safenet, bit4id, gemalto, ica
        
        # Profily
        self.selected_signing_profile = tk.StringVar()  # Vybraný podpisový profil
        self.selected_tsa_profile = tk.StringVar()      # Vybraný TSA profil

        # Kontrola Ghostscriptu
        self.gs_available = find_ghostscript() is not None
        
        # Config Manager pro profily
        self.config_manager = get_config_manager()

        self._create_ui()
        self._setup_drag_drop()
        self._check_ghostscript()
        self._load_profiles()  # Načteme profily při startu

    def _create_ui(self):
        """Vytvoří uživatelské rozhraní s podporou scrollování"""
        # Vytvoříme hlavní kontejner s Canvas pro scrollování
        container = ttk.Frame(self.root)
        container.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # Canvas pro scrollování
        canvas = tk.Canvas(container, highlightthickness=0)
        scrollbar = ttk.Scrollbar(container, orient=tk.VERTICAL, command=canvas.yview)
        scrollable_frame = ttk.Frame(canvas)
        
        # Konfigurace scrollování
        def configure_scroll_region(event=None):
            canvas.configure(scrollregion=canvas.bbox("all"))
        
        scrollable_frame.bind("<Configure>", configure_scroll_region)
        
        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        
        # Aktualizace scrollregion při změně velikosti okna
        def on_canvas_configure(event):
            canvas_width = event.width
            canvas.itemconfig(canvas.find_all()[0], width=canvas_width)
        
        canvas.bind('<Configure>', on_canvas_configure)
        
        # Mousewheel scrollování
        def _on_mousewheel(event):
            canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
        canvas.bind_all("<MouseWheel>", _on_mousewheel)
        
        # Uložíme canvas pro pozdější aktualizace
        self.canvas = canvas
        self.scrollable_frame = scrollable_frame
        
        # Pack canvas a scrollbar
        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        # Main frame uvnitř scrollable_frame
        main_frame = ttk.Frame(scrollable_frame, padding=15)
        main_frame.pack(fill=tk.BOTH, expand=True)

        # === TITLE ===
        title = ttk.Label(main_frame, text="PDF Converter", style="Title.TLabel")
        title.pack(pady=(0, 5))

        subtitle = ttk.Label(main_frame, text="Odstranění podpisů • Konverze na PDF/A • Elektronické podepisování")
        subtitle.pack(pady=(0, 10))

        # === VSTUPNÍ SOUBORY ===
        input_frame = ttk.LabelFrame(main_frame, text="Vstupní soubory (drag & drop podporováno)", padding=10)
        input_frame.pack(fill=tk.BOTH, expand=True, pady=5, padx=10)

        btn_frame = ttk.Frame(input_frame)
        btn_frame.pack(fill=tk.X, pady=(0, 10), padx=5)

        ttk.Button(btn_frame, text="Přidat soubory...", command=self._add_files).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="Přidat složku...", command=self._add_folder).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="Vymazat seznam", command=self._clear_files).pack(side=tk.LEFT, padx=5)

        # Seznam souborů s drag & drop
        list_frame = ttk.Frame(input_frame)
        list_frame.pack(fill=tk.BOTH, expand=True, pady=5, padx=5)

        self.file_listbox = tk.Listbox(list_frame, height=8, selectmode=tk.EXTENDED)
        scrollbar = ttk.Scrollbar(list_frame, orient=tk.VERTICAL, command=self.file_listbox.yview)
        self.file_listbox.configure(yscrollcommand=scrollbar.set)

        self.file_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # Drag & drop hint
        if DND_AVAILABLE:
            hint_text = "💡 Přetáhněte sem PDF soubory nebo složky"
        else:
            hint_text = "💡 Pro drag & drop nainstalujte: pip install tkinterdnd2"
        
        hint_label = ttk.Label(input_frame, text=hint_text, font=("Segoe UI", 8), foreground="gray")
        hint_label.pack(anchor=tk.W, pady=(5, 0), padx=5)

        self.files_count_label = ttk.Label(input_frame, text="0 souborů")
        self.files_count_label.pack(anchor=tk.W, pady=(2, 5), padx=5)

        # === VÝSTUPNÍ SLOŽKA ===
        output_frame = ttk.LabelFrame(main_frame, text="Výstupní složka", padding=10)
        output_frame.pack(fill=tk.X, pady=5, padx=10)

        entry_frame = ttk.Frame(output_frame)
        entry_frame.pack(fill=tk.X, pady=(0, 5), padx=5)
        ttk.Entry(entry_frame, textvariable=self.output_dir).pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 10))
        ttk.Button(entry_frame, text="Procházet...", command=self._browse_output).pack(side=tk.RIGHT)
        
        # Checkbox pro podsložku "Signed"
        ttk.Checkbutton(output_frame, text="Ukládat do podsložky 'Signed'", variable=self.use_signed_subfolder).pack(anchor=tk.W, pady=(5, 5), padx=5)
        
        # === NÁZEV SOUBORU ===
        filename_frame = ttk.LabelFrame(main_frame, text="Název výstupního souboru", padding=10)
        filename_frame.pack(fill=tk.X, pady=5, padx=10)
        
        # Přepsat existující soubory
        ttk.Checkbutton(filename_frame, text="Přepsat existující soubory", variable=self.overwrite).pack(anchor=tk.W, pady=5, padx=5)
        
        # Prefix (volitelný)
        prefix_frame = ttk.Frame(filename_frame)
        prefix_frame.pack(fill=tk.X, pady=5, padx=5)
        ttk.Label(prefix_frame, text="Prefix (volitelné):").pack(side=tk.LEFT, padx=(0, 10))
        ttk.Entry(prefix_frame, textvariable=self.filename_prefix, width=20).pack(side=tk.LEFT)
        
        # Automatický suffix nebo vlastní
        suffix_frame = ttk.Frame(filename_frame)
        suffix_frame.pack(fill=tk.X, pady=5, padx=5)
        ttk.Checkbutton(suffix_frame, text="Použít vlastní suffix místo automatického:", variable=self.use_custom_suffix).pack(side=tk.LEFT, padx=(0, 10))
        suffix_entry = ttk.Entry(suffix_frame, textvariable=self.filename_suffix, width=20, state=tk.DISABLED)
        suffix_entry.pack(side=tk.LEFT, padx=5)
        
        def toggle_suffix_entry():
            state = tk.NORMAL if self.use_custom_suffix.get() else tk.DISABLED
            suffix_entry.configure(state=state)
        
        self.use_custom_suffix.trace_add('write', lambda *args: toggle_suffix_entry())
        toggle_suffix_entry()  # Nastavíme počáteční stav

        # === NASTAVENÍ ===
        settings_frame = ttk.LabelFrame(main_frame, text="Nastavení", padding=10)
        settings_frame.pack(fill=tk.X, pady=5, padx=10)

        # Řádek 1: Checkboxy
        row1 = ttk.Frame(settings_frame)
        row1.pack(fill=tk.X, pady=5, padx=5)

        ttk.Checkbutton(row1, text="✓ Odstranit podpisy", variable=self.remove_signatures,
                       command=self._validate_settings).pack(side=tk.LEFT, padx=10)
        
        self.pdfa_check = ttk.Checkbutton(row1, text="✓ Převést na PDF/A", variable=self.convert_pdfa,
                                          command=self._on_pdfa_toggle)
        self.pdfa_check.pack(side=tk.LEFT, padx=10)
        
        self.sign_check = ttk.Checkbutton(row1, text="✓ Podepsat", variable=self.sign_after,
                                          command=self._on_sign_toggle)
        self.sign_check.pack(side=tk.LEFT, padx=10)
        
        ttk.Checkbutton(row1, text="Přepsat existující", variable=self.overwrite).pack(side=tk.LEFT, padx=10)

        # Řádek 2: PDF/A verze
        row2 = ttk.Frame(settings_frame)
        row2.pack(fill=tk.X, pady=2)

        ttk.Label(row2, text="PDF/A verze:").pack(side=tk.LEFT, padx=(10, 5))
        self.version_combo = ttk.Combobox(row2, textvariable=self.pdfa_version, values=["1", "2", "3"], width=5,
                                          state="readonly")
        self.version_combo.pack(side=tk.LEFT)

        ttk.Label(row2, text="Conformance:").pack(side=tk.LEFT, padx=(20, 5))
        self.conform_combo = ttk.Combobox(row2, textvariable=self.pdfa_conformance, values=["A", "B"], width=5,
                                          state="readonly")
        self.conform_combo.pack(side=tk.LEFT)

        # Ghostscript warning
        self.gs_warning = ttk.Label(row2, text="", style="Warning.TLabel")
        self.gs_warning.pack(side=tk.RIGHT, padx=10)

        # === PODEPISOVÁNÍ NASTAVENÍ ===
        self.signing_frame = ttk.LabelFrame(main_frame, text="Nastavení podepisování", padding=10)
        # Bude zobrazeno pouze pokud je zaškrtnuto "Podepsat"
        
        # Řádek 1: Výběr profilů
        sign_row1 = ttk.Frame(self.signing_frame)
        sign_row1.pack(fill=tk.X, pady=5, padx=5)
        
        ttk.Label(sign_row1, text="Podepsat jako:").pack(side=tk.LEFT, padx=(10, 5))
        self.signing_profile_combo = ttk.Combobox(sign_row1, textvariable=self.selected_signing_profile, 
                                                   width=30, state="readonly")
        self.signing_profile_combo.pack(side=tk.LEFT, padx=5)
        self.signing_profile_combo.bind('<<ComboboxSelected>>', lambda e: self._on_signing_profile_selected())
        
        ttk.Button(sign_row1, text="Správa profilů...", command=self._show_profile_manager).pack(side=tk.LEFT, padx=10)
        
        # Řádek 2: TSA profil
        sign_row2 = ttk.Frame(self.signing_frame)
        sign_row2.pack(fill=tk.X, pady=5, padx=5)
        
        ttk.Label(sign_row2, text="Použít TSA:").pack(side=tk.LEFT, padx=(10, 5))
        self.tsa_profile_combo = ttk.Combobox(sign_row2, textvariable=self.selected_tsa_profile, 
                                               width=30, state="readonly")
        self.tsa_profile_combo.pack(side=tk.LEFT, padx=5)
        self.tsa_profile_combo.bind('<<ComboboxSelected>>', lambda e: self._on_tsa_profile_selected())
        
        # Řádek 3: Typ podpisu a čárové razítko
        sign_row3 = ttk.Frame(self.signing_frame)
        sign_row3.pack(fill=tk.X, pady=5, padx=5)
        
        ttk.Label(sign_row3, text="Typ:").pack(side=tk.LEFT, padx=(10, 5))
        ttk.Radiobutton(sign_row3, text="Podpis", variable=self.signature_type, value="podpis",
                       command=self._on_signature_type_change).pack(side=tk.LEFT, padx=5)
        ttk.Radiobutton(sign_row3, text="Autorizační razítko", variable=self.signature_type, value="razitko",
                       command=self._on_signature_type_change).pack(side=tk.LEFT, padx=5)
        
        ttk.Checkbutton(sign_row3, text="Čárové razítko", variable=self.visual_signature).pack(side=tk.LEFT, padx=10)
        
        # Řádek 5: Důvod a lokace
        sign_row5 = ttk.Frame(self.signing_frame)
        sign_row5.pack(fill=tk.X, pady=5, padx=5)
        
        ttk.Label(sign_row5, text="Důvod:").pack(side=tk.LEFT, padx=(10, 5))
        ttk.Entry(sign_row5, textvariable=self.signing_reason, width=30).pack(side=tk.LEFT, padx=5)
        
        ttk.Label(sign_row5, text="Lokace:").pack(side=tk.LEFT, padx=(20, 5))
        ttk.Entry(sign_row5, textvariable=self.signing_location, width=30).pack(side=tk.LEFT, padx=5)
        
        # Zpočátku skryté
        self.signing_frame.pack_forget()

        # === PROGRESS ===
        progress_frame = ttk.Frame(main_frame)
        progress_frame.pack(fill=tk.X, pady=10)

        self.progress_var = tk.DoubleVar()
        self.progress_bar = ttk.Progressbar(progress_frame, variable=self.progress_var, maximum=100)
        self.progress_bar.pack(fill=tk.X)

        self.status_label = ttk.Label(progress_frame, text="Připraveno", style="Status.TLabel")
        self.status_label.pack(anchor=tk.W, pady=(2, 0))

        # === TLAČÍTKA ===
        btn_frame = ttk.Frame(main_frame)
        btn_frame.pack(fill=tk.X, pady=15, padx=10)

        self.start_btn = ttk.Button(btn_frame, text="▶ Spustit konverzi", command=self._start_processing)
        self.start_btn.pack(side=tk.LEFT, padx=10)

        ttk.Button(btn_frame, text="Zavřít", command=self.root.quit).pack(side=tk.RIGHT, padx=10)

        # === VÝSLEDKY ===
        results_frame = ttk.LabelFrame(main_frame, text="Výsledky", padding=10)
        results_frame.pack(fill=tk.BOTH, expand=True, pady=5, padx=10)

        self.results_text = scrolledtext.ScrolledText(results_frame, height=10, wrap=tk.WORD, state=tk.DISABLED,
                                                      font=("Consolas", 9))
        self.results_text.pack(fill=tk.BOTH, expand=True)

    def _setup_drag_drop(self):
        """Nastaví drag & drop pro listbox"""
        if not DND_AVAILABLE:
            return
        
        try:
            self.file_listbox.drop_target_register(DND_FILES)
            self.file_listbox.dnd_bind('<<Drop>>', self._on_drop)
        except Exception as e:
            print(f"Chyba při nastavení drag & drop: {e}")

    def _on_drop(self, event):
        """Zpracuje přetažené soubory/složky"""
        files = self.root.tk.splitlist(event.data)
        added_count = 0
        
        for file_path in files:
            file_path = file_path.strip('{}')  # Odstraníme závorky z Windows paths
            
            path = Path(file_path)
            
            if path.is_file() and path.suffix.lower() == '.pdf':
                # Přidáme PDF soubor
                f_str = str(path)
                if f_str not in self.files_to_process:
                    self.files_to_process.append(f_str)
                    self.file_listbox.insert(tk.END, path.name)
                    added_count += 1
                    # Automaticky nastavíme výstupní složku na složku prvního souboru
                    if added_count == 1:
                        input_dir = str(path.parent)
                        if not self.output_dir.get() or self.output_dir.get() == self.last_input_dir:
                            self.output_dir.set(input_dir)
                            self.last_input_dir = input_dir
            elif path.is_dir():
                # Přidáme všechny PDF ze složky
                pdf_files = list(path.glob("*.pdf"))
                for pdf_file in pdf_files:
                    f_str = str(pdf_file)
                    if f_str not in self.files_to_process:
                        self.files_to_process.append(f_str)
                        self.file_listbox.insert(tk.END, pdf_file.name)
                        added_count += 1
                
                # Automaticky nastavíme výstupní složku na složku prvního souboru
                if added_count > 0:
                    input_dir = str(path)
                    # Nastavíme pouze pokud je prázdná nebo byla nastavena automaticky
                    if not self.output_dir.get() or self.output_dir.get() == self.last_input_dir:
                        self.output_dir.set(input_dir)
                        self.last_input_dir = input_dir
        
        if added_count > 0:
            self._update_files_count()
            self._log_result(f"Přidáno {added_count} souborů z drag & drop")

    def _check_ghostscript(self):
        """Zkontroluje dostupnost Ghostscriptu"""
        if not self.gs_available:
            self.gs_warning.configure(text="⚠ Ghostscript nenalezen - PDF/A konverze nebude fungovat")
        else:
            self.gs_warning.configure(text="✓ Ghostscript nalezen")

    def _validate_settings(self):
        """Ověří že je vybrána alespoň jedna operace"""
        pass  # Validace se provede při spuštění

    def _on_pdfa_toggle(self):
        """Při změně checkboxu PDF/A"""
        state = "readonly" if self.convert_pdfa.get() else "disabled"
        self.version_combo.configure(state=state)
        self.conform_combo.configure(state=state)
        
        # PDF/A automaticky vyžaduje odstranění podpisů
        if self.convert_pdfa.get():
            # Automaticky zaškrtneme odstranění podpisů (PDF/A nemůže obsahovat podpisy)
            self.remove_signatures.set(True)
            # Varování pokud není Ghostscript
            if not self.gs_available:
                self._check_ghostscript()
    
    def _on_sign_toggle(self):
        """Při změně checkboxu Podepsat"""
        if self.sign_after.get():
            # Kontrola pyhanko
            if not PYHANKO_AVAILABLE:
                messagebox.showerror(
                    "Chyba",
                    "pyhanko není nainstalován!\n\n"
                    "Pro podepisování nainstalujte:\n"
                    "pip install pyhanko pyhanko-certvalidator python-pkcs11\n\n"
                    "Podepisování nebude fungovat."
                )
                self.sign_after.set(False)
                return
            
            # Zobrazíme nastavení podepisování (používáme profily místo dialogu)
            if not self.signing_frame.winfo_viewable():
                self.signing_frame.pack(fill=tk.X, pady=5, padx=10)
                # Aktualizujeme scrollregion po zobrazení
                if hasattr(self, 'canvas'):
                    self.root.after(100, lambda: self.canvas.configure(scrollregion=self.canvas.bbox("all")))
        else:
            # Skryjeme nastavení podepisování
            self.signing_frame.pack_forget()
    
    def _show_signature_dialog(self):
        """Zobrazí dialog pro konfiguraci podepisování"""
        dialog = tk.Toplevel(self.root)
        dialog.title("Nastavení podepisování")
        dialog.minsize(700, 600)  # Minimální velikost
        dialog.geometry("750x650")  # Větší výchozí velikost
        dialog.transient(self.root)
        dialog.grab_set()
        dialog.resizable(True, True)  # Povolíme změnu velikosti
        
        # Centrování dialogu
        dialog.update_idletasks()
        x = (dialog.winfo_screenwidth() // 2) - (dialog.winfo_width() // 2)
        y = (dialog.winfo_screenheight() // 2) - (dialog.winfo_height() // 2)
        dialog.geometry(f"+{x}+{y}")
        
        result = {'confirmed': False}
        
        # Hlavní frame pro celý obsah
        main_container = ttk.Frame(dialog)
        main_container.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Scrollable frame pro obsah (pokud by byl obsah příliš dlouhý)
        canvas = tk.Canvas(main_container)
        scrollbar = ttk.Scrollbar(main_container, orient="vertical", command=canvas.yview)
        scrollable_frame = ttk.Frame(canvas)
        
        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )
        
        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        
        # Frame pro obsah
        content = ttk.Frame(scrollable_frame, padding=20)
        content.pack(fill=tk.BOTH, expand=True)
        
        # Typ certifikátu
        cert_type_frame = ttk.LabelFrame(content, text="Typ certifikátu", padding=10)
        cert_type_frame.pack(fill=tk.X, pady=5)
        
        cert_type = tk.StringVar(value="pfx")
        ttk.Radiobutton(cert_type_frame, text=".pfx soubor", variable=cert_type, value="pfx").pack(anchor=tk.W, pady=2)
        ttk.Radiobutton(cert_type_frame, text="Token (iSignum/PKCS#11)", variable=cert_type, value="token").pack(anchor=tk.W, pady=2)
        
        # .pfx soubor
        pfx_frame = ttk.LabelFrame(content, text=".pfx certifikát", padding=10)
        pfx_frame.pack(fill=tk.X, pady=5)
        
        # Řádek pro cestu k souboru a tlačítko Procházet
        pfx_path_frame = ttk.Frame(pfx_frame)
        pfx_path_frame.pack(fill=tk.X, pady=(0, 5))
        
        pfx_path = tk.StringVar(value=self.certificate_path.get())
        pfx_entry = ttk.Entry(pfx_path_frame, textvariable=pfx_path, width=50)
        pfx_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 5))
        
        def browse_pfx():
            file = filedialog.askopenfilename(
                title="Vyberte .pfx/.p12 certifikát",
                filetypes=[("PFX soubory", "*.pfx *.p12"), ("Všechny soubory", "*.*")]
            )
            if file:
                pfx_path.set(file)
        
        browse_btn = ttk.Button(pfx_path_frame, text="Procházet...", command=browse_pfx, width=15)
        browse_btn.pack(side=tk.RIGHT, padx=(5, 0))
        
        # Heslo pro .pfx
        pfx_password_frame = ttk.Frame(pfx_frame)
        pfx_password_frame.pack(fill=tk.X, pady=(5, 0))
        
        ttk.Label(pfx_password_frame, text="Heslo:").pack(side=tk.LEFT, padx=(0, 5))
        pfx_password = tk.StringVar()
        pfx_password_entry = ttk.Entry(pfx_password_frame, textvariable=pfx_password, width=30, show="*")  # echoMode equivalent
        pfx_password_entry.pack(side=tk.LEFT, fill=tk.X, expand=True)
        
        # Tlačítko pro ověření certifikátu
        verify_btn = ttk.Button(pfx_password_frame, text="Ověřit", width=10)
        verify_btn.pack(side=tk.LEFT, padx=(5, 0))
        
        # Status label pro certifikát (VELMI VÝRAZNÝ)
        cert_status_frame = ttk.Frame(pfx_frame)
        cert_status_frame.pack(fill=tk.X, pady=(10, 0))
        
        cert_status_label = ttk.Label(
            cert_status_frame, 
            text="❌ Certifikát není ověřen", 
            foreground="red",
            font=("Segoe UI", 10, "bold")
        )
        cert_status_label.pack(anchor=tk.W)
        
        # Uložené informace o certifikátu
        verified_cert_info = {'info': None, 'signer': None}
        is_verified = tk.BooleanVar(value=False)
        
        def verify_certificate():
            """Ověří certifikát"""
            if not pfx_path.get():
                cert_status_label.configure(
                    text="❌ Vyberte .pfx soubor",
                    foreground="red"
                )
                is_verified.set(False)
                update_confirm_button()
                return
            
            if not Path(pfx_path.get()).exists():
                cert_status_label.configure(
                    text="❌ Soubor neexistuje",
                    foreground="red"
                )
                is_verified.set(False)
                update_confirm_button()
                return
            
            # Importujeme validátor
            try:
                from pdf_converter.cert_validator import verify_certificate as verify_cert
            except ImportError as e:
                cert_status_label.configure(
                    text=f"❌ Chyba: {str(e)}",
                    foreground="red"
                )
                is_verified.set(False)
                update_confirm_button()
                messagebox.showerror("Chyba", str(e))
                return
            
            # Ověříme certifikát
            try:
                success, cert_info, error_msg = verify_cert(pfx_path.get(), pfx_password.get())
                
                if success and cert_info:
                    verified_cert_info['info'] = cert_info
                    verified_cert_info['signer'] = cert_info.get('signer_obj')
                    is_verified.set(True)
                    
                    # Zobrazíme informace
                    cn = cert_info.get('common_name', 'Neznámé')
                    exp_date = cert_info.get('expiration_date')
                    if exp_date:
                        if isinstance(exp_date, datetime):
                            exp_str = exp_date.strftime("%d.%m.%Y")
                        else:
                            exp_str = str(exp_date)
                    else:
                        exp_str = "Neznámé"
                    
                    cert_status_label.configure(
                        text=f"✅ Certifikát připraven: {cn} | Platnost do: {exp_str}",
                        foreground="green",
                        font=("Segoe UI", 10, "bold")
                    )
                else:
                    verified_cert_info['info'] = None
                    verified_cert_info['signer'] = None
                    is_verified.set(False)
                    error_display = error_msg or "Certifikát nenačten"
                    cert_status_label.configure(
                        text=f"❌ {error_display}",
                        foreground="red"
                    )
            except Exception as e:
                verified_cert_info['info'] = None
                verified_cert_info['signer'] = None
                is_verified.set(False)
                cert_status_label.configure(
                    text=f"❌ Chyba: {str(e)}",
                    foreground="red"
                )
                messagebox.showerror("Chyba", f"Chyba při ověřování: {str(e)}")
            
            update_confirm_button()
        
        verify_btn.configure(command=verify_certificate)
        
        # Debounce timer pro automatické ověření (aby se nevolalo při každém znaku)
        verify_timer = None
        
        def schedule_verify():
            """Naplánuje ověření po 500ms (debounce)"""
            nonlocal verify_timer
            if verify_timer:
                dialog.after_cancel(verify_timer)
            
            def do_verify():
                if cert_type.get() == "pfx":
                    pwd = pfx_password.get()
                    # Validujeme pouze pokud máme cestu, soubor existuje a heslo má alespoň 1 znak
                    if pfx_path.get() and Path(pfx_path.get()).exists() and pwd and len(pwd) >= 1:
                        # Automaticky ověříme pokud máme cestu i heslo (alespoň 1 znak)
                        verify_certificate()
                    elif pfx_path.get() or pfx_password.get():
                        # Reset statusu pokud není kompletní
                        cert_status_label.configure(
                            text="❌ Certifikát není ověřen",
                            foreground="red"
                        )
                        verified_cert_info['info'] = None
                        verified_cert_info['signer'] = None
                        is_verified.set(False)
                        update_confirm_button()
            
            verify_timer = dialog.after(500, do_verify)  # 500ms debounce
        
        def on_pfx_change(*args):
            """Při změně cesty nebo hesla - naplánuje ověření s debounce"""
            schedule_verify()
        
        pfx_path.trace('w', on_pfx_change)
        pfx_password.trace('w', on_pfx_change)
        
        # Tlačítko Potvrdit (bude zamčené pokud není ověřen certifikát)
        # Definujeme proměnnou, která bude nastavena později
        confirm_btn_ref = {'btn': None}
        
        def update_confirm_button():
            """Aktualizuje stav tlačítka Potvrdit"""
            if confirm_btn_ref['btn']:
                if cert_type.get() == "pfx":
                    if is_verified.get() and verified_cert_info['info']:
                        confirm_btn_ref['btn'].configure(state=tk.NORMAL)
                    else:
                        confirm_btn_ref['btn'].configure(state=tk.DISABLED)
                else:
                    # Pro token není potřeba ověření
                    confirm_btn_ref['btn'].configure(state=tk.NORMAL)
        
        # Token nastavení (skryté zpočátku)
        token_frame = ttk.LabelFrame(content, text="Token nastavení", padding=10)
        
        ttk.Label(token_frame, text="PIN:").pack(anchor=tk.W)
        token_pin = tk.StringVar(value=self.token_pin.get())
        token_pin_entry = ttk.Entry(token_frame, textvariable=token_pin, width=30, show="*")
        token_pin_entry.pack(fill=tk.X, pady=(2, 10))
        
        def on_cert_type_change():
            if cert_type.get() == "pfx":
                pfx_frame.pack(fill=tk.X, pady=5)
                token_frame.pack_forget()
            else:
                pfx_frame.pack_forget()
                token_frame.pack(fill=tk.X, pady=5)
            update_confirm_button()
        
        on_cert_type_change()
        
        # Nastavení časového razítka (TSA)
        tsa_frame = ttk.LabelFrame(content, text="Nastavení časového razítka", padding=10)
        tsa_frame.pack(fill=tk.X, pady=5)
        
        use_tsa = tk.BooleanVar(value=self.use_tsa.get())
        tsa_checkbox = ttk.Checkbutton(tsa_frame, text="Použít časové razítko (TSA)", variable=use_tsa)
        tsa_checkbox.pack(anchor=tk.W, pady=2)
        
        # TSA URL
        tsa_url_frame = ttk.Frame(tsa_frame)
        tsa_url_frame.pack(fill=tk.X, pady=(5, 0))
        ttk.Label(tsa_url_frame, text="TSA URL:").pack(side=tk.LEFT, padx=(0, 5))
        tsa_url = tk.StringVar(value=self.tsa_url.get())
        tsa_url_entry = ttk.Entry(tsa_url_frame, textvariable=tsa_url, width=50)
        tsa_url_entry.pack(side=tk.LEFT, fill=tk.X, expand=True)
        
        # TSA Username
        tsa_user_frame = ttk.Frame(tsa_frame)
        tsa_user_frame.pack(fill=tk.X, pady=(5, 0))
        ttk.Label(tsa_user_frame, text="TSA Jméno:").pack(side=tk.LEFT, padx=(0, 5))
        tsa_username = tk.StringVar(value=self.tsa_username.get())
        tsa_username_entry = ttk.Entry(tsa_user_frame, textvariable=tsa_username, width=30)
        tsa_username_entry.pack(side=tk.LEFT, fill=tk.X, expand=True)
        
        # TSA Password
        tsa_pass_frame = ttk.Frame(tsa_frame)
        tsa_pass_frame.pack(fill=tk.X, pady=(5, 0))
        ttk.Label(tsa_pass_frame, text="TSA Heslo:").pack(side=tk.LEFT, padx=(0, 5))
        tsa_password = tk.StringVar(value=self.tsa_password.get())
        tsa_password_entry = ttk.Entry(tsa_pass_frame, textvariable=tsa_password, width=30, show="*")
        tsa_password_entry.pack(side=tk.LEFT, fill=tk.X, expand=True)
        
        # Funkce pro povolení/zakázání TSA polí
        def toggle_tsa_fields():
            """Povolí nebo zakáže TSA pole podle stavu checkboxu"""
            state = tk.NORMAL if use_tsa.get() else tk.DISABLED
            tsa_url_entry.configure(state=state)
            tsa_username_entry.configure(state=state)
            tsa_password_entry.configure(state=state)
        
        # Nastavíme počáteční stav (vypnuto = disabled)
        toggle_tsa_fields()
        
        # Připojíme callback při změně checkboxu
        use_tsa.trace_add('write', lambda *args: toggle_tsa_fields())
        
        # Další nastavení
        options_frame = ttk.LabelFrame(content, text="Další nastavení", padding=10)
        options_frame.pack(fill=tk.X, pady=5)
        
        visual_sig = tk.BooleanVar(value=self.visual_signature.get())
        ttk.Checkbutton(options_frame, text="Čárové razítko (vizuální podpis)", variable=visual_sig).pack(anchor=tk.W, pady=2)
        
        # Tlačítka - vždy viditelná dole (mimo scrollable area)
        btn_frame = ttk.Frame(main_container)
        btn_frame.pack(fill=tk.X, pady=(10, 0), side=tk.BOTTOM)
        
        def confirm():
            # Validace
            if cert_type.get() == "pfx":
                if not pfx_path.get():
                    messagebox.showerror("Chyba", "Vyberte .pfx soubor!")
                    return
                if not Path(pfx_path.get()).exists():
                    messagebox.showerror("Chyba", "Zadaný .pfx soubor neexistuje!")
                    return
                
                # STRICT: Certifikát MUSÍ být ověřen
                if not is_verified.get() or not verified_cert_info['info']:
                    messagebox.showerror(
                        "Chyba",
                        "Certifikát není ověřen!\n\n"
                        "Klikněte na tlačítko 'Ověřit' a ujistěte se, že se zobrazí zelený status ✅."
                    )
                    return
                
                # Uložíme do GUI proměnných
                self.certificate_path.set(pfx_path.get())
                self.token_pin.set(pfx_password.get())  # Uložíme heslo jako token_pin (pro .pfx)
                self.use_token.set(False)
                
                # Uložíme ověřený signer objekt pro batch processing
                self.verified_signer = verified_cert_info.get('signer')
                self.certificate_info = verified_cert_info.get('info')
            else:
                if not token_pin.get():
                    messagebox.showerror("Chyba", "Zadejte PIN pro token!")
                    return
                self.token_pin.set(token_pin.get())
                self.use_token.set(True)
                self.verified_signer = None
                self.certificate_info = None
            
            # Uložíme nastavení do SigningOptions dataclass
            self.use_tsa.set(use_tsa.get())
            self.tsa_url.set(tsa_url.get())
            self.tsa_username.set(tsa_username.get())
            self.tsa_password.set(tsa_password.get())
            self.visual_signature.set(visual_sig.get())
            
            result['confirmed'] = True
            dialog.destroy()
        
        def cancel():
            dialog.destroy()
        
        # Tlačítko Potvrdit - bude zamčené pokud není ověřen certifikát (pro .pfx)
        confirm_btn_ref['btn'] = ttk.Button(btn_frame, text="✓ Potvrdit", command=confirm, state=tk.DISABLED, width=15)
        confirm_btn_ref['btn'].pack(side=tk.RIGHT, padx=(10, 5))
        ttk.Button(btn_frame, text="✗ Zrušit", command=cancel, width=15).pack(side=tk.RIGHT, padx=5)
        
        # Tlačítka jsou nyní vždy viditelná, protože jsou mimo scrollable area
        
        # Aktualizujeme tlačítko po vytvoření
        update_confirm_button()
        
        # Čekáme na uzavření dialogu
        dialog.wait_window()
        return result['confirmed']
    
    def _on_cert_type_change(self):
        """Při změně typu certifikátu (token/.pfx)"""
        if self.use_token.get():
            # Zobrazíme token nastavení
            self.token_frame.pack(fill=tk.X, pady=2)
            self.pfx_frame.pack_forget()
            
            # Najdeme správnou PKCS#11 knihovnu podle typu tokenu
            token_type = self.selected_token_type.get()
            if token_type == "auto":
                self.pkcs11_lib = find_pkcs11_library()
            else:
                self.pkcs11_lib = find_pkcs11_library(token_type)
            
            # Zkusíme načíst certifikáty
            if self.pkcs11_lib:
                # Neautomaticky načítáme - uživatel musí kliknout na tlačítko
                pass
            else:
                # Zobrazíme varování
                messagebox.showwarning(
                    "Varování",
                    f"PKCS#11 knihovna pro token typu '{token_type}' nebyla nalezena.\n\n"
                    "Ujistěte se, že máte nainstalované ovladače pro váš token:\n"
                    "- BIT4ID: BIT4ID eToken software\n"
                    "- SafeNet: SafeNet Authentication Client\n"
                    "- Gemalto: IDGo 800 PKCS#11 driver\n"
                    "- I.CA: I.CA PKCS#11 driver"
                )
        else:
            # Zobrazíme .pfx nastavení
            self.token_frame.pack_forget()
            self.pfx_frame.pack(fill=tk.X, pady=2)
    
    def _load_certificates(self):
        """Načte certifikáty z tokenu"""
        if not self.pkcs11_lib:
            messagebox.showwarning("Varování", "PKCS#11 knihovna nenalezena!\n\nNainstalujte SafeNet Authentication Client.")
            return
        
        pin = self.token_pin.get()
        if not pin:
            pin = tk.simpledialog.askstring("PIN", "Zadejte PIN pro token:", show='*')
            if pin:
                self.token_pin.set(pin)
            else:
                return
        
        try:
            certs = list_certificates_from_token(self.pkcs11_lib, pin)
            if certs:
                self.available_certificates = certs
                cert_labels = [f"{c['label']} - {c['subject'][:50]}..." for c in certs]
                self.cert_combo['values'] = cert_labels
                if cert_labels:
                    self.cert_combo.current(0)
                    self.certificate_label.set(certs[0]['label'])
                messagebox.showinfo("Úspěch", f"Načteno {len(certs)} certifikátů z tokenu.")
            else:
                messagebox.showwarning("Varování", "Na tokenu nebyly nalezeny žádné certifikáty.")
        except Exception as e:
            messagebox.showerror("Chyba", f"Nepodařilo se načíst certifikáty:\n{str(e)}")
    
    def _browse_pfx(self):
        """Vybere .pfx soubor"""
        file = filedialog.askopenfilename(
            title="Vyberte .pfx/.p12 certifikát",
            filetypes=[("PFX soubory", "*.pfx *.p12"), ("Všechny soubory", "*.*")]
        )
        if file:
            self.certificate_path.set(file)
    
    def _on_signature_type_change(self):
        """Při změně typu podpisu (podpis/razítko)"""
        if self.signature_type.get() == "razitko":
            # Autorizační razítko - upravíme výchozí hodnoty
            if self.signing_reason.get() == "Elektronický podpis":
                self.signing_reason.set("Elektronické autorizační razítko")
        else:
            # Obyčejný podpis
            if self.signing_reason.get() == "Elektronické autorizační razítko":
                self.signing_reason.set("Elektronický podpis")

    def _add_files(self):
        """Přidá soubory do seznamu"""
        files = filedialog.askopenfilenames(
            title="Vyberte PDF soubory",
            filetypes=[("PDF soubory", "*.pdf"), ("Všechny soubory", "*.*")]
        )
        if files:
            # Automaticky nastavíme výstupní složku na složku prvního souboru
            first_file = Path(files[0])
            input_dir = str(first_file.parent)
            
            # Nastavíme výstupní složku pouze pokud:
            # 1. Je prázdná, NEBO
            # 2. Byla nastavena automaticky z předchozího výběru (stejná jako last_input_dir)
            if not self.output_dir.get() or self.output_dir.get() == self.last_input_dir:
                self.output_dir.set(input_dir)
                self.last_input_dir = input_dir
            
            for f in files:
                if f not in self.files_to_process:
                    self.files_to_process.append(f)
                    self.file_listbox.insert(tk.END, Path(f).name)

            self._update_files_count()

    def _add_folder(self):
        """Přidá všechny PDF ze složky"""
        folder = filedialog.askdirectory(title="Vyberte složku s PDF soubory")
        if folder:
            pdf_files = list(Path(folder).glob("*.pdf"))
            if pdf_files:
                # Automaticky nastavíme výstupní složku na vybranou složku
                # Nastavíme pouze pokud je prázdná nebo byla nastavena automaticky
                if not self.output_dir.get() or self.output_dir.get() == self.last_input_dir:
                    self.output_dir.set(folder)
                    self.last_input_dir = folder
                
                for f in pdf_files:
                    f_str = str(f)
                    if f_str not in self.files_to_process:
                        self.files_to_process.append(f_str)
                        self.file_listbox.insert(tk.END, f.name)

                self._update_files_count()

    def _clear_files(self):
        """Vymaže seznam souborů"""
        self.files_to_process.clear()
        self.file_listbox.delete(0, tk.END)
        self._update_files_count()
        self._log_result("Seznam souborů vymazán")

    def _update_files_count(self):
        """Aktualizuje počet souborů"""
        count = len(self.files_to_process)
        self.files_count_label.configure(text=f"{count} souborů")

    def _browse_output(self):
        """Vybere výstupní složku"""
        folder = filedialog.askdirectory(title="Vyberte výstupní složku")
        if folder:
            self.output_dir.set(folder)

    def _log_result(self, text):
        """Zapíše text do výsledků"""
        self.results_text.configure(state=tk.NORMAL)
        self.results_text.insert(tk.END, text + "\n")
        self.results_text.see(tk.END)
        self.results_text.configure(state=tk.DISABLED)

    def _start_processing(self):
        """Spustí zpracování"""
        if self.is_processing:
            return

        if not self.files_to_process:
            messagebox.showwarning("Upozornění", "Nejsou vybrány žádné soubory!")
            return

        if not self.remove_signatures.get() and not self.convert_pdfa.get() and not self.sign_after.get():
            messagebox.showwarning("Upozornění", "Vyberte alespoň jednu operaci:\n• Odstranit podpisy\n• Převést na PDF/A\n• Podepsat")
            return
        
        # Validace podepisování
        if self.sign_after.get():
            if not PYHANKO_AVAILABLE:
                messagebox.showerror("Chyba", "pyhanko není nainstalován!\n\nInstalujte: pip install pyhanko pyhanko-certvalidator python-pkcs11")
                return
            
            if self.use_token.get():
                if not self.pkcs11_lib:
                    messagebox.showerror("Chyba", "PKCS#11 knihovna nenalezena!\n\nNainstalujte SafeNet Authentication Client.")
                    return
                if not self.token_pin.get():
                    messagebox.showerror("Chyba", "Zadejte PIN pro token!")
                    return
                if not self.certificate_label.get():
                    messagebox.showerror("Chyba", "Vyberte certifikát z tokenu!")
                    return
            else:
                if not self.certificate_path.get():
                    messagebox.showerror("Chyba", "Vyberte .pfx soubor!")
                    return
                if not Path(self.certificate_path.get()).exists():
                    messagebox.showerror("Chyba", "Zadaný .pfx soubor neexistuje!")
                    return

        # PDF/A automaticky vyžaduje odstranění podpisů - informujeme uživatele
        if self.convert_pdfa.get() and not self.remove_signatures.get():
            # Toto by nemělo nastat díky _on_pdfa_toggle, ale pro jistotu
            self.remove_signatures.set(True)
            self._log_result("POZNAMKA: PDF/A konverze automaticky odstraní podpisy (PDF/A nemůže obsahovat podpisy)")

        # Varování pokud není Ghostscript ale chceme PDF/A
        if self.convert_pdfa.get() and not self.gs_available:
            response = messagebox.askyesno(
                "Varování",
                "Ghostscript není nainstalován!\n\nPDF/A konverze nebude fungovat.\n\n"
                "Chcete pokračovat pouze s odstraněním podpisů?",
                icon="warning"
            )
            if not response:
                return
            # Vypneme PDF/A konverzi
            self.convert_pdfa.set(False)
            self._on_pdfa_toggle()

        # Výstupní složka
        output = self.output_dir.get()
        if not output:
            output = os.path.dirname(self.files_to_process[0])
            self.output_dir.set(output)

        os.makedirs(output, exist_ok=True)

        # Reset UI
        self.results_text.configure(state=tk.NORMAL)
        self.results_text.delete(1.0, tk.END)
        self.results_text.configure(state=tk.DISABLED)
        self.progress_var.set(0)
        self.is_processing = True
        self.start_btn.configure(state=tk.DISABLED, text="⏳ Zpracovává se...")

        # Spustíme v novém vlákně
        thread = threading.Thread(target=self._process_files, daemon=True)
        thread.start()

    def _process_files(self):
        """Zpracuje soubory (běží v novém vlákně)"""
        try:
            # Vytvoříme SigningOptions pokud je podepisování aktivní
            signing_options = None
            if self.sign_after.get():
                # Získáme heslo - buď z profilu nebo z GUI
                pfx_password = None
                if not self.use_token.get():
                    # Pro PFX - použijeme heslo z profilu pokud je k dispozici
                    if hasattr(self, '_profile_password') and self._profile_password:
                        pfx_password = self._profile_password
                    # Pokud není v profilu, uživatel musí zadat heslo při podepisování
                
                # Pro PFX: použijeme heslo z profilu pokud je k dispozici
                pfx_password = None
                if not self.use_token.get():
                    if hasattr(self, '_profile_password') and self._profile_password:
                        pfx_password = self._profile_password
                
                signing_options = SigningOptions(
                    certificate_path=self.certificate_path.get() if not self.use_token.get() else None,
                    pkcs11_lib=self.pkcs11_lib if self.use_token.get() else None,
                    token_pin=self.token_pin.get() if self.use_token.get() else (pfx_password if pfx_password else None),
                    certificate_label=self.certificate_label.get() if self.use_token.get() else None,
                    signature_type=self.signature_type.get(),
                    reason=self.signing_reason.get(),
                    location=self.signing_location.get(),
                    use_tsa=self.use_tsa.get(),
                    tsa_url=self.tsa_url.get(),
                    tsa_username=self.tsa_username.get() if self.tsa_username.get() else None,
                    tsa_password=self.tsa_password.get() if self.tsa_password.get() else None,
                    visual_signature=self.visual_signature.get(),
                    page_number=-1,  # Poslední stránka
                    signature_position=(-1, -1, -1, -1)  # Auto - pravý dolní roh
                )
            
            options = ProcessingOptions(
                remove_signatures=self.remove_signatures.get(),
                convert_to_pdfa=self.convert_pdfa.get(),
                pdfa_version=self.pdfa_version.get(),
                pdfa_conformance=self.pdfa_conformance.get(),
                sign_after=self.sign_after.get(),
                signing_options=signing_options,
                output_dir=self.output_dir.get(),
                overwrite=self.overwrite.get(),
                filename_prefix=self.filename_prefix.get() if self.filename_prefix.get() else None,
                filename_suffix=self.filename_suffix.get() if self.use_custom_suffix.get() and self.filename_suffix.get() else None,
                use_auto_suffix=not self.use_custom_suffix.get() or not self.filename_suffix.get(),
                use_signed_subfolder=self.use_signed_subfolder.get(),
                max_workers=4
            )

            total = len(self.files_to_process)

            # Log nastavení
            ops = []
            if options.remove_signatures:
                ops.append("Odstranění podpisů")
            if options.convert_to_pdfa:
                ops.append(f"Konverze na PDF/A-{options.pdfa_version}{options.pdfa_conformance}")
            if options.sign_after and options.signing_options:
                sign_type = "Token" if options.signing_options.pkcs11_lib else ".pfx"
                tsa_info = " s TSA" if options.signing_options.use_tsa else ""
                ops.append(f"Podepisování ({sign_type}{tsa_info})")
            
            self.root.after(0, lambda: self._log_result(f"{'=' * 60}"))
            self.root.after(0, lambda: self._log_result(f"Zpracovávám {total} souborů"))
            self.root.after(0, lambda: self._log_result(f"Operace: {', '.join(ops) if ops else 'Žádná'}\n"))

            def progress_callback(current, total_files, filename):
                progress = (current / total_files) * 100
                self.root.after(0, lambda: self._update_progress(progress, f"[{current}/{total_files}] {filename}"))

            results = process_pdf_batch(self.files_to_process, options, progress_callback)

            # Výsledky
            success_count = sum(1 for r in results if r.success)
            error_count = total - success_count

            self.root.after(0, lambda: self._log_result(f"\n{'=' * 60}"))
            self.root.after(0, lambda: self._log_result(f"VÝSLEDKY: {success_count} úspěšně, {error_count} chyb\n"))

            for r in results:
                status = "✓" if r.success else "✗"
                msg = f"{status} {Path(r.input_file).name}"
                self.root.after(0, lambda m=msg: self._log_result(m))

                for step in r.steps:
                    self.root.after(0, lambda s=step: self._log_result(f"    → {s}"))

                if r.error:
                    error_msg = r.error
                    self.root.after(0, lambda e=error_msg: self._log_result(f"    ✗ CHYBA: {e}"))
                    # Zobrazíme error dialog pro chyby podepisování
                    if "podepisování" in error_msg.lower() or "signing" in error_msg.lower() or "tsa" in error_msg.lower():
                        self.root.after(0, lambda e=error_msg: messagebox.showerror("Chyba při podepisování", f"Podepisování selhalo:\n\n{e}\n\nZkontrolujte:\n- Cestu k certifikátu\n- Heslo pro .pfx soubor\n- Připojení k TSA serveru"))
                
                if r.output_file:
                    self.root.after(0, lambda o=r.output_file: self._log_result(f"    → Výstup: {Path(o).name}"))

            self.root.after(0, lambda: self._log_result(f"\n{'=' * 60}"))
            self.root.after(0, lambda: self._log_result(f"Hotovo! Výsledky jsou ve složce: {options.output_dir}"))

        except Exception as e:
            self.root.after(0, lambda: self._log_result(f"\n✗ FATÁLNÍ CHYBA: {e}"))
            import traceback
            self.root.after(0, lambda: self._log_result(traceback.format_exc()))

        finally:
            self.root.after(0, self._processing_done)

    def _update_progress(self, value, status):
        """Aktualizuje progress bar"""
        self.progress_var.set(value)
        self.status_label.configure(text=status)

    def _processing_done(self):
        """Ukončení zpracování"""
        self.is_processing = False
        self.start_btn.configure(state=tk.NORMAL, text="▶ Spustit konverzi")
        self.progress_var.set(100)
        self.status_label.configure(text="Hotovo")
    
    # === SPRÁVA PROFILŮ ===
    
    def _load_profiles(self):
        """Načte profily do comboboxů"""
        # Načteme podpisové profily
        signing_profiles = self.config_manager.get_signing_profiles()
        profile_names = [p.get("name", "") for p in signing_profiles if p.get("name")]
        self.signing_profile_combo['values'] = profile_names
        
        # Načteme TSA profily
        tsa_profiles = self.config_manager.get_tsa_profiles()
        tsa_names = ["Žádné"] + [p.get("name", "") for p in tsa_profiles if p.get("name")]
        self.tsa_profile_combo['values'] = tsa_names
        if tsa_names:
            self.tsa_profile_combo.current(0)  # Výchozí "Žádné"
    
    def _on_signing_profile_selected(self):
        """Při výběru podpisového profilu"""
        profile_name = self.selected_signing_profile.get()
        if not profile_name:
            return
        
        profile = self.config_manager.get_signing_profile(profile_name)
        if not profile:
            messagebox.showerror("Chyba", f"Profil '{profile_name}' nebyl nalezen.")
            return
        
        # Aplikujeme profil
        profile_type = profile.get("type", "pfx").lower()
        if profile_type == "pfx":
            self.use_token.set(False)
            self.certificate_path.set(profile.get("path", ""))
            # Pokud má profil heslo, uložíme ho (ale neukazujeme v GUI)
            if "password" in profile:
                # Heslo uložíme do interní proměnné pro pozdější použití
                self._profile_password = profile.get("password")
        elif profile_type == "token":
            self.use_token.set(True)
            # Pro token uložíme path jako PKCS#11 knihovnu
            if "path" in profile:
                self.pkcs11_lib = profile.get("path")
            if "label" in profile:
                self.certificate_label.set(profile.get("label"))
            if "username" in profile:
                self.token_pin.set(profile.get("username"))  # PIN může být v username
        
        # Aktualizujeme UI - už nepotřebujeme _on_cert_type_change, protože používáme profily
    
    def _on_tsa_profile_selected(self):
        """Při výběru TSA profilu"""
        profile_name = self.selected_tsa_profile.get()
        if profile_name == "Žádné" or not profile_name:
            self.use_tsa.set(False)
            self.tsa_url.set("http://tsa.postsignum.cz/tsp")
            self.tsa_username.set("")
            self.tsa_password.set("")
            return
        
        profile = self.config_manager.get_tsa_profile(profile_name)
        if not profile:
            messagebox.showerror("Chyba", f"TSA profil '{profile_name}' nebyl nalezen.")
            return
        
        # Aplikujeme TSA profil
        self.use_tsa.set(True)
        self.tsa_url.set(profile.get("url", "http://tsa.postsignum.cz/tsp"))
        self.tsa_username.set(profile.get("username", ""))
        self.tsa_password.set(profile.get("password", ""))
    
    def _show_profile_manager(self):
        """Zobrazí dialog pro správu profilů"""
        dialog = tk.Toplevel(self.root)
        dialog.title("Správa profilů")
        dialog.minsize(800, 600)
        dialog.geometry("900x700")
        dialog.transient(self.root)
        dialog.grab_set()
        dialog.resizable(True, True)
        
        # Centrování
        dialog.update_idletasks()
        x = (dialog.winfo_screenwidth() // 2) - (dialog.winfo_width() // 2)
        y = (dialog.winfo_screenheight() // 2) - (dialog.winfo_height() // 2)
        dialog.geometry(f"+{x}+{y}")
        
        # Notebook pro taby
        notebook = ttk.Notebook(dialog)
        notebook.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Tab 1: Podpisové certifikáty
        signing_tab = ttk.Frame(notebook, padding=10)
        notebook.add(signing_tab, text="Podpisové certifikáty")
        self._create_signing_profiles_tab(signing_tab)
        
        # Tab 2: TSA Servery
        tsa_tab = ttk.Frame(notebook, padding=10)
        notebook.add(tsa_tab, text="TSA Servery")
        self._create_tsa_profiles_tab(tsa_tab)
        
        # Tlačítka
        btn_frame = ttk.Frame(dialog)
        btn_frame.pack(fill=tk.X, padx=10, pady=5)
        ttk.Button(btn_frame, text="Zavřít", command=dialog.destroy).pack(side=tk.RIGHT, padx=5)
    
    def _create_signing_profiles_tab(self, parent):
        """Vytvoří tab pro správu podpisových profilů"""
        # Seznam profilů
        list_frame = ttk.LabelFrame(parent, text="Profily", padding=5)
        list_frame.pack(fill=tk.BOTH, expand=True, pady=5)
        
        # Treeview pro zobrazení profilů
        columns = ("Název", "Typ", "Cesta")
        tree = ttk.Treeview(list_frame, columns=columns, show="headings", height=10)
        for col in columns:
            tree.heading(col, text=col)
            tree.column(col, width=200)
        
        scrollbar = ttk.Scrollbar(list_frame, orient=tk.VERTICAL, command=tree.yview)
        tree.configure(yscrollcommand=scrollbar.set)
        
        tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        def refresh_list():
            tree.delete(*tree.get_children())
            profiles = self.config_manager.get_signing_profiles()
            for profile in profiles:
                tree.insert("", tk.END, values=(
                    profile.get("name", ""),
                    profile.get("type", "").upper(),
                    profile.get("path", "")
                ))
        
        refresh_list()
        
        # Tlačítka
        btn_frame = ttk.Frame(parent)
        btn_frame.pack(fill=tk.X, pady=5)
        
        def add_profile():
            self._edit_signing_profile(None, refresh_list)
        
        def edit_profile():
            selection = tree.selection()
            if not selection:
                messagebox.showwarning("Varování", "Vyberte profil k úpravě.")
                return
            item = tree.item(selection[0])
            profile_name = item['values'][0]
            profile = self.config_manager.get_signing_profile(profile_name)
            if profile:
                self._edit_signing_profile(profile, refresh_list)
        
        def delete_profile():
            selection = tree.selection()
            if not selection:
                messagebox.showwarning("Varování", "Vyberte profil ke smazání.")
                return
            item = tree.item(selection[0])
            profile_name = item['values'][0]
            if messagebox.askyesno("Potvrdit", f"Opravdu chcete smazat profil '{profile_name}'?"):
                if self.config_manager.delete_signing_profile(profile_name):
                    refresh_list()
                    self._load_profiles()  # Obnovíme comboboxy v hlavním okně
        
        ttk.Button(btn_frame, text="Přidat", command=add_profile).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="Upravit", command=edit_profile).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="Smazat", command=delete_profile).pack(side=tk.LEFT, padx=5)
    
    def _create_tsa_profiles_tab(self, parent):
        """Vytvoří tab pro správu TSA profilů"""
        # Seznam profilů
        list_frame = ttk.LabelFrame(parent, text="TSA Profily", padding=5)
        list_frame.pack(fill=tk.BOTH, expand=True, pady=5)
        
        # Treeview
        columns = ("Název", "URL", "Uživatel")
        tree = ttk.Treeview(list_frame, columns=columns, show="headings", height=10)
        for col in columns:
            tree.heading(col, text=col)
            tree.column(col, width=250)
        
        scrollbar = ttk.Scrollbar(list_frame, orient=tk.VERTICAL, command=tree.yview)
        tree.configure(yscrollcommand=scrollbar.set)
        
        tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        def refresh_list():
            tree.delete(*tree.get_children())
            profiles = self.config_manager.get_tsa_profiles()
            for profile in profiles:
                tree.insert("", tk.END, values=(
                    profile.get("name", ""),
                    profile.get("url", ""),
                    profile.get("username", "")
                ))
        
        refresh_list()
        
        # Tlačítka
        btn_frame = ttk.Frame(parent)
        btn_frame.pack(fill=tk.X, pady=5)
        
        def add_profile():
            self._edit_tsa_profile(None, refresh_list)
        
        def edit_profile():
            selection = tree.selection()
            if not selection:
                messagebox.showwarning("Varování", "Vyberte profil k úpravě.")
                return
            item = tree.item(selection[0])
            profile_name = item['values'][0]
            profile = self.config_manager.get_tsa_profile(profile_name)
            if profile:
                self._edit_tsa_profile(profile, refresh_list)
        
        def delete_profile():
            selection = tree.selection()
            if not selection:
                messagebox.showwarning("Varování", "Vyberte profil ke smazání.")
                return
            item = tree.item(selection[0])
            profile_name = item['values'][0]
            if messagebox.askyesno("Potvrdit", f"Opravdu chcete smazat TSA profil '{profile_name}'?"):
                if self.config_manager.delete_tsa_profile(profile_name):
                    refresh_list()
                    self._load_profiles()  # Obnovíme comboboxy
        
        ttk.Button(btn_frame, text="Přidat", command=add_profile).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="Upravit", command=edit_profile).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="Smazat", command=delete_profile).pack(side=tk.LEFT, padx=5)
    
    def _edit_signing_profile(self, profile, refresh_callback):
        """Dialog pro úpravu/přidání podpisového profilu"""
        dialog = tk.Toplevel(self.root)
        dialog.title("Podpisový profil" if profile else "Nový podpisový profil")
        dialog.geometry("500x400")
        dialog.transient(self.root)
        dialog.grab_set()
        
        # Formulář
        form_frame = ttk.Frame(dialog, padding=10)
        form_frame.pack(fill=tk.BOTH, expand=True)
        
        # Název
        ttk.Label(form_frame, text="Název:").grid(row=0, column=0, sticky=tk.W, pady=5)
        name_var = tk.StringVar(value=profile.get("name", "") if profile else "")
        ttk.Entry(form_frame, textvariable=name_var, width=40).grid(row=0, column=1, pady=5, padx=5)
        
        # Typ
        ttk.Label(form_frame, text="Typ:").grid(row=1, column=0, sticky=tk.W, pady=5)
        type_var = tk.StringVar(value=profile.get("type", "pfx") if profile else "pfx")
        type_frame = ttk.Frame(form_frame)
        type_frame.grid(row=1, column=1, sticky=tk.W, pady=5, padx=5)
        ttk.Radiobutton(type_frame, text="PFX soubor", variable=type_var, value="pfx").pack(side=tk.LEFT, padx=5)
        ttk.Radiobutton(type_frame, text="Token", variable=type_var, value="token").pack(side=tk.LEFT, padx=5)
        
        # Cesta
        ttk.Label(form_frame, text="Cesta:").grid(row=2, column=0, sticky=tk.W, pady=5)
        path_var = tk.StringVar(value=profile.get("path", "") if profile else "")
        path_frame = ttk.Frame(form_frame)
        path_frame.grid(row=2, column=1, sticky=tk.EW, pady=5, padx=5)
        form_frame.columnconfigure(1, weight=1)
        ttk.Entry(path_frame, textvariable=path_var, width=35).pack(side=tk.LEFT, fill=tk.X, expand=True)
        
        def browse_path():
            if type_var.get() == "pfx":
                file = filedialog.askopenfilename(title="Vyberte .pfx soubor", filetypes=[("PFX", "*.pfx *.p12"), ("Vše", "*.*")])
            else:
                file = filedialog.askopenfilename(title="Vyberte PKCS#11 knihovnu", filetypes=[("DLL", "*.dll"), ("Vše", "*.*")])
            if file:
                path_var.set(file)
        
        ttk.Button(path_frame, text="Procházet...", command=browse_path).pack(side=tk.LEFT, padx=5)
        
        # Heslo (pro PFX)
        ttk.Label(form_frame, text="Heslo (PFX):").grid(row=3, column=0, sticky=tk.W, pady=5)
        password_var = tk.StringVar(value=profile.get("password", "") if profile else "")
        ttk.Entry(form_frame, textvariable=password_var, width=40, show="*").grid(row=3, column=1, pady=5, padx=5)
        
        # Label (pro Token)
        ttk.Label(form_frame, text="Label (Token):").grid(row=4, column=0, sticky=tk.W, pady=5)
        label_var = tk.StringVar(value=profile.get("label", "") if profile else "")
        ttk.Entry(form_frame, textvariable=label_var, width=40).grid(row=4, column=1, pady=5, padx=5)
        
        # Tlačítka
        btn_frame = ttk.Frame(dialog)
        btn_frame.pack(fill=tk.X, padx=10, pady=10)
        
        def save():
            name = name_var.get().strip()
            if not name:
                messagebox.showerror("Chyba", "Název profilu je povinný.")
                return
            
            profile_data = {
                "name": name,
                "type": type_var.get(),
                "path": path_var.get().strip()
            }
            
            if type_var.get() == "pfx" and password_var.get():
                profile_data["password"] = password_var.get()
            elif type_var.get() == "token":
                if label_var.get():
                    profile_data["label"] = label_var.get()
            
            if profile:
                # Úprava existujícího
                if self.config_manager.update_signing_profile(profile.get("name"), profile_data):
                    messagebox.showinfo("Úspěch", "Profil byl aktualizován.")
                    refresh_callback()
                    self._load_profiles()
                    dialog.destroy()
            else:
                # Nový profil
                if self.config_manager.add_signing_profile(profile_data):
                    messagebox.showinfo("Úspěch", "Profil byl přidán.")
                    refresh_callback()
                    self._load_profiles()
                    dialog.destroy()
                else:
                    messagebox.showerror("Chyba", "Nepodařilo se přidat profil. Možná už existuje profil se stejným názvem.")
        
        ttk.Button(btn_frame, text="Uložit", command=save).pack(side=tk.RIGHT, padx=5)
        ttk.Button(btn_frame, text="Zrušit", command=dialog.destroy).pack(side=tk.RIGHT, padx=5)
    
    def _edit_tsa_profile(self, profile, refresh_callback):
        """Dialog pro úpravu/přidání TSA profilu"""
        dialog = tk.Toplevel(self.root)
        dialog.title("TSA profil" if profile else "Nový TSA profil")
        dialog.geometry("500x300")
        dialog.transient(self.root)
        dialog.grab_set()
        
        # Formulář
        form_frame = ttk.Frame(dialog, padding=10)
        form_frame.pack(fill=tk.BOTH, expand=True)
        
        # Název
        ttk.Label(form_frame, text="Název:").grid(row=0, column=0, sticky=tk.W, pady=5)
        name_var = tk.StringVar(value=profile.get("name", "") if profile else "")
        ttk.Entry(form_frame, textvariable=name_var, width=40).grid(row=0, column=1, pady=5, padx=5)
        
        # URL
        ttk.Label(form_frame, text="URL:").grid(row=1, column=0, sticky=tk.W, pady=5)
        url_var = tk.StringVar(value=profile.get("url", "http://tsa.postsignum.cz/tsp") if profile else "http://tsa.postsignum.cz/tsp")
        ttk.Entry(form_frame, textvariable=url_var, width=40).grid(row=1, column=1, pady=5, padx=5)
        
        # Uživatel
        ttk.Label(form_frame, text="Uživatel:").grid(row=2, column=0, sticky=tk.W, pady=5)
        username_var = tk.StringVar(value=profile.get("username", "") if profile else "")
        ttk.Entry(form_frame, textvariable=username_var, width=40).grid(row=2, column=1, pady=5, padx=5)
        
        # Heslo
        ttk.Label(form_frame, text="Heslo:").grid(row=3, column=0, sticky=tk.W, pady=5)
        password_var = tk.StringVar(value=profile.get("password", "") if profile else "")
        ttk.Entry(form_frame, textvariable=password_var, width=40, show="*").grid(row=3, column=1, pady=5, padx=5)
        
        # Tlačítka
        btn_frame = ttk.Frame(dialog)
        btn_frame.pack(fill=tk.X, padx=10, pady=10)
        
        def save():
            name = name_var.get().strip()
            if not name:
                messagebox.showerror("Chyba", "Název profilu je povinný.")
                return
            
            url = url_var.get().strip()
            if not url:
                messagebox.showerror("Chyba", "URL je povinná.")
                return
            
            profile_data = {
                "name": name,
                "url": url,
                "username": username_var.get().strip(),
                "password": password_var.get()
            }
            
            if profile:
                # Úprava existujícího
                if self.config_manager.update_tsa_profile(profile.get("name"), profile_data):
                    messagebox.showinfo("Úspěch", "TSA profil byl aktualizován.")
                    refresh_callback()
                    self._load_profiles()
                    dialog.destroy()
            else:
                # Nový profil
                if self.config_manager.add_tsa_profile(profile_data):
                    messagebox.showinfo("Úspěch", "TSA profil byl přidán.")
                    refresh_callback()
                    self._load_profiles()
                    dialog.destroy()
                else:
                    messagebox.showerror("Chyba", "Nepodařilo se přidat profil. Možná už existuje profil se stejným názvem.")
        
        ttk.Button(btn_frame, text="Uložit", command=save).pack(side=tk.RIGHT, padx=5)
        ttk.Button(btn_frame, text="Zrušit", command=dialog.destroy).pack(side=tk.RIGHT, padx=5)


def main():
    """Hlavní entry point"""
    # Použijeme TkinterDnD pokud je dostupný
    if DND_AVAILABLE:
        root = TkinterDnD.Tk()
    else:
        root = tk.Tk()
    
    app = PDFConverterApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
