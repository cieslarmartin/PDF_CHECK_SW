# invoice_generator.py – generování PDF faktury (daňový doklad pro neplátce DPH)
# Knihovny: fpdf2, qrcode. Unicode: TrueType font (DejaVu nebo systémový Arial).

import os
import io
import logging
import traceback
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

INVOICES_DIR = os.path.join(os.path.dirname(__file__), 'data', 'invoices')
FONTS_DIR = os.path.join(os.path.dirname(__file__), 'fonts')


def _get_unicode_font_path():
    """Vrátí (cesta_regular, cesta_bold nebo None) pro TrueType font s Unicode."""
    dejaVu = os.path.join(FONTS_DIR, 'DejaVuSans.ttf')
    dejaVuBold = os.path.join(FONTS_DIR, 'DejaVuSans-Bold.ttf')
    if os.path.isfile(dejaVu):
        return (dejaVu, dejaVuBold if os.path.isfile(dejaVuBold) else None)
    if os.name == 'nt':
        arial = os.path.join(os.environ.get('SystemRoot', 'C:\\Windows'), 'Fonts', 'arial.ttf')
        if os.path.isfile(arial):
            return (arial, None)
    for path in ('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf',
                 '/usr/share/fonts/TTF/DejaVuSans.ttf'):
        if os.path.isfile(path):
            bold = path.replace('DejaVuSans.ttf', 'DejaVuSans-Bold.ttf')
            return (path, bold if os.path.isfile(bold) else None)
    return (None, None)


def _ensure_invoices_dir():
    path = INVOICES_DIR
    try:
        os.makedirs(path, exist_ok=True)
    except Exception as e:
        print('[invoice_generator] Chyba pri vytvareni slozky {}: {}'.format(path, e))
        print(traceback.format_exc())
        raise
    return path


def _spayd_string(iban, amount_czk, vs, message='Faktura DokuCheck'):
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
                         supplier_name, supplier_address, supplier_ico, bank_iban, bank_account,
                         invoice_number=None):
    """
    Vygeneruje PDF fakturu (daňový doklad) pro neplátce DPH a uloží do data/invoices/.
    invoice_number: číslo ve tvaru RRMMNNN (např. 2502001). Pokud chybí, použije se order_id.
    Používá Unicode font (DejaVu/Arial). Při chybě vrátí None a zapíše do logu.
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
            logger.error('[invoice_generator] Nainstalujte: pip install fpdf2')
            return None

    font_path, font_path_bold = _get_unicode_font_path()
    if not font_path or not os.path.isfile(font_path):
        logger.error('[invoice_generator] Nenalezen font s Unicode. Přidejte web_app/fonts/DejaVuSans.ttf')
        return None

    cislo_faktury = (invoice_number or str(order_id)).strip()
    today = datetime.now()
    datum_vystaveni = today.strftime('%d.%m.%Y')
    datum_splatnosti = (today + timedelta(days=14)).strftime('%d.%m.%Y')
    datum_plneni = datum_vystaveni

    try:
        _name = supplier_name or 'Ing. Martin Cieślar'
        _addr = supplier_address or 'Porubská 1, 742 83 Klimkovice – Václavovice'
        _ico = supplier_ico or '04830661'
        zivnost = 'Fyzická osoba zapsaná v Živnostenském rejstříku vedeném na Magistrátu města Ostrava.'
        dph_text = 'Nejsem plátce DPH.'

        class SimpleFPDF(FPDF):
            def __init__(self, font_path, font_path_bold, *args, **kwargs):
                super().__init__(*args, **kwargs)
                self._font_path = font_path
                self._font_path_bold = font_path_bold

            def header(self):
                self.set_font('DejaVu', 'B', 12)
                self.cell(0, 6, 'Faktura - Daňový doklad č. {}'.format(cislo_faktury), 0, 1, 'C')
                self.ln(2)

            def footer(self):
                self.set_y(-18)
                self.set_font('DejaVu', '', 8)
                self.cell(0, 6, 'DokuCheck | www.dokucheck.cz', 0, 1, 'C')
                self.cell(0, 6, 'Faktura vygenerována automaticky.', 0, 1, 'C')

        pdf = SimpleFPDF(font_path, font_path_bold)
        pdf.add_font('DejaVu', '', font_path, uni=True)
        pdf.add_font('DejaVu', 'B', font_path_bold or font_path, uni=True)
        pdf.add_page()
        pdf.set_auto_page_break(True, margin=18)
        pdf.set_font('DejaVu', '', 10)

        # Datumy (jedna řádka)
        pdf.set_font('DejaVu', '', 9)
        pdf.cell(0, 5, 'Datum vystavení: {}   |   Datum splatnosti: {}   |   Datum uskutečnění zdanitelného plnění: {}'.format(
            datum_vystaveni, datum_splatnosti, datum_plneni), 0, 1)
        pdf.ln(4)

        # Dva sloupce: Dodavatel | Odběratel
        col_w = 92
        y_start = pdf.get_y()
        # Levý sloupec – Dodavatel
        pdf.set_font('DejaVu', 'B', 10)
        pdf.cell(col_w, 6, 'Dodavatel', 0, 1)
        pdf.set_font('DejaVu', '', 9)
        pdf.multi_cell(col_w, 5, '{}\n{}\nIČ: {}\n{}\n{}'.format(_name, _addr, _ico, zivnost, dph_text))
        y_end_left = pdf.get_y()
        # Pravý sloupec – Odběratel
        pdf.set_xy(10 + col_w + 6, y_start)
        pdf.set_font('DejaVu', 'B', 10)
        pdf.cell(col_w, 6, 'Odběratel', 0, 1)
        pdf.set_font('DejaVu', '', 9)
        pdf.multi_cell(col_w, 5, '{}\nIČ: {}\nE-mail: {}'.format(
            jmeno_firma or '—',
            ico or '—',
            email or '—'
        ))
        pdf.set_y(max(y_end_left, pdf.get_y()) + 6)

        # Tabulka položek (cena zarovnaná vpravo)
        pdf.set_font('DejaVu', 'B', 10)
        pdf.cell(100, 6, 'Položka', 1, 0)
        pdf.cell(25, 6, 'Množství', 1, 0)
        pdf.cell(35, 6, 'Cena (Kč)', 1, 1, 'R')
        pdf.set_font('DejaVu', '', 10)
        pdf.cell(100, 8, 'Licence DokuCheck PRO', 1, 0)
        pdf.cell(25, 8, '1', 1, 0)
        pdf.cell(35, 8, str(int(amount_czk)), 1, 1, 'R')
        pdf.ln(4)
        pdf.cell(0, 6, 'Variabilní symbol: {}'.format(order_id), 0, 1)
        pdf.cell(0, 6, 'Částka k úhradě: {} Kč'.format(int(amount_czk)), 0, 1)
        if bank_account or bank_iban:
            pdf.cell(0, 6, 'Účet: {}'.format(bank_iban or bank_account or ''), 0, 1)
        pdf.ln(8)

        # QR kód SPAYD
        spayd = _spayd_string(bank_iban or bank_account or '', amount_czk, order_id, 'Faktura {}'.format(cislo_faktury))
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
                logger.warning('[invoice_generator] QR kód: %s', e)
                pdf.cell(0, 6, 'QR platba (SPAYD): {}'.format(spayd[:70] + '...'), 0, 1)
        else:
            pdf.cell(0, 6, 'Pro QR platbu nastavte v Adminu účet (IBAN).', 0, 1)

        filename = 'faktura_{}.pdf'.format(order_id)
        filepath = os.path.join(INVOICES_DIR, filename)
        pdf.output(filepath)
        return filepath

    except Exception as e:
        logger.error('[invoice_generator] Chyba pri generovani PDF: %s', e)
        logger.error(traceback.format_exc())
        return None
