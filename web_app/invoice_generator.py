# invoice_generator.py – generování PDF faktury (daňový doklad pro neplátce DPH)
# Redesign dle vzoru: hlavička FAKTURA | DOKLAD Č., sloupce Dodavatel/Odběratel, platební blok, tabulka, pata, QR platba.
# Unicode: DejaVu/Arial.

import os
import io
import logging
import traceback
import re
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

INVOICES_DIR = os.path.join(os.path.dirname(__file__), 'data', 'invoices')
FONTS_DIR = os.path.join(os.path.dirname(__file__), 'fonts')


def _get_unicode_font_path():
    """Vrátí (cesta_regular, cesta_bold nebo None) pro TrueType font s Unicode (DejaVu/Arial)."""
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


def _cz_account_to_iban(account_with_code):
    """
    Převod českého čísla účtu (172912882/0300) na IBAN pro QR platbu (SPD).
    Vrátí řetězec CZ + 2 kontrolní číslice + 4 kód banky + 14 číslic (6 prefix + 8–10 číslo účtu).
    """
    s = (account_with_code or '').replace(' ', '').strip()
    if not s or '/' not in s:
        return None
    parts = s.split('/', 1)
    account_part = re.sub(r'[^0-9]', '', parts[0])
    bank_code = re.sub(r'[^0-9]', '', parts[1])[:4].zfill(4)
    if len(bank_code) != 4 or not account_part:
        return None
    # Prefix (první část před pomlčkou) a základní část – zde jednoduchý tvar: pouze číslo účtu
    if '-' in account_part:
        prefix, base = account_part.split('-', 1)
        prefix = prefix.zfill(6)[:6]
        base = base.zfill(10)[-10:]
    else:
        prefix = '000000'
        base = account_part.zfill(10)[-10:]
    bban = bank_code + prefix + base  # 4 + 6 + 10 = 20 znaků
    # Kontrolní číslice IBAN: (BBAN + "CZ00") jako číslo mod 97, check = 98 - mod
    def mod97(s):
        n = 0
        for c in s:
            if c.isalpha():
                n = n * 10 + (ord(c.upper()) - ord('A') + 10) if ord(c.upper()) <= ord('Z') else n
            else:
                n = n * 10 + int(c)
        return n % 97
    # IBAN check digits: (BBAN + "CZ00") převedeno na číslo, mod 97, check = 98 - mod
    check_str = bban + 'CZ00'
    num_str = ''
    for c in check_str:
        if c.isalpha():
            num_str += str(ord(c.upper()) - ord('A') + 10)  # C=12, Z=35
        else:
            num_str += c
    remainder = 0
    for i in range(0, len(num_str), 9):
        chunk = num_str[i:i+9]
        remainder = (remainder * (10 ** len(chunk)) + int(chunk)) % 97
    check = 98 - remainder
    return 'CZ' + str(check).zfill(2) + bban


def _spayd_string(iban, amount_czk, vs, message='Faktura DokuCheck'):
    """SPAYD řetězec pro QR platbu. iban může být CZ IBAN nebo None (pak vrátí None)."""
    acc = (iban or '').replace(' ', '').strip()
    if not acc:
        return None
    if not acc.upper().startswith('CZ'):
        acc = 'CZ' + acc
    acc = acc[:24]
    if len(acc) < 24:
        return None
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
                         invoice_number=None, supplier_trade_register=None, output_dir=None,
                         supplier_bank_name=None, supplier_phone=None, supplier_email=None):
    """
    Vygeneruje PDF fakturu (daňový doklad) pro neplátce DPH.
    Redesign: hlavička FAKTURA vlevo / DOKLAD Č. vpravo, sloupce Dodavatel|Odběratel,
    platební blok, tabulka "Fakturujeme Vám za:", CELKEM K ÚHRADĚ, pata Vystavil/Telefon/E-mail, QR kód dole.
    Pro QR platbu: pokud je bank_iban vyplněn, použije se; jinak se z bank_account (172912882/0300) převede na IBAN.
    Unicode font (DejaVu/Arial). Při chybě vrátí None a zapíše do logu.
    """
    save_dir = (output_dir or '').strip() or INVOICES_DIR
    try:
        os.makedirs(save_dir, exist_ok=True)
    except Exception:
        if save_dir == INVOICES_DIR:
            try:
                _ensure_invoices_dir()
            except Exception:
                return None
        else:
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

    try:
        _name = supplier_name or 'Ing. Martin Cieślar'
        _addr = supplier_address or 'Porubská 1, 742 83 Klimkovice – Václavovice'
        _ico = supplier_ico or '04830661'
        _bank_name = (supplier_bank_name or '').strip() or 'ČSOB'
        _account_display = (bank_account or bank_iban or '').strip()
        _phone = (supplier_phone or '').strip()
        _email = (supplier_email or '').strip()
        zivnost = (supplier_trade_register or '').strip() or 'Fyzická osoba zapsaná v Živnostenském rejstříku vedeném na Magistrátu města Ostrava.'
        dph_text = 'Nejsem plátce DPH.'

        # IBAN pro QR: preferujeme vyplněný bank_iban, jinak převod z CZ účtu
        iban_for_qr = (bank_iban or '').replace(' ', '').strip()
        if not iban_for_qr and bank_account and '/' in str(bank_account):
            iban_for_qr = _cz_account_to_iban(bank_account)
        if iban_for_qr and not iban_for_qr.upper().startswith('CZ'):
            iban_for_qr = 'CZ' + iban_for_qr

        class SimpleFPDF(FPDF):
            def __init__(self, font_path, font_path_bold, *args, **kwargs):
                super().__init__(*args, **kwargs)
                self._font_path = font_path
                self._font_path_bold = font_path_bold

            def header(self):
                self.set_font('DejaVu', 'B', 16)
                self.cell(0, 8, 'FAKTURA', 0, 0, 'L')
                self.cell(0, 8, 'DOKLAD Č. {}'.format(cislo_faktury), 0, 1, 'R')
                self.ln(4)

            def footer(self):
                self.set_y(-28)
                self.set_font('DejaVu', '', 8)
                self.cell(0, 5, 'Vystavil: {}'.format(_name), 0, 1, 'L')
                self.cell(0, 5, 'Telefon: {}'.format(_phone or '—'), 0, 1, 'L')
                self.cell(0, 5, 'E-mail: {}'.format(_email or '—'), 0, 1, 'L')
                self.ln(2)
                self.cell(0, 5, 'DokuCheck | www.dokucheck.cz', 0, 1, 'C')

        pdf = SimpleFPDF(font_path, font_path_bold)
        pdf.add_font('DejaVu', '', font_path, uni=True)
        pdf.add_font('DejaVu', 'B', font_path_bold or font_path, uni=True)
        pdf.add_page()
        pdf.set_auto_page_break(True, margin=28)
        pdf.set_font('DejaVu', '', 10)

        # Dva sloupce: Dodavatel | Odběratel
        col_w = 92
        y_start = pdf.get_y()
        pdf.set_font('DejaVu', 'B', 10)
        pdf.cell(col_w, 6, 'Dodavatel', 0, 1)
        pdf.set_font('DejaVu', '', 9)
        pdf.multi_cell(col_w, 5, '{}\n{}\nIČ: {}\n{}\n{}'.format(_name, _addr, _ico, zivnost, dph_text))
        y_end_left = pdf.get_y()
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

        # Platební blok: Banka, Číslo účtu, Variabilní symbol, Datum vystavení, Datum splatnosti
        pdf.set_font('DejaVu', 'B', 10)
        pdf.cell(0, 6, 'Platební údaje', 0, 1)
        pdf.set_font('DejaVu', '', 9)
        pdf.cell(0, 5, 'Banka: {}'.format(_bank_name), 0, 1)
        pdf.cell(0, 5, 'Číslo účtu: {}'.format(_account_display or '—'), 0, 1)
        pdf.cell(0, 5, 'Variabilní symbol: {}'.format(order_id), 0, 1)
        pdf.cell(0, 5, 'Datum vystavení: {}   |   Datum splatnosti: {}'.format(datum_vystaveni, datum_splatnosti), 0, 1)
        pdf.ln(4)

        # Tabulka: Fakturujeme Vám za: / Množství / Cena
        pdf.set_font('DejaVu', 'B', 10)
        pdf.cell(110, 7, 'Fakturujeme Vám za:', 1, 0)
        pdf.cell(25, 7, 'Množství', 1, 0)
        pdf.cell(35, 7, 'Cena (Kč)', 1, 1, 'R')
        pdf.set_font('DejaVu', '', 10)
        pdf.cell(110, 8, 'Licence DokuCheck PRO', 1, 0)
        pdf.cell(25, 8, '1', 1, 0)
        pdf.cell(35, 8, str(int(amount_czk)), 1, 1, 'R')
        pdf.set_font('DejaVu', 'B', 11)
        pdf.cell(110, 9, 'CELKEM K ÚHRADĚ', 1, 0)
        pdf.cell(25, 9, '1', 1, 0)
        pdf.cell(35, 9, str(int(amount_czk)), 1, 1, 'R')
        pdf.set_font('DejaVu', '', 10)
        pdf.ln(8)

        # QR kód SPAYD (dolní část faktury)
        spayd = _spayd_string(iban_for_qr, amount_czk, order_id, 'Faktura {}'.format(cislo_faktury))
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
                qr_path = os.path.join(save_dir, '_qr_temp_{}.png'.format(order_id))
                with open(qr_path, 'wb') as f:
                    f.write(buf.getvalue())
                if os.path.isfile(qr_path):
                    pdf.image(qr_path, x=10, y=pdf.get_y(), w=42)
                    try:
                        os.remove(qr_path)
                    except Exception:
                        pass
            except Exception as e:
                logger.warning('[invoice_generator] QR kód: %s', e)
                pdf.cell(0, 6, 'QR platba (SPAYD): účet nebyl k dispozici nebo chyba generování.', 0, 1)
        else:
            pdf.cell(0, 6, 'Pro QR platbu vyplňte v Nastavení firmy Číslo účtu a kód banky (např. 172912882/0300) nebo IBAN.', 0, 1)

        filename = 'faktura_{}.pdf'.format(order_id)
        filepath = os.path.join(save_dir, filename)
        pdf.output(filepath)
        return filepath

    except Exception as e:
        logger.error('[invoice_generator] Chyba pri generovani PDF: %s', e)
        logger.error(traceback.format_exc())
        return None
