# invoice_generator.py – generování PDF faktury s QR kódem (SPAYD)
# Knihovny: fpdf2, qrcode. Dodavatel: Ing. Martin Cieślar; odběratel z objednávky.

import os
import io
import logging
import traceback

logger = logging.getLogger(__name__)

# Cesta k složce faktur – vytvoří se včetně web_app/data/ při prvním volání
INVOICES_DIR = os.path.join(os.path.dirname(__file__), 'data', 'invoices')


def _ensure_invoices_dir():
    """Vytvoří složku web_app/data/invoices/ (a data/), pokud neexistuje. Vyhnutí se FileNotFoundError."""
    path = INVOICES_DIR
    try:
        os.makedirs(path, exist_ok=True)
    except Exception as e:
        print('[invoice_generator] Chyba pri vytvareni slozky {}: {}'.format(path, e))
        print(traceback.format_exc())
        raise
    return path


def _spayd_string(iban, amount_czk, vs, message='Faktura DokuCheck'):
    """Vytvoří SPAYD řetězec pro QR platbu (české banky). ACC = IBAN, AM = částka, X-VS = variabilní symbol."""
    acc = (iban or '').replace(' ', '').strip()
    if not acc:
        return None
    if not acc.upper().startswith('CZ'):
        acc = 'CZ' + acc
    acc = acc[:46]
    am = '{:.2f}'.format(float(amount_czk))
    parts = ['SPD', '1.0', 'ACC:{}'.format(acc), 'AM:{}'.format(am), 'CC:CZK']
    if vs:
        parts.append('X-VS:{}'.format(str(vs).strip()[:10]))
    if message:
        msg_clean = (message or '')[:60].replace('*', '%2A')
        parts.append('MSG:{}'.format(msg_clean))
    return '*'.join(parts)


def generate_invoice_pdf(order_id, jmeno_firma, ico, email, tarif, amount_czk,
                         supplier_name, supplier_address, supplier_ico, bank_iban, bank_account):
    """
    Vygeneruje PDF fakturu a uloží ji do web_app/data/invoices/faktura_{order_id}.pdf.
    Dodavatel z parametrů (fallback: Ing. Martin Cieślar), odběratel z objednávky.
    QR kód SPAYD: IBAN, částka, variabilní symbol (ID objednávky).
    Při chybě vypíše traceback do konzole a vrátí None.
    """
    try:
        _ensure_invoices_dir()
    except Exception:
        return None

    try:
        from fpdf import FPDF
    except ImportError:
        try:
            from fpdf2 import FPDF
        except ImportError:
            print('[invoice_generator] Chyba: nebyla nalezena knihovna fpdf2. Nainstalujte: pip install fpdf2')
            print(traceback.format_exc())
            return None

    try:
        # Výchozí údaje dodavatele: Ing. Martin Cieślar (doplňte adresu a IČO v Adminu nebo zde)
        _name = supplier_name or 'Ing. Martin Cieślar'
        _addr = supplier_address or 'Porubská 1, 742 83 Klimkovice – Václavovice'
        _ico = supplier_ico or '04830661'

        class SimpleFPDF(FPDF):
            def header(self):
                self.set_font('Helvetica', 'B', 14)
                self.cell(0, 8, 'FAKTURA', 0, 1, 'C')
                self.ln(4)

            def footer(self):
                self.set_y(-18)
                self.set_font('Helvetica', '', 8)
                self.cell(0, 6, 'DokuCheck | www.dokucheck.cz', 0, 1, 'C')
                self.cell(0, 6, 'Faktura vygenerována automaticky.', 0, 1, 'C')

        pdf = SimpleFPDF()
        pdf.add_page()
        pdf.set_auto_page_break(True, margin=18)
        pdf.set_font('Helvetica', '', 10)

        # Dodavatel
        pdf.set_font('Helvetica', 'B', 10)
        pdf.cell(0, 6, 'Dodavatel', 0, 1)
        pdf.set_font('Helvetica', '', 10)
        pdf.multi_cell(0, 5, '{}\n{}\nIČ: {}'.format(_name, _addr, _ico))
        pdf.ln(6)

        # Odběratel (z objednávky)
        pdf.set_font('Helvetica', 'B', 10)
        pdf.cell(0, 6, 'Odběratel', 0, 1)
        pdf.set_font('Helvetica', '', 10)
        pdf.multi_cell(0, 5, '{}\nIČ: {}\nE-mail: {}'.format(
            jmeno_firma or '—',
            ico or '—',
            email or '—'
        ))
        pdf.ln(8)

        # Tabulka položek
        pdf.set_font('Helvetica', 'B', 10)
        pdf.cell(100, 6, 'Položka', 1, 0)
        pdf.cell(30, 6, 'Množství', 1, 0)
        pdf.cell(30, 6, 'Cena (Kč)', 1, 1)
        pdf.set_font('Helvetica', '', 10)
        pdf.cell(100, 8, 'Licence DokuCheck PRO', 1, 0)
        pdf.cell(30, 8, '1', 1, 0)
        pdf.cell(30, 8, str(int(amount_czk)), 1, 1)
        pdf.ln(4)
        pdf.cell(0, 6, 'Variabilní symbol: {}'.format(order_id), 0, 1)
        pdf.cell(0, 6, 'Částka k úhradě: {} Kč'.format(int(amount_czk)), 0, 1)
        if bank_account or bank_iban:
            pdf.cell(0, 6, 'Účet: {}'.format(bank_iban or bank_account or ''), 0, 1)
        pdf.ln(8)

        # QR kód SPAYD (pokud máme IBAN/účet)
        spayd = _spayd_string(bank_iban or bank_account or '', amount_czk, order_id, 'Faktura {}'.format(order_id))
        if spayd:
            try:
                import qrcode
                qr = qrcode.QRCode(version=1, box_size=3, border=2)
                qr.add_data(spayd)
                qr.make(fit=True)
                img = qr.make_image(fill_color='black', back_color='white')
                buf = io.BytesIO()
                img.save(buf, format='PNG')
                buf.seek(0)
                qr_path = os.path.join(INVOICES_DIR, '_qr_temp_{}.png'.format(order_id))
                with open(qr_path, 'wb') as f:
                    f.write(buf.getvalue())
                if os.path.isfile(qr_path):
                    pdf.image(qr_path, x=10, y=pdf.get_y(), w=40)
                    try:
                        os.remove(qr_path)
                    except Exception:
                        pass
            except Exception as e:
                print('[invoice_generator] QR kód se nepodařilo vygenerovat:', e)
                print(traceback.format_exc())
                pdf.cell(0, 6, 'QR platba (SPAYD): {}'.format(spayd[:70] + '...'), 0, 1)
        else:
            pdf.cell(0, 6, 'Pro QR platbu nastavte v Adminu účet (IBAN).', 0, 1)

        filename = 'faktura_{}.pdf'.format(order_id)
        filepath = os.path.join(INVOICES_DIR, filename)
        try:
            pdf.output(filepath)
        except Exception as write_err:
            logger.error('[invoice_generator] Chyba pri zapisu PDF souboru %s: %s', filepath, write_err)
            logger.error(traceback.format_exc())
            return None
        return filepath

    except Exception as e:
        logger.error('[invoice_generator] Chyba pri generovani PDF faktury: %s', e)
        logger.error(traceback.format_exc())
        print('[invoice_generator] Chyba pri generovani PDF faktury:', e)
        print(traceback.format_exc())
        return None
