# tsa_registry.py
# Registr TSA autorit platných pro ISSŘ (ČR). Stejná logika jako na webu.

DEFAULT_TSA_REGISTRY = [
    {
        "display_name": "PostSignum",
        "keywords": ["postsignum", "PostSignum TSA"],
        "is_qualified": True,
    },
    {
        "display_name": "I.CA",
        "keywords": ["i.ca", "I.CA"],
        "is_qualified": True,
    },
    {
        "display_name": "eIdentity",
        "keywords": ["eidentity", "eIdentity"],
        "is_qualified": True,
    },
]


def is_tsa_issuer_qualified(tsa_issuer, registry):
    """
    Vyhodnotí, zda je vyextrahovaný tsa_issuer v registru jako kvalifikovaná autorita (platná pro ISSŘ).
    Porovnání: case-insensitive substring match na pole keywords.
    """
    if not tsa_issuer or not isinstance(tsa_issuer, str):
        return False
    tsa_lower = tsa_issuer.strip().lower()
    if not tsa_lower or tsa_lower == "—":
        return False
    if not registry or not isinstance(registry, list):
        return False
    for entry in registry:
        if not entry.get("is_qualified"):
            continue
        keywords = entry.get("keywords") or []
        for kw in keywords:
            if kw and isinstance(kw, str) and kw.lower() in tsa_lower:
                return True
    return False
