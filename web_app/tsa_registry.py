# tsa_registry.py
# Whitelist TSA autorit platných pro ISSŘ (ČR). Kvalifikace z pevného seznamu v constants.

from constants import SUPPORTED_TSA_AUTHORITIES


def is_tsa_issuer_qualified(tsa_issuer):
    """
    Vyhodnotí, zda je vyextrahovaný tsa_issuer na whitelistu kvalifikovaných autorit (platné pro ISSŘ).
    Porovnání: case-insensitive – alespoň jeden řetězec z SUPPORTED_TSA_AUTHORITIES je obsažen v tsa_issuer jako substring.
    """
    if not tsa_issuer or not isinstance(tsa_issuer, str):
        return False
    tsa_lower = tsa_issuer.strip().lower()
    if not tsa_lower or tsa_lower == "—":
        return False
    for keyword in SUPPORTED_TSA_AUTHORITIES:
        if keyword and keyword.lower() in tsa_lower:
            return True
    return False
