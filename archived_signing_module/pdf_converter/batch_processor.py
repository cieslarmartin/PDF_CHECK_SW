# batch_processor.py
# Dávkové zpracování PDF souborů - kompletní flow
# Build 1.1 | © 2025 Ing. Martin Cieślar

import os
import shutil
import logging
from pathlib import Path
from dataclasses import dataclass
from typing import List, Optional, Callable
from concurrent.futures import ThreadPoolExecutor, as_completed

from .signature_remover import remove_signatures
from .pdfa_converter import convert_to_pdfa
from .signer import sign_pdf, SigningOptions

logger = logging.getLogger(__name__)


@dataclass
class ProcessingOptions:
    """Nastavení pro dávkové zpracování"""
    remove_signatures: bool = True      # Odstranit podpisy
    convert_to_pdfa: bool = True        # Převést na PDF/A
    pdfa_version: str = "3"             # Verze PDF/A (1, 2, 3)
    pdfa_conformance: str = "B"         # Conformance (A, B)
    sign_after: bool = False            # Podepsat po konverzi (Fáze 2)
    signing_options: Optional[SigningOptions] = None  # Nastavení podepisování
    output_dir: Optional[str] = None    # Výstupní složka
    overwrite: bool = False             # Přepsat existující soubory
    filename_prefix: Optional[str] = None  # Prefix pro název souboru
    filename_suffix: Optional[str] = None  # Suffix pro název souboru (např. "signed")
    use_auto_suffix: bool = True        # Použít automatický suffix podle operací
    use_signed_subfolder: bool = False  # Ukládat do podsložky "Signed"
    max_workers: int = 4                # Počet paralelních vláken


@dataclass
class ProcessingResult:
    """Výsledek zpracování jednoho souboru"""
    input_file: str
    output_file: Optional[str]
    success: bool
    steps: List[str]  # Provedené kroky
    error: Optional[str] = None


def process_single_pdf(input_path: str, options: ProcessingOptions) -> ProcessingResult:
    """
    Zpracuje jeden PDF soubor podle nastavených možností.

    Flow:
    1. (volitelně) Odstranění podpisů
    2. (volitelně) Převod na PDF/A
    3. (budoucnost) Podepsání

    Args:
        input_path: Cesta k vstupnímu PDF
        options: Nastavení zpracování

    Returns:
        ProcessingResult
    """
    input_path = Path(input_path)
    steps = []
    current_file = str(input_path)
    temp_files = []

    try:
        # Určíme výstupní složku
        if options.output_dir:
            output_dir = Path(options.output_dir)
            output_dir.mkdir(parents=True, exist_ok=True)
        else:
            output_dir = input_path.parent
        
        # Pokud je aktivní podsložka "Signed", vytvoříme ji
        if options.use_signed_subfolder:
            signed_dir = output_dir / "Signed"
            signed_dir.mkdir(parents=True, exist_ok=True)
            output_dir = signed_dir

        # Určíme finální název souboru podle operací
        base_name = input_path.stem
        
        # Přidáme prefix pokud je zadán
        if options.filename_prefix:
            base_name = f"{options.filename_prefix}{base_name}"
        
        # Určíme suffix
        if options.use_auto_suffix:
            # Automatický suffix podle operací
            suffix_parts = []
            if options.remove_signatures:
                suffix_parts.append("unsigned")
            if options.convert_to_pdfa:
                suffix_parts.append(f"pdfa{options.pdfa_version}{options.pdfa_conformance.lower()}")
            if options.sign_after:
                suffix_parts.append("signed")
            
            if suffix_parts:
                auto_suffix = "_" + "_".join(suffix_parts)
            else:
                auto_suffix = "_copy"
            
            # Pokud je zadán vlastní suffix, použijeme ho místo automatického
            if options.filename_suffix:
                final_suffix = f"_{options.filename_suffix}"
            else:
                final_suffix = auto_suffix
        else:
            # Použijeme pouze vlastní suffix nebo žádný
            if options.filename_suffix:
                final_suffix = f"_{options.filename_suffix}"
            else:
                final_suffix = ""
        
        # Pokud se podepisuje, vždy přidáme "_signed" před příponu (pokud tam ještě není)
        if options.sign_after and "_signed" not in final_suffix:
            if final_suffix:
                final_suffix = f"{final_suffix}_signed"
            else:
                final_suffix = "_signed"
        
        final_name = f"{base_name}{final_suffix}.pdf"
        final_path = output_dir / final_name

        # Pokud soubor existuje a nechceme přepsat
        if final_path.exists() and not options.overwrite:
            counter = 1
            while final_path.exists():
                # Použijeme formát (01), (02), ... místo _1, _2
                final_path = output_dir / f"{base_name}{final_suffix}({counter:02d}).pdf"
                counter += 1

        # Krok 1: Odstranění podpisů
        if options.remove_signatures:
            # Pokud budeme dělat i konverzi, použijeme dočasný soubor
            if options.convert_to_pdfa:
                unsigned_path = output_dir / f"_temp_{input_path.stem}_unsigned.pdf"
                temp_files.append(unsigned_path)
            else:
                # Jinak přímo finální soubor
                unsigned_path = final_path

            success, message = remove_signatures(current_file, str(unsigned_path))

            if success:
                steps.append(f"Podpisy: {message}")
                current_file = str(unsigned_path)
            else:
                return ProcessingResult(
                    input_file=str(input_path),
                    output_file=None,
                    success=False,
                    steps=steps,
                    error=f"Odstranění podpisů selhalo: {message}"
                )

        # Krok 2: Převod na PDF/A
        if options.convert_to_pdfa:
            # PDF/A nemůže obsahovat podpisy - pokud nebyly odstraněny, odstraníme je teď
            if not options.remove_signatures:
                # Musíme odstranit podpisy před konverzí na PDF/A
                temp_unsigned = output_dir / f"_temp_{input_path.stem}_unsigned_for_pdfa.pdf"
                temp_files.append(temp_unsigned)
                
                success, message = remove_signatures(current_file, str(temp_unsigned))
                if success:
                    steps.append(f"Podpisy: {message} (automaticky před PDF/A konverzí)")
                    current_file = str(temp_unsigned)
                else:
                    return ProcessingResult(
                        input_file=str(input_path),
                        output_file=None,
                        success=False,
                        steps=steps,
                        error=f"PDF/A vyžaduje odstranění podpisů, ale odstranění selhalo: {message}"
                    )
            
            success, message = convert_to_pdfa(
                current_file,
                str(final_path),
                options.pdfa_version,
                options.pdfa_conformance
            )

            if success:
                steps.append(f"PDF/A: Převedeno na PDF/A-{options.pdfa_version}{options.pdfa_conformance}")
                current_file = str(final_path)
            else:
                return ProcessingResult(
                    input_file=str(input_path),
                    output_file=None,
                    success=False,
                    steps=steps,
                    error=f"Konverze na PDF/A selhala: {message}"
                )

        # Krok 3: Podepsání (Fáze 2) - PO konverzi na PDF/A
        if options.sign_after and options.signing_options:
            # Podepíšeme finální soubor (po PDF/A konverzi nebo po odstranění podpisů)
            # Vytvoříme nový soubor s _signed suffix
            signed_path = output_dir / f"{input_path.stem}_signed.pdf"
            
            # Pokud už máme finální soubor, použijeme ho jako vstup
            input_for_signing = current_file
            
            # Uložíme cestu k PDF/A souboru pro případ selhání podepisování
            pdfa_backup_path = current_file if options.convert_to_pdfa else None
            
            try:
                success, message = sign_pdf(input_for_signing, str(signed_path), options.signing_options)
                
                if success:
                    steps.append(f"Podpis: {message}")
                    current_file = str(signed_path)
                    # Aktualizujeme finální cestu
                    final_path = signed_path
                else:
                    # Podepisování selhalo - NEsmazeme PDF/A soubor
                    # Vrátíme PDF/A soubor jako výsledek, pokud existuje
                    if pdfa_backup_path and Path(pdfa_backup_path).exists():
                        logger.warning(f"Podepisování selhalo, ale PDF/A soubor je zachován: {pdfa_backup_path}")
                        return ProcessingResult(
                            input_file=str(input_path),
                            output_file=pdfa_backup_path,
                            success=True,  # PDF/A konverze byla úspěšná
                            steps=steps,
                            error=f"Podepisování selhalo: {message}. PDF/A soubor je zachován."
                        )
                    else:
                        return ProcessingResult(
                            input_file=str(input_path),
                            output_file=current_file if Path(current_file).exists() else None,
                            success=False,
                            steps=steps,
                            error=f"Podepisování selhalo: {message}"
                        )
            except Exception as e:
                logger.exception(f"Chyba při podepisování: {e}")
                # Necháme PDF/A soubor zachovaný
                if pdfa_backup_path and Path(pdfa_backup_path).exists():
                    logger.warning(f"Výjimka při podepisování, ale PDF/A soubor je zachován: {pdfa_backup_path}")
                    return ProcessingResult(
                        input_file=str(input_path),
                        output_file=pdfa_backup_path,
                        success=True,  # PDF/A konverze byla úspěšná
                        steps=steps,
                        error=f"Chyba při podepisování: {str(e)}. PDF/A soubor je zachován."
                    )
                else:
                    return ProcessingResult(
                        input_file=str(input_path),
                        output_file=current_file if Path(current_file).exists() else None,
                        success=False,
                        steps=steps,
                        error=f"Chyba při podepisování: {str(e)}"
                    )

        # Vyčistíme dočasné soubory
        for temp_file in temp_files:
            try:
                if temp_file.exists() and str(temp_file) != current_file:
                    temp_file.unlink()
            except Exception as e:
                logger.warning(f"Nelze smazat dočasný soubor {temp_file}: {e}")

        # Pokud jsme dělali pouze odstranění podpisů (bez PDF/A), ujistíme se že výstupní soubor existuje
        if options.remove_signatures and not options.convert_to_pdfa:
            # current_file by měl být finální soubor
            if not Path(current_file).exists():
                logger.error(f"Výstupní soubor neexistuje: {current_file}")
                return ProcessingResult(
                    input_file=str(input_path),
                    output_file=None,
                    success=False,
                    steps=steps,
                    error="Výstupní soubor nebyl vytvořen"
                )

        return ProcessingResult(
            input_file=str(input_path),
            output_file=current_file,
            success=True,
            steps=steps
        )

    except Exception as e:
        logger.exception(f"Chyba při zpracování {input_path}: {e}")
        return ProcessingResult(
            input_file=str(input_path),
            output_file=None,
            success=False,
            steps=steps,
            error=str(e)
        )


def process_pdf_batch(
    input_files: List[str],
    options: ProcessingOptions,
    progress_callback: Optional[Callable[[int, int, str], None]] = None
) -> List[ProcessingResult]:
    """
    Dávkové zpracování více PDF souborů.

    Args:
        input_files: Seznam cest k PDF souborům
        options: Nastavení zpracování
        progress_callback: Callback pro průběh (current, total, filename)

    Returns:
        Seznam ProcessingResult
    """
    results = []
    total = len(input_files)

    # Pro malý počet souborů zpracujeme sekvenčně
    if total <= 2 or options.max_workers <= 1:
        for i, input_file in enumerate(input_files):
            if progress_callback:
                progress_callback(i + 1, total, Path(input_file).name)

            result = process_single_pdf(input_file, options)
            results.append(result)

        if progress_callback:
            progress_callback(total, total, "Hotovo")

    else:
        # Pro více souborů použijeme paralelní zpracování
        with ThreadPoolExecutor(max_workers=options.max_workers) as executor:
            future_to_file = {
                executor.submit(process_single_pdf, f, options): f
                for f in input_files
            }

            completed = 0
            for future in as_completed(future_to_file):
                input_file = future_to_file[future]
                completed += 1

                if progress_callback:
                    progress_callback(completed, total, Path(input_file).name)

                try:
                    result = future.result()
                    results.append(result)
                except Exception as e:
                    results.append(ProcessingResult(
                        input_file=input_file,
                        output_file=None,
                        success=False,
                        steps=[],
                        error=str(e)
                    ))

    return results


def get_pdf_files_from_folder(folder_path: str, recursive: bool = False) -> List[str]:
    """
    Získá seznam PDF souborů ze složky.

    Args:
        folder_path: Cesta ke složce
        recursive: Zda hledat i v podsložkách

    Returns:
        Seznam cest k PDF souborům
    """
    folder = Path(folder_path)
    if not folder.exists():
        return []

    if recursive:
        return [str(f) for f in folder.rglob("*.pdf")]
    else:
        return [str(f) for f in folder.glob("*.pdf")]


# Test
if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("Použití: python batch_processor.py <složka_s_pdf> [výstupní_složka]")
        print("\nPříklad:")
        print("  python batch_processor.py C:/Documents/PDFs C:/Documents/Output")
        sys.exit(1)

    input_folder = sys.argv[1]
    output_folder = sys.argv[2] if len(sys.argv) > 2 else None

    # Najdeme PDF soubory
    pdf_files = get_pdf_files_from_folder(input_folder)
    print(f"Nalezeno {len(pdf_files)} PDF souborů")

    if not pdf_files:
        print("Žádné PDF soubory nenalezeny.")
        sys.exit(0)

    # Nastavení
    options = ProcessingOptions(
        remove_signatures=True,
        convert_to_pdfa=True,
        pdfa_version="3",
        pdfa_conformance="B",
        output_dir=output_folder,
        overwrite=False
    )

    # Progress callback
    def progress(current, total, filename):
        print(f"[{current}/{total}] {filename}")

    # Zpracování
    results = process_pdf_batch(pdf_files, options, progress)

    # Výsledky
    print("\n" + "=" * 50)
    success_count = sum(1 for r in results if r.success)
    print(f"Hotovo: {success_count}/{len(results)} úspěšně")

    for r in results:
        status = "✓" if r.success else "✗"
        print(f"{status} {Path(r.input_file).name}")
        for step in r.steps:
            print(f"    {step}")
        if r.error:
            print(f"    CHYBA: {r.error}")
