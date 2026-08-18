---
title: TejaratYar
emoji: 🌐
colorFrom: blue
colorTo: emerald
sdk: docker
app_port: 7860
pinned: false
---

# تجارت‌یار — TejaratYar

**سامانه هوشمند و شواهدمحور تصمیم‌گیری تجارت بین‌الملل**

طراحی و توسعه: **ستایش جعفری — Setayesh Jafari**

[![Open In Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/Setayesh-Jafari/tejaratyar/blob/main/TejaratYar.ipynb)

تجارت‌یار برای تشکیل پرونده حرفه‌ای ارزیابی واردات طراحی شده است. سامانه مشخصات کالا را دریافت می‌کند، منابع وب را غربال می‌کند، سرنخ‌های تأمین را به شرکت‌های قابل شناسایی تبدیل می‌کند و خروجی‌های مدیریتی قابل ممیزی می‌سازد.

## قابلیت‌ها

- Product Brief و تحقیق کاندید HS
- بررسی اولیه بازار و ماتریس مقررات ایران
- Supplier Sourcing با Entity Resolution و حذف نتایج نامرتبط
- مدل امتیازدهی ۱۰۰ امتیازی با Evidence Cap
- Hard Gate پیش از Top 5 و انتخاب نهایی
- Due Diligence تفکیک‌شده برای هر شرکت
- RFQ محصول‌محور و Supplier-specific
- Source Log با Evidence ID، تاریخ، درجه و Claim
- Workbook تحلیلی شامل QA، پاسخ RFQ و Landed Cost
- وضعیت حرفه‌ای `Not Ready` به‌جای ساختن نتیجه اجباری
- دسترسی خصوصی هر پرونده با Job Token

## اصل طراحی

نتیجه جستجو با Supplier واقعی یکسان نیست. هیچ شرکت، گواهی، مجوز، آمار یا وضعیت رسمی نباید بدون شاهد قابل بررسی قطعی تلقی شود.

## خروجی‌ها

1. گزارش Word تصمیم‌گیری
2. Workbook تحلیلی Excel
3. بسته Word مکاتبات RFQ
4. فایل روش‌شناسی، قواعد ایجنت و پرامپت‌ها

## اجرای محلی

```bash
python3 -m pip install -r requirements.txt
python3 app.py
```

سپس باز کنید:

```text
http://127.0.0.1:5000
```

## اجرای Colab

فایل `TejaratYar.ipynb` را در Colab باز و **Runtime → Run all** را اجرا کنید. Notebook به‌صورت آماده مخزن `Setayesh-Jafari/tejaratyar` را دریافت می‌کند و برنامه را از ریشه مخزن اجرا می‌کند؛ نیازی به تغییر آدرس یا مسیر نیست.

## متغیرهای محیطی

```text
PORT=5000
MAX_ACTIVE_JOBS=3
JOB_TTL_HOURS=24
APP_TIMEZONE=Asia/Tehran
```

## استقرار با Docker

```bash
docker build -t tejaratyar .
docker run --rm -p 7860:7860 tejaratyar
```

## روش تحقیق

نسخه فعلی از جست‌وجوی عمومی وب با `ddgs`، واکشی صفحات عمومی، استخراج ساختاریافته، Entity Resolution و قواعد شواهدمحور استفاده می‌کند. اگر API یک سرویس اجرا نشده باشد، نام آن سرویس به‌عنوان ابزار استفاده‌شده ثبت نمی‌شود.

سامانه‌های رسمی ایران، پایگاه‌های ثبت شرکت و پایگاه‌های گواهی ممکن است Login یا CAPTCHA داشته باشند. کنترل نهایی HS ملی، تعرفه، مجوز، استاندارد، ثبت سفارش، ارز، ثبت شرکت و گواهی‌ها باید پیش از هر تصمیم تجاری توسط کارشناس انجام شود.

## حدود مسئولیت

تجارت‌یار ابزار تصمیم‌سازی اولیه است و جایگزین مشاوره حقوقی، گمرکی، بانکی، استاندارد، بازرسی یا Due Diligence رسمی نیست. هیچ خروجی سامانه به‌تنهایی مجوز خرید، پرداخت یا انعقاد قرارداد محسوب نمی‌شود.
# tejaratyar
