"""Sector/industry classification for NSE & BSE symbols.

Sourced from Zerodha's public markets site (https://zerodha.com/markets/),
which publishes a sector breadcrumb on each stock page and a separate ETF
directory. This module is self-contained: it only depends on ``httpx`` and
does not import from ``market_data`` so it can be reused or tested in
isolation.
"""

from __future__ import annotations

import re
import threading
import time
from typing import Optional
from urllib.parse import quote

import httpx

_HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"}
_SECTOR_LINK = re.compile(r'bcrumb_industry">\s*<a href="/markets/sector/[^"]+">\s*([^<]+?)\s*</a>', re.S)
_CACHE_TTL_SECONDS = 86400

_cache: dict[str, tuple[float, str]] = {}
_cache_lock = threading.Lock()

# Symbols listed on Zerodha's ETF directory (https://zerodha.com/markets/etf/).
# ETFs don't have an "industry sector" the way individual companies do (a
# Nifty 50 ETF, a Gold ETF, and a Banking ETF are all just "ETF" for
# allocation purposes), and Zerodha's stock-page breadcrumb has no sector for
# them. Any symbol in this set is classified as sector "ETF" directly,
# without a network request.
ETF_SYMBOLS = frozenset({
    "ABGSEC", "ABSL10BANK", "ABSLBANETF", "ABSLLIQUID", "ABSLMSCIN", "ABSLNN50ET", "ABSLPSE", "ALPHA",
    "ALPHAETF", "ALPL30IETF", "AONEGOLD", "AONELIQUID", "AONENIFTY", "AONESILVER", "AONETMMQ50", "AONETOTAL",
    "AUTOBEES", "AUTOIETF", "AXISBPSETF", "BANK10ADD", "BANK10BETF", "BANKADD", "BANKBEES", "BANKBETA",
    "BANKBETF", "BANKETF", "BANKIETF", "BANKNIFTY1", "BANKPSU", "BBETF0432", "BBNPNBETF", "BBNPPGOLD", "BFSI",
    "BNKETFAXIS", "BSE500IETF", "BSLGOLDETF", "BSLNIFTY", "BSLSENETFG", "CASHIETF", "CEMNTGROWW", "CHEMICAL",
    "CHOICEGOLD", "COMMOIETF", "CONS", "CONSUMAXIS", "CONSUMBEES", "CONSUMER", "CONSUMIETF", "CPSEETF",
    "DEFENCE", "DIVIDEND", "DIVOPPBEES", "EBANKNIFTY", "EBBETF0425", "EBBETF0430", "EBBETF0431", "EBBETF0433",
    "ECAPINSURE", "EGOLD", "ELIQUID", "ELM250", "EMETAL", "EMULTIMQ", "ENERGY", "ENEXT50", "ENIFTY",
    "EQUAL200", "EQUAL50", "EQUAL50ADD", "ESENSEX", "ESG", "ESILVER", "EVIETF", "EVINDIA", "FINIETF",
    "FLEXIADD", "FMCGADD", "FMCGIETF", "GILT10BETA", "GILT5BETA", "GILT5YBEES", "GOLD1", "GOLD360", "GOLDADD",
    "GOLDAXIS", "GOLDBEES", "GOLDBETA", "GOLDBND", "GOLDCASE", "GOLDETF", "GOLDIETF", "GROWWCAPM",
    "GROWWCHEM", "GROWWDEFNC", "GROWWEV", "GROWWGOLD", "GROWWHOSPI", "GROWWLIQID", "GROWWLOVOL", "GROWWMC150",
    "GROWWMETAL", "GROWWMOM50", "GROWWN200", "GROWWNET", "GROWWNIFTY", "GROWWNXT50", "GROWWPOWER", "GROWWPSE",
    "GROWWPSUBK", "GROWWRAIL", "GROWWRLTY", "GROWWSC250", "GROWWSLVR", "GSEC10ABSL", "GSEC10IETF",
    "GSEC10YEAR", "GSEC5IETF", "HDFCBSE500", "HDFCGOLD", "HDFCGROWTH", "HDFCLIQUID", "HDFCLOWVOL",
    "HDFCMID150", "HDFCMOMENT", "HDFCNEXT50", "HDFCNIF100", "HDFCNIFBAN", "HDFCNIFIT", "HDFCNIFTY",
    "HDFCPSUBK", "HDFCPVTBAN", "HDFCQUAL", "HDFCSENSEX", "HDFCSILVER", "HDFCSML250", "HDFCVALUE", "HEALTHADD",
    "HEALTHAXIS", "HEALTHCARE", "HEALTHIETF", "HEALTHY", "HNGSNGBEES", "HSBCGOLD", "ICICIB22", "IDFNIFTYET",
    "IDFSENSEXE", "INFRA", "INFRABEES", "INFRAIETF", "INTERNET", "IT", "ITADD", "ITAXIS", "ITBEES", "ITBETA",
    "ITETF", "ITIETF", "IVZINGOLD", "IVZINNIFTY", "JUNIORBEES", "LICMFGOLD", "LICNETFGSC", "LICNETFN50",
    "LICNETFSEN", "LICNFNHGP", "LICNMID100", "LIQGRWBEES", "LIQUID", "LIQUID1", "LIQUIDADD", "LIQUIDBEES",
    "LIQUIDBETA", "LIQUIDBETF", "LIQUIDCASE", "LIQUIDETF", "LIQUIDIETF", "LIQUIDPLUS", "LIQUIDSBI",
    "LIQUIDSHRI", "LOWVOL", "LOWVOL1", "LOWVOLIETF", "LTGILTBEES", "LTGILTCASE", "MAFANG", "MAHKTECH",
    "MAKEINDIA", "MANUFGBEES", "MASPTOP50", "METAL", "METALIETF", "MID150", "MID150BEES", "MID150CASE",
    "MIDCAP", "MIDCAPADD", "MIDCAPBETA", "MIDCAPETF", "MIDCAPIETF", "MIDQ50ADD", "MIDSELIETF", "MIDSMALL",
    "MNC", "MOALPHA50", "MOBANK10", "MOCAPITAL", "MODEFENCE", "MOENERGY", "MOGOLD", "MOGSEC", "MOHEALTH",
    "MOINFRA", "MOIPO", "MOLOWVOL", "MOM100", "MOM30IETF", "MOM50", "MOMENTUM", "MOMENTUM30", "MOMENTUM50",
    "MOMGF", "MOMIDMTM", "MOMMIDCAP", "MOMNC", "MOMOMENTUM", "MON100", "MON50EQUAL", "MONEXT50", "MONIFTY100",
    "MONIFTY500", "MONQ50", "MOPSE", "MOQUALITY", "MOREALTY", "MOSERVICE", "MOSILVER", "MOSMALL250", "MOTOUR",
    "MOVALUE", "MSCI360", "MSCIADD", "MSCIINDIA", "MULTICAP", "NAVINIFTY", "NETF", "NEXT30ADD", "NEXT50",
    "NEXT50ADD", "NEXT50BETA", "NEXT50ETF", "NEXT50IETF", "NIF100BEES", "NIF100IETF", "NIFTY1", "NIFTY100EW",
    "NIFTYADD", "NIFTYAXIS", "NIFTYBEES", "NIFTYBETA", "NIFTYBETF", "NIFTYCASE", "NIFTYETF", "NIFTYIETF",
    "NIFTYQLITY", "NPBET", "NV20", "NV20BEES", "NV20IETF", "OILIETF", "PHARMABEES", "PSUBANK", "PSUBANKADD",
    "PSUBNKBEES", "PSUBNKIETF", "PVTBANIETF", "PVTBANK", "PVTBANKADD", "PVTBKGROWW", "QGOLDHALF", "QNIFTY",
    "QUAL30IETF", "QUALITY30", "SBIBPB", "SBIETFCON", "SBIETFIT", "SBIETFPB", "SBIETFQLTY", "SBILIQETF",
    "SBIMIDMOM", "SBINEQWETF", "SBINMID150", "SBISENSEX", "SBISILVER", "SBISMLETF", "SBIVALETF", "SDL24BEES",
    "SDL26BEES", "SELECTIPO", "SENSEX1", "SENSEXADD", "SENSEXAXIS", "SENSEXBEES", "SENSEXBETA", "SENSEXETF",
    "SENSEXIETF", "SETF10GILT", "SETFBSE100", "SETFGOLD", "SETFNIF50", "SETFNIFBK", "SETFNN50", "SETFSN50",
    "SHARIABEES", "SILVER", "SILVER1", "SILVER360", "SILVERADD", "SILVERAG", "SILVERAXIS", "SILVERBEES",
    "SILVERBETA", "SILVERBND", "SILVERCASE", "SILVERIETF", "SMALL250", "SMALLADD", "SMALLCAP", "SMALLGROWW",
    "SMALLIETF", "SML100CASE", "SNXT30BEES", "SNXT50BEES", "SNXT50BETA", "TATAGOLD", "TATSILV", "TECH",
    "TNIDETF", "TOP100CASE", "TOP10ADD", "TOP15IETF", "TOP20", "TWCGOLDETF", "UNIONGOLD", "VAL30IETF",
    "VALUE", "VALUEAXIS",
})


def _normalize(symbol: str, exchange: str) -> tuple[str, str]:
    clean_symbol = re.sub(r"-(?:E|EQ)$", "", symbol.strip().upper().removesuffix(".NS").removesuffix(".BO"))
    clean_exchange = "BSE" if exchange.upper() == "BSE" else "NSE"
    return clean_symbol, clean_exchange


def _cache_get(key: str) -> Optional[str]:
    with _cache_lock:
        item = _cache.get(key)
    return item[1] if item and item[0] > time.monotonic() else None


def _cache_set(key: str, value: str) -> None:
    with _cache_lock:
        _cache[key] = (time.monotonic() + _CACHE_TTL_SECONDS, value)


def _is_real_page(html: str) -> bool:
    """Zerodha returns HTTP 200 with a generic shell page (title "Zerodha
    Markets") for symbols that don't exist, instead of a real 404, so page
    validity is checked from content rather than status code alone."""
    if len(html) < 500:
        return False
    title = re.search(r"<title>([^<]+)</title>", html)
    return bool(title) and title.group(1).strip() != "Zerodha Markets"


def _get_page(path: str) -> Optional[str]:
    try:
        response = httpx.get(f"https://zerodha.com{path}", headers=_HEADERS, timeout=8.0, follow_redirects=True)
    except Exception:
        return None
    return response.text if response.status_code == 200 else None


def _stock_sector(symbol: str, exchange: str) -> Optional[str]:
    """Scrape the sector name from a Zerodha stock page's breadcrumb link."""
    html = _get_page(f"/markets/stocks/{exchange}/{quote(symbol, safe='')}/")
    match = _SECTOR_LINK.search(html) if html else None
    return match.group(1).strip() if match else None


def _is_listed_etf(symbol: str, exchange: str) -> bool:
    """Confirm a symbol resolves to a real Zerodha ETF page."""
    html = _get_page(f"/markets/etf/{exchange}/{quote(symbol, safe='')}/")
    return bool(html and _is_real_page(html))


def fetch_sector(symbol: str, exchange: str = "NSE") -> str:
    """Return the sector classification for a symbol.

    Checks the bundled ETF symbol list first, then scrapes Zerodha's stock
    page breadcrumb, then confirms an unmatched symbol as an ETF via
    Zerodha's ETF directory. Falls back to "Unknown". Results are cached for
    a day since sector/industry classification rarely changes.
    """
    clean_symbol, clean_exchange = _normalize(symbol, exchange)
    cache_key = f"{clean_exchange}:{clean_symbol}"

    cached = _cache_get(cache_key)
    if cached is not None:
        return cached

    if clean_symbol in ETF_SYMBOLS:
        sector = "ETF"
    else:
        sector = _stock_sector(clean_symbol, clean_exchange) or ("ETF" if _is_listed_etf(clean_symbol, clean_exchange) else None)

    result = sector or "Unknown"
    _cache_set(cache_key, result)
    return result
