# analytics_ua.py
# Parsování User-Agent a bot filtr pro first-party analytiku (bez cookies).

from __future__ import annotations

import hashlib
import re
from datetime import datetime, timezone


_BOT_PATTERNS = re.compile(
    r'(bot|crawler|spider|slurp|bingpreview|facebookexternalhit|embedly|'
    r'quora link preview|outbrain|pinterest|vkshare|w3c_validator|'
    r'whatsapp|telegram|preview|headlesschrome|phantomjs|selenium|'
    r'python-requests|curl|wget|httpclient|scrapy|semrush|ahrefs|'
    r'dotbot|petalbot|bytespider|gptbot|claudebot|anthropic|openai)',
    re.I,
)


def is_bot_user_agent(ua: str | None) -> bool:
    if not ua or not str(ua).strip():
        return True
    return bool(_BOT_PATTERNS.search(ua))


def parse_device_type(ua: str | None) -> str:
    u = (ua or '').lower()
    if not u:
        return 'unknown'
    if re.search(r'ipad|tablet|kindle|silk|(android(?!.*mobile))', u):
        return 'tablet'
    if re.search(r'mobi|iphone|ipod|android.*mobile|windows phone', u):
        return 'mobile'
    return 'desktop'


def parse_browser(ua: str | None) -> str:
    u = ua or ''
    if not u:
        return 'unknown'
    # Pořadí: Edge/Edg před Chrome, Firefox, Safari
    if re.search(r'Edg(?:e|A|iOS)?/', u):
        return 'Edge'
    if 'OPR/' in u or 'Opera' in u:
        return 'Opera'
    if 'Firefox/' in u or 'FxiOS/' in u:
        return 'Firefox'
    if 'Chrome/' in u or 'CriOS/' in u:
        return 'Chrome'
    if 'Safari/' in u and 'Chrome' not in u and 'Chromium' not in u:
        return 'Safari'
    if 'MSIE' in u or 'Trident/' in u:
        return 'IE'
    return 'other'


def make_visitor_id(ip: str | None, ua: str | None, day: str | None = None) -> str:
    """Denní anonymní visitor-ID: hash(IP + UA + datum UTC). GDPR-friendly."""
    if day is None:
        day = datetime.now(timezone.utc).strftime('%Y-%m-%d')
    raw = f'{(ip or "").strip()}|{(ua or "")[:300]}|{day}'
    return hashlib.sha256(raw.encode('utf-8', errors='ignore')).hexdigest()[:32]
