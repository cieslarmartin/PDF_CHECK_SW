# csob_payments.py – párování příchozích plateb z e-mailových avíz ČSOB
# Parser podle skutečné šablony „Moje info - Avízo“ (noreply@csob.cz, DKIM d=csob.cz).

from __future__ import annotations

import hashlib
import imaplib
import logging
import os
import re
import secrets
from email import message_from_bytes
from email.header import decode_header, make_header
from email.utils import parseaddr
from html import unescape
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

CSOB_DKIM_DOMAIN = 'csob.cz'
CSOB_FROM_DOMAINS = ('csob.cz',)

WAITING_STATUSES = frozenset({
    'WAITING_PAYMENT', 'PAYMENT_SENT', 'NEW_ORDER', 'PENDING',
    'waiting_payment', 'payment_sent', 'new_order', 'pending',
})
ACTIVE_STATUSES = frozenset({'ACTIVE', 'active'})

STAV_NOVE = 'nove'
STAV_SHODA = 'shoda'
STAV_SPAROVANO = 'sparovano'
STAV_NESPAROVANO = 'nesparovano'
STAV_PODEZRELE = 'podezrele'
STAV_CHYBA_PARSOVANI = 'chyba_parsovani'
STAV_PREPLATEK = 'preplatek'
STAV_VYRIZENO = 'vyrizeno'


# ---------------------------------------------------------------------------
# Parsing
# ---------------------------------------------------------------------------

def _strip_html(html: str) -> str:
    text = re.sub(r'(?is)<script[^>]*>.*?</script>', ' ', html or '')
    text = re.sub(r'(?is)<style[^>]*>.*?</style>', ' ', text)
    text = re.sub(r'(?i)<br\s*/?>', '\n', text)
    text = re.sub(r'(?i)</p>', '\n', text)
    text = re.sub(r'(?i)</tr>', '\n', text)
    text = re.sub(r'(?i)</td>', '\t', text)
    text = re.sub(r'<[^>]+>', ' ', text)
    text = unescape(text)
    text = text.replace('\xa0', ' ').replace('\u00a0', ' ')
    text = re.sub(r'[ \t]+', ' ', text)
    text = re.sub(r'\n\s*\n+', '\n', text)
    return text.strip()


def _extract_table_fields(html: str) -> Dict[str, str]:
    """Extrahuje páry štítek → hodnota z HTML tabulky Parametry platby."""
    fields: Dict[str, str] = {}
    # quoted-printable už musí být dekódované; NBSP → mezera
    html_n = (html or '').replace('\xa0', ' ').replace('&nbsp;', ' ')
    row_re = re.compile(
        r'(?is)<tr[^>]*>\s*<td[^>]*>(.*?)</td>\s*<td[^>]*>(.*?)</td>\s*</tr>'
    )
    for m in row_re.finditer(html_n):
        label = _strip_html(m.group(1)).strip().rstrip(':')
        value = _strip_html(m.group(2)).strip()
        if label:
            fields[label] = value
    return fields


def parse_amount_to_haleru(amount_str: str) -> Optional[Tuple[int, str]]:
    """
    Převede řetězec typu '+1 590,00 CZK' / '+1590.00 CZK' na (haléře, měna).
    Oddělovač tisíců může být mezera nebo NBSP; desetinná čárka nebo tečka.
    """
    if not amount_str:
        return None
    s = str(amount_str).replace('\xa0', ' ').replace('\u00a0', ' ').strip()
    s = s.replace('+', '').strip()
    m = re.match(
        r'^([\d\s]+(?:[.,]\d{1,2})?)\s*([A-Za-z]{3})?$',
        s
    )
    if not m:
        return None
    num_part = m.group(1).replace(' ', '')
    mena = (m.group(2) or 'CZK').upper()
    if ',' in num_part and '.' in num_part:
        # 1.590,00 → evropský formát
        num_part = num_part.replace('.', '').replace(',', '.')
    elif ',' in num_part:
        num_part = num_part.replace(',', '.')
    try:
        crowns = float(num_part)
    except ValueError:
        return None
    return int(round(crowns * 100)), mena


def order_amount_to_haleru(order: dict) -> Optional[int]:
    """Částka objednávky v haléřích z amount_czk_final / amount_czk."""
    if not order:
        return None
    amt = order.get('amount_czk_final')
    if amt is None:
        amt = order.get('amount_czk')
    if amt is None:
        return None
    try:
        return int(round(float(amt) * 100))
    except (TypeError, ValueError):
        return None


def parse_csob_avizo_html(html: str) -> Dict[str, Any]:
    """
    Extrahuje pole z HTML těla avíza ČSOB.
    Vrací dict: castka_haleru, mena, variabilni_symbol, protiucet, datum_zauctovani,
    zprava_pro_prijemce, nazev_protistrany. Při chybě klíč 'error'.
    """
    if not html or not str(html).strip():
        return {'error': 'Prázdné HTML tělo'}
    fields = _extract_table_fields(html)
    if not fields:
        return {'error': 'Nepodařilo se najít tabulku Parametry platby'}

    # Částka – přesný štítek „Částka“, ne „Zůstatek…“ ani „Zaslaná částka…“
    castka_raw = fields.get('Částka') or fields.get('Castka')
    if not castka_raw:
        return {'error': 'Chybí řádek Částka', 'fields': fields}

    parsed_amt = parse_amount_to_haleru(castka_raw)
    if not parsed_amt:
        return {'error': 'Nepodařilo se naparsovat částku: {}'.format(castka_raw), 'fields': fields}
    castka_haleru, mena = parsed_amt

    vs = (fields.get('Variabilní symbol') or fields.get('Variabilni symbol') or '').strip() or None
    protiucet = (
        fields.get('Účet protistrany')
        or fields.get('Ucet protistrany')
        or fields.get('Účet protistrany')
        or ''
    ).strip() or None
    datum = (fields.get('Datum účtování') or fields.get('Datum uctovani') or '').strip() or None
    zprava = (fields.get('Zpráva pro příjemce') or fields.get('Zprava pro prijemce') or '').strip() or None
    nazev = (fields.get('Název protistrany') or fields.get('Nazev protistrany') or '').strip() or None

    return {
        'castka_haleru': castka_haleru,
        'mena': mena,
        'variabilni_symbol': vs,
        'protiucet': protiucet,
        'datum_zauctovani': datum,
        'zprava_pro_prijemce': zprava,
        'nazev_protistrany': nazev,
        'fields': fields,
    }


def _get_html_body(msg) -> str:
    """Vrátí HTML (nebo plain) tělo e-mailové zprávy jako unicode."""
    if msg.is_multipart():
        html_part = None
        plain_part = None
        for part in msg.walk():
            ctype = (part.get_content_type() or '').lower()
            if ctype == 'text/html' and html_part is None:
                html_part = part
            elif ctype == 'text/plain' and plain_part is None:
                plain_part = part
        part = html_part or plain_part
        if part is None:
            return ''
        payload = part.get_payload(decode=True) or b''
        charset = part.get_content_charset() or 'utf-8'
        return payload.decode(charset, errors='replace')
    payload = msg.get_payload(decode=True) or b''
    charset = msg.get_content_charset() or 'utf-8'
    return payload.decode(charset, errors='replace')


def _decode_header_value(raw) -> str:
    if raw is None:
        return ''
    try:
        return str(make_header(decode_header(raw)))
    except Exception:
        return str(raw)


def compute_message_hash(castka_haleru, variabilni_symbol, datum_zauctovani, protiucet, message_id) -> str:
    """Stabilní hash pro idempotenci: částka + VS + datum + protiúčet + Message-ID."""
    parts = [
        str(castka_haleru if castka_haleru is not None else ''),
        str(variabilni_symbol or '').strip(),
        str(datum_zauctovani or '').strip(),
        str(protiucet or '').strip(),
        str(message_id or '').strip(),
    ]
    raw = '|'.join(parts)
    return hashlib.sha256(raw.encode('utf-8')).hexdigest()


# ---------------------------------------------------------------------------
# DKIM
# ---------------------------------------------------------------------------

def extract_dkim_domain(raw_bytes: bytes) -> Optional[str]:
    """Vrátí d= z první DKIM-Signature hlavičky, nebo None."""
    try:
        text = raw_bytes.decode('utf-8', errors='replace')
    except Exception:
        text = raw_bytes.decode('latin-1', errors='replace')
    m = re.search(r'(?im)^DKIM-Signature:.*?[\s;]d=([^\s;]+)', text)
    if not m:
        # multiline folded
        m = re.search(r'(?is)DKIM-Signature:.*?[\s;]d=([^\s;]+)', text)
    return m.group(1).strip().lower() if m else None


def verify_dkim(raw_bytes: bytes, expected_domain: str = CSOB_DKIM_DOMAIN) -> Tuple[bool, str]:
    """
    Ověří DKIM podpis. Vyžaduje dkimpy (+ dnspython).
    Vrací (ok, důvod).
    """
    if not raw_bytes:
        return False, 'Prázdná zpráva'
    dkim_domain = extract_dkim_domain(raw_bytes)
    if not dkim_domain:
        return False, 'Chybí DKIM-Signature'
    if dkim_domain != expected_domain.lower():
        return False, 'DKIM doména {} neodpovídá {}'.format(dkim_domain, expected_domain)
    try:
        import dkim
    except ImportError:
        return False, 'Knihovna dkimpy není nainstalována'
    try:
        ok = dkim.verify(raw_bytes)
        if ok:
            return True, 'DKIM OK (d={})'.format(dkim_domain)
        return False, 'DKIM podpis neplatný (d={})'.format(dkim_domain)
    except Exception as e:
        return False, 'DKIM ověření selhalo: {}'.format(e)


def sender_domain_ok(msg) -> Tuple[bool, str]:
    """Kontrola, že From je z domény ČSOB (doplněk k DKIM, nestačí samo)."""
    from_hdr = _decode_header_value(msg.get('From', ''))
    _, addr = parseaddr(from_hdr)
    addr = (addr or '').lower().strip()
    if not addr or '@' not in addr:
        return False, 'Neplatný From: {}'.format(from_hdr)
    domain = addr.rsplit('@', 1)[-1]
    if domain in CSOB_FROM_DOMAINS or domain.endswith('.' + CSOB_DKIM_DOMAIN):
        return True, addr
    return False, 'From doména {} není ČSOB'.format(domain)


# ---------------------------------------------------------------------------
# Aktivace licence
# ---------------------------------------------------------------------------

def send_activation_for_order(db, order: dict, api_key: str, has_password: bool) -> bool:
    """Odešle aktivační e-mail zákazníkovi existující šablonou. Vrátí True při úspěchu."""
    from email_sender import get_activation_email_preview, send_email_with_attachment

    email = (order.get('email') or '').strip()
    if not email:
        return False
    user_name = (order.get('jmeno_firma') or email).strip()
    download_url = db.get_global_setting('download_url', '') or 'https://www.dokucheck.cz/download'
    base = (db.get_global_setting('base_url') or os.environ.get('BASE_URL', 'https://www.dokucheck.cz')).rstrip('/')
    login_url = base + '/portal'
    set_password_url = None
    if not has_password:
        set_pwd_token = secrets.token_urlsafe(32)
        if db.store_set_password_token(set_pwd_token, api_key, expires_at=None):
            set_password_url = base + '/portal/set-password?token=' + set_pwd_token

    subject, body_plain, body_html = get_activation_email_preview(
        user_email=email,
        password_plain=None,
        download_url=download_url,
        login_url=login_url,
        user_name=user_name,
        set_password_url=set_password_url,
    )
    invoice_path = None
    invoice_filename = None
    if order.get('invoice_path') and os.path.isfile(order.get('invoice_path')):
        invoice_path = order.get('invoice_path')
        display_num = (order.get('invoice_number') or order.get('order_display_number') or '').strip() or str(order.get('id'))
        invoice_filename = 'faktura_{}.pdf'.format(display_num)

    ok = send_email_with_attachment(
        to_email=email,
        subject=subject,
        body_plain=body_plain,
        body_html=body_html,
        attachment_path=invoice_path,
        attachment_filename=invoice_filename,
        append_footer=True,
    )
    try:
        db.log_email(email, subject, 'success' if ok else 'error')
    except Exception:
        pass
    return bool(ok)


def activate_order_from_payment(db, order: dict, platba: dict, admin_id=None, source: str = 'auto') -> Dict[str, Any]:
    """
    Vytvoří/přiřadí licenci, nastaví objednávku ACTIVE, odešle aktivační e-mail.
    source: 'auto' | 'manual_match' | 'manual_activate'
    """
    from settings_loader import normalize_tarif_slug

    order_id = order.get('id')
    email = (order.get('email') or '').strip()
    if not email:
        return {'ok': False, 'error': 'Objednávka nemá e-mail'}

    tier_row = db.get_tier_by_name(normalize_tarif_slug(order.get('tarif')))
    if not tier_row:
        return {'ok': False, 'error': 'Nepodařilo se určit tarif'}

    tier_id = tier_row.get('id')
    user_name = (order.get('jmeno_firma') or email).strip()
    existing = db.get_license_by_email(email)
    has_password = bool(existing and (existing.get('password_hash') or '').strip())

    if existing:
        ok = db.admin_assign_order_to_existing_license(
            existing['api_key'], tier_id, days=365, password_plain=None, user_name=user_name
        )
        if not ok:
            return {'ok': False, 'error': 'Aktualizace existující licence selhala'}
        api_key = existing['api_key']
    else:
        api_key = db.admin_create_license_by_tier_id(user_name, email, tier_id, days=365, password=None)
        if not api_key:
            return {'ok': False, 'error': 'Vytvoření licence selhalo'}

    db.update_pending_order_status(order_id, 'ACTIVE')

    mail_ok = False
    try:
        mail_ok = send_activation_for_order(db, order, api_key, has_password)
    except Exception as e:
        logger.exception('Aktivační e-mail selhal: %s', e)

    note = 'Aktivace ({}) platba #{} VS {} částka {} haléřů'.format(
        source, platba.get('id'), platba.get('variabilni_symbol'), platba.get('castka_haleru')
    )
    try:
        db.insert_payment_log(api_key, 'csob_aktivace', details=note)
    except Exception:
        pass

    update_kw = {
        'stav': STAV_SPAROVANO,
        'order_id': order_id,
        'poznamka': note,
        'zpracovano_at': __import__('datetime').datetime.now().isoformat(sep=' ', timespec='seconds'),
    }
    if admin_id is not None:
        update_kw['sparoval_admin_id'] = admin_id
    db.update_csob_platba(platba.get('id'), **update_kw)

    try:
        from email_sender import notify_admin
        notify_admin(
            'ČSOB: licence aktivována – objednávka #{}'.format(order.get('order_display_number') or order_id),
            '{}\nZákazník: {} ({})\nZdroj: {}\nE-mail odeslán: {}'.format(
                note, user_name, email, source, 'ano' if mail_ok else 'ne'
            ),
        )
    except Exception:
        pass

    return {'ok': True, 'api_key': api_key, 'mail_ok': mail_ok, 'order_id': order_id}


# ---------------------------------------------------------------------------
# Párování
# ---------------------------------------------------------------------------

def is_auto_activate_enabled(db) -> bool:
    return bool(db.get_setting_bool('auto_activate_csob', False))


def pair_payment(db, platba: dict, auto_activate: Optional[bool] = None) -> Dict[str, Any]:
    """
    Spáruje uloženou platbu s objednávkou podle přesného VS + částky na haléř.
    Bez platného dkim_ok nikdy neaktivuje.
    """
    if auto_activate is None:
        auto_activate = is_auto_activate_enabled(db)

    platba_id = platba.get('id')
    if not platba.get('dkim_ok'):
        db.update_csob_platba(
            platba_id,
            stav=STAV_PODEZRELE,
            poznamka='Bez platného DKIM – aktivace zakázána',
        )
        return {'ok': False, 'stav': STAV_PODEZRELE, 'reason': 'dkim'}

    vs = (platba.get('variabilni_symbol') or '').strip()
    castka = platba.get('castka_haleru')
    if not vs:
        db.update_csob_platba(
            platba_id,
            stav=STAV_NESPAROVANO,
            poznamka='Chybí variabilní symbol',
        )
        _notify_unmatched(db, platba, 'Chybí variabilní symbol')
        return {'ok': False, 'stav': STAV_NESPAROVANO, 'reason': 'missing_vs'}

    if castka is None:
        db.update_csob_platba(
            platba_id,
            stav=STAV_NESPAROVANO,
            poznamka='Chybí částka',
        )
        _notify_unmatched(db, platba, 'Chybí částka')
        return {'ok': False, 'stav': STAV_NESPAROVANO, 'reason': 'missing_amount'}

    order = db.get_pending_order_by_vs(vs)
    if not order:
        db.update_csob_platba(
            platba_id,
            stav=STAV_NESPAROVANO,
            poznamka='Neznámý VS {}'.format(vs),
        )
        _notify_unmatched(db, platba, 'Neznámý VS {}'.format(vs))
        return {'ok': False, 'stav': STAV_NESPAROVANO, 'reason': 'unknown_vs'}

    status = (order.get('status') or '').strip()
    if status in ACTIVE_STATUSES:
        db.update_csob_platba(
            platba_id,
            stav=STAV_PREPLATEK,
            order_id=order.get('id'),
            poznamka='Objednávka #{} už je ACTIVE – přeplatek'.format(order.get('order_display_number') or order.get('id')),
        )
        _notify_unmatched(db, platba, 'Přeplatek na už aktivní objednávku #{}'.format(
            order.get('order_display_number') or order.get('id')
        ))
        return {'ok': False, 'stav': STAV_PREPLATEK, 'reason': 'already_active', 'order_id': order.get('id')}

    if status not in WAITING_STATUSES and status.upper() not in {s.upper() for s in WAITING_STATUSES}:
        db.update_csob_platba(
            platba_id,
            stav=STAV_NESPAROVANO,
            order_id=order.get('id'),
            poznamka='Objednávka ve stavu {} – nelze párovat'.format(status),
        )
        _notify_unmatched(db, platba, 'Objednávka ve stavu {}'.format(status))
        return {'ok': False, 'stav': STAV_NESPAROVANO, 'reason': 'bad_status'}

    expected = order_amount_to_haleru(order)
    if expected is None or int(castka) != int(expected):
        db.update_csob_platba(
            platba_id,
            stav=STAV_NESPAROVANO,
            order_id=order.get('id'),
            poznamka='Částka nesedí: platba {} vs objednávka {} haléřů'.format(castka, expected),
        )
        _notify_unmatched(
            db, platba,
            'Částka nesedí (platba {} / objednávka {} haléřů), VS {}'.format(castka, expected, vs),
        )
        return {'ok': False, 'stav': STAV_NESPAROVANO, 'reason': 'amount_mismatch', 'order_id': order.get('id')}

    # Shoda VS + částka
    if not auto_activate:
        db.update_csob_platba(
            platba_id,
            stav=STAV_SHODA,
            order_id=order.get('id'),
            poznamka='Shoda VS+částka – autoaktivace vypnutá, čeká na ruční potvrzení',
        )
        try:
            from email_sender import notify_admin
            notify_admin(
                'ČSOB: shoda platby (autoaktivace VYPNUTÁ) VS {}'.format(vs),
                'Platba #{} sedí na objednávku #{} ({} Kč).\n'
                'Automatická aktivace je vypnutá – aktivujte ručně v adminu Příchozí platby.'.format(
                    platba_id,
                    order.get('order_display_number') or order.get('id'),
                    (expected or 0) / 100.0,
                ),
            )
        except Exception:
            pass
        return {'ok': True, 'stav': STAV_SHODA, 'order_id': order.get('id'), 'activated': False}

    result = activate_order_from_payment(db, order, platba, source='auto')
    return {
        'ok': result.get('ok'),
        'stav': STAV_SPAROVANO if result.get('ok') else STAV_NESPAROVANO,
        'order_id': order.get('id'),
        'activated': bool(result.get('ok')),
        'error': result.get('error'),
    }


def _notify_unmatched(db, platba, reason: str) -> None:
    try:
        from email_sender import notify_admin
        notify_admin(
            'ČSOB: nespárovaná platba',
            'Platba #{} – {}\nVS: {}\nČástka: {} haléřů\nProtiúčet: {}\nDatum: {}'.format(
                platba.get('id'),
                reason,
                platba.get('variabilni_symbol') or '—',
                platba.get('castka_haleru'),
                platba.get('protiucet') or '—',
                platba.get('datum_zauctovani') or '—',
            ),
        )
    except Exception:
        pass


# ---------------------------------------------------------------------------
# Zpracování raw e-mailu
# ---------------------------------------------------------------------------

def process_raw_email(db, raw_bytes: bytes, imap_uid: Optional[str] = None,
                      skip_dkim: bool = False, auto_activate: Optional[bool] = None) -> Dict[str, Any]:
    """
    Zpracuje jeden raw e-mail (bytes): DKIM → parse → insert (unique hash) → párování.
    skip_dkim=True jen pro unit testy parseru (v produkci nikdy).
    """
    if not raw_bytes:
        return {'ok': False, 'error': 'Prázdná zpráva'}

    msg = message_from_bytes(raw_bytes)
    message_id = (msg.get('Message-ID') or msg.get('Message-Id') or '').strip()
    from_ok, from_info = sender_domain_ok(msg)

    dkim_ok = False
    dkim_reason = ''
    if skip_dkim:
        dkim_ok = True
        dkim_reason = 'skip_dkim (test)'
    else:
        dkim_ok, dkim_reason = verify_dkim(raw_bytes)

    if not from_ok or not dkim_ok:
        # Podezřelé – uložit raw, nepárovat/neaktivovat
        h = compute_message_hash(None, None, None, None, message_id or hashlib.sha256(raw_bytes).hexdigest())
        existing = db.get_csob_platba_by_hash(h)
        if existing:
            return {'ok': True, 'duplicate': True, 'platba_id': existing.get('id'), 'stav': existing.get('stav')}
        note = 'Podezřelé: From={} ({}); DKIM={}'.format(from_info, 'OK' if from_ok else 'FAIL', dkim_reason)
        platba_id = db.insert_csob_platba(
            message_hash=h,
            imap_message_id=imap_uid or message_id,
            raw_email=raw_bytes.decode('utf-8', errors='replace'),
            dkim_ok=False,
            stav=STAV_PODEZRELE,
            poznamka=note,
        )
        if platba_id is None:
            existing = db.get_csob_platba_by_hash(h)
            return {'ok': True, 'duplicate': True, 'platba_id': existing.get('id') if existing else None}
        try:
            from email_sender import notify_admin
            notify_admin('ČSOB: podezřelý e-mail (DKIM/From)', note)
        except Exception:
            pass
        try:
            db.insert_system_log('WARNING', note)
        except Exception:
            pass
        return {'ok': False, 'stav': STAV_PODEZRELE, 'platba_id': platba_id, 'reason': note}

    html = _get_html_body(msg)
    parsed = parse_csob_avizo_html(html)
    if parsed.get('error'):
        h = compute_message_hash(None, None, None, None, message_id or hashlib.sha256(raw_bytes).hexdigest())
        existing = db.get_csob_platba_by_hash(h)
        if existing:
            return {'ok': True, 'duplicate': True, 'platba_id': existing.get('id'), 'stav': existing.get('stav')}
        note = 'Chyba parsování: {}'.format(parsed.get('error'))
        platba_id = db.insert_csob_platba(
            message_hash=h,
            imap_message_id=imap_uid or message_id,
            raw_email=raw_bytes.decode('utf-8', errors='replace'),
            dkim_ok=True,
            stav=STAV_CHYBA_PARSOVANI,
            poznamka=note,
        )
        if platba_id is None:
            existing = db.get_csob_platba_by_hash(h)
            return {'ok': True, 'duplicate': True, 'platba_id': existing.get('id') if existing else None}
        try:
            from email_sender import notify_admin
            notify_admin('ČSOB: chyba parsování avíza', note + '\nMessage-ID: ' + message_id)
        except Exception:
            pass
        try:
            db.insert_system_log('ERROR', note)
        except Exception:
            pass
        return {'ok': False, 'stav': STAV_CHYBA_PARSOVANI, 'platba_id': platba_id, 'error': parsed.get('error')}

    h = compute_message_hash(
        parsed.get('castka_haleru'),
        parsed.get('variabilni_symbol'),
        parsed.get('datum_zauctovani'),
        parsed.get('protiucet'),
        message_id,
    )
    existing = db.get_csob_platba_by_hash(h)
    if existing:
        return {'ok': True, 'duplicate': True, 'platba_id': existing.get('id'), 'stav': existing.get('stav')}

    nazev = parsed.get('nazev_protistrany') or ''
    note_info = 'Protistrana: {}'.format(nazev) if nazev else None
    platba_id = db.insert_csob_platba(
        message_hash=h,
        imap_message_id=imap_uid or message_id,
        castka_haleru=parsed.get('castka_haleru'),
        mena=parsed.get('mena'),
        variabilni_symbol=parsed.get('variabilni_symbol'),
        protiucet=parsed.get('protiucet'),
        datum_zauctovani=parsed.get('datum_zauctovani'),
        zprava_pro_prijemce=parsed.get('zprava_pro_prijemce'),
        raw_email=raw_bytes.decode('utf-8', errors='replace'),
        dkim_ok=True,
        stav=STAV_NOVE,
        poznamka=note_info,
    )
    if platba_id is None:
        existing = db.get_csob_platba_by_hash(h)
        return {'ok': True, 'duplicate': True, 'platba_id': existing.get('id') if existing else None}

    platba = db.get_csob_platba_by_id(platba_id)
    pair_result = pair_payment(db, platba, auto_activate=auto_activate)
    pair_result['platba_id'] = platba_id
    pair_result['parsed'] = {
        'castka_haleru': parsed.get('castka_haleru'),
        'variabilni_symbol': parsed.get('variabilni_symbol'),
        'mena': parsed.get('mena'),
    }
    return pair_result


# ---------------------------------------------------------------------------
# IMAP
# ---------------------------------------------------------------------------

def _imap_config() -> Dict[str, Any]:
    """IMAP údaje jen z env (nikdy z DB / gitu). Default user = cieslar@dokucheck.cz."""
    return {
        'host': (os.environ.get('IMAP_HOST') or 'imap.seznam.cz').strip(),
        'port': int(os.environ.get('IMAP_PORT', '993') or 993),
        'user': (os.environ.get('IMAP_USER') or 'cieslar@dokucheck.cz').strip(),
        'password': (os.environ.get('IMAP_PASSWORD') or '').strip(),
        'folder': (os.environ.get('IMAP_FOLDER') or 'INBOX').strip() or 'INBOX',
    }


def get_imap_status() -> Dict[str, Any]:
    """Stav IMAP konfigurace pro admin UI – heslo nikdy nevrací."""
    cfg = _imap_config()
    dkimpy_ok = False
    try:
        import dkim  # noqa: F401
        dkimpy_ok = True
    except ImportError:
        dkimpy_ok = False
    password_set = bool(cfg['password'])
    return {
        'host': cfg['host'],
        'port': cfg['port'],
        'user': cfg['user'],
        'folder': cfg['folder'],
        'password_set': password_set,
        'configured': password_set and bool(cfg['user']),
        'dkimpy_installed': dkimpy_ok,
    }


def test_imap_connection() -> Dict[str, Any]:
    """Ověří přihlášení k IMAP a počet UNSEEN. Heslo nevrací."""
    cfg = _imap_config()
    if not cfg['password']:
        return {
            'ok': False,
            'error': 'IMAP_PASSWORD není nastavené v env na serveru (PythonAnywhere → Environment variables).',
            'status': get_imap_status(),
        }
    try:
        mail = imaplib.IMAP4_SSL(cfg['host'], cfg['port'])
        mail.login(cfg['user'], cfg['password'])
        typ, _ = mail.select(cfg['folder'])
        if typ != 'OK':
            mail.logout()
            return {'ok': False, 'error': 'Nelze otevřít složku {}'.format(cfg['folder']), 'status': get_imap_status()}
        typ, data = mail.search(None, 'UNSEEN')
        unseen = len((data[0] or b'').split()) if typ == 'OK' else 0
        typ2, data2 = mail.search(None, 'FROM', 'csob.cz')
        csob_total = len((data2[0] or b'').split()) if typ2 == 'OK' else 0
        mail.logout()
        return {
            'ok': True,
            'unseen': unseen,
            'csob_from_count': csob_total,
            'status': get_imap_status(),
        }
    except Exception as e:
        logger.exception('IMAP test selhal: %s', e)
        return {'ok': False, 'error': str(e), 'status': get_imap_status()}


def fetch_and_process_imap(db, auto_activate: Optional[bool] = None, limit: int = 50,
                           include_seen: bool = False, seen_days: int = 14) -> Dict[str, Any]:
    """
    Načte zprávy z IMAP. Zpracuje jen ty od ČSOB (From/DKIM).
    - include_seen=False (default): jen UNSEEN
    - include_seen=True: FROM csob.cz za posledních seen_days dní (i přečtené) – pro ladění
    Cizí maily NEOZNAČÍ jako Seen. ČSOB avíza označí Seen až po zápisu do DB.
    """
    cfg = _imap_config()
    if not cfg['password']:
        return {
            'ok': False,
            'error': 'IMAP_PASSWORD není nastavené v env. Nastavte na PythonAnywhere a Reload.',
        }

    results: List[Dict[str, Any]] = []
    processed = 0
    skipped = 0
    duplicates = 0
    errors = 0

    try:
        mail = imaplib.IMAP4_SSL(cfg['host'], cfg['port'])
        mail.login(cfg['user'], cfg['password'])
        mail.select(cfg['folder'])

        if include_seen:
            from datetime import datetime, timedelta
            days = max(1, min(int(seen_days or 14), 90))
            since = (datetime.now() - timedelta(days=days)).strftime('%d-%b-%Y')
            # IMAP: FROM csob.cz SINCE ...
            typ, data = mail.search(None, 'FROM', 'csob.cz', 'SINCE', since)
            search_desc = 'FROM csob.cz SINCE {}'.format(since)
        else:
            typ, data = mail.search(None, 'UNSEEN')
            search_desc = 'UNSEEN'

        if typ != 'OK':
            mail.logout()
            return {'ok': False, 'error': 'IMAP SEARCH ({}) selhal: {}'.format(search_desc, typ)}

        ids = (data[0] or b'').split()
        for num in ids[:limit]:
            typ, msg_data = mail.fetch(num, '(RFC822)')
            if typ != 'OK' or not msg_data or not msg_data[0]:
                errors += 1
                continue
            raw = msg_data[0][1]
            if not isinstance(raw, (bytes, bytearray)):
                errors += 1
                continue
            raw_bytes = bytes(raw)

            # Rychlá předfiltr: jen From *@csob.cz nebo DKIM d=csob.cz
            msg = message_from_bytes(raw_bytes)
            from_ok, _ = sender_domain_ok(msg)
            dkim_domain = extract_dkim_domain(raw_bytes)
            looks_csob = from_ok or (dkim_domain == CSOB_DKIM_DOMAIN)
            if not looks_csob:
                skipped += 1
                continue  # nechat UNSEEN

            try:
                res = process_raw_email(
                    db, raw_bytes,
                    imap_uid=num.decode() if isinstance(num, bytes) else str(num),
                    auto_activate=auto_activate,
                )
                results.append(res)
                if res.get('duplicate'):
                    duplicates += 1
                else:
                    processed += 1
                # Označit Seen až po zápisu (i podezřelé/chyba – ať se neopakují)
                mail.store(num, '+FLAGS', '\\Seen')
            except Exception as e:
                logger.exception('Zpracování IMAP zprávy selhalo: %s', e)
                errors += 1
                results.append({'ok': False, 'error': str(e)})

        mail.logout()
    except Exception as e:
        logger.exception('IMAP selhalo: %s', e)
        return {'ok': False, 'error': str(e), 'results': results}

    return {
        'ok': True,
        'search': search_desc,
        'processed': processed,
        'duplicates': duplicates,
        'skipped_non_csob': skipped,
        'errors': errors,
        'results': results,
    }
