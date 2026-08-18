"""Quality-first seven-stage import decision pipeline.

Version 2 does not manufacture the required 20 suppliers.  It discovers leads,
validates identity/product relevance, and reports a shortfall when public-web
evidence is insufficient.  This is safer for both the university assignment
and any real purchasing decision.
"""

from __future__ import annotations

import datetime as dt
import re
from collections import Counter, defaultdict
from typing import Any, Callable
from zoneinfo import ZoneInfo

from . import extract as ex
from . import toolkit as tk
from . import webutil as web

Emit = Callable[[str, str, dict | None], None]
LOCAL_TZ = ZoneInfo("Asia/Tehran")
TODAY = dt.datetime.now(LOCAL_TZ).date().isoformat()

OFFICIAL_IRAN_BASE = [
    ("سامانه جامع تجارت (NTSW)", "https://www.ntsw.ir", "ثبت سفارش، مجوزها و وضعیت مجاز/مشروط/ممنوع"),
    ("گمرک جمهوری اسلامی ایران", "https://www.irica.ir", "کد تعرفه ملی، ارزش و رویه گمرکی"),
    ("سازمان ملی استاندارد", "https://www.inso.gov.ir", "استاندارد اجباری و ارزیابی انطباق"),
    ("سازمان توسعه تجارت ایران", "https://tpo.ir", "مقررات و سیاست‌های تجاری"),
    ("بانک مرکزی", "https://www.cbi.ir", "منشأ ارز، اولویت و محدودیت ارزی"),
]

CATEGORY_PROFILES: dict[str, dict[str, Any]] = {
    "agricultural_food": {
        "label_fa": "کالای کشاورزی/غذایی خام",
        "keywords": ["coffee bean", "green coffee", "tea", "grain", "rice", "spice", "cocoa", "seed", "fruit", "beans", "قهوه", "چای", "برنج", "ادویه", "دانه"],
        "roles": ["producer", "processor", "exporter", "cooperative", "processing mill"],
        "origins": ["Brazil", "Colombia", "Ethiopia", "Vietnam", "India"],
        "certs": ["HACCP", "ISO 22000", "FSSC 22000", "BRCGS", "GLOBALG.A.P.", "Organic", "Fairtrade"],
        "official": [
            ("سازمان حفظ نباتات", "https://ppo.ir", "شرایط قرنطینه نباتی و گواهی Phytosanitary"),
            ("سازمان غذا و دارو", "https://www.fda.gov.ir", "ضوابط سلامت، مجوز و برچسب‌گذاری مواد غذایی"),
            ("وزارت جهاد کشاورزی", "https://www.maj.ir", "مجوزهای تخصصی و سیاست کالای کشاورزی"),
        ],
        "risks": [
            ("قرنطینه نباتی", "بررسی نیاز به مجوز قرنطینه، گواهی بهداشت نباتی، ضدعفونی یا شرایط مبدأ."),
            ("سلامت و ایمنی غذایی", "کنترل COA، حدود آلاینده/سموم/سموم قارچی و ضوابط سازمان غذا و دارو متناسب با محصول."),
            ("گواهی مبدأ و رهگیری محموله", "Lot traceability، کشور/منطقه تولید و Certificate of Origin باید در RFQ و اسناد حمل روشن باشد."),
        ],
        "technical": [
            "Please state the exact origin, region, crop/harvest year, variety and processing method for the offered lot.",
            "Please provide the lot-specific quality specification, grading method, moisture limits, defect tolerances and certificate of analysis.",
            "What traceability records and food-safety or phytosanitary documents will accompany the shipment?",
            "Please describe export packing, liner/bag material, net weight per package and container loading plan.",
        ],
        "documents": ["Certificate of Origin", "Phytosanitary/health certificate if applicable", "lot-specific COA", "packing list", "traceability record"],
    },
    "processed_food": {
        "label_fa": "غذا، مکمل یا ماده اولیه خوراکی فرآوری‌شده",
        "keywords": ["whey", "protein", "supplement", "fish oil", "food ingredient", "powder", "concentrate", "extract", "مکمل", "پروتئین", "روغن ماهی", "خوراکی"],
        "roles": ["manufacturer", "ingredient producer", "exporter", "contract manufacturer"],
        "origins": ["Germany", "Netherlands", "India", "Turkey", "China"],
        "certs": ["HACCP", "ISO 22000", "FSSC 22000", "BRCGS", "GMP", "Halal"],
        "official": [("سازمان غذا و دارو", "https://www.fda.gov.ir", "مجوز، ثبت منبع/محصول، سلامت و برچسب‌گذاری")],
        "risks": [
            ("مجوز و ثبت سلامت", "ممکن است ثبت منبع/محصول، IRC یا مجوز تخصصی سازمان غذا و دارو لازم باشد."),
            ("ترکیبات و ادعاهای برچسب", "فرمول، آلرژن، ادعاهای تغذیه‌ای و برچسب فارسی باید کنترل شود."),
            ("آزمون و عمر ماندگاری", "COA هر بچ، روش آزمون، شرایط نگهداری و حداقل shelf life هنگام ورود باید مشخص شود."),
        ],
        "technical": [
            "Please provide the complete composition, ingredient/allergen declaration and product specification with test methods.",
            "Please provide a batch-specific COA, microbiological/contaminant limits and available stability or shelf-life data.",
            "Which food-safety certificates are valid for the actual manufacturing site? Please include certificate numbers and scope.",
            "What is the remaining shelf life at shipment and the required storage/transport condition?",
        ],
        "documents": ["batch COA", "ingredient/allergen statement", "GMP/food-safety certificates", "health/free-sale certificate if applicable", "shelf-life data"],
    },
    "medical_device": {
        "label_fa": "تجهیزات یا ملزومات پزشکی",
        "keywords": ["ultrasound", "medical device", "scanner", "diagnostic", "patient", "surgical", "examination gloves", "nitrile gloves", "سونوگرافی", "تجهیزات پزشکی", "دستکش معاینه"],
        "roles": ["legal manufacturer", "medical device manufacturer", "authorized exporter"],
        "origins": ["Germany", "China", "Malaysia", "Turkey", "South Korea"],
        "certs": ["ISO 13485", "CE", "FDA"],
        "official": [("اداره کل تجهیزات و ملزومات پزشکی", "https://www.imed.ir", "ثبت شرکت/محصول، نمایندگی و مجوز ورود")],
        "risks": [
            ("ثبت تجهیزات پزشکی", "طبقه خطر، ثبت محصول/شرکت و نمایندگی در IMED باید پیش از خرید کنترل شود."),
            ("انطباق و مدارک فنی", "ISO 13485، گواهی انطباق، Declaration of Conformity و scope باید متعلق به مدل و سایت واقعی باشد."),
            ("خدمات پس از فروش", "برای تجهیزات، نصب، آموزش، قطعه، کالیبراسیون و گارانتی باید قابل اجرا در ایران باشد."),
        ],
        "technical": [
            "Please confirm the exact model, intended use, risk class and complete configuration included in the quotation.",
            "Please provide the technical datasheet, Declaration of Conformity and ISO 13485 certificate for the legal manufacturer and site.",
            "Which consumables, probes/accessories, software licences and calibration or preventive-maintenance items are required?",
            "Please state warranty, spare-parts availability, training, service manuals and expected product lifetime.",
        ],
        "documents": ["Declaration of Conformity", "ISO 13485", "model-specific certificate/registration", "technical file summary", "warranty/service statement"],
    },
    "electrical_electronic": {
        "label_fa": "کالای برقی/الکترونیکی و انرژی",
        "keywords": ["solar", "inverter", "pv module", "battery", "electrical", "electronic", "voltage", "power", "پنل خورشیدی", "اینورتر", "برقی", "الکترونیکی"],
        "roles": ["manufacturer", "OEM manufacturer", "authorized exporter"],
        "origins": ["China", "Germany", "Turkey", "South Korea", "Taiwan"],
        "certs": ["IEC", "CE", "TÜV", "UL", "RoHS"],
        "official": [],
        "risks": [
            ("استاندارد و ایمنی الکتریکی", "استاندارد اجباری، ولتاژ/فرکانس، EMC و گزارش آزمون مدل باید کنترل شود."),
            ("خدمات و قطعات", "گارانتی، نرم‌افزار/فریم‌ور، قطعات یدکی و امکان خدمات در ایران ریسک کلیدی است."),
            ("حمل کالای خطرناک", "برای باتری یا اقلام دارای سلول لیتیومی، UN38.3/MSDS و محدودیت حمل بررسی شود."),
        ],
        "technical": [
            "Please confirm the exact model, rated input/output, voltage/frequency, efficiency, protection class and operating conditions.",
            "Please provide model-specific IEC/EN test reports and certificates with verifiable numbers and issuing bodies.",
            "What are the warranty terms, failure-rate data, spare-parts policy and firmware/software support period?",
            "Please state packing, gross/net weight, HS code used for export and any dangerous-goods documents required.",
        ],
        "documents": ["model-specific datasheet", "IEC/EN test report", "certificate and Declaration of Conformity", "warranty", "packing data"],
    },
    "machinery": {
        "label_fa": "ماشین‌آلات و تجهیزات صنعتی",
        "keywords": ["machine", "machinery", "equipment", "production line", "espresso machine", "compressor", "pump", "cnc", "دستگاه", "ماشین", "خط تولید", "کمپرسور", "پمپ"],
        "roles": ["manufacturer", "OEM factory", "industrial exporter"],
        "origins": ["China", "Turkey", "Italy", "Germany", "India"],
        "certs": ["ISO 9001", "CE", "UL"],
        "official": [],
        "risks": [
            ("استاندارد و ایمنی ماشین", "مدل، حفاظت‌ها، برق ورودی، Declaration of Conformity و استانداردهای ایمنی باید تطبیق یابد."),
            ("نصب و راه‌اندازی", "هزینه نصب، آموزش، FAT/SAT و الزامات زیرساختی باید در Quote روشن شود."),
            ("قطعات یدکی و توقف تولید", "لیست spare parts، زمان تأمین و تعهد خدمات پس از فروش باید ارزیابی شود."),
        ],
        "technical": [
            "Please provide the exact model, rated capacity, utility requirements, dimensions, net/gross weight and layout drawing.",
            "Please identify all included components, exclusions, recommended spare parts and consumables for two years of operation.",
            "What FAT/SAT, installation, commissioning and operator-training support is included?",
            "Please provide model-specific safety certificates, manuals, warranty terms and reference installations.",
        ],
        "documents": ["technical datasheet", "GA/layout drawing", "manual", "certificate/DoC", "spare-parts list", "warranty"],
    },
    "chemical_material": {
        "label_fa": "مواد شیمیایی/پلیمری/اولیه صنعتی",
        "keywords": ["chemical", "resin", "polymer", "oil", "acid", "powder", "granule", "compound", "sheet", "steel", "galvanized", "پارچه", "اسپان", "ورق", "فولاد", "مواد شیمیایی"],
        "roles": ["producer", "manufacturer", "mill", "exporter"],
        "origins": ["China", "Turkey", "India", "Germany", "UAE"],
        "certs": ["ISO 9001", "REACH", "RoHS", "OEKO-TEX"],
        "official": [],
        "risks": [
            ("ترکیب و گرید", "CAS/grade/composition و tolerances باید با کاربرد و کد تعرفه منطبق باشد."),
            ("ایمنی و حمل", "SDS، طبقه خطر، UN number و محدودیت حمل/انبارش در صورت شیمیایی بودن کنترل شود."),
            ("آزمون و استاندارد", "COA هر بچ، روش آزمون و استاندارد ASTM/EN/ISO مرتبط باید درخواست شود."),
        ],
        "technical": [
            "Please confirm the exact grade, composition, applicable ASTM/EN/ISO standard and guaranteed tolerances.",
            "Please provide a recent lot COA, technical data sheet and SDS where applicable.",
            "What are the production route, monthly capacity, minimum order and batch-to-batch consistency controls?",
            "Please state export packing, corrosion/moisture protection, coil/roll/sheet dimensions and loading plan as applicable.",
        ],
        "documents": ["TDS", "lot COA", "SDS if applicable", "standard compliance statement", "packing specification"],
    },
    "automotive": {
        "label_fa": "قطعات و ملزومات خودرویی",
        "keywords": ["tire", "tyre", "automotive", "car", "vehicle", "brake", "bearing", "تایر", "لاستیک", "خودرو"],
        "roles": ["manufacturer", "OEM/OES supplier", "authorized exporter"],
        "origins": ["China", "Turkey", "Thailand", "South Korea", "India"],
        "certs": ["IATF 16949", "ECE", "DOT", "ISO 9001"],
        "official": [],
        "risks": [
            ("استاندارد و اصالت مدل", "استاندارد اجباری، E-mark/DOT یا تأیید نوع و تطابق سایز/مدل باید کنترل شود."),
            ("تاریخ تولید و رهگیری", "DOT/date code، batch traceability و حداقل عمر باقیمانده در ورود اهمیت دارد."),
            ("نمایندگی و خدمات", "اصالت برند، گارانتی و مسئولیت محصول باید روشن شود."),
        ],
        "technical": [
            "Please confirm exact size/model, load and speed ratings, construction, pattern and applicable ECE/DOT approvals.",
            "Please provide approval numbers, IATF/quality certificates and model-specific test reports.",
            "What maximum production age at shipment, batch traceability and warranty terms can you guarantee?",
            "Please state packing, units per container, monthly capacity and OEM/OES references.",
        ],
        "documents": ["type approval", "IATF/quality certificate", "model test report", "warranty", "production-date commitment"],
    },
    "general": {
        "label_fa": "کالای عمومی",
        "keywords": [],
        "roles": ["manufacturer", "producer", "exporter"],
        "origins": ["China", "Turkey", "India", "Germany", "UAE"],
        "certs": ["ISO 9001", "industry-specific certificate"],
        "official": [],
        "risks": [
            ("طبقه‌بندی و مجوز تخصصی", "کد HS، استاندارد و مجوز تخصصی باید با کاربرد نهایی و مشخصات دقیق کنترل شود."),
            ("کیفیت و انطباق", "TDS/COA/test report و scope گواهی باید متعلق به مدل و سایت تولید باشد."),
            ("حمل و بسته‌بندی", "شرایط حمل، بسته‌بندی صادراتی، خطرپذیری و بیمه باید بررسی شود."),
        ],
        "technical": [
            "Please confirm the exact grade/model and provide a complete technical specification with guaranteed tolerances.",
            "Please provide model- or lot-specific test reports and verifiable certificates relevant to this product.",
            "What is your actual manufacturing/processing role, monthly capacity and standard production lead time?",
            "Please describe sample policy, export packing, warranty/shelf life and quality-claim procedure.",
        ],
        "documents": ["technical specification", "test report/COA", "relevant certificates", "packing specification", "warranty or shelf-life statement"],
    },
}

CATEGORY_ALIASES = {
    "food": "processed_food", "agriculture": "agricultural_food", "medical": "medical_device",
    "electrical": "electrical_electronic", "industrial": "machinery", "chemical": "chemical_material",
}

PROMPT_LIBRARY = [
    {"stage": "مرحله ۱", "purpose": "Product Brief و HS", "prompt": "تعریف محصول را فقط از ورودی و منابع پذیرفته‌شده بساز. ویژگی‌های مؤثر بر طبقه‌بندی HS را جدا کن. هیچ کد ملی ۸/۱۰ رقمی را بدون مرجع رسمی قطعی اعلام نکن."},
    {"stage": "مرحله ۲", "purpose": "بازار و مقررات ایران", "prompt": "فقط نتیجه‌ای را شاهد واردات ایران بدان که هم محصول، هم ایران و هم مفهوم واردات/تعرفه را داشته باشد. منابع رسمی را از فروشنده و مقاله تفکیک کن؛ موارد رسمی کنترل‌نشده را «نیازمند راستی‌آزمایی» بنویس."},
    {"stage": "مرحله ۳", "purpose": "Supplier Sourcing", "prompt": "نتیجه جستجو supplier نیست. قبل از Longlist نام معتبر، شاهد محصول، نقش تأمین، کشور/دامنه و URL مشخص را بررسی کن. صفحات category، buyer lead، مقاله و دایرکتوری عمومی را حذف کن. اگر کمتر از ۲۰ شرکت معتبر یافت شد، کمبود را صریح گزارش کن و رکورد نساز."},
    {"stage": "مرحله ۴", "purpose": "Scoring", "prompt": "هر نمره را به شاهد متصل کن. گواهی ادعایی بدون شماره/مرجع حداکثر ۲ از ۱۰ است. پاسخ‌گویی تا قبل از پاسخ واقعی صفر/N/A است. شرکت فاقد هویت نباید Top 5 شود."},
    {"stage": "مرحله ۵", "purpose": "Due Diligence", "prompt": "نام، دامنه، ایمیل و کشور هر شرکت را در فضای داده جدا بررسی کن. وب‌سایت یا نتیجه شرکت دیگر را متصل نکن. ثبت و گواهی فقط پس از کنترل مرجع رسمی verified محسوب شود."},
    {"stage": "مرحله ۶", "purpose": "RFQ", "prompt": "ایمیل انگلیسی کوتاه، پاسخ‌پذیر و محصول‌محور بساز. فقط fact تأییدشده را برای personalization استفاده کن و placeholder یا عبارت نامشخص را حذف کن."},
    {"stage": "مرحله ۷", "purpose": "Decision", "prompt": "انتخاب را فقط میان گزینه‌های عبورکرده از Hard Gate انجام بده. اگر دو گزینه قابل دفاع نیست، به‌جای انتخاب اجباری وضعیت Not Ready و برنامه اقدام ارائه کن."},
]


def _product_en(inp: dict) -> str:
    return (inp.get("name_en") or inp.get("name_fa") or "product").strip()


def _product_fa(inp: dict) -> str:
    return (inp.get("name_fa") or inp.get("name_en") or "محصول").strip()


def _unverified(msg: str) -> str:
    return f"{msg} — نیازمند راستی‌آزمایی"


def _contains_persian(text: str) -> bool:
    return bool(re.search(r"[\u0600-\u06FF]", text or ""))


def classify_product(inp: dict) -> tuple[str, dict[str, Any]]:
    requested = (inp.get("product_category") or "auto").strip().lower()
    requested = CATEGORY_ALIASES.get(requested, requested)
    if requested in CATEGORY_PROFILES and requested != "general":
        return requested, CATEGORY_PROFILES[requested]
    blob = " ".join(str(inp.get(k) or "") for k in ("name_fa", "name_en", "application", "specs", "grade_model")).lower()
    scores: dict[str, int] = {}
    for key, profile in CATEGORY_PROFILES.items():
        if key == "general":
            continue
        scores[key] = sum(1 for kw in profile["keywords"] if kw.lower() in blob)
    best = max(scores, key=scores.get) if scores and max(scores.values()) > 0 else "general"
    return best, CATEGORY_PROFILES[best]


def assess_input(inp: dict) -> dict[str, Any]:
    fields = ["name_fa", "name_en", "application", "specs", "grade_model", "unit", "qty_hint", "target_customer", "origin_pref"]
    present = [f for f in fields if str(inp.get(f) or "").strip()]
    warnings: list[str] = []
    if not inp.get("name_en"):
        warnings.append("نام انگلیسی تکمیل نشده؛ کیفیت جستجوی بین‌المللی کاهش می‌یابد.")
    if not inp.get("specs"):
        warnings.append("مشخصات فنی تکمیل نشده؛ HS، تطابق محصول و RFQ قطعی نیست.")
    if not inp.get("qty_hint"):
        warnings.append("مقدار تقریبی سفارش مشخص نشده؛ Quote قابل مقایسه نخواهد بود.")
    if not inp.get("origin_pref"):
        warnings.append("مبدأ ترجیحی وارد نشده؛ ایجنت از کشورهای رایج همان گروه محصول استفاده می‌کند.")
    score = round(len(present) / len(fields) * 100)
    return {"score": score, "present_fields": present, "missing_fields": [f for f in fields if f not in present], "warnings": warnings, "status": "good" if score >= 75 else "partial" if score >= 45 else "insufficient"}


def _origin_list(inp: dict, profile: dict[str, Any]) -> list[str]:
    raw = (inp.get("origin_pref") or "").strip()
    fa_map = {"چین": "China", "ترکیه": "Turkey", "هند": "India", "آلمان": "Germany", "ایتالیا": "Italy", "برزیل": "Brazil", "کلمبیا": "Colombia", "اتیوپی": "Ethiopia", "ویتنام": "Vietnam", "مالزی": "Malaysia", "کره جنوبی": "South Korea", "تایوان": "Taiwan", "سریلانکا": "Sri Lanka", "امارات": "UAE"}
    for fa, en in fa_map.items():
        raw = raw.replace(fa, en)
    parts = [p.strip() for p in re.split(r"[/,،;|]|\bor\b", raw, flags=re.I) if p.strip()]
    clean: list[str] = []
    for p in parts:
        if len(p) <= 30 and p not in clean:
            clean.append(p)
    return (clean or list(profile.get("origins") or []))[:5]


def _build_search_phrases(name_en: str, inp: dict, profile: dict[str, Any], origins: list[str]) -> list[str]:
    base = name_en.strip()
    roles = profile.get("roles") or ["manufacturer", "exporter"]
    phrases = [f'"{base}" {role}' for role in roles[:4]]
    for origin in origins[:4]:
        phrases.append(f'"{base}" {roles[0]} {origin}')
    if inp.get("specs") and not _contains_persian(inp["specs"]):
        phrases.append(f'"{base}" "{inp["specs"][:100]}" supplier')
    phrases += [f'"{base}" company profile exporter', f'"{base}" contact supplier']
    return list(dict.fromkeys(phrases))[:12]


def _hs_attributes(name: str, category: str) -> list[str]:
    low = name.lower()
    attrs: list[str] = []
    if category in {"agricultural_food", "processed_food"}:
        attrs += ["processed or unprocessed", "species/composition", "retail or bulk form"]
        if "coffee" in low:
            attrs += ["roasted or not roasted", "decaffeinated or not decaffeinated"]
    elif category == "medical_device":
        attrs += ["intended use", "principal function", "complete device or part/accessory"]
    elif category == "electrical_electronic":
        attrs += ["principal electrical function", "power/voltage", "complete unit or component"]
    elif category == "chemical_material":
        attrs += ["chemical composition/material", "grade/purity", "form and end use"]
    elif category == "machinery":
        attrs += ["principal function", "stand-alone machine or line", "complete unit or part"]
    else:
        attrs += ["material/composition", "principal function", "complete good or part"]
    return list(dict.fromkeys(attrs))


# ---------------------------------------------------------------------------
# Stage 1 — Product Brief and HS candidate research
# ---------------------------------------------------------------------------
def stage1_product(inp: dict, sources: list, emit: Emit, tools: tk.ToolLog) -> dict:
    name_en, name_fa = _product_en(inp), _product_fa(inp)
    category, profile = classify_product(inp)
    origins = _origin_list(inp, profile)
    emit("stage1", f"تعریف محصول و طبقه‌بندی گروه: {profile['label_fa']}", None)

    queries = [
        f'"{name_en}" HS code customs', f'"{name_en}" harmonized tariff code',
        f'"{name_en}" product specification', f'کد تعرفه "{name_fa}"',
        f'تعرفه گمرکی "{name_fa}" واردات',
    ]
    if inp.get("specs"):
        queries.append(f'"{name_en}" "{inp["specs"][:100]}" HS code')
    hits = tk.run_queries(tools, "public_web_search", "مرحله ۱", queries, max_results=7, note="جستجوی کاندید HS و مشخصات؛ نتیجه خام هنوز منبع پذیرفته‌شده نیست")

    weighted: Counter[str] = Counter()
    counts: Counter[str] = Counter()
    evidence: defaultdict[str, list] = defaultdict(list)
    grade_weight = {"A": 4, "B": 3, "C": 1, "D": 0}
    for h in hits:
        blob = f"{h.get('title','')} {h.get('snippet','')}"
        relevance = ex.product_match_score(blob, name_en)
        if relevance < 0.35 or h.get("authority_grade") == "D":
            continue
        codes = ex.extract_hs_candidates(blob)
        if not codes:
            continue
        for code in codes:
            counts[code] += 1
            weighted[code] += grade_weight.get(h.get("authority_grade") or "C", 1)
            evidence[code].append(h)
            web.log_source(sources, h, "مرحله ۱ — HS candidate", claim=f"کاندید HS برای {name_en}: {code}", relevance=relevance)

    ranked_codes = sorted(weighted, key=lambda c: (weighted[c], counts[c]), reverse=True)
    six_digit = [c for c in ranked_codes if len(re.sub(r"\D", "", c)) == 6]
    primary = six_digit[0] if six_digit else (ranked_codes[0] if ranked_codes else "")
    alternatives = [c for c in ranked_codes if c != primary][:3]
    hs_evidence = []
    for code in ranked_codes[:4]:
        hs_evidence.append({
            "code": code, "weighted_score": weighted[code], "observations": counts[code],
            "source_ids": list(dict.fromkeys(h.get("sid") for h in evidence[code] if h.get("sid"))),
            "confidence": "medium" if weighted[code] >= 6 else "low",
        })
    if primary:
        reason = (
            f"کد {primary} صرفاً کاندید پژوهشی است؛ از {counts[primary]} نتیجه پذیرفته‌شده با امتیاز وزنی {weighted[primary]} استخراج شد. "
            "ویژگی‌های فنی مؤثر و کد ۸/۱۰ رقمی ایران باید در کتاب مقررات/سامانه رسمی همان سال کنترل شود."
        )
    else:
        reason = _unverified("کد HS قابل اتکا از منابع باز استخراج نشد؛ از درج کد حدسی خودداری شد")

    phrases = _build_search_phrases(name_en, inp, profile, origins)
    input_quality = assess_input(inp)
    description = (
        f"{name_fa} / {name_en}. کاربرد اعلام‌شده: {inp.get('application') or 'تکمیل نشده'}. "
        f"مشخصات اعلام‌شده: {inp.get('specs') or 'تکمیل نشده'}. این تعریف از ورودی کاربر ساخته شده و متن تبلیغاتی وب در آن ادغام نشده است."
    )
    brief = {
        "name_fa": name_fa, "name_en": name_en,
        "application": inp.get("application") or _unverified("کاربرد در ایران تکمیل نشده"),
        "specs": inp.get("specs") or _unverified("مشخصات فنی تکمیل نشده"),
        "grade_model": inp.get("grade_model") or _unverified("گرید/مدل تکمیل نشده"),
        "unit": inp.get("unit") or _unverified("واحد خرید تکمیل نشده"),
        "target_customer": inp.get("target_customer") or _unverified("مشتری هدف تکمیل نشده"),
        "qty_hint": inp.get("qty_hint") or _unverified("مقدار سفارش تکمیل نشده"),
        "description_web": description,
        "product_category": category, "product_category_label": profile["label_fa"],
        "origin_strategy": origins, "supplier_roles": profile["roles"],
        "classification_attributes": _hs_attributes(name_en, category),
        "search_phrases": phrases,
        "hs_primary": primary, "hs_alternatives": alternatives, "hs_reason": reason,
        "hs_counts": dict(counts), "hs_evidence": hs_evidence,
        "input_quality": input_quality,
        "notes": [
            "کد شش‌رقمی HS جهانی با کد ۸/۱۰ رقمی ملی یکسان نیست.",
            "خروجی جستجوی وب به‌تنهایی منبع قطعی طبقه‌بندی نیست.",
            "اگر مشخصات مؤثر بر طبقه‌بندی ناقص باشد، نتیجه باید نیازمند راستی‌آزمایی بماند.",
        ],
    }
    emit("stage1", f"Product Brief آماده شد | HS: {primary or 'تأیید نشد'} | کیفیت ورودی: {input_quality['score']}٪", {"brief": True})
    return brief


# ---------------------------------------------------------------------------
# Stage 2 — Iran import opportunity and regulatory matrix
# ---------------------------------------------------------------------------
def _official_portals(profile: dict[str, Any]) -> list[dict[str, str]]:
    rows = OFFICIAL_IRAN_BASE + list(profile.get("official") or [])
    seen: set[str] = set()
    out = []
    for name, url, check in rows:
        if url in seen:
            continue
        seen.add(url)
        out.append({"name": name, "url": url, "check": check, "status": "کنترل دستی/رسمی در تاریخ پروژه الزامی است", "verified": False})
    return out


def stage2_market(inp: dict, brief: dict, sources: list, emit: Emit, tools: tk.ToolLog) -> dict:
    name_fa, name_en = brief["name_fa"], brief["name_en"]
    profile = CATEGORY_PROFILES[brief["product_category"]]
    emit("stage2", "جستجوی شواهد ایران‌محور و ساخت ماتریس مقررات…", None)
    queries = [
        f'واردات "{name_fa}" ایران', f'تعرفه گمرکی "{name_fa}" ثبت سفارش',
        f'"{name_en}" import Iran customs', f'استاندارد اجباری "{name_fa}"',
        f'مجوز واردات "{name_fa}" ایران', f'"{name_en}" Iran importer market',
    ]
    hits = tk.run_queries(tools, "public_web_search", "مرحله ۲", queries, max_results=8, note="فیلتر سه‌گانه محصول + ایران + مفهوم واردات/تعرفه")
    accepted = []
    import_terms = ("واردات", "تعرفه", "گمرک", "ثبت سفارش", "import", "customs", "tariff")
    iran_terms = ("ایران", "iran", ".ir/")
    for h in hits:
        blob = f"{h.get('title','')} {h.get('snippet','')} {h.get('url','')}".lower()
        relevance = max(ex.product_match_score(blob, name_en), ex.product_match_score(blob, name_fa))
        if relevance < 0.35 or not any(x in blob for x in import_terms) or not any(x in blob for x in iran_terms):
            continue
        if h.get("authority_grade") == "D" or ex.page_kind(h.get("url") or "", h.get("title") or "", h.get("snippet") or "") in {"buyer_or_lead", "content_or_social", "content_or_article"}:
            continue
        h = {**h, "relevance": relevance}
        accepted.append(h)
    accepted.sort(key=lambda x: ({"A": 0, "B": 1, "C": 2}.get(x.get("authority_grade"), 3), -x["relevance"]))
    accepted = accepted[:12]
    evidence_rows = []
    for h in accepted:
        sid = web.log_source(sources, h, "مرحله ۲ — شواهد واردات ایران", claim=f"شاهد احتمالی واردات/بازار ایران برای {name_fa}", relevance=h["relevance"])
        evidence_rows.append({
            "claim": (h.get("title") or "")[:180], "url": h.get("url"), "domain": h.get("domain"),
            "snippet": (h.get("snippet") or "")[:400], "checked_on": TODAY,
            "authority_grade": h.get("authority_grade"), "source_type": h.get("source_type"),
            "relevance": round(h["relevance"], 2), "source_id": sid,
        })
    has_strong = any(e.get("authority_grade") in {"A", "B"} for e in evidence_rows)
    imported_likely = len(evidence_rows) >= 3 or (len(evidence_rows) >= 2 and has_strong)
    if imported_likely:
        statement = f"{len(evidence_rows)} شاهد ایران‌محور پس از فیلتر پذیرفته شد؛ وجود جریان واردات محتمل است، اما مجازبودن و آمار قطعی هنوز باید رسمی کنترل شود."
    elif evidence_rows:
        statement = _unverified(f"فقط {len(evidence_rows)} شاهد ایران‌محور قابل قبول پیدا شد و برای نتیجه قطعی کافی نیست")
    else:
        statement = _unverified("شاهد ایران‌محور کافی از وب عمومی پیدا نشد؛ ایجنت ادعای واردات قطعی نمی‌کند")

    generic_risks = [
        ("ثبت سفارش و وضعیت ورود", "مجاز/مشروط/ممنوع، گروه کالایی و مجوزهای سیستمی باید در NTSW همان روز کنترل شود."),
        ("HS و حقوق ورودی", "کد ملی، مأخذ حقوق ورودی، مالیات و رویه گمرکی باید از کتاب مقررات و گمرک کنترل شود."),
        ("ارز، پرداخت و تحریم", "روش تأمین ارز، امکان بانک/حواله و ریسک تحریم کشور/فروشنده باید پیش از قرارداد بررسی شود."),
        ("استاندارد اجباری", "فهرست استاندارد اجباری و روش ارزیابی انطباق ممکن است تغییر کند."),
    ]
    risks = []
    for title, detail in generic_risks + list(profile.get("risks") or []):
        risks.append({
            "title": title, "level": "نامشخص تا کنترل رسمی", "detail": detail,
            "verification": "نیازمند راستی‌آزمایی در منبع رسمی/استعلام کارشناس", "verified": False,
            "evidence_ids": [],
        })
    snapshot = {
        "imported_evidence": evidence_rows, "imported_likely": imported_likely,
        "imported_statement": statement, "regulatory_risks": risks,
        "official_portals": _official_portals(profile),
        "official_verification_status": "not_verified",
        "opportunity_notes": [
            "تعداد نتایج جستجو با تعداد اسناد پذیرفته‌شده یکسان نیست.",
            "وجود بازار یا فروش داخلی، مجازبودن واردات را اثبات نمی‌کند.",
            "هر مورد رسمی کنترل‌نشده در این گزارش عمداً «نیازمند راستی‌آزمایی» باقی مانده است.",
        ],
    }
    emit("stage2", f"شواهد پذیرفته‌شده: {len(evidence_rows)} | وضعیت رسمی: کنترل نشده", {"market": True})
    return snapshot


# ---------------------------------------------------------------------------
# Stage 3 — supplier discovery, entity extraction and hard relevance gates
# ---------------------------------------------------------------------------
CHANNEL_NAMES = {
    "alibaba.com": "Alibaba", "made-in-china.com": "Made-in-China", "globalsources.com": "Global Sources",
    "indiamart.com": "IndiaMART", "tradeindia.com": "TradeIndia", "europages.com": "Europages",
    "europages.co.uk": "Europages", "ec21.com": "EC21", "21food.com": "21food",
    "goldsupplier.com": "GoldSupplier", "go4worldbusiness.com": "go4WorldBusiness",
    "globaltradeplaza.com": "Global Trade Plaza", "tradekey.com": "TradeKey", "tradewheel.com": "TradeWheel",
}


def _sourcing_queries(name_en: str, profile: dict[str, Any], origins: list[str]) -> tuple[list[str], list[str]]:
    roles = profile.get("roles") or ["manufacturer", "exporter"]
    open_queries = [f'"{name_en}" "{r}"' for r in roles[:4]]
    for origin in origins[:5]:
        open_queries += [f'"{name_en}" {roles[0]} {origin}', f'"{name_en}" exporter {origin}']
    open_queries += [f'"{name_en}" "Co., Ltd."', f'"{name_en}" "LLC" exporter', f'"{name_en}" company profile contact']
    targeted = [
        f'site:made-in-china.com/product "{name_en}"', f'site:alibaba.com/product-detail "{name_en}"',
        f'site:indiamart.com "{name_en}" manufacturer', f'site:europages.com "{name_en}" supplier',
        f'site:ec21.com "{name_en}" supplier', f'site:globalsources.com "{name_en}" supplier',
        f'site:21food.com "{name_en}"', f'site:goldsupplier.com "{name_en}"',
    ]
    return list(dict.fromkeys(open_queries))[:18], targeted


def _candidate_grade(c: dict) -> str:
    if c.get("legal_name") and c.get("official_website") and c.get("contact") and ex.email_matches_website(c["contact"], c["official_website"]):
        return "A"
    if c.get("legal_name") and (c.get("official_website") or c.get("profile_url")) and c.get("country") != "نامشخص":
        return "B"
    return "C"


def _candidate_from_hit(h: dict, page: dict, brief: dict) -> tuple[dict | None, str]:
    title, snippet, url = h.get("title") or "", h.get("snippet") or "", h.get("url") or ""
    kind = ex.page_kind(url, title, snippet)
    if kind in {"content_or_social", "content_or_article", "directory_or_data", "buyer_or_lead", "marketplace_category", "directory_or_category"}:
        return None, f"صفحه غیرشرکتی ({kind})"
    page_title = page.get("title") or ""
    if page_title.lower().strip() in {"error page", "just a moment...", "page not found", "404 not found"}:
        return None, "صفحه خطا/ضدبات به‌جای پروفایل شرکت"
    combined = " ".join([title, snippet, page_title, page.get("meta_description") or "", (page.get("text") or "")[:5000]])
    result_relevance = ex.product_match_score(f"{title} {snippet}", brief["name_en"])
    page_relevance = ex.product_match_score(" ".join([page_title, page.get("meta_description") or "", (page.get("text") or "")[:1600]]), brief["name_en"])
    relevance = max(result_relevance, page_relevance)
    if relevance < 0.45:
        return None, f"تطابق محصول ناکافی ({relevance:.2f})"
    # If the page was fetched, its primary title/intro must also concern the
    # product; this prevents an unrelated storefront product from passing due
    # to a footer/list of other products.
    if page.get("ok") and page_title and page_relevance < 0.35:
        return None, f"محصول در محتوای اصلی صفحه دیده نشد ({page_relevance:.2f})"
    if not ex.looks_like_supplier(title, combined, url, brief["name_en"]):
        return None, "نقش تأمین/تولید/صادرات قابل مشاهده نیست"
    entity = ex.extract_company_entity(title, snippet, url, page)
    name = entity.get("name") or ""
    if not name or not ex.is_credible_company_name(name):
        return None, "نام شرکت/برند قابل استناد استخراج نشد"
    if not entity.get("legal_name"):
        name_tokens = set(ex.distinctive_name_tokens(name))
        product_tokens = set(ex.meaningful_product_tokens(brief["name_en"]))
        overlap = len(name_tokens & product_tokens) / max(1, len(name_tokens))
        host_blob = ex.base_domain(url).replace("-", "").replace(".", "")
        domain_support = any(t in host_blob for t in name_tokens if len(t) >= 5)
        if overlap >= 0.66 and not domain_support:
            return None, "نام استخراج‌شده صرفاً عبارت محصول است، نه هویت شرکت"
    country_context = " ".join([title, page.get("title") or "", page.get("meta_description") or "", (page.get("text") or "")[:1800]])
    country = ex.guess_company_country(country_context, page.get("final_url") or url, page.get("addresses") or []) or "نامشخص"
    official = ""
    market = ex.marketplace_of(url)
    if not market and page.get("ok"):
        official = page.get("canonical_url") or page.get("final_url") or url
    email = ex.first_email(page.get("emails") or [], official)
    signals = ex.snippet_signals(combined)
    candidate = {
        "name": name, "legal_name": entity.get("legal_name") or "",
        "entity_method": entity.get("method"), "entity_confidence": entity.get("confidence") or 0,
        "page_kind": kind, "url": url, "profile_url": url,
        "official_website": official, "country": country,
        "origin_preference_match": country.lower() in {str(x).lower() for x in (brief.get("origin_strategy") or [])},
        "company_type": " / ".join(brief.get("supplier_roles") or [])[:120],
        "related_product": brief["name_en"], "product_match": round(relevance, 2),
        "product_evidence": (page.get("meta_description") or snippet or page.get("text") or "")[:500],
        "contact": email, "phones": ex.plausible_phones(page.get("phones") or []),
        "source_channel": CHANNEL_NAMES.get(market or "", "وب‌سایت مستقل/وب عمومی"),
        "source_tool": h.get("tool_name") or "Public web search (ddgs)",
        "source_title": title, "snippet": (snippet + " | " + (page.get("text") or "")[:220])[:600],
        "checked_on": TODAY, "year_founded": ex.year_founded(page.get("text") or ""),
        "certs_mentioned": ex.extract_certs(combined), "certs_verified": [],
        "signals": signals, "discovery_urls": [url], "source_ids": [],
        "key": ex.company_key(name, official or url),
    }
    candidate["candidate_grade"] = _candidate_grade(candidate)
    candidate["identity_status"] = "supported_public_identity" if candidate["candidate_grade"] in {"A", "B"} else "candidate_needs_identity_check"
    candidate["eligible_for_scoring"] = bool(candidate["entity_confidence"] >= 0.64 and relevance >= 0.45)
    return candidate, ""


def stage3_sourcing(inp: dict, brief: dict, sources: list, emit: Emit, tools: tk.ToolLog) -> dict:
    name_en = brief["name_en"]
    profile = CATEGORY_PROFILES[brief["product_category"]]
    origins = brief["origin_strategy"]
    persona = {
        "country_pref": " / ".join(origins),
        "company_type": "، ".join(profile["roles"]),
        "track_record": "هویت قابل جستجو، سابقه و دامنه/پروفایل پایدار؛ نه صرفاً عنوان یک نتیجه جستجو",
        "capacity": "توان تأمین مقدار سفارش با شاهد عددی یا توضیح فرآیند/سایت تولید",
        "certificates": "گواهی مرتبط با گروه محصول؛ ادعا بدون شماره و مرجع verified نیست",
        "moq": "متناسب با سفارش آزمایشی و تجاری؛ فقط از صفحه رسمی یا Quote",
        "export_markets": "شاهد صادرات، مقصد یا سابقه مستند؛ عبارت global به‌تنهایی کافی نیست",
        "terms": "Incoterms 2020، نمونه، lead time، payment و packing در پاسخ RFQ",
    }
    emit("stage3", "کشف سرنخ‌ها با توجه به نوع کالا و مبدأ ترجیحی…", None)
    open_q, targeted_q = _sourcing_queries(name_en, profile, origins)
    hits = tk.run_queries(tools, "public_web_search", "مرحله ۳", open_q, max_results=6, note="جستجوی نقش‌محور و مبدأمحور")
    hits += tk.run_queries(tools, "targeted_site_search", "مرحله ۳", targeted_q, max_results=6, note="site search در B2B؛ API این پلتفرم‌ها استفاده نشده است")
    # Deduplicate search hits before any fetch.
    unique: dict[str, dict] = {}
    for h in hits:
        if h.get("url") and h["url"] not in unique:
            unique[h["url"]] = h
    hits = list(unique.values())

    prefiltered: list[dict] = []
    rejected: list[dict] = []
    for h in hits:
        kind = ex.page_kind(h.get("url") or "", h.get("title") or "", h.get("snippet") or "")
        relevance = ex.product_match_score(f"{h.get('title','')} {h.get('snippet','')}", name_en)
        if kind in {"content_or_social", "content_or_article", "directory_or_data", "buyer_or_lead", "marketplace_category", "directory_or_category"}:
            rejected.append({"reason": f"صفحه غیرشرکتی ({kind})", "title": h.get("title"), "url": h.get("url")})
            continue
        if relevance < 0.30:
            rejected.append({"reason": f"نامرتبط با محصول ({relevance:.2f})", "title": h.get("title"), "url": h.get("url")})
            continue
        prefiltered.append(h)

    emit("stage3", f"{len(prefiltered)} سرنخ برای واکشی و استخراج هویت انتخاب شد", None)
    pages = web.fetch_many([h["url"] for h in prefiltered[:90]], workers=8, timeout=9)
    candidates: list[dict] = []
    by_key: dict[str, dict] = {}
    for h in prefiltered[:90]:
        page = pages.get(h["url"]) or {}
        candidate, reason = _candidate_from_hit(h, page, brief)
        if not candidate:
            rejected.append({"reason": reason, "title": h.get("title"), "url": h.get("url")})
            continue
        key = candidate["key"]
        # Official domain is an additional dedup key; a marketplace and official
        # page with the same legal name merge instead of becoming two suppliers.
        domain_key = ex.base_domain(candidate.get("official_website") or "")
        duplicate = by_key.get(key) or (by_key.get("domain:" + domain_key) if domain_key else None)
        if duplicate:
            duplicate["discovery_urls"] = list(dict.fromkeys(duplicate.get("discovery_urls", []) + [candidate["url"]]))
            duplicate["product_match"] = max(duplicate["product_match"], candidate["product_match"])
            duplicate["certs_mentioned"] = sorted(set(duplicate.get("certs_mentioned", []) + candidate.get("certs_mentioned", [])))
            if not duplicate.get("contact") and candidate.get("contact"):
                duplicate["contact"] = candidate["contact"]
            rejected.append({"reason": "تکراری پس از Entity Resolution", "title": candidate["name"], "url": candidate["url"]})
            continue
        by_key[key] = candidate
        if domain_key:
            by_key["domain:" + domain_key] = candidate
        candidates.append(candidate)
        sid = web.log_source(sources, h, "مرحله ۳ — Supplier candidate", claim=f"شاهد هویت/محصول برای {candidate['name']}", relevance=candidate["product_match"])
        if sid:
            candidate["source_ids"].append(sid)

    # If the strict result is short, run focused legal-name/origin queries once.
    if len(candidates) < 20:
        extra_q = []
        for origin in origins[:4]:
            extra_q += [f'"{name_en}" "Company Limited" {origin}', f'"{name_en}" "export" "contact" {origin}']
        extra_q += [f'"{name_en}" "Co., Ltd." manufacturer', f'"{name_en}" "Pvt Ltd" exporter', f'"{name_en}" "GmbH" supplier']
        extra_hits = tk.run_queries(tools, "regional_search", "مرحله ۳", extra_q, max_results=7, note="جستجوی تکمیلی فقط با نام حقوقی/مبدأ؛ بدون پرکردن مصنوعی")
        extra_hits = [h for h in extra_hits if h.get("url") not in {x.get("url") for x in hits}]
        extra_pre = []
        for h in extra_hits:
            kind = ex.page_kind(h.get("url") or "", h.get("title") or "", h.get("snippet") or "")
            if kind in {"content_or_social", "content_or_article", "directory_or_data", "buyer_or_lead", "marketplace_category", "directory_or_category"}:
                rejected.append({"reason": f"صفحه غیرشرکتی ({kind})", "title": h.get("title"), "url": h.get("url")})
                continue
            if ex.product_match_score(f"{h.get('title','')} {h.get('snippet','')}", name_en) >= 0.30:
                extra_pre.append(h)
        extra_pages = web.fetch_many([h["url"] for h in extra_pre[:50]], workers=8, timeout=9)
        for h in extra_pre[:50]:
            candidate, reason = _candidate_from_hit(h, extra_pages.get(h["url"]) or {}, brief)
            if not candidate:
                rejected.append({"reason": reason, "title": h.get("title"), "url": h.get("url")})
                continue
            key = candidate["key"]
            domain_key = ex.base_domain(candidate.get("official_website") or "")
            if by_key.get(key) or (domain_key and by_key.get("domain:" + domain_key)):
                rejected.append({"reason": "تکراری پس از Entity Resolution", "title": candidate["name"], "url": candidate["url"]})
                continue
            by_key[key] = candidate
            if domain_key:
                by_key["domain:" + domain_key] = candidate
            candidates.append(candidate)
            sid = web.log_source(sources, h, "مرحله ۳ — Supplier candidate", claim=f"شاهد هویت/محصول برای {candidate['name']}", relevance=candidate["product_match"])
            if sid:
                candidate["source_ids"].append(sid)
            if len(candidates) >= 30:
                break

    candidates.sort(key=lambda c: (0 if c.get("origin_preference_match") else 1, {"A": 0, "B": 1, "C": 2}[c["candidate_grade"]], -c["entity_confidence"], -c["product_match"]))
    longlist = candidates[:32]
    channels = sorted(set(c["source_channel"] for c in longlist))
    requirement_met = len(longlist) >= 20
    requirement_status = (
        f"الزام حداقل ۲۰ تأمین‌کننده برآورده شد ({len(longlist)} رکورد عبورکرده از فیلتر)."
        if requirement_met else
        f"فقط {len(longlist)} تأمین‌کننده از فیلتر سخت‌گیرانه عبور کرد؛ کمبود {20-len(longlist)} مورد باید با تحقیق دستی/منبع تکمیلی جبران شود و رکورد جعلی ساخته نشد."
    )
    tools.add("page_fetch", "مرحله ۳", ["fetch accepted discovery URLs"], len(pages), note="واکشی صفحات عمومی و استخراج JSON-LD/هویت/تماس")
    tools.add("entity_resolution", "مرحله ۳", ["name + legal suffix + domain + country + product evidence"], len(longlist), note="حذف category/buyer/article و deduplicate شرکت‌ها")
    emit("stage3", f"Longlist معتبر: {len(longlist)} | {'الزام ۲۰تایی کامل' if requirement_met else 'کمبود شفاف ثبت شد'}", {"sourcing": True})
    return {
        "persona": persona, "longlist": longlist, "rejected": rejected[:120],
        "channels_used": channels, "queries_used": open_q + targeted_q,
        "requirement_met": requirement_met, "requirement_status": requirement_status,
        "raw_hits_count": len(hits), "prefiltered_count": len(prefiltered),
    }


# ---------------------------------------------------------------------------
# Stage 4 — evidence-based scoring
# ---------------------------------------------------------------------------
CRITERIA = [
    ("product_fit", "تطابق محصول", 20), ("digital", "سابقه و حضور دیجیتال", 15),
    ("export", "شواهد صادرات", 15), ("certs", "گواهی‌ها", 10),
    ("identity", "شفافیت هویتی", 10), ("capacity", "توان تولید", 10),
    ("terms", "شرایط تجاری", 10), ("response", "کیفیت پاسخ‌گویی پس از RFQ", 10),
]


def _score_supplier(s: dict) -> dict:
    reasons: dict[str, str] = {}
    evidence_ids = {k: list(s.get("source_ids") or []) for k, _, _ in CRITERIA}
    pm = float(s.get("product_match") or 0)
    product_fit = min(20, max(0, round(pm * 18) + (2 if s.get("product_evidence") else 0)))
    reasons["product_fit"] = f"Product relevance={pm:.2f}; شاهد از صفحه/اسنیپت همان رکورد ثبت شده است."

    digital = 0
    if s.get("official_website"): digital += 6
    if s.get("legal_name"): digital += 3
    if s.get("contact"): digital += 3
    if s.get("year_founded"): digital += 2
    if len(s.get("discovery_urls") or []) >= 2: digital += 1
    digital = min(15, digital)
    reasons["digital"] = f"سایت رسمی: {'دارد' if s.get('official_website') else 'تأیید نشد'}؛ نام حقوقی: {'دارد' if s.get('legal_name') else 'تأیید نشد'}؛ تماس: {'دارد' if s.get('contact') else 'ندارد'}؛ تأسیس: {s.get('year_founded') or 'نامشخص'}."

    signals = s.get("signals") or {}
    export = 0
    if signals.get("mentions_export"): export += 6
    if s.get("country") not in {"", "نامشخص", None}: export += 2
    if s.get("origin_preference_match"): export += 2
    if s.get("official_website") and signals.get("mentions_export"): export += 3
    # Without shipment/reference documents, public claims are capped at 11/15.
    export = min(11, export)
    reasons["export"] = "امتیاز از ادعای عمومی صادرات/کشور است؛ BL، مرجع مشتری یا داده تجارت هنوز تأیید نشده و سقف اعمال شد."

    verified = s.get("certs_verified") or []
    claimed = s.get("certs_mentioned") or []
    certs = min(10, 7 + min(3, len(verified))) if verified else min(2, len(claimed))
    reasons["certs"] = (
        f"گواهی تأییدشده: {', '.join(verified)}" if verified else
        f"فقط ادعای عمومی: {', '.join(claimed) or 'هیچ موردی'}؛ بدون شماره/مرجع حداکثر ۲ از ۱۰."
    )

    identity = 0
    if s.get("legal_name"): identity += 4
    if s.get("official_website"): identity += 3
    if s.get("country") not in {"", "نامشخص", None}: identity += 1
    if s.get("contact"):
        identity += 1
        if s.get("official_website") and ex.email_matches_website(s["contact"], s["official_website"]): identity += 1
    identity = min(10, identity)
    reasons["identity"] = f"درجه کاندید {s.get('candidate_grade')}; روش استخراج نام: {s.get('entity_method')}; تطابق دامنه ایمیل در امتیاز لحاظ شده است."

    capacity = 0
    if signals.get("mentions_factory"): capacity += 4
    if signals.get("capacity_numbers"): capacity += 4
    if s.get("official_website") and signals.get("mentions_factory"): capacity += 1
    capacity = min(9, capacity)
    reasons["capacity"] = f"اشاره به تولید/فرآوری: {'بله' if signals.get('mentions_factory') else 'خیر'}؛ ظرفیت عددی: {', '.join(signals.get('capacity_numbers') or []) or 'ثبت نشد'}."

    terms = 0
    if signals.get("mentions_moq"): terms += 2
    if signals.get("mentions_terms"): terms += 3
    if "sample" in (s.get("snippet") or "").lower(): terms += 1
    terms = min(6, terms)  # Quote not received: hard cap.
    reasons["terms"] = "فقط شرایط عمومی قابل مشاهده امتیاز گرفته؛ تا دریافت Quote سقف ۶ از ۱۰ اعمال شده است."

    response = 0
    reasons["response"] = "هنوز RFQ ارسال/پاسخ دریافت نشده است؛ N/A و امتیاز صفر."

    scores = {"product_fit": product_fit, "digital": digital, "export": export, "certs": certs, "identity": identity, "capacity": capacity, "terms": terms, "response": response}
    total = sum(scores.values())
    hard_gate = bool(s.get("eligible_for_scoring") and product_fit >= 10 and identity >= 5 and s.get("candidate_grade") in {"A", "B"})
    disqualify = []
    if not s.get("legal_name") and not (s.get("official_website") and s.get("entity_confidence", 0) >= 0.82): disqualify.append("هویت حقوقی/برند مستقل کافی نیست")
    if product_fit < 10: disqualify.append("تطابق محصول زیر حداقل")
    if identity < 5: disqualify.append("شفافیت هویتی زیر حداقل")
    return {"scores": scores, "total": total, "pre_rfq_total": total, "reasons": reasons, "evidence_ids": evidence_ids, "eligible_for_top5": hard_gate and not disqualify, "disqualify_reasons": disqualify}


def stage4_scoring(sourcing: dict, brief: dict, emit: Emit, tools: tk.ToolLog) -> dict:
    emit("stage4", "امتیازدهی با Evidence Cap و Hard Gate…", None)
    rows = []
    for s in sourcing.get("longlist") or []:
        rows.append({**s, **_score_supplier(s)})
    rows.sort(key=lambda r: (r.get("eligible_for_top5", False), r.get("origin_preference_match", False), r["total"], r.get("candidate_grade") == "A"), reverse=True)
    eligible = [r for r in rows if r.get("eligible_for_top5")]
    top5 = eligible[:5]
    tools.add("evidence_scoring", "مرحله ۴", ["100-point rubric + evidence caps + hard gate"], len(rows), note="گواهی ادعایی حداکثر ۲؛ response پیش از تماس صفر؛ هویت ضعیف حذف")
    emit("stage4", f"امتیازدهی {len(rows)} رکورد | واجد Top 5: {len(eligible)} | انتخاب‌شده: {len(top5)}", {"scoring": True})
    return {
        "criteria": [{"id": i, "title": t, "max": m} for i, t, m in CRITERIA],
        "scored": rows, "top5": top5,
        "eligible_count": len(eligible),
        "model_note": "مدل پیش از RFQ حداکثر عملی ۹۰/۱۰۰ دارد؛ معیار پاسخ‌گویی تا دریافت پاسخ واقعی صفر/N/A است. گواهی ادعایی و شرایط عمومی سقف دارند.",
        "top5_status": "complete" if len(top5) == 5 else f"فقط {len(top5)} گزینه از Hard Gate عبور کرد؛ Top 5 کامل نیست.",
    }


# ---------------------------------------------------------------------------
# Stage 5 — strict company-separated due diligence
# ---------------------------------------------------------------------------
def stage5_diligence(top5: list, brief: dict, sources: list, emit: Emit, tools: tk.ToolLog) -> list:
    emit("stage5", "اعتبارسنجی هویت با تطبیق سخت‌گیرانه نام و دامنه…", None)
    if not top5:
        tools.add("entity_resolution", "مرحله ۵", ["no eligible Top 5"], 0, note="هیچ رکوردی از Hard Gate عبور نکرد")
        return []
    queries: list[str] = []
    for s in top5:
        country = s.get("country") if s.get("country") != "نامشخص" else ""
        queries += [
            f'"{s["name"]}" official website {country}',
            f'"{s["name"]}" contact address {country}',
            f'"{s["name"]}" registration certificate export',
        ]
    hits = tk.run_queries(tools, "targeted_site_search", "مرحله ۵", queries, max_results=5, note="جستجوی عمومی دقیق؛ D&B/Hunter API استفاده نشده است")
    matched: dict[str, list[dict]] = {s["key"]: [] for s in top5}
    for h in hits:
        matches = []
        for s in top5:
            known = s.get("official_website") or ""
            if ex.hit_matches_company(h.get("title") or "", h.get("snippet") or "", h.get("url") or "", s["name"], known):
                matches.append(s)
        # Ambiguous result is intentionally not shared across companies.
        if len(matches) == 1:
            matched[matches[0]["key"]].append(h)

    fetch_urls: list[str] = []
    for s in top5:
        fetch_urls += [s.get("official_website") or s.get("profile_url") or s.get("url")]
        for h in matched[s["key"]][:5]:
            if not ex.marketplace_of(h.get("url") or ""):
                fetch_urls.append(h["url"])
    pages = web.fetch_many([u for u in fetch_urls if u], workers=7, timeout=10)
    tools.add("page_fetch", "مرحله ۵", ["fetch exact-match company pages"], len(pages), note="هر شرکت فضای داده جدا دارد؛ نتیجه مبهم بین کارت‌ها توزیع نمی‌شود")

    cards = []
    for s in top5:
        primary_url = s.get("official_website") or s.get("profile_url") or s.get("url")
        primary_page = pages.get(primary_url) or {}
        extra = matched.get(s["key"], [])
        official = s.get("official_website") or ""
        # Only replace/add an official site when name AND product fit; never use
        # the first generic search result.
        if not official:
            for h in extra:
                u = h.get("url") or ""
                p = pages.get(u) or {}
                if not u or ex.marketplace_of(u):
                    continue
                if ex.website_fits_company(u, (p.get("text") or "") + " " + (h.get("snippet") or ""), s["name"], ex.meaningful_product_tokens(brief["name_en"])):
                    official = p.get("canonical_url") or u
                    primary_page = p
                    break
        text = " ".join([s.get("snippet") or "", primary_page.get("text") or "", " ".join((h.get("snippet") or "") for h in extra[:5])])
        emails = []
        if s.get("contact"): emails.append(s["contact"])
        emails += primary_page.get("emails") or []
        email = ex.first_email(emails, official)
        phones = ex.plausible_phones((s.get("phones") or []) + (primary_page.get("phones") or []))
        legal_name = s.get("legal_name") or (s["name"] if ex.has_legal_suffix(s["name"]) else "")
        year = s.get("year_founded") or ex.year_founded(text)
        address = (primary_page.get("addresses") or [""])[0]
        certs_claimed = sorted(set((s.get("certs_mentioned") or []) + ex.extract_certs(text)))
        certs_verified: list[str] = []
        contradictions: list[str] = []
        green: list[str] = []
        red: list[str] = []
        if legal_name: green.append(f"نام حقوقی در صفحه/پروفایل عمومی دیده شد: {legal_name}")
        else: red.append("نام حقوقی کامل تأیید نشد")
        if official: green.append(f"وب‌سایت با نام و محصول همان شرکت تطبیق یافت: {official}")
        else: red.append("وب‌سایت مستقل تأیید نشد؛ اتکا به پروفایل B2B است")
        if email:
            if official and ex.email_matches_website(email, official): green.append("دامنه ایمیل با وب‌سایت تطبیق دارد")
            elif official:
                red.append("عدم تطابق هویت: دامنه ایمیل با وب‌سایت رسمی یکسان نیست")
                contradictions.append("دامنه ایمیل و وب‌سایت رسمی تطبیق ندارد")
            else: red.append("ایمیل وجود دارد اما دامنه رسمی شرکت تأیید نشده")
        else: red.append("ایمیل عمومی قابل اتکا پیدا نشد")
        if s.get("country") != "نامشخص":
            green.append(f"کشور محتمل: {s['country']}")
            if s.get("origin_preference_match"):
                green.append("کشور با مبدأهای ترجیحی ورودی تطبیق دارد")
            else:
                red.append("کشور خارج از مبدأهای ترجیحی ورودی است؛ دلیل استفاده باید توضیح داده شود")
        else: red.append("کشور نامشخص است")
        if certs_claimed: red.append("گواهی‌های مشاهده‌شده صرفاً ادعا هستند تا شماره و مرجع صادرکننده کنترل شود: " + ", ".join(certs_claimed))
        if s.get("signals", {}).get("mentions_factory"): green.append("نقش تولید/فرآوری در شاهد عمومی ذکر شده است")
        else: red.append("تولیدکننده‌بودن قطعی نیست")

        for h in extra[:5]:
            web.log_source(sources, h, "مرحله ۵ — Due Diligence", claim=f"ردپای هویتی دقیق برای {s['name']}", relevance=ex.product_match_score(f"{h.get('title','')} {h.get('snippet','')}", brief["name_en"]))
        card = {
            "name": s["name"], "legal_name": legal_name or _unverified("نام حقوقی کامل"),
            "legal_name_verified": False, "official_website": official,
            "profile_url": s.get("profile_url") or s.get("url"), "country": s.get("country") or "نامشخص",
            "origin_preference_match": bool(s.get("origin_preference_match")),
            "address": address or _unverified("آدرس ثبتی"), "phone": phones[0] if phones else _unverified("شماره تماس"),
            "email": email or "یافت نشد", "year_founded": year or "نامشخص",
            "registry": _unverified("شماره ثبت در مرجع رسمی کشور مبدأ"), "registry_verified": False,
            "certs_claimed": certs_claimed, "certs_verified": certs_verified,
            "digital_footprint": [{"title": h.get("title"), "url": h.get("url"), "domain": h.get("domain"), "checked_on": TODAY} for h in extra[:5]],
            "contradictions": contradictions, "green_flags": green, "red_flags": red,
            "notes": "هیچ ثبت شرکت یا گواهی صرفاً با مشاهده متن وب verified نشده است.",
            "tools_used": ["Public web search (ddgs)", "Public page fetch", "Deterministic entity resolution"],
            "scores": s.get("scores"), "total": s.get("total"), "reasons": s.get("reasons"),
            "source_ids": s.get("source_ids") or [],
        }
        card["citation_grade"] = ex.citation_grade(card)
        card["rfq_eligible"] = bool(card["citation_grade"].startswith(("A", "B")) and email and card.get("country") not in {"", "نامشخص", None} and "عدم تطابق هویت" not in " ".join(red))
        card["strengths"] = green[:4]
        card["weaknesses"] = red[:4]
        cards.append(card)
        emit("stage5", f"{s['name']}: {card['citation_grade']} | RFQ {'مجاز' if card['rfq_eligible'] else 'پیش‌نویس/متوقف'}", None)
    return cards


# ---------------------------------------------------------------------------
# Stage 6 — product-aware RFQ, without false personalisation
# ---------------------------------------------------------------------------
PERSIAN_DIGITS = str.maketrans("۰۱۲۳۴۵۶۷۸۹", "0123456789")


def _english_value(value: str, fallback: str) -> str:
    raw = (value or "").strip().translate(PERSIAN_DIGITS)
    exact = {
        "یک کانتینر 20 فوت": "one 20-foot container", "یک کانتینر 40 فوت": "one 40-foot container",
        "کیسه 60 کیلویی": "60 kg bags", "کیسه 25 کیلویی": "25 kg bags",
        "کیلوگرم": "kg", "تن": "metric tons", "دستگاه": "units", "کارتن": "cartons",
    }
    if raw in exact: return exact[raw]
    replacements = {"یک ": "one ", " کانتینر ": " container ", " فوت": " ft", " دستگاه": " units", " کیلو": " kg", " کیلوگرم": " kg", " تن": " metric tons", " کارتن": " cartons", " حلقه": " units"}
    for fa, en in replacements.items(): raw = raw.replace(fa, en)
    return fallback if _contains_persian(raw) or not raw else raw


def _rfq_questions(profile: dict[str, Any], product: str) -> tuple[list[str], list[str]]:
    tech = list(profile.get("technical") or CATEGORY_PROFILES["general"]["technical"])
    dd = [
        "Please provide the full legal company name, registration number, registered address and actual manufacturing/processing-site address.",
        "Are you the legal manufacturer/producer, an authorized exporter or a trading company? Please identify the actual site and your contractual role.",
        "Which countries received this product during the last 24 months? Please provide a redacted bill of lading, customs record or customer reference where possible.",
        "Please provide certificate copies with certificate numbers, scope, manufacturing-site name, issuing body and expiry date.",
        "Can you provide a pre-shipment sample and accept independent pre-shipment inspection/testing? Please state the procedure and cost.",
    ]
    return tech, dd


def _initial_email(buyer: str, email: str, city: str, product: str, specs: str, qty: str, grade: str, unit: str, docs: list[str]) -> str:
    docs_text = "; ".join(docs)
    return f"""Subject: RFQ – {product} for Iran

Dear Export Sales Team,

My name is {buyer}. I am evaluating qualified suppliers for the import of {product} into Iran.

Requirement
• Product: {product}
• Specification: {specs}
• Grade/model: {grade}
• Purchase unit: {unit}
• Indicative quantity: {qty}

Please provide a formal quotation stating:
1. Unit price and currency, MOQ and price breaks
2. FOB named port and CFR/CIF Bandar Abbas under Incoterms 2020
3. Production lead time, monthly capacity and offer validity
4. Payment terms available to a new buyer, subject to banking/compliance checks
5. Export packing, net/gross weight and loading plan
6. Sample policy and pre-shipment inspection options
7. Available documents: {docs_text}

Please do not treat this email as a purchase commitment. Regulatory, banking and supplier due diligence must be completed before any order.

Best regards,
{buyer}
{city}
{email}
"""


def _personalized_email(buyer: str, email: str, city: str, product: str, specs: str, qty: str, grade: str, unit: str, card: dict, tech: list[str], dd: list[str], docs: list[str]) -> dict:
    name = card.get("name") or "Export Sales Team"
    verified_facts: list[str] = []
    if card.get("official_website"): verified_facts.append(f"the product information published on {card['official_website']}")
    if card.get("country") not in {"", "نامشخص", None}: verified_facts.append(f"your public presence in {card['country']}")
    if any("نقش تولید" in x for x in card.get("green_flags") or []): verified_facts.append("your publicly stated manufacturing/processing role")
    research_line = "I reviewed " + " and ".join(verified_facts[:2]) + "." if verified_facts else "I reviewed your public supplier profile; your legal identity and manufacturing role remain subject to verification."
    tech_text = "\n".join(f"T{i}. {q}" for i, q in enumerate(tech, 1))
    dd_text = "\n".join(f"D{i}. {q}" for i, q in enumerate(dd, 1))
    status = "ready_for_manual_review" if card.get("rfq_eligible") else "draft_do_not_send_until_identity_verified"
    draft_warning = "" if card.get("rfq_eligible") else "DRAFT ONLY — DO NOT SEND UNTIL THE SUPPLIER'S LEGAL IDENTITY AND CONTACT CHANNEL ARE VERIFIED.\n\n"
    subject_prefix = "" if card.get("rfq_eligible") else "[DRAFT – IDENTITY NOT VERIFIED] "
    body = f"""{draft_warning}Subject: {subject_prefix}RFQ – {product} | {name}

Dear Export Sales Team,

My name is {buyer}, based in {city}. {research_line}

Please quote the following requirement:
• Product: {product}
• Specification: {specs}
• Grade/model: {grade}
• Purchase unit: {unit}
• Indicative quantity: {qty}
• Destination: Bandar Abbas, Iran

Commercial quotation
1. Unit price/currency, MOQ and price breaks
2. FOB named port and CFR/CIF Bandar Abbas — Incoterms 2020
3. Lead time, monthly capacity, payment terms and offer validity
4. Export packing, net/gross weight and loading plan
5. Sample and independent pre-shipment inspection policy
6. Documents available: {'; '.join(docs)}

Technical questions
{tech_text}

Due-diligence questions
{dd_text}

We will review the quotation and documents before discussing a purchase order. No payment or order will be made until regulatory, banking and supplier verification is complete.

Best regards,
{buyer}
{city}
{email}
"""
    return {
        "supplier": name, "send_status": status,
        "personalization_facts": {"company": name, "country": card.get("country"), "website_or_profile": card.get("official_website") or card.get("profile_url"), "verified_facts_used": verified_facts, "citation_grade": card.get("citation_grade")},
        "final_email": body,
        "draft_note": "شخصی‌سازی فقط از factهای عمومی همان شرکت انجام شد؛ در وضعیت Draft نباید پیش از تأیید هویت ارسال شود.",
    }


def stage6_rfq(inp: dict, brief: dict, cards: list, emit: Emit, tools: tk.ToolLog, sources: list | None = None) -> dict:
    emit("stage6", "ساخت RFQ محصول‌محور و حذف placeholderهای ناایمن…", None)
    profile = CATEGORY_PROFILES[brief["product_category"]]
    buyer = (inp.get("buyer_name_en") or inp.get("owner_en") or "Buyer Name").strip()
    buyer = buyer if not _contains_persian(buyer) else "Buyer Name"
    email = (inp.get("buyer_email") or "[buyer email]").strip()
    city = (inp.get("buyer_city") or "Tehran, Iran").strip()
    city = city if not _contains_persian(city) else "Tehran, Iran"
    product = brief["name_en"] if not _contains_persian(brief["name_en"]) else "[English product name required]"
    specs = _english_value(inp.get("specs") or "", "[confirm the complete specification in English]")
    qty = _english_value(inp.get("qty_hint") or "", "[confirm quantity in English]")
    grade = _english_value(inp.get("grade_model") or "", "[confirm grade/model]")
    unit = _english_value(inp.get("unit") or "", "[confirm purchase unit]")
    docs = profile.get("documents") or CATEGORY_PROFILES["general"]["documents"]
    tech, dd = _rfq_questions(profile, product)
    prompts = {
        "initial": f"Write a concise English RFQ for {product}. Use only the buyer-confirmed specification and quantity. Ask for price, MOQ, Incoterms 2020, payment, lead time, packing, sample and documents. Do not invent company facts.",
        "personalize": "Use only supplier facts linked to that supplier's domain/profile and citation grade. Omit unknown facts; never print an unknown placeholder as a fact.",
        "tech_questions": f"Create product-category-specific technical questions for category {brief['product_category_label']} that test lot/model conformity, evidence and inspection readiness.",
        "dd_questions": "Ask for legal identity, registration, actual site, export evidence, verifiable certificate numbers and inspection/sample acceptance.",
        "critique": "Check: one language, no unresolved Persian text, concise asks, Incoterms with named place, quote comparability, no false personalization, and explicit verification condition.",
    }
    initial = _initial_email(buyer, email, city, product, specs, qty, grade, unit, docs)
    personalized = [_personalized_email(buyer, email, city, product, specs, qty, grade, unit, c, tech, dd, docs) for c in cards]
    ready_count = sum(1 for p in personalized if p["send_status"] == "ready_for_manual_review")
    rfq_ready = all(x not in initial for x in ("[buyer email]", "[confirm", "[English product")) and ready_count > 0
    tools.add("document_generator", "مرحله ۶", ["product-aware RFQ template + supplier facts"], len(personalized), note="هیچ سرویس Hunter/LLM ادعا نشده؛ متن با قالب ساختاریافته ساخته شد")
    emit("stage6", f"RFQ: {len(personalized)} پیش‌نویس | آماده بازبینی دستی: {ready_count}", {"rfq": True})
    return {
        "prompts": prompts, "initial_email": initial, "technical_questions": tech, "dd_questions": dd,
        "personalized": personalized,
        "improvements": [
            "پرسش‌های فنی بر اساس نوع کالا انتخاب شد، نه قالب ثابت.",
            "Incoterms 2020 و named port/place برای مقایسه Quote روشن شد.",
            "fact نامشخص یا متعلق به شرکت دیگر از Personalization حذف شد.",
            "Draftهای دارای هویت ضعیف با Do not send علامت‌گذاری شدند.",
            "مدارک محصول، نمونه و بازرسی پیش از حمل به‌صورت صریح درخواست شد.",
        ],
        "buyer": {"name": inp.get("buyer_name") or inp.get("owner_fa") or "", "name_en": buyer, "email": email, "city": city},
        "rfq_ready": rfq_ready, "ready_count": ready_count,
    }


# ---------------------------------------------------------------------------
# Stage 7 — recommendation only when hard gates are met
# ---------------------------------------------------------------------------
def stage7_decision(cards: list, scoring: dict, emit: Emit, tools: tk.ToolLog) -> dict:
    emit("stage7", "جمع‌بندی با امکان نتیجه No Recommendation…", None)
    ranked = sorted(cards, key=lambda c: (c.get("rfq_eligible", False), c.get("origin_preference_match", False), c.get("total") or 0), reverse=True)
    qualified = [c for c in ranked if c.get("rfq_eligible") and str(c.get("citation_grade", "")).startswith(("A", "B"))]
    first = qualified[0] if qualified else None
    second = qualified[1] if len(qualified) > 1 else None
    if first and second:
        status = "ready_for_initial_negotiation"
        status_fa = "دو گزینه برای شروع مذاکره اولیه از Hard Gate عبور کردند؛ خرید هنوز توصیه نمی‌شود."
    elif first:
        status = "only_one_qualified"
        status_fa = "فقط یک گزینه قابل شروع مذاکره است؛ گزینه دوم باید با تحقیق تکمیلی پیدا شود."
    else:
        status = "not_ready"
        status_fa = "هیچ گزینه‌ای برای توصیه قابل دفاع نیست؛ انتخاب اول/دوم به‌اجبار ساخته نشد."

    def reasons(card: dict | None, backup: bool = False) -> list[str]:
        if not card: return []
        out = [
            f"امتیاز پیش از RFQ: {card.get('total')}/100؛ معیار پاسخ‌گویی هنوز صفر/N/A است.",
            f"درجه استناد Due Diligence: {card.get('citation_grade')}.",
            f"Green/Red Flag: {len(card.get('green_flags') or [])}/{len(card.get('red_flags') or [])}.",
        ]
        if card.get("official_website"): out.append(f"سایت تطبیق‌یافته: {card['official_website']}")
        if backup: out.append("گزینه پشتیبان برای کاهش وابستگی؛ پس از Quote باید دوباره امتیازدهی شود.")
        return out

    comparison = []
    for c in ranked:
        comparison.append({
            "name": c.get("name"), "total": c.get("total"), "country": c.get("country"), "email": c.get("email"),
            "citation_grade": c.get("citation_grade"), "rfq_eligible": c.get("rfq_eligible"),
            "strengths": (c.get("green_flags") or [])[:4], "weaknesses": (c.get("red_flags") or [])[:4],
            "red_flags": c.get("red_flags") or [], "green_flags": c.get("green_flags") or [],
        })
    decision = {
        "recommendation_status": status, "recommendation_status_fa": status_fa,
        "comparison": comparison,
        "first_choice": first["name"] if first else "",
        "second_choice": second["name"] if second else "",
        "first_reasons": reasons(first), "second_reasons": reasons(second, True),
        "open_items": [
            "کنترل مجاز/مشروط/ممنوع، ثبت سفارش، مجوز، استاندارد و کد ملی HS در سامانه رسمی همان تاریخ",
            "تأیید ثبت شرکت، ذی‌نفع نهایی، آدرس سایت و دامنه بانکی/ایمیل فروشنده",
            "راستی‌آزمایی گواهی‌ها با شماره، scope، سایت و مرجع صادرکننده",
            "ارسال RFQ فقط به گزینه‌های تأییدشده و بازنگری Response Quality پس از پاسخ واقعی",
            "مقایسه Quote، نمونه/بازرسی، شرایط پرداخت، تحریم و مسیر بانکی قبل از هر تعهد",
            "محاسبه Landed Cost با Quote واقعی؛ اعداد خالی/فرضی نباید داده واقعی تلقی شوند",
        ],
        "disclaimer": "این پرونده ابزار تصمیم‌سازی اولیه است، نه توصیه خرید یا پرداخت. نتیجه Not Ready یک خروجی معتبر و بهتر از انتخاب ساختگی است.",
    }
    tools.add("evidence_scoring", "مرحله ۷", ["citation grade + RFQ eligibility + hard gate"], len(qualified), note="فقط A/B و دارای کانال قابل اتکا وارد انتخاب می‌شوند")
    emit("stage7", status_fa, {"decision": True})
    return decision


def _quality_assurance(dossier: dict) -> dict[str, Any]:
    ll = dossier["sourcing"].get("longlist") or []
    src = dossier.get("sources") or []
    urls = [s.get("url") for s in src if s.get("url")]
    checks = [
        {"check": "Product Brief و HS candidate", "passed": bool(dossier["brief"].get("hs_primary")), "detail": dossier["brief"].get("hs_reason")},
        {"check": "حداقل دو شاهد بازار ایران", "passed": len(dossier["market"].get("imported_evidence") or []) >= 2, "detail": dossier["market"].get("imported_statement")},
        {"check": "حداقل ۲۰ Supplier معتبر", "passed": len(ll) >= 20, "detail": f"{len(ll)} رکورد"},
        {"check": "Top 5 پس از Hard Gate", "passed": len(dossier["scoring"].get("top5") or []) == 5, "detail": dossier["scoring"].get("top5_status")},
        {"check": "Source Log بدون تکرار URL+claim", "passed": len(urls) == len(set((s.get("url"), s.get("used_for"), s.get("claim")) for s in src)), "detail": f"{len(src)} ردیف پذیرفته‌شده"},
        {"check": "مقررات رسمی کنترل شده", "passed": dossier["market"].get("official_verification_status") == "verified", "detail": "در این محیط کنترل رسمی دستی نشده است"},
        {"check": "دو گزینه قابل مذاکره", "passed": dossier["decision"].get("recommendation_status") == "ready_for_initial_negotiation", "detail": dossier["decision"].get("recommendation_status_fa")},
        {"check": "RFQ بدون placeholder", "passed": dossier["rfq"].get("rfq_ready", False), "detail": f"{dossier['rfq'].get('ready_count',0)} پیش‌نویس آماده بازبینی"},
    ]
    critical_pass = all(checks[i]["passed"] for i in (0, 1, 2, 3, 6, 7))
    return {"status": "ready_for_expert_review" if critical_pass else "conditional_not_ready", "checks": checks, "passed": sum(1 for c in checks if c["passed"]), "total": len(checks)}


# ---------------------------------------------------------------------------
# Orchestrator
# ---------------------------------------------------------------------------
def run_pipeline(inp: dict, emit: Emit) -> dict:
    sources: list[dict] = []
    tools = tk.ToolLog()
    emit("init", "تجارت‌یار شروع به تشکیل پرونده کرد؛ داده نامطمئن به‌عنوان واقعیت ثبت نخواهد شد", None)
    brief = stage1_product(inp, sources, emit, tools)
    market = stage2_market(inp, brief, sources, emit, tools)
    sourcing = stage3_sourcing(inp, brief, sources, emit, tools)
    scoring = stage4_scoring(sourcing, brief, emit, tools)
    cards = stage5_diligence(scoring["top5"], brief, sources, emit, tools)
    rfq = stage6_rfq(inp, brief, cards, emit, tools, sources)
    decision = stage7_decision(cards, scoring, emit, tools)
    dossier = {
        "meta": {
            "owner_fa": inp.get("owner_fa") or "تهیه‌کننده گزارش",
            "owner_en": inp.get("owner_en") or "Report Owner",
            "organization": inp.get("organization") or "",
            "project_title": inp.get("project_title") or f"پرونده ارزیابی واردات {brief['name_fa']}",
            "report_purpose": inp.get("report_purpose") or "ارزیابی اولیه فرصت واردات و تأمین‌کنندگان",
            "platform": "تجارت‌یار — سامانه هوشمند تصمیم‌یار تجارت بین‌الملل",
            "developer_fa": "ستایش جعفری",
            "developer_en": "Setayesh Jafari",
            "generated_on": TODAY, "agent_version": "4.0-trade-ready",
            "product_fa": brief["name_fa"], "product_en": brief["name_en"],
        },
        "input": inp, "brief": brief, "market": market, "sourcing": sourcing,
        "scoring": scoring, "cards": cards, "rfq": rfq, "decision": decision,
        "sources": sources, "tool_log": tools.summary(), "tool_catalog": tk.CATALOG,
        "prompt_log": PROMPT_LIBRARY,
    }
    dossier["quality_assurance"] = _quality_assurance(dossier)
    emit("done", f"۷ مرحله تمام شد | QA: {dossier['quality_assurance']['status']} | ساخت فایل‌ها…", None)
    return dossier
