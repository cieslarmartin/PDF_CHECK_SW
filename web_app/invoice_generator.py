# invoice_generator.py – generování PDF faktury s QR kódem (SPAYD)
# Dodavatel z DB, odběratel z objednávky, položka: Licence DokuCheck PRO

import os
import io

INVOICES_DIR = os.path.join(os.path.dirname(__file__), 'data', 'invoices')


def _ensure_invoices_dir():
    path = INVOICES_DIR
    os.makedirs(path, exist_ok=True)
    return path


def _spayd_string(iban, amount_czk, vs, message='Faktura DokuCheck'):
    """Vytvoří SPAYD řetězec pro QR platbu (CZ)."""
    # ACC může být IBAN (max 46 znaků). Pro CZ účty: CZ + 22 číslic
    acc = (iban or '').replace(' ', '').strip()
    if not acc.upper().startswith('CZ'):
        acc = 'CZ' + acc
    am = '{:.2f}'.format(float(amount_czk))
    parts = ['SPD', '1.0', 'ACC:{}'.format(acc[:46]), 'AM:{}'.format(am), 'CC:CZK']
    if vs:
        parts.append('X-VS:{}'.format(str(vs).strip()[:10]))
    if message:
        msg_clean = (message or '')[:60].replace('*', '%2A')
        parts.append('MSG:{}'.format(msg_clean))
    return '*'.join(parts)


def generate_invoice_pdf(order_id, jmeno_firma, ico, email, tarif, amount_czk,
                         supplier_name, supplier_address, supplier_ico, bank_iban, bank_account):
    """
    Vygeneruje PDF fakturu a uloží ji na disk. Vrátí cestu k souboru nebo None.
    """
    _ensure_invoices_dir()
    try:
        from fpdf import FPDF
    except ImportError:
        try:
            from fpdf2 import FPDF
        except ImportError:
            return None

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
    pdf.multi_cell(0, 5, '{}\n{}\nIC: {}'.format(
        supplier_name or 'Ing. Martin Cieslar',
        supplier_address or 'Porubska 1, 742 83 Klimkovice',
        supplier_ico or '04830661'
    ))
    pdf.ln(6)

    # Odběratel
    pdf.set_font('Helvetica', 'B', 10)
    pdf.cell(0, 6, 'Odběratel', 0, 1)
    pdf.set_font('Helvetica', '', 10)
    pdf.multi_cell(0, 5, '{}\nIC: {}\nE-mail: {}'.format(
        jmeno_firma or '—',
        ico or '—',
        email or '—'
    ))
    pdf.ln(8)

    # Tabulka položek
    pdf.set_font('Helvetica', 'B', 10)
    pdf.cell(100, 6, 'Položka', 1, 0)
    pdf.cell(30, 6, 'Množství', 1, 0)
    pdf.cell(30, 6, 'Cena (Kc)', 1, 1)
    pdf.set_font('Helvetica', '', 10)
    pdf.cell(100, 8, 'Licence DokuCheck PRO', 1, 0)
    pdf.cell(30, 8, '1', 1, 0)
    pdf.cell(30, 8, str(int(amount_czk)), 1, 1)
    pdf.ln(4)
    pdf.cell(0, 6, 'Variabilni symbol: {}'.format(order_id), 0, 1)
    pdf.cell(0, 6, 'Castka k uhrade: {} Kc'.format(int(amount_czk)), 0, 1)
    if bank_account or bank_iban:
        pdf.cell(0, 6, 'Účet: {}'.format(bank_iban or bank_account or ''), 0, 1)
    pdf.ln(8)

    # QR kód (SPAYD)
    spayd = _spayd_string(bank_iban or bank_account or '', amount_czk, order_id, 'Faktura {}'.format(order_id))
    try:
        import qrcode
        qr = qrcode.QRCode(version=1, box_size=3, border=2)
        qr.add_data(spayd)
        qr.make(fit=True)
        img = qr.make_image(fill_color='black', back_color='white')
        buf = io.BytesIO()
        img.save(buf, format='PNG')
        qr_path = os.path.join(INVOICES_DIR, '_qr_temp_{}.png'.format(order_id))
        with open(qr_path, 'wb') as f:
            f.write(buf.getvalue())
        if os.path.isfile(qr_path):
            pdf.image(qr_path, x=10, y=pdf.get_y(), w=40)
            try:
                os.remove(qr_path)
            except Exception:
                pass
    except Exception:
        pdf.cell(0, 6, 'QR platba: {}'.format(spayd[:80] + '...'), 0, 1)

    filename = 'faktura_{}.pdf'.format(order_id)
    filepath = os.path.join(INVOICES_DIR, filename)
    try:
        pdf.output(filepath)
        return filepath
    except Exception:
        return None
