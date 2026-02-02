# machine_id.py
# Stabilní identifikátor počítače pro device locking (anti-sharing).
# © 2025 Ing. Martin Cieślar

import hashlib
import platform
import uuid
import os


def get_machine_id():
    """
    Vygeneruje stabilní unikátní ID stroje (hash MAC + OS info).
    Používá se v hlavičkách X-Machine-ID pro API.
    """
    try:
        # MAC adresa (na Windows/Linux stabilní)
        node = uuid.getnode()
        mac = ':'.join(('%012X' % node)[i:i+2] for i in range(0, 12, 2))
        # OS a hostname pro větší unikátnost
        os_name = platform.system()
        os_release = platform.release() or ''
        host = get_hostname() or ''
        raw = f"{mac}|{os_name}|{os_release}|{host}"
        return hashlib.sha256(raw.encode('utf-8', errors='replace')).hexdigest()[:32]
    except Exception:
        # Fallback: náhodný uuid převedený na hash (méně stabilní mezi restarty)
        return hashlib.sha256(str(uuid.uuid4()).encode()).hexdigest()[:32]


def get_hostname():
    """Vrátí hostname počítače (pro hlavičku X-Machine-Name)."""
    try:
        return platform.node() or os.environ.get('COMPUTERNAME', '') or os.environ.get('HOSTNAME', '') or 'unknown'
    except Exception:
        return 'unknown'
