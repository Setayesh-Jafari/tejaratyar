"""Truthful tool and method logging.

The project uses the open-source ``ddgs`` client and direct HTTP page fetches.
It does *not* claim to have used Perplexity, Apify, Hunter or D&B APIs when it
only searched their public pages.  This distinction is important for the
assignment's audit trail.
"""

from __future__ import annotations

from typing import Any

from . import webutil as web

CATALOG: dict[str, dict[str, str]] = {
    "public_web_search": {
        "name": "Public web search (ddgs)",
        "role": "کشف منابع، صفحات محصول و سرنخ‌های تأمین‌کننده",
        "method": "پرس‌وجوی وب عمومی با کتابخانه ddgs؛ نتیجه جستجو تا عبور از فیلترها منبع پذیرفته‌شده نیست.",
    },
    "targeted_site_search": {
        "name": "Targeted site search",
        "role": "جستجوی هدفمند در دامنه‌های B2B، رسمی یا ثبتی",
        "method": "استفاده از site:domain در جستجوی عمومی؛ به معنای استفاده از API آن سرویس نیست.",
    },
    "regional_search": {
        "name": "Regional/language web search",
        "role": "پوشش مبدأهای ترجیحی و عبارات محلی",
        "method": "پرس‌وجوهای کشورمحور و نقش‌محور در وب عمومی.",
    },
    "page_fetch": {
        "name": "Public page fetch + structured extraction",
        "role": "استخراج نام سازمان، ایمیل، تلفن، کشور و شواهد محصول",
        "method": "واکشی صفحه عمومی، JSON-LD/Organization، عنوان، متن و اطلاعات تماس؛ صفحات نیازمند ورود قابل واکشی نیستند.",
    },
    "entity_resolution": {
        "name": "Deterministic entity resolution",
        "role": "تطبیق نام شرکت، دامنه، کشور و حذف تکراری/نامرتبط",
        "method": "قواعد قابل آزمون؛ هیچ نام شرکت از روی حدس ساخته نمی‌شود.",
    },
    "evidence_scoring": {
        "name": "Evidence-based scoring",
        "role": "امتیازدهی ۱۰۰ امتیازی با سقف برای ادعاهای تأییدنشده",
        "method": "هر نمره با وضعیت شاهد و دلیل ثبت می‌شود؛ پاسخ‌گویی پیش از RFQ برابر N/A/0 است.",
    },
    "document_generator": {
        "name": "python-docx + openpyxl",
        "role": "ساخت گزارش Word، Excel، RFQ و بسته پرامپت‌ها",
        "method": "تولید فایل محلی از داده ساختاریافته؛ اعداد فرضی از داده واقعی جدا می‌شوند.",
    },
}


class ToolLog:
    def __init__(self) -> None:
        self.rows: list[dict[str, Any]] = []

    def add(self, tool_id: str, stage: str, queries: list[str], hits: int, note: str = "") -> None:
        meta = CATALOG.get(tool_id, {"name": tool_id, "role": "", "method": ""})
        self.rows.append({
            "tool_id": tool_id,
            "tool": meta["name"],
            "stage": stage,
            "role": meta["role"],
            "method": meta["method"],
            "how": note or meta["method"],
            "queries": list(dict.fromkeys(q for q in queries if q)),
            "hits": int(hits or 0),
        })

    def for_stage(self, stage: str) -> list[dict[str, Any]]:
        return [r for r in self.rows if r["stage"] == stage]

    def summary(self) -> list[dict[str, Any]]:
        return list(self.rows)


def run_queries(
    log: ToolLog,
    tool_id: str,
    stage: str,
    queries: list[str],
    *,
    max_results: int = 8,
    backend: str | None = None,
    note: str = "",
) -> list[dict[str, Any]]:
    """Run and log discovery queries.  Callers decide which hits are evidence."""
    hits = web.search_many(queries, max_results=max_results, workers=4, backend=backend)
    for row in hits:
        row["tool"] = tool_id
        row["tool_name"] = CATALOG.get(tool_id, {}).get("name", tool_id)
    log.add(tool_id, stage, queries, len(hits), note=note)
    return hits
