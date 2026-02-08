#!/usr/bin/env python3
# test_invoice.py – ladění vzhledu faktury (Unicode font, diakritika)
#
# Spuštění: z adresáře web_app příkazem  python test_invoice.py
# Vygeneruje test_faktura.pdf v aktuální složce.
#
# Závislosti: pip install fpdf2  (volitelně qrcode pro QR platbu)
# Font: Používá se Unicode font z invoice_generator (DejaVu nebo systémový Arial).
#       Pro plnou diakritiku přidejte web_app/fonts/DejaVuSans.ttf (viz fonts/README.txt).

import os
import sys
import shutil
import random

# Aby import fungoval při spuštění z kořene projektu i z web_app
_web_app = os.path.dirname(os.path.abspath(__file__))
if _web_app not in sys.path:
    sys.path.insert(0, _web_app)

from invoice_generator import generate_invoice_pdf

# --- Neměnné údaje dodavatele (Tvé údaje) ---
SUPPLIER_NAME = 'Ing. Martin Cieślar'
SUPPLIER_ADDRESS = 'Porubská 1, 742 83 Klimkovice – Václavovice'
SUPPLIER_ICO = '04830661'
BANK_IBAN = 'CZ65 0800 0000 1920 0014 5399'
BANK_ACCOUNT = '192000145399/0800'

# --- Testovací údaje odběratele (měnné – s diakritikou) ---
TEST_ORDER_ID = 'test'
TEST_JMENO_FIRMA = 'Pán s diakritikou řůščś'
# Náhodné 8místné IČO (pouze pro vizuální test)
TEST_ICO = str(random.randint(10000000, 99999999))
TEST_EMAIL = 'test.odberatel@example.cz'
TEST_TARIF = 'standard'
TEST_AMOUNT_CZK = 1990


def main():
    print('Generuji testovací fakturu (Unicode font: DejaVu/Arial)...')
    filepath = generate_invoice_pdf(
        order_id=TEST_ORDER_ID,
        jmeno_firma=TEST_JMENO_FIRMA,
        ico=TEST_ICO,
        email=TEST_EMAIL,
        tarif=TEST_TARIF,
        amount_czk=TEST_AMOUNT_CZK,
        supplier_name=SUPPLIER_NAME,
        supplier_address=SUPPLIER_ADDRESS,
        supplier_ico=SUPPLIER_ICO,
        bank_iban=BANK_IBAN,
        bank_account=BANK_ACCOUNT,
        invoice_number='2502TEST',
    )
    if not filepath or not os.path.isfile(filepath):
        print('Chyba: Fakturu se nepodařilo vygenerovat. Zkontrolujte font (web_app/fonts/DejaVuSans.ttf).')
        sys.exit(1)
    # Zkopírovat do aktuální složky jako test_faktura.pdf
    cwd = os.getcwd()
    dest = os.path.join(cwd, 'test_faktura.pdf')
    shutil.copy2(filepath, dest)
    print('Hotovo: {}'.format(dest))
    print('Faktura obsahuje: Dodavatel, Odběratel, položku (Licence DokuCheck PRO), platební údaje a QR kód.')


if __name__ == '__main__':
    main()
