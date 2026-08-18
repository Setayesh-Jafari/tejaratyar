"""Public-web search, safe page fetch and claim-level source logging."""

from __future__ import annotations

import datetime as dt
import hashlib
import ipaddress
import json
import re
import socket
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any
from zoneinfo import ZoneInfo
from urllib.parse import urljoin, urlparse

import requests
import trafilatura
from bs4 import BeautifulSoup
from ddgs import DDGS

from . import extract as ex

LOCAL_TZ = ZoneInfo("Asia/Tehran")
TODAY = dt.datetime.now(LOCAL_TZ).date().isoformat()
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36 TejaratYar/3.0"
)
HEADERS = {
    "User-Agent": USER_AGENT,
    "Accept-Language": "en-US,en;q=0.9,fa;q=0.8",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}

_lock = threading.Lock()
_ddg_lock = threading.Lock()

OFFICIAL_IRAN_DOMAINS = {
    "ntsw.ir", "irica.ir", "inso.gov.ir", "tpo.ir", "cbi.ir", "fda.gov.ir",
    "imed.ir", "ppo.ir", "ivo.ir", "maj.ir", "isiri.gov.ir",
}
AUTHORITY_DOMAINS = {
    "wcoomd.org", "trade.gov", "usitc.gov", "europa.eu", "gov.uk", "iso.org",
    "fao.org", "who.int", "worldbank.org", "intracen.org", "unctad.org",
}
TRADE_DATA_DOMAINS = {
    "trademap.org", "comtradeplus.un.org", "oec.world", "volza.com", "panjiva.com",
    "importgenius.com", "seair.co.in", "tariffnumber.com",
}


def now_iso() -> str:
    return dt.datetime.now(LOCAL_TZ).isoformat(timespec="seconds")


def domain_of(url: str) -> str:
    return ex.base_domain(url)


def source_id(url: str) -> str:
    return hashlib.sha1((ex.canonical_url(url) or url or "").encode("utf-8")).hexdigest()[:12]


def source_authority(url: str) -> tuple[str, str]:
    host = domain_of(url)
    if host in OFFICIAL_IRAN_DOMAINS or host.endswith(".gov.ir"):
        return "A", "official_iran"
    if host in AUTHORITY_DOMAINS or host.endswith(".gov") or host.endswith(".gov.uk"):
        return "A", "official_or_intergovernmental"
    if host in TRADE_DATA_DOMAINS:
        return "B", "trade_data"
    if ex.marketplace_of(url):
        return "D", "b2b_marketplace"
    if any(host == d or host.endswith("." + d) for d in ex.SOCIAL_OR_CONTENT_DOMAINS):
        return "D", "content_or_social"
    return "C", "company_or_open_web"


def _is_public_http_url(url: str) -> bool:
    try:
        p = urlparse(url)
        if p.scheme not in {"http", "https"} or not p.hostname:
            return False
        host = p.hostname.lower()
        if host in {"localhost", "127.0.0.1", "0.0.0.0", "::1"} or host.endswith(".local"):
            return False
        try:
            ip = ipaddress.ip_address(host)
            return not (ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved)
        except ValueError:
            return True
    except Exception:
        return False


# ddgs v9 supports several DDG text backends.  We try them in order so that if
# one engine is blocked/rate-limited another can still return leads.
TEXT_BACKENDS = [
    "mullvad_google", "google", "brave", "bing", "mojeek", "yahoo", "mullvad_brave",
]


def _normalize_hit(hit: dict, query: str, engine: str) -> dict | None:
    url = ex.canonical_url(hit.get("href") or hit.get("url") or "")
    if not url or not _is_public_http_url(url):
        return None
    grade, source_type = source_authority(url)
    return {
        "title": re.sub(r"\s+", " ", (hit.get("title") or "")).strip()[:240],
        "url": url,
        "snippet": re.sub(r"\s+", " ", (hit.get("body") or hit.get("description") or "")).strip()[:1000],
        "query": query.strip(),
        "checked_on": TODAY,
        "retrieved_at": now_iso(),
        "domain": domain_of(url),
        "sid": source_id(url),
        "search_provider": "ddgs/multi-engine web search",
        "search_engine": engine,
        "authority_grade": grade,
        "source_type": source_type,
    }


def _ddg_text_once(query: str, max_results: int, region: str, backend: str) -> list[dict]:
    with _ddg_lock:
        with DDGS(timeout=9) as ddg:
            hits = ddg.text(
                query.strip(),
                max_results=max_results,
                region=region,
                safesearch="moderate",
                backend=backend,
            )
            return list(hits or [])


def search(query: str, max_results: int = 8, region: str = "wt-wt", backend: str | None = None) -> list[dict[str, Any]]:
    """Search the public web through the open-source ddgs client with engine fallback.

    Tries a prioritized list of engines so a single blocked engine cannot fail
    the whole discovery step.  Returned rows are discovery leads, not verified
    evidence — stages must apply relevance/identity gates before Source Log.
    """
    rows: list[dict[str, Any]] = []
    if not query or not query.strip():
        return rows
    engines = [backend] if backend else TEXT_BACKENDS
    seen: set[str] = set()
    for engine in engines:
        try:
            hits = _ddg_text_once(query, max_results, region, engine)
        except Exception:
            time.sleep(0.25)
            continue
        for hit in hits:
            row = _normalize_hit(hit, query, engine)
            if not row:
                continue
            if row["url"] in seen:
                continue
            seen.add(row["url"])
            rows.append(row)
        if len(rows) >= max_results:
            break
    return rows[:max_results * 2]


def search_many(queries: list[str], max_results: int = 6, workers: int = 4, backend: str | None = None) -> list[dict[str, Any]]:
    seen: set[str] = set()
    out: list[dict[str, Any]] = []
    unique_queries = list(dict.fromkeys(q.strip() for q in queries if q and q.strip()))
    with ThreadPoolExecutor(max_workers=max(1, min(workers, 8))) as pool:
        futs = {pool.submit(search, q, max_results, "wt-wt", backend): q for q in unique_queries}
        for fut in as_completed(futs):
            try:
                rows = fut.result()
            except Exception:
                rows = []
            for row in rows:
                key = row.get("url") or ""
                if not key or key in seen:
                    continue
                seen.add(key)
                out.append(row)
    return out


def _jsonld_organisations(soup: BeautifulSoup) -> tuple[list[str], list[str], list[str]]:
    names: list[str] = []
    urls: list[str] = []
    addresses: list[str] = []

    def walk(obj: Any) -> None:
        if isinstance(obj, list):
            for item in obj:
                walk(item)
            return
        if not isinstance(obj, dict):
            return
        typ = obj.get("@type")
        types = [typ] if isinstance(typ, str) else (typ or [])
        types = {str(x).lower() for x in types}
        if types & {"organization", "corporation", "localbusiness", "store", "manufacturer", "ngo"}:
            name = obj.get("legalName") or obj.get("name")
            if isinstance(name, str) and ex.is_credible_company_name(name):
                names.append(ex.clean_company_name(name))
            url = obj.get("url")
            if isinstance(url, str) and url.startswith("http"):
                urls.append(url)
            address = obj.get("address")
            if isinstance(address, dict):
                bits = [address.get(k) for k in ("streetAddress", "addressLocality", "addressRegion", "postalCode", "addressCountry")]
                joined = ", ".join(str(x) for x in bits if x)
                if joined:
                    addresses.append(joined)
            elif isinstance(address, str):
                addresses.append(address)
        for value in obj.values():
            if isinstance(value, (dict, list)):
                walk(value)

    for tag in soup.find_all("script", attrs={"type": re.compile("ld\\+json", re.I)}):
        raw = tag.string or tag.get_text("", strip=True)
        if not raw:
            continue
        try:
            walk(json.loads(raw))
        except Exception:
            continue
    return list(dict.fromkeys(names))[:10], list(dict.fromkeys(urls))[:10], list(dict.fromkeys(addresses))[:5]


def fetch_page(url: str, timeout: int = 12) -> dict[str, Any]:
    """Fetch one public page and extract text + identity metadata. Never raises."""
    canonical = ex.canonical_url(url)
    result: dict[str, Any] = {
        "url": canonical or url, "final_url": "", "canonical_url": canonical or url,
        "ok": False, "status": None, "title": "", "meta_description": "", "text": "",
        "emails": [], "phones": [], "org_names": [], "org_urls": [], "addresses": [],
        "error": "", "checked_on": TODAY, "retrieved_at": now_iso(), "domain": domain_of(url),
    }
    if not canonical or not _is_public_http_url(canonical):
        result["error"] = "invalid-or-nonpublic-url"
        return result
    host = domain_of(canonical)
    blocked = {"alibaba.com", "facebook.com", "linkedin.com", "instagram.com", "tiktok.com", "x.com"}
    if any(host == b or host.endswith("." + b) for b in blocked):
        result["error"] = "skip-bot-blocked-host"
        return result
    try:
        resp = requests.get(canonical, headers=HEADERS, timeout=timeout, allow_redirects=True, stream=True)
        result["status"] = resp.status_code
        ctype = (resp.headers.get("content-type") or "").lower()
        if "text/html" not in ctype and "application/xhtml" not in ctype and ctype:
            result["error"] = "non-html-content"
            return result
        # Keep memory bounded on arbitrary search results.
        content = resp.content[:2_500_000]
        html = content.decode(resp.encoding or "utf-8", errors="replace")
        result["final_url"] = ex.canonical_url(resp.url)
        soup = BeautifulSoup(html, "lxml")
        if soup.title:
            result["title"] = re.sub(r"\s+", " ", soup.title.get_text(" ", strip=True))[:240]
        meta = soup.find("meta", attrs={"name": re.compile("description", re.I)}) or soup.find("meta", property="og:description")
        if meta:
            result["meta_description"] = re.sub(r"\s+", " ", meta.get("content") or "").strip()[:800]
        canonical_tag = soup.find("link", rel=lambda value: value and "canonical" in [str(x).lower() for x in (value if isinstance(value, list) else [value])])
        if canonical_tag and canonical_tag.get("href"):
            candidate = ex.canonical_url(urljoin(resp.url, canonical_tag["href"]))
            if candidate:
                result["canonical_url"] = candidate
        org_names, org_urls, addresses = _jsonld_organisations(soup)
        result["org_names"] = org_names
        result["org_urls"] = org_urls
        result["addresses"] = addresses
        extracted = trafilatura.extract(html, include_comments=False, include_tables=False, favor_precision=True) or ""
        if not extracted:
            for node in soup(["script", "style", "noscript", "svg"]):
                node.decompose()
            extracted = soup.get_text(" ", strip=True)
        extracted = re.sub(r"\s+", " ", extracted).strip()
        result["text"] = extracted[:16000]
        email_blob = extracted + " " + html[:120000]
        result["emails"] = sorted(set(re.findall(r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}", email_blob)))[:20]
        phones = re.findall(r"\+?\d[\d\s().\-]{7,}\d", extracted)
        result["phones"] = ex.plausible_phones(phones)
        result["ok"] = 200 <= resp.status_code < 400 and bool(result["text"] or result["org_names"])
    except Exception as exc:
        result["error"] = str(exc)[:240]
    return result


def fetch_many(urls: list[str], workers: int = 6, timeout: int = 12) -> dict[str, dict[str, Any]]:
    pages: dict[str, dict[str, Any]] = {}
    uniq = list(dict.fromkeys(ex.canonical_url(u) for u in urls if ex.canonical_url(u)))
    with ThreadPoolExecutor(max_workers=max(1, min(workers, 10))) as pool:
        futs = {pool.submit(fetch_page, u, timeout): u for u in uniq}
        for fut in as_completed(futs):
            try:
                pages[futs[fut]] = fut.result()
            except Exception as exc:
                pages[futs[fut]] = {"url": futs[fut], "ok": False, "error": str(exc)[:200]}
    return pages


def log_source(
    store: list[dict[str, Any]], item: dict[str, Any], used_for: str,
    *, claim: str = "", relevance: float | None = None, evidence_status: str = "accepted",
) -> str:
    """Append a deduplicated, claim-level source and return its evidence id."""
    url = ex.canonical_url(item.get("url") or item.get("canonical_url") or "")
    if not url:
        return ""
    sid = item.get("sid") or source_id(url)
    key = (url, used_for, claim.strip().lower()[:160])
    with _lock:
        for existing in store:
            existing_key = (
                ex.canonical_url(existing.get("url") or ""),
                existing.get("used_for") or "",
                (existing.get("claim") or "").strip().lower()[:160],
            )
            if existing_key == key:
                return existing.get("sid") or sid
        grade, source_type = source_authority(url)
        store.append({
            "used_for": used_for,
            "claim": claim or "",
            "title": item.get("title") or "",
            "url": url,
            "domain": item.get("domain") or domain_of(url),
            "snippet": (item.get("snippet") or item.get("meta_description") or item.get("text") or "")[:500],
            "query": item.get("query") or "",
            "checked_on": item.get("checked_on") or TODAY,
            "retrieved_at": item.get("retrieved_at") or now_iso(),
            "sid": sid,
            "authority_grade": item.get("authority_grade") or grade,
            "source_type": item.get("source_type") or source_type,
            "relevance": round(float(relevance), 2) if relevance is not None else None,
            "evidence_status": evidence_status,
        })
    return sid
