"""Strict entity, product, HS and evidence extraction helpers.

The module deliberately prefers rejecting an uncertain search result over
turning a page title or snippet into a fictional supplier.  Every helper is
pure/deterministic so it can be unit-tested without network access.
"""

from __future__ import annotations

import re
from typing import Any
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

# B2B marketplaces may be useful discovery channels, but a category/search
# page is not a supplier.  Specific storefront/profile/product pages are kept.
MARKETPLACE_DOMAINS = {
    "alibaba.com", "made-in-china.com", "globalsources.com", "indiamart.com",
    "tradeindia.com", "exportersindia.com", "europages.com", "europages.co.uk",
    "thomasnet.com", "kompass.com", "exporthub.com", "ec21.com", "diytrade.com",
    "tradekey.com", "21food.com", "goldsupplier.com", "go4worldbusiness.com",
    "globaltradeplaza.com", "tradewheel.com", "tradees.com", "1688.com", "accio.com",
}

SOCIAL_OR_CONTENT_DOMAINS = {
    "wikipedia.org", "youtube.com", "facebook.com", "instagram.com", "tiktok.com", "linkedin.com",
    "reddit.com", "pinterest.com", "quora.com", "imdb.com", "medium.com", "x.com", "twitter.com",
}

DIRECTORY_OR_NEWS_DOMAINS = {
    "yellowpages.com", "volza.com", "trademap.org", "importgenius.com",
    "panjiva.com", "seair.co.in", "statista.com", "amazon.com", "ebay.com", "ebay.ca",
    "springer.com", "sciencedirect.com", "researchgate.net", "mdpi.com", "tandfonline.com",
    "contactout.com", "rocketreach.co", "zoominfo.com", "addisbiz.com",
}

NOISE_TITLES = {
    "alibaba", "made-in-china", "made in china", "global sources", "indiamart",
    "home", "products", "product", "suppliers", "supplier", "manufacturers",
    "manufacturer", "wholesale", "login", "sign in", "contact us", "about us",
    "company profile", "search", "catalog", "directory", "data inc",
}

# These words are useful for a search query but should not make an unrelated
# page pass the product-relevance gate by themselves.
PRODUCT_STOPWORDS = {
    "the", "and", "for", "with", "from", "into", "type", "grade", "model",
    "product", "products", "equipment", "device", "machine", "system", "unit",
    "high", "quality", "premium", "best", "new", "green", "black", "white",
    "industrial", "commercial", "medical", "raw", "fresh", "bulk", "organic",
    "manufacturer", "supplier", "factory", "exporter", "wholesale", "oem", "odm",
    "کالا", "محصول", "دستگاه", "صنعتی", "پزشکی", "سبز", "سیاه", "سفید",
}

GENERIC_NAME_WORDS = {
    "pure", "best", "high", "quality", "hot", "sale", "wholesale", "factory",
    "supplier", "manufacturer", "china", "global", "new", "the", "company",
    "product", "products", "official", "home", "group", "international",
    "contact", "online", "website", "export", "import", "data", "catalog",
}

UI_OR_SENTENCE_MARKERS = {
    "contact supplier", "request quote", "get latest price", "chat now", "aibot",
    "online this conversation", "similar products", "leading supplier from",
    "contact now", "page is loading", "buyer from", "wanted :", "wanted:",
}

JUNK_PAGE_MARKERS = (
    "wikipedia", "dictionary", "definition & meaning", "what is hs code",
    "hs code finder", "w3schools", "stackoverflow", "github.com", "pure css",
    "merriam-webster", "shades of", "color code", "college", "university",
)

BUYER_MARKERS = (
    "buyer from", "buyers & importers", "buyers and importers", "wanted :",
    "wanted:", "buying request", "buying lead", "buy lead", "importers list",
    "request for quotation", "post rfq", "buyer requirement",
)

CATEGORY_PATH_MARKERS = (
    "/suppliers", "/supplier", "/manufacturers", "/manufacturer", "/buyers",
    "/buyer", "/importers", "/search", "/products-search", "/category/",
    "/categories/", "/wholesale-", "/directory/", "/business-directory/", "/companies/", "/plp/", "-suppliers", "-manufacturers",
)

PROFILE_PATH_MARKERS = (
    "/company-profile", "/company_profile", "/company/", "/supplier/",
    "/manufacturer/", "/about", "/contact", "/profile/",
)

CONTENT_PATH_MARKERS = (
    "/article/", "/articles/", "/story/", "/stories/", "/news/", "/blog/",
    "/journal/", "/research/", "/wiki/", "/itm/",
)

LEGAL_SUFFIX_RE = (
    r"Co\.?\s*,?\s*Ltd\.?|Company\s+Limited|Pvt\.?\s*Ltd\.?|Private\s+Limited|"
    r"Ltd\.?|Limited|LLC|L\.L\.C\.?|GmbH|AG|Inc\.?|Corp\.?|Corporation|"
    r"S\.?A\.?S?\.?|SAS|S\.r\.l\.?|B\.?V\.?|Oy|AB|Sdn\.?\s*Bhd\.?|"
    r"JSC|PJSC|PLC|FZE|FZC|Cooperative|Co-operative|Association|Sp\.?\s*z\.?\s*o\.?\s*o\.?"
)
# One to twelve name-like tokens followed by a legal suffix.  Unlike the old
# regex it cannot start hundreds of characters earlier and swallow a sentence.
LEGAL_NAME_RE = re.compile(
    rf"\b((?:[A-Z0-9][A-Za-z0-9&'()./\-]*\s+){{1,11}}(?:{LEGAL_SUFFIX_RE}))\b",
    re.I,
)

HS_RE = re.compile(r"(?<!\d)(\d{4}[.\s-]?\d{2}(?:[.\s-]?\d{2,4})?)(?!\d)")

CERT_PATTERNS = [
    (r"\bISO\s*9001\b", "ISO 9001"), (r"\bISO\s*14001\b", "ISO 14001"),
    (r"\bISO\s*13485\b", "ISO 13485"), (r"\bISO\s*22000\b", "ISO 22000"),
    (r"\bISO\s*17025\b", "ISO/IEC 17025"), (r"\bCE\b", "CE"),
    (r"\bFDA\b", "FDA"), (r"\bUL\b", "UL"), (r"\bRoHS\b", "RoHS"),
    (r"\bREACH\b", "REACH"), (r"\bGMP\b", "GMP"),
    (r"\bHACCP\b", "HACCP"), (r"\bHALAL\b", "Halal"),
    (r"\bKOSHER\b", "Kosher"), (r"\bIEC\s*61215\b", "IEC 61215"),
    (r"\bIEC\s*61730\b", "IEC 61730"), (r"\bT[ÜU]V\b", "TÜV"),
    (r"\bSGS\b", "SGS"), (r"\bBSCI\b", "BSCI"),
    (r"\bSEDEX\b", "SEDEX"), (r"\bBRC(?:GS)?\b", "BRCGS"),
    (r"\bFSSC\s*22000\b", "FSSC 22000"), (r"\bGLOBALG\.?A\.?P\.?\b", "GLOBALG.A.P."),
    (r"\bOEKO[ -]?TEX\b", "OEKO-TEX"), (r"\bIATF\s*16949\b", "IATF 16949"),
]

COUNTRY_HINTS = {
    "china": "China", "chinese": "China", "yunnan": "China", "shenzhen": "China",
    "guangzhou": "China", "ningbo": "China", "shanghai": "China", "zhejiang": "China",
    "jiangsu": "China", "dongguan": "China", "india": "India", "mumbai": "India",
    "delhi": "India", "ahmedabad": "India", "gujarat": "India", "turkey": "Turkey",
    "turkish": "Turkey", "istanbul": "Turkey", "izmir": "Turkey", "germany": "Germany",
    "italy": "Italy", "spain": "Spain", "france": "France", "korea": "South Korea",
    "taiwan": "Taiwan", "vietnam": "Vietnam", "lam dong": "Vietnam", "thailand": "Thailand",
    "malaysia": "Malaysia", "indonesia": "Indonesia", "ethiopia": "Ethiopia",
    "brazil": "Brazil", "colombia": "Colombia", "uganda": "Uganda", "kenya": "Kenya",
    "uae": "UAE", "dubai": "UAE", "pakistan": "Pakistan", "poland": "Poland",
    "netherlands": "Netherlands", "japan": "Japan", "united states": "USA", " usa ": "USA",
    "sri lanka": "Sri Lanka", "ceylon": "Sri Lanka", "bangladesh": "Bangladesh",
}


def canonical_url(url: str) -> str:
    """Remove tracking parameters/fragments so Source Log can be deduplicated."""
    try:
        p = urlparse(url or "")
        if p.scheme not in {"http", "https"}:
            return ""
        query = [(k, v) for k, v in parse_qsl(p.query, keep_blank_values=True)
                 if not k.lower().startswith("utm_") and k.lower() not in {"gclid", "fbclid", "ref", "source"}]
        path = re.sub(r"/{2,}", "/", p.path or "/")
        if path != "/":
            path = path.rstrip("/")
        host = p.netloc.lower()
        if host.startswith("www."):
            host = host[4:]
        return urlunparse((p.scheme.lower(), host, path, "", urlencode(query), ""))
    except Exception:
        return ""


def base_domain(url: str) -> str:
    host = urlparse(url or "").netloc.lower().split(":")[0]
    host = host[4:] if host.startswith("www.") else host
    parts = host.split(".")
    if len(parts) <= 2:
        return host
    # Basic public-suffix handling sufficient for common supplier domains.
    if ".".join(parts[-2:]) in {"co.uk", "com.cn", "com.tr", "com.vn", "co.in", "com.br", "co.id", "com.my"}:
        return ".".join(parts[-3:])
    return ".".join(parts[-2:])


def marketplace_of(url: str) -> str | None:
    host = base_domain(url)
    for m in MARKETPLACE_DOMAINS:
        if host == m or host.endswith("." + m):
            return m
    return None


def meaningful_product_tokens(text: str) -> list[str]:
    tokens = [t.lower() for t in re.findall(r"[A-Za-z][A-Za-z0-9+\-]{2,}|[\u0600-\u06FF]{3,}", text or "")]
    out: list[str] = []
    for token in tokens:
        token = token.strip("-+")
        if token in PRODUCT_STOPWORDS or token.isdigit() or len(token) < 3:
            continue
        if token not in out:
            out.append(token)
    return out[:12]


def product_match_score(text: str, product_name: str) -> float:
    blob = (text or "").lower()
    tokens = meaningful_product_tokens(product_name)
    if not tokens:
        return 0.0
    matches = sum(1 for t in tokens if re.search(rf"(?<![\w]){re.escape(t)}(?![\w])", blob, re.I))
    ratio = matches / len(tokens)
    compact_product = re.sub(r"\s+", " ", product_name.lower()).strip()
    phrase_bonus = 0.20 if compact_product and compact_product in re.sub(r"\s+", " ", blob) else 0.0
    # One generic-looking token is not enough to bless a page.
    if len(tokens) >= 3 and matches < 2:
        return min(0.30, ratio)
    return min(1.0, ratio * 0.8 + phrase_bonus)


def guess_country(text: str, url: str = "") -> str:
    blob = f" {text or ''} {url or ''} ".lower()
    for key, country in COUNTRY_HINTS.items():
        if key in blob:
            return country
    host = urlparse(url or "").netloc.lower()
    tld_map = {
        ".cn": "China", ".de": "Germany", ".in": "India", ".tr": "Turkey",
        ".it": "Italy", ".kr": "South Korea", ".tw": "Taiwan", ".vn": "Vietnam",
        ".jp": "Japan", ".fr": "France", ".nl": "Netherlands", ".pl": "Poland",
        ".br": "Brazil", ".co": "Colombia", ".et": "Ethiopia", ".lk": "Sri Lanka",
    }
    for tld, country in tld_map.items():
        if host.endswith(tld):
            return country
    return ""


def guess_company_country(text: str, url: str = "", addresses: list[str] | None = None) -> str:
    """Infer supplier location conservatively, not merely product origin."""
    for address in addresses or []:
        country = guess_country(address, url)
        if country:
            return country
    blob = re.sub(r"\s+", " ", text or "")
    patterns = [
        r"(?:company|supplier|manufacturer|exporter|factory|headquartered|located|based)\s+(?:is\s+)?(?:in|at|from)\s+([A-Za-z ]{3,28})",
        r"(?:registered address|factory address|address)\s*[:\-]\s*([^.;]{4,80})",
    ]
    for pat in patterns:
        for m in re.finditer(pat, blob, re.I):
            country = guess_country(m.group(1), url)
            if country:
                return country
    # Country-specific TLD is stronger than commodity-origin mentions.
    return guess_country("", url)


def _normalise_punctuation(text: str) -> str:
    text = re.sub(r"\s+", " ", text or "").strip()
    text = re.sub(r"\s+([,.;:])", r"\1", text)
    text = re.sub(r",\s*Ltd\b", ", Ltd", text, flags=re.I)
    return text


def clean_company_name(name: str) -> str:
    name = _normalise_punctuation(name).strip(" -|·,;:")
    name = re.sub(r"^(?:buy|shop|wholesale|hot sale|best price|high quality|factory direct)\s*[-:]?\s*", "", name, flags=re.I)
    # Remove common title/UI prefixes without eating a real legal name.
    name = re.sub(r"^(?:welcome to|about)\s+", "", name, flags=re.I)
    name = re.sub(r"^.*\b(?:no reviews yet|from|by)\s+(?=[A-Z][A-Za-z0-9])", "", name, flags=re.I)
    name = re.sub(r"\b(Ltd|Inc|Corp)$", r"\1.", name, flags=re.I)
    if len(name) < 3 or len(name) > 100:
        return ""
    return name


def has_legal_suffix(name: str) -> bool:
    return bool(re.search(rf"(?:{LEGAL_SUFFIX_RE})\s*$", clean_company_name(name), re.I))


def is_credible_company_name(name: str, *, allow_brand: bool = True) -> bool:
    n = clean_company_name(name)
    if len(n) < 4 or len(n) > 100:
        return False
    low = n.lower()
    if low in NOISE_TITLES or low in GENERIC_NAME_WORDS:
        return False
    if re.fullmatch(r"\d+", low) or low in {k.strip() for k in COUNTRY_HINTS} or low in {v.lower() for v in COUNTRY_HINTS.values()}:
        return False
    if low in {"stories", "our story", "error page", "just a moment", "green coffee beans", "coffee beans", "arabica coffee", "organic green coffee beans"}:
        return False
    if any(marker in low for marker in UI_OR_SENTENCE_MARKERS):
        return False
    if any(marker in low for marker in ("definition", "meaning", "shades of", "color code", "wikipedia")):
        return False
    if low.endswith(("conversa", "wholesa", "availab", "agric", "inc")) and not has_legal_suffix(n):
        return False
    words = [w for w in re.split(r"\s+", n) if w]
    if len(words) > 14:
        return False
    # A sentence fragment normally contains many lower-case glue/verb words.
    glue = {"is", "a", "the", "from", "for", "and", "with", "are", "also", "this", "of", "to", "in"}
    if sum(1 for w in words if w.lower().strip(".,") in glue) >= 3 and not has_legal_suffix(n):
        return False
    if any(ch in n for ch in "!?…"):
        return False
    role_terms = sum(1 for term in ("supplier", "manufacturer", "exporter", "export", "wholesale", "factory", "product") if re.search(rf"\b{term}\b", low))
    if not has_legal_suffix(n) and role_terms >= 2:
        return False
    if not allow_brand and not has_legal_suffix(n):
        return False
    distinctive = [re.sub(r"[^a-z0-9]", "", w.lower()) for w in words]
    distinctive = [w for w in distinctive if w and w not in GENERIC_NAME_WORDS and w not in {"co", "ltd", "llc", "inc"}]
    return bool(distinctive)


def _legal_names(text: str) -> list[str]:
    norm = _normalise_punctuation(text)
    names: list[str] = []
    for m in LEGAL_NAME_RE.finditer(norm):
        candidate = clean_company_name(m.group(1))
        # Trim leading product/ad words by keeping at most 8 words before suffix.
        words = candidate.split()
        if len(words) > 10:
            candidate = " ".join(words[-10:])
        if is_credible_company_name(candidate, allow_brand=False) and candidate.lower() not in {x.lower() for x in names}:
            names.append(candidate)
    return names


def company_from_subdomain(url: str) -> str:
    try:
        p = urlparse(url or "")
        host = p.netloc.lower().split(":")[0]
        path = p.path or ""
    except Exception:
        return ""
    host = host[4:] if host.startswith("www.") else host
    marketplace = marketplace_of(url)
    # foo.en.alibaba.com, foo.made-in-china.com, foo.goldsupplier.com
    if marketplace:
        root = marketplace
        if host.endswith("." + root):
            prefix = host[: -(len(root) + 1)].split(".")[0]
            if prefix not in {"www", "m", "en", "login", "my", "seller", "trade", "importer", "dir", "directory", "kenya", "china", "india", "turkey"} and len(prefix) >= 4 and not prefix.isdigit():
                brand = clean_company_name(prefix.replace("-", " ").title())
                if is_credible_company_name(brand):
                    return brand
        if marketplace == "indiamart.com":
            m = re.match(r"/([a-z0-9-]{4,})", path, re.I)
            if m and m.group(1).lower() not in {"proddetail", "search", "city", "impcat"}:
                return clean_company_name(m.group(1).replace("-", " ").title())
    return ""


def _brand_from_domain_or_title(title: str, url: str) -> str:
    host = urlparse(url or "").netloc.lower().split(":")[0]
    host = host[4:] if host.startswith("www.") else host
    if not host or marketplace_of(url):
        return ""
    label_raw = host.split(".")[0]
    compact_host = re.sub(r"[^a-z0-9]", "", label_raw)
    choices: list[tuple[int, str]] = []
    for seg in re.split(r"\s+[|–—]\s+|\s+-\s+|::", title or "")[:5]:
        seg = clean_company_name(seg)
        if not is_credible_company_name(seg) or len(seg.split()) > 8:
            continue
        low = seg.lower()
        if any(x in low for x in ("price", "wholesale", "buy ", "supplier", "manufacturer")):
            continue
        tokens = distinctive_name_tokens(seg)
        support = sum(1 for t in tokens if t in compact_host)
        score = support * 5 - len(tokens)
        choices.append((score, seg))
    if choices:
        choices.sort(key=lambda x: x[0], reverse=True)
        if choices[0][0] > 0:
            return choices[0][1]
    label = re.sub(r"[-_]", " ", label_raw).title()
    return label if is_credible_company_name(label) else (choices[0][1] if choices else "")


def page_kind(url: str, title: str = "", snippet: str = "") -> str:
    blob = f"{title} {snippet}".lower()
    low_url = (url or "").lower()
    host = base_domain(url)
    if any(host == d or host.endswith("." + d) for d in SOCIAL_OR_CONTENT_DOMAINS):
        return "content_or_social"
    if any(host == d or host.endswith("." + d) for d in DIRECTORY_OR_NEWS_DOMAINS):
        return "directory_or_data"
    if any(m in low_url for m in CONTENT_PATH_MARKERS):
        return "content_or_article"
    if any(m in blob or m in low_url for m in BUYER_MARKERS):
        return "buyer_or_lead"
    market = marketplace_of(url)
    if market:
        subbrand = company_from_subdomain(url)
        if subbrand:
            return "marketplace_profile"
        if any(m in low_url for m in PROFILE_PATH_MARKERS):
            return "marketplace_profile"
        # Product-detail URLs may identify one supplier through title/snippet.
        product_markers = ("product-detail", "/product/", "/show/", "/provide/", "product_details", ".html")
        if any(m in low_url for m in product_markers) and not any(m in low_url for m in CATEGORY_PATH_MARKERS):
            return "marketplace_product"
        return "marketplace_category"
    if any(m in low_url for m in CATEGORY_PATH_MARKERS):
        return "directory_or_category"
    return "official_candidate"


def extract_company_entity(title: str, snippet: str, url: str, page: dict[str, Any] | None = None) -> dict[str, Any]:
    """Return the best supported company/brand name and extraction evidence."""
    page = page or {}
    kind = page_kind(url, title, snippet)
    if kind in {"content_or_social", "content_or_article", "directory_or_data", "buyer_or_lead", "marketplace_category", "directory_or_category"}:
        return {"name": "", "legal_name": "", "method": "rejected_page_kind", "confidence": 0.0, "page_kind": kind}

    candidates: list[tuple[str, str, float]] = []
    # Marketplace JSON-LD normally identifies the marketplace itself, not the
    # seller. Only keep a structured marketplace name when it is a legal name
    # and is also supported by the result title/snippet.
    for org in page.get("org_names") or []:
        org = clean_company_name(org)
        if not is_credible_company_name(org):
            continue
        if kind.startswith("marketplace") and (not has_legal_suffix(org) or not hit_matches_company(title, snippet, url, org)):
            continue
        candidates.append((org, "page_structured_data", 0.96 if has_legal_suffix(org) else 0.84))
    for name in _legal_names(f"{title} | {page.get('title','')}"):
        candidates.append((name, "page_or_result_title_legal_name", 0.90))
    for name in _legal_names(snippet):
        candidates.append((name, "search_snippet_legal_name", 0.76))
    sub = company_from_subdomain(url)
    if sub:
        candidates.append((sub, "marketplace_storefront_domain", 0.68))
    if kind.startswith("marketplace"):
        m = re.match(r"\s*(.+?)\s*[-|–—]\s*(?:supplier|manufacturer|exporter|seller|service provider)\b", title or "", re.I)
        if m:
            market_brand = clean_company_name(m.group(1))
            if is_credible_company_name(market_brand):
                candidates.append((market_brand, "marketplace_profile_title", 0.72))
    else:
        m = re.search(r"(?:welcome\s+to\s+)?([A-Z][A-Za-z0-9&'\- ]{3,60}?)(?:,|\s+is\s+)(?:your|a|an|the|one\s+of)", snippet or "", re.I)
        if m:
            intro_brand = clean_company_name(m.group(1))
            if is_credible_company_name(intro_brand):
                candidates.append((intro_brand, "independent_page_intro_brand", 0.70))
    brand = _brand_from_domain_or_title(page.get("title") or title, url)
    if brand:
        candidates.append((brand, "independent_domain_or_title_brand", 0.64))

    best: tuple[str, str, float] | None = None
    host_text = (urlparse(url or "").netloc + " " + (page.get("title") or "") + " " + (page.get("text") or "")[:3000]).lower()
    for name, method, conf in candidates:
        if not is_credible_company_name(name):
            continue
        tokens = distinctive_name_tokens(name)
        identity_support = sum(1 for t in tokens[:3] if t in host_text)
        if method == "page_structured_data" and not has_legal_suffix(name) and identity_support == 0:
            continue
        if method.startswith("page_") and identity_support:
            conf = min(0.99, conf + 0.03)
        if not best or conf > best[2]:
            best = (name, method, conf)
    if not best:
        return {"name": "", "legal_name": "", "method": "not_found", "confidence": 0.0, "page_kind": kind}
    name, method, conf = best
    return {"name": name, "legal_name": name if has_legal_suffix(name) else "", "method": method, "confidence": round(conf, 2), "page_kind": kind}


def extract_company_name(title: str, snippet: str, url: str) -> str:
    return extract_company_entity(title, snippet, url).get("name") or ""


def company_key(name: str, url: str = "") -> str:
    tokens = distinctive_name_tokens(name)
    if tokens:
        return "".join(tokens)[:60]
    return base_domain(url) or re.sub(r"[^a-z0-9]+", "", (name or "").lower())[:60]


def distinctive_name_tokens(name: str) -> list[str]:
    toks = [t.lower() for t in re.findall(r"[A-Za-z0-9]{2,}", name or "")]
    legal = {"co", "ltd", "limited", "llc", "gmbh", "inc", "corp", "corporation", "company", "pvt", "private", "jsc", "plc", "ag", "sa", "sas"}
    return [t for t in toks if t not in legal and t not in GENERIC_NAME_WORDS]


def looks_like_supplier(title: str, snippet: str, url: str, product_tokens: list[str] | str) -> bool:
    product = " ".join(product_tokens) if isinstance(product_tokens, list) else product_tokens
    blob = f"{title} {snippet} {url}".lower()
    if any(x in blob for x in JUNK_PAGE_MARKERS):
        return False
    kind = page_kind(url, title, snippet)
    if kind in {"content_or_social", "content_or_article", "directory_or_data", "buyer_or_lead", "marketplace_category", "directory_or_category"}:
        return False
    if product_match_score(blob, product) < 0.45:
        return False
    supplier_signal = bool(re.search(r"manufactur|supplier|export|factory|producer|processor|cooperative|mill|wholesale|distributor|trading", blob, re.I))
    return supplier_signal


def hit_matches_company(title: str, snippet: str, url: str, company_name: str, known_domain: str = "") -> bool:
    blob = f"{title} {snippet} {url}".lower()
    if any(x in blob for x in JUNK_PAGE_MARKERS):
        return False
    if known_domain and base_domain(url) == base_domain(known_domain):
        return True
    tokens = distinctive_name_tokens(company_name)
    if len(tokens) >= 2:
        return sum(1 for t in tokens[:4] if re.search(rf"\b{re.escape(t)}\b", blob)) >= min(2, len(tokens))
    return bool(tokens and len(tokens[0]) >= 7 and re.search(rf"\b{re.escape(tokens[0])}\b", blob))


def website_fits_company(url: str, page_text: str, company_name: str, product_tokens: list[str]) -> bool:
    if not url or marketplace_of(url):
        return False
    host = base_domain(url)
    if any(host == d or host.endswith("." + d) for d in SOCIAL_OR_CONTENT_DOMAINS | DIRECTORY_OR_NEWS_DOMAINS):
        return False
    blob = f"{host} {page_text or ''}".lower()
    name_tokens = distinctive_name_tokens(company_name)
    name_hits = sum(1 for t in name_tokens[:4] if t in blob)
    name_ok = bool(name_tokens and (name_hits >= min(2, len(name_tokens)) or name_tokens[0] in host.replace("-", "")))
    product = " ".join(product_tokens)
    return name_ok and product_match_score(blob, product) >= 0.35


def email_domain(email: str) -> str:
    if "@" not in (email or ""):
        return ""
    return base_domain("https://" + email.rsplit("@", 1)[-1].strip().lower())


def email_matches_website(email: str, website: str) -> bool:
    ed = email_domain(email)
    wd = base_domain(website)
    free = {"gmail.com", "yahoo.com", "hotmail.com", "outlook.com", "qq.com", "163.com", "proton.me"}
    if not ed or not wd or ed in free:
        return False
    return ed == wd or ed.endswith("." + wd) or wd.endswith("." + ed)


def extract_hs_candidates(text: str) -> list[str]:
    found: list[str] = []
    for raw in HS_RE.findall(text or ""):
        digits = re.sub(r"\D", "", raw)
        if len(digits) not in {6, 8, 10}:
            continue
        # Date/year and impossible HS chapters are discarded.
        chapter = int(digits[:2])
        if chapter < 1 or chapter > 97 or digits.startswith("20") and len(digits) > 8:
            continue
        pretty = f"{digits[:4]}.{digits[4:6]}"
        if len(digits) >= 8:
            pretty += f".{digits[6:8]}"
        if len(digits) == 10:
            pretty += f".{digits[8:10]}"
        if pretty not in found:
            found.append(pretty)
    return found[:12]


def extract_certs(text: str) -> list[str]:
    return [label for pat, label in CERT_PATTERNS if re.search(pat, text or "", flags=re.I)]


def plausible_phones(phones: list[str]) -> list[str]:
    out: list[str] = []
    for raw in phones or []:
        digits = re.sub(r"\D", "", raw or "")
        if len(digits) < 8 or len(digits) > 15 or len(set(digits)) <= 2:
            continue
        cleaned = re.sub(r"\s+", " ", raw).strip()
        if cleaned not in out:
            out.append(cleaned)
    return out[:4]


def year_founded(text: str) -> str:
    years = re.findall(r"(?:established|founded|since|est\.?)\s*(?:in\s*)?(19\d{2}|20[0-2]\d)", text or "", re.I)
    return years[0] if years else ""


def first_email(emails: list[str], preferred_domain: str = "") -> str:
    bad_parts = ("example.com", "sentry", "wixpress", "schema", ".png", ".jpg", "noreply", "no-reply")
    clean: list[str] = []
    for e in emails or []:
        e = e.strip(" .,:;<>[]()\"").lower()
        if not re.fullmatch(r"[a-z0-9._%+\-]+@[a-z0-9.\-]+\.[a-z]{2,}", e):
            continue
        if any(x in e for x in bad_parts):
            continue
        if e not in clean:
            clean.append(e)
    if preferred_domain:
        matched = [e for e in clean if email_matches_website(e, preferred_domain)]
        if matched:
            return matched[0]
    free = ("gmail.com", "yahoo.com", "hotmail.com", "outlook.com", "qq.com", "163.com")
    corporate = [e for e in clean if not e.endswith(free)]
    return (corporate or clean or [""])[0]


def snippet_signals(text: str) -> dict[str, Any]:
    t = (text or "").lower()
    capacity_numbers = re.findall(r"\b\d[\d,.]*\s*(?:tons?|tonnes?|units?|pieces?|pcs|mw|kw)\s*(?:per|/)?\s*(?:year|month|day|annum)?", t)
    return {
        "mentions_export": bool(re.search(r"\bexport(?:s|ed|ing|er)?\b|worldwide|global market|shipped to|overseas", t)),
        "mentions_factory": bool(re.search(r"factory|manufactur|processing (?:plant|mill|facility)|production line|producer|cooperative", t)),
        "mentions_moq": bool(re.search(r"\bmoq\b|minimum order", t)),
        "mentions_terms": bool(re.search(r"\bfob\b|\bcif\b|\bcfr\b|incoterm|payment terms|sample available", t)),
        "has_contact": bool(re.search(r"contact|email|tel|phone|whatsapp", t)),
        "capacity_numbers": capacity_numbers[:3],
    }


def citation_grade(card: dict) -> str:
    """Conservative grade; grade A/B is required for a recommendation."""
    score = 0
    email = str(card.get("email") or "")
    official = card.get("official_website") or ""
    if card.get("legal_name_verified"):
        score += 3
    elif card.get("legal_name") and has_legal_suffix(str(card.get("legal_name"))):
        score += 2
    if official:
        score += 2
    if email and "@" in email:
        score += 1
        if official and email_matches_website(email, official):
            score += 1
    if card.get("country") not in {"", "نامشخص", None}:
        score += 1
    if card.get("registry_verified"):
        score += 2
    if card.get("certs_verified"):
        score += 1
    if any("عدم تطابق هویت" in x or "نامعتبر" in x for x in (card.get("red_flags") or [])):
        score -= 3
    if card.get("contradictions"):
        score -= 1
    if score >= 8:
        return "A — قابل استناد نسبی"
    if score >= 5:
        return "B — قابل بررسی با احتیاط"
    if score >= 2:
        return "C — شواهد ضعیف"
    return "D — غیرقابل استناد در این مرحله"
