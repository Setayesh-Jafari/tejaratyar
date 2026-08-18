/* TejaratYar 4.1 Premium — front-end application (self-contained, no CDN) */
"use strict";

const $ = (s, r = document) => r.querySelector(s);
const $$ = (s, r = document) => [...r.querySelectorAll(s)];
const LS_KEY = "tejaratyar_last_job";

const STAGE_LABEL = {
  form: "تعریف پرونده", init: "شروع",
  stage1: "تعریف محصول", stage2: "بازار ایران", stage3: "تأمین‌کننده‌یابی",
  stage4: "غربالگری", stage5: "اعتبارسنجی", stage6: "ایمیل RFQ", stage7: "انتخاب نهایی",
  done: "تحویل", error: "خطا",
};
const STAGE_ORDER = ["stage1", "stage2", "stage3", "stage4", "stage5", "stage6", "stage7"];
const WIZARD_STEPS = [
  { t: "کالا", s: "محصول و دسته" },
  { t: "مشخصات", s: "فنی و تجاری" },
  { t: "خریدار", s: "هویت گزارش" },
  { t: "مرور", s: "تأیید نهایی" },
];

const SCENARIOS = [
  { fa: "پنل خورشیدی مونوکریستال", en: "Monocrystalline solar PV module", app: "نیروگاه خانگی و صنعتی کوچک", specs: "550W, 144 cells, N-type", unit: "وات / پالت", qty: "one 40-foot container", tag: "انرژی" },
  { fa: "اینورتر خورشیدی متصل به شبکه", en: "On-grid solar inverter", app: "نیروگاه خورشیدی", specs: "50kW three-phase", unit: "دستگاه", qty: "10 units", tag: "انرژی" },
  { fa: "دانه قهوه سبز عربیکا", en: "Green Arabica coffee beans", app: "برشته‌کاری و کافی‌شاپ", specs: "Washed, screen 16+, moisture ≤12%", unit: "کیسه ۶۰ کیلویی", qty: "one 20-foot container", tag: "کشاورزی" },
  { fa: "چای سیاه سیلان", en: "Ceylon black tea", app: "بسته‌بندی و خرده‌فروشی", specs: "Broken Orange Pekoe, Sri Lanka", unit: "کیلوگرم", qty: "5 tons trial", tag: "کشاورزی" },
  { fa: "مکمل پروتئین وی کنسانتره", en: "Whey protein concentrate", app: "باشگاه و فروش آنلاین", specs: "WPC 80%, instantized, unflavored", unit: "کیسه ۲۵ کیلویی", qty: "500 kg", tag: "مکمل" },
  { fa: "روغن ماهی امگا ۳", en: "Fish oil omega-3 concentrate", app: "مکمل و داروخانه", specs: "18/12 EPA/DHA, molecular distilled", unit: "کیلوگرم", qty: "300 kg", tag: "مکمل" },
  { fa: "دستگاه سونوگرافی پرتابل", en: "Portable ultrasound scanner", app: "کلینیک و اورژانس", specs: "Color Doppler, 2 probes", unit: "دستگاه", qty: "5 units", tag: "پزشکی" },
  { fa: "دستکش معاینه نیتریل", en: "Nitrile examination gloves", app: "بیمارستان و آزمایشگاه", specs: "Powder-free, size M, CE", unit: "کارتن", qty: "50 cartons", tag: "پزشکی" },
  { fa: "دستگاه اسپرسو صنعتی دو گروپ", en: "Commercial 2-group espresso machine", app: "کافه و رستوران", specs: "2 group, heat exchanger", unit: "دستگاه", qty: "8 units", tag: "صنعت" },
  { fa: "ورق فولادی گالوانیزه", en: "Galvanized steel sheet", app: "ساختمان و تولید", specs: "DX51D, Z275, 0.5mm", unit: "تن", qty: "one container", tag: "فلز" },
  { fa: "تایر سواری رادیال", en: "Passenger car radial tire", app: "عمده‌فروشی لاستیک", specs: "205/55R16, ECE", unit: "حلقه", qty: "500 units", tag: "خودرو" },
  { fa: "پارچه اسپان‌باند پزشکی", en: "Medical PP spunbond nonwoven", app: "تولید ماسک و گان", specs: "SS 25gsm, hydrophilic", unit: "کیلوگرم / رول", qty: "2 tons", tag: "نساجی" },
];

const state = { jobId: null, token: null, timer: null, tick: null, startedAt: 0, dossier: null, curStep: 0 };

/* ---------------- Utilities ---------------- */
function esc(s) { return String(s ?? "").replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;"); }
function link(url, label) { if (!url || !/^https?:\/\//i.test(String(url))) return "—"; return `<a href="${esc(url)}" target="_blank" rel="noopener noreferrer">${esc(label || url)}</a>`; }
function toast(msg, type = "info") {
  const box = $("#toasts");
  const el = document.createElement("div");
  el.className = `toast ${type}`;
  const ico = type === "ok" ? "✓" : type === "err" ? "✕" : "ℹ";
  el.innerHTML = `<span class="ico">${ico}</span><span>${esc(msg)}</span>`;
  box.appendChild(el);
  setTimeout(() => { el.style.opacity = "0"; el.style.transition = "opacity .3s"; setTimeout(() => el.remove(), 320); }, 4200);
}
async function copyText(text, label) {
  try { await navigator.clipboard.writeText(text); toast(`${label || "متن"} کپی شد ✓`, "ok"); }
  catch (e) { toast("کپی در این مرورگر ممکن نشد", "err"); }
}
function show(view) {
  $$(".view").forEach((v) => v.classList.remove("active"));
  $(`#view-${view}`).classList.add("active");
  const caps = $("#capabilityGrid");
  if (caps) caps.hidden = view !== "form";
}
function markStages(current, completed = []) {
  $$("#stageNav .step").forEach((li) => {
    const st = li.dataset.stage;
    li.classList.toggle("done", completed.includes(st));
    li.classList.toggle("active", st === current || (current === "done" && st === "stage7"));
  });
}
function gaugeHtml(score, size = 150) {
  const s = Math.max(0, Math.min(100, Math.round(score || 0)));
  return `<div class="gauge" style="--g:${s};width:${size}px;height:${size}px">
    <div class="g-in"><div class="g-num">${s}</div><div class="g-lbl">از ۱۰۰</div></div></div>`;
}
function badgeCls(tone) { return ({ ok: "ok", ready: "ok", partial: "warn", warn: "warn", early: "pending", danger: "danger", pending: "pending", gold: "gold" }[tone] || "pending"); }

/* ---------------- Wizard ---------------- */
function buildWizardBar() {
  $("#wizardBar").innerHTML = WIZARD_STEPS.map((w, i) => `
    <div class="wz-step" data-wz="${i}"><div class="dot"><span class="n">${["۱", "۲", "۳", "۴"][i]}</span><span class="check">✓</span></div>
      <div class="t"><b>${esc(w.t)}</b><small>${esc(w.s)}</small></div></div>`).join("");
}
function wizardRender() {
  const steps = $$(".wizard-step");
  steps.forEach((el, i) => el.classList.toggle("active", i === state.curStep));
  $$("#wizardBar .wz-step").forEach((el, i) => {
    el.classList.toggle("on", i === state.curStep);
    el.classList.toggle("passed", i < state.curStep);
  });
  $("#prevBtn").style.visibility = state.curStep === 0 ? "hidden" : "visible";
  const next = $("#nextBtn");
  next.textContent = state.curStep === 3 ? "شروع تحلیل ←" : "ادامه ←";
  if (state.curStep === 3) fillReview();
}
function validateStep(step) {
  const f = $("#intake");
  const clear = (n) => $(`[name="${n}"]`)?.closest(".field")?.classList.remove("invalid");
  const flag = (n) => $(`[name="${n}"]`)?.closest(".field")?.classList.add("invalid");
  if (step === 0) {
    clear("product_fa"); clear("product_en");
    const ok = (f.product_fa.value.trim() || f.product_en.value.trim());
    if (!ok) { flag("product_fa"); flag("product_en"); toast("نام کالا را به فارسی یا انگلیسی وارد کنید.", "err"); }
    return ok;
  }
  if (step === 1) {
    let ok = true;
    ["specs", "qty_hint"].forEach((n) => {
      clear(n);
      if (!f[n].value.trim()) { flag(n); ok = false; }
    });
    if (!ok) toast("مشخصات فنی و مقدار سفارش الزامی است.", "err");
    return ok;
  }
  return true;
}
function goTo(step) {
  state.curStep = Math.max(0, Math.min(3, step));
  wizardRender();
  window.scrollTo({ top: $("#view-form").offsetTop - 10, behavior: "smooth" });
}
function fillReview() {
  const f = $("#intake");
  const rows = [
    ["نام کالا", f.product_fa.value.trim() || f.product_en.value.trim()],
    ["نام انگلیسی", f.product_en.value.trim() || "—"],
    ["گروه محصول", f.product_category.selectedOptions[0].text],
    ["مشخصات فنی", f.specs.value.trim() || "—"],
    ["مقدار سفارش", f.qty_hint.value.trim() || "—"],
    ["کاربرد", f.application.value.trim() || "—"],
    ["گرید / مدل", f.grade_model.value.trim() || "—"],
    ["واحد خرید", f.unit.value.trim() || "—"],
    ["مشتری هدف", f.target_customer.value.trim() || "—"],
    ["مبدأ ترجیحی", f.origin_pref.value.trim() || "—"],
    ["عنوان پرونده", f.project_title.value.trim() || "—"],
    ["سازمان", f.organization.value.trim() || "—"],
    ["هدف گزارش", f.report_purpose.value.trim() || "—"],
    ["تهیه‌کننده", f.owner_fa.value.trim() || "—"],
    ["ایمیل خریدار", f.buyer_email.value.trim() || "—"],
  ];
  $("#reviewBox").innerHTML = rows.map(([k, v]) => `<div class="review-row"><b>${esc(k)}</b><span>${esc(v)}</span></div>`).join("");
}
async function submitForm() {
  if (!validateStep(0) || !validateStep(1)) { wizardRender(); return; }
  const fd = new FormData($("#intake"));
  const payload = Object.fromEntries(fd.entries());
  payload.name_fa = (payload.product_fa || "").trim();
  payload.name_en = (payload.product_en || "").trim();
  const btn = $("#nextBtn");
  btn.disabled = true; btn.textContent = "در حال شروع…";
  try {
    const res = await fetch("/api/run", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(payload) });
    const data = await res.json();
    if (!data.ok) throw new Error(data.error || "خطا در شروع");
    state.jobId = data.job_id; state.token = data.access_token; state.startedAt = Date.now();
    saveLocal();
    startRunUI();
  } catch (err) {
    toast(err.message, "err");
    btn.disabled = false; btn.textContent = "شروع تحلیل ←";
  }
}

/* ---------------- Scenarios / chips ---------------- */
function renderChips() {
  const wrap = $("#quickChips");
  wrap.innerHTML = SCENARIOS.map((s, i) => `<button type="button" class="chip" data-i="${i}">${esc(s.fa)}<small>${esc(s.tag)}</small></button>`).join("");
  $$("#quickChips .chip").forEach((btn) => btn.addEventListener("click", () => {
    $$("#quickChips .chip").forEach((b) => b.classList.remove("selected"));
    btn.classList.add("selected");
    const f = $("#intake"); const s = SCENARIOS[+btn.dataset.i];
    f.product_fa.value = s.fa; f.product_en.value = s.en; f.application.value = s.app;
    f.specs.value = s.specs; f.unit.value = s.unit; f.qty_hint.value = s.qty;
    toast(`سناریوی «${s.fa}» بارگذاری شد`);
  }));
}

/* ---------------- Run ---------------- */
function startRunUI() {
  $("#logBox").innerHTML = ""; $("#runBar").style.width = "2%"; $("#runPct").textContent = "0%";
  $("#runStatus").textContent = "تجارت‌یار در حال تحلیل و تشکیل پرونده است…";
  $("#runNow").textContent = "آماده‌سازی موتور جستجو…"; $("#elapsed").textContent = "00:00";
  $("#currentStageLabel").textContent = "شروع";
  buildStageTrack({ current: "stage1", completed: [] });
  show("run"); markStages("stage1", []); startTimer(); poll();
}
function buildStageTrack(job) {
  $("#stageTrack").innerHTML = STAGE_ORDER.map((st, i) => {
    const cls = job.completed.includes(st) ? "done" : (job.current_stage === st ? "active" : "");
    return `<div class="st ${cls}"><div class="dot"></div><span>${i + 1}</span></div>`;
  }).join("");
}
function startTimer() {
  if (state.tick) clearInterval(state.tick);
  state.tick = setInterval(() => {
    const s = Math.floor((Date.now() - state.startedAt) / 1000);
    $("#elapsed").textContent = `${String(Math.floor(s / 60)).padStart(2, "0")}:${String(s % 60).padStart(2, "0")}`;
  }, 1000);
}
function stopTimer() { if (state.tick) clearInterval(state.tick); }

/* ---------------- Polling / downloads ---------------- */
function apiGet(path) { return fetch(path, { headers: { "X-Job-Token": state.token || "" } }); }
function poll() {
  if (state.timer) clearInterval(state.timer);
  const tick = async () => {
    let job;
    try {
      const res = await apiGet(`/api/job/${encodeURIComponent(state.jobId)}`);
      job = await res.json();
      if (!res.ok || !job.ok) throw new Error(job.error || "خطا در دریافت وضعیت");
    } catch (err) { $("#runNow").textContent = `ارتباط موقتاً برقرار نیست: ${err.message}`; return; }
    const pct = job.progress || 0;
    $("#runBar").style.width = `${pct}%`; $("#runPct").textContent = `${pct}%`;
    $("#runNow").textContent = (job.logs.at(-1) || {}).message || "…";
    $("#currentStageLabel").textContent = STAGE_LABEL[job.current_stage] || job.current_stage;
    markStages(job.current_stage, job.completed || []); buildStageTrack(job); renderLogs(job.logs || []);
    if (job.status === "done") {
      clearInterval(state.timer); stopTimer(); state.dossier = job.dossier;
      bindDownloads(job.id); renderReport(job.dossier);
      show("result"); $("#downloadBar").hidden = false;
      const b = job.dossier.brief || {}, meta = job.dossier.meta || {};
      $("#pageTitle").textContent = b.name_fa || "پرونده";
      $("#pageSub").textContent = `پرونده آماده بازبینی است — ${meta.owner_fa || "تهیه‌کننده گزارش"}${meta.organization ? ` — ${meta.organization}` : ""} — ${meta.generated_on || ""}`;
      $("#nextBtn").disabled = false; $("#nextBtn").textContent = "شروع تحلیل ←";
      toast("پرونده تکمیل شد. گزارش‌ها آماده دانلودند.", "ok");
    }
    if (job.status === "error") {
      clearInterval(state.timer); stopTimer();
      $("#runStatus").textContent = "خطا در اجرا"; $("#runNow").textContent = job.error || "خطای ناشناخته";
      $("#nextBtn").disabled = false; $("#nextBtn").textContent = "شروع تحلیل ←";
      toast(job.error || "خطا در اجرای پرونده", "err");
    }
  };
  tick(); state.timer = setInterval(tick, 1600);
}
function renderLogs(logs) {
  const box = $("#logBox");
  box.innerHTML = logs.map((l) => `<div class="row"><time>${esc(l.t)}</time><span class="stage ${esc(l.stage)}">${esc(STAGE_LABEL[l.stage] || l.stage)}</span><span>${esc(l.message)}</span></div>`).join("");
  box.scrollTop = box.scrollHeight;
}
const FILE_KINDS = { dlReport: "report", dlExcel: "excel", dlRfq: "rfq", dlPrompts: "prompts" };
function triggerDownload(blob, fname) {
  const url = URL.createObjectURL(blob); const a = document.createElement("a");
  a.href = url; a.download = fname; document.body.appendChild(a); a.click();
  setTimeout(() => { URL.revokeObjectURL(url); a.remove(); }, 400);
}
function bindDownloads(id) {
  Object.entries(FILE_KINDS).forEach(([el, kind]) => {
    $(`#${el}`).onclick = async () => {
      const btn = $(`#${el}`); btn.disabled = true;
      try {
        const res = await apiGet(`/api/job/${encodeURIComponent(id)}/file/${kind}`);
        if (!res.ok) throw new Error((await res.json()).error || "خطا در دریافت فایل");
        const blob = await res.blob();
        const disp = res.headers.get("Content-Disposition") || "";
        const m = disp.match(/filename="?([^"]+)"?/i);
        const fname = m ? m[1] : `${kind}.${kind === "prompts" ? "txt" : kind === "excel" ? "xlsx" : "docx"}`;
        triggerDownload(blob, fname); toast("دانلود آغاز شد", "ok");
      } catch (e) { toast(e.message, "err"); }
      btn.disabled = false;
    };
  });
  $("#printBtn").onclick = () => window.print();
}

/* ============================================================
   REPORT RENDERER — sectioned executive report
   ============================================================ */
const REPORT_SECTIONS = [
  { id: "overview", label: "خلاصه", fn: rOverview },
  { id: "product", label: "محصول", fn: rProduct },
  { id: "market", label: "بازار", fn: rMarket },
  { id: "suppliers", label: "تأمین‌کنندگان", fn: rSuppliers },
  { id: "scoring", label: "امتیاز", fn: rScoring },
  { id: "diligence", label: "اعتبارسنجی", fn: rDiligence },
  { id: "compare", label: "مقایسه", fn: rCompare },
  { id: "rfq", label: "RFQ", fn: rRfq },
  { id: "decision", label: "تصمیم", fn: rDecision },
  { id: "cost", label: "هزینه", fn: rCost },
  { id: "tools", label: "ابزارها", fn: rTools },
  { id: "sources", label: "منابع", fn: rSources },
];

function renderReport(d) {
  const nav = $("#reportNav");
  nav.innerHTML = REPORT_SECTIONS.map((s, i) => (i === 0 ? "" : `<span class="sep"></span>`) + `<a href="#sec-${s.id}" data-sec="${s.id}">${esc(s.label)}</a>`).join("");
  $("#reportMount").innerHTML = REPORT_SECTIONS.map((s) => `<section id="sec-${s.id}" class="report-section" data-sec="${s.id}">${s.fn(d)}</section>`).join("");
  bindReportInteractions();
  bindScrollspy();
}

function rOverview(d) {
  const dec = d.decision || {}, qa = d.quality_assurance || { checks: [] }, meta = d.meta || {};
  const sum = d.summary || { score: 0, stages: {}, metrics: {}, highlights: [] };
  const statusTone = dec.recommendation_status === "ready_for_initial_negotiation" ? "ok" : dec.recommendation_status === "only_one_qualified" ? "warn" : "danger";
  const meters = Object.entries(sum.stages || {}).map(([k, v]) => `<div class="meter"><b>${esc(v.label)}</b><div class="tr"><i style="width:${v.score}%"></i></div><div class="v">${v.score}</div></div>`).join("");
  return `
  <div class="hero">
    <div class="hero-inner">
      <div>
        <div class="kicker">Executive Import Dossier</div>
        <h1>${esc(meta.project_title || "پرونده تصمیم‌گیری واردات")}</h1>
        <p>${esc(meta.report_purpose || "ارزیابی اولیه فرصت واردات و تأمین‌کنندگان")} — ${esc(meta.owner_fa || "تهیه‌کننده گزارش")}${meta.organization ? ` · ${esc(meta.organization)}` : ""}</p>
        <div class="hero-meta">
          ${(sum.highlights || []).map((h) => `<span class="hero-chip">${esc(h)}</span>`).join("")}
        </div>
      </div>
      ${gaugeHtml(sum.score)}
    </div>
  </div>

  <div class="kpis">
    <div class="kpi"><span class="ic">🏢</span><small>Longlist معتبر</small><strong>${sum.metrics.longlist ?? (d.sourcing?.longlist || []).length}</strong><span>رکورد عبورکرده از فیلتر</span></div>
    <div class="kpi"><span class="ic">⭐</span><small>Shortlist</small><strong>${sum.metrics.shortlist ?? (d.scoring?.top5 || []).length}</strong><span>عبورکرده از Hard Gate</span></div>
    <div class="kpi"><span class="ic">🔗</span><small>Evidence Log</small><strong>${sum.metrics.sources ?? (d.sources || []).length}</strong><span>منبع قابل ردیابی</span></div>
    <div class="kpi"><span class="ic">✅</span><small>QA Controls</small><strong>${qa.passed || 0}/${qa.total || 0}</strong><span>${esc(qa.status || "…")}</span></div>
  </div>

  <div class="card">
    <div class="section-head"><div><h2>آمادگی پرونده بر اساس مرحله</h2></div>
      <span class="badge ${badgeCls(sum.tone)}">${esc(sum.label)}</span></div>
    <div class="stage-meter">${meters}</div>
  </div>

  <div class="decision-pair">
    <div class="choice first"><h4>گزینه اول برای شروع مذاکره</h4><strong>${esc(dec.first_choice || "هنوز انتخاب نشده")}</strong>
      <ul>${(dec.first_reasons || []).map((r) => `<li>${esc(r)}</li>`).join("")}</ul></div>
    <div class="choice"><h4>گزینه دوم (پشتیبان)</h4><strong>${esc(dec.second_choice || "نیازمند تحقیق تکمیلی")}</strong>
      <ul>${(dec.second_reasons || []).map((r) => `<li>${esc(r)}</li>`).join("")}</ul></div>
  </div>

  <div class="card">
    <div class="section-head"><div><h2>وضعیت تصمیم</h2><p class="muted" style="margin:0">${esc(dec.recommendation_status_fa || "وضعیت نامشخص")}</p></div>
      <span class="badge ${statusTone}">${esc(dec.recommendation_status || "not_ready")}</span></div>
    ${actionPlan(dec)}
  </div>

  <div class="card">
    <div class="section-head"><div><h3>کنترل کیفیت پرونده</h3></div></div>
    <div class="qa-list">${(qa.checks || []).map((c) => `<div class="qa ${c.passed ? "pass" : "open"}"><b>${c.passed ? "✓" : "!"} ${esc(c.check)}</b><span>${esc(c.detail)}</span></div>`).join("")}</div>
  </div>

  <div class="card"><h3>مشخصات و دامنه پرونده</h3>
    <div class="kv">
      <b>محصول</b><span>${esc(d.brief?.name_fa)} / ${esc(d.brief?.name_en)}</span>
      <b>گروه محصول</b><span>${esc(d.brief?.product_category_label || "—")}</span>
      <b>کیفیت ورودی</b><span>${esc((d.brief?.input_quality || {}).score || 0)}٪</span>
      <b>HS کاندید</b><span>${esc(d.brief?.hs_primary || "تأیید نشد")} — کد ملی باید رسمی کنترل شود</span>
      <b>وضعیت بازار</b><span>${esc(d.market?.imported_statement)}</span>
      <b>مبدأهای هدف</b><span>${esc((d.brief?.origin_strategy || []).join("، "))}</span>
    </div>
    <p class="warn" style="margin-top:10px">${esc(dec.disclaimer)}</p>
  </div>`;
}
function actionPlan(dec) {
  if (dec.recommendation_status === "ready_for_initial_negotiation")
    return `<div class="notice green"><strong>برنامه اقدام پیشنهادی</strong>۱) RFQ تأییدشده را به دو گزینه اول و دوم ارسال کنید. ۲) سؤال فنی/اعتبارسنجی را پاسخ بگیرید. ۳) گواهی‌ها را با شماره و مرجع راستی‌آزمایی کنید. ۴) Quoteها را در ماشین‌حساب هزینه مقایسه کنید. ۵) پیش از پرداخت، ثبت سفارش/استاندارد/ارز را رسمی کنترل کنید.</div>`;
  return `<div class="notice amber"><strong>هنوز برای مذاکره آماده نیست — برنامه اقدام</strong>۱) شواهد تأمین‌کننده بیشتری بیابید (یا دستی جستجو کنید). ۲) کشور/کانال را تغییر دهید و پرونده را دوباره بسازید. ۳) کنترل رسمی مقررات را در سامانه‌های ذکرشده انجام دهید. این «آماده نبودن» نتیجه‌ای معتبر و بهتر از انتخاب جعلی است.</div>`;
}

function rProduct(d) {
  const b = d.brief || {};
  return `<div class="card"><h2>تعریف محصول و کد HS</h2>
    <div class="kv">
      <b>نام فارسی</b><span>${esc(b.name_fa)}</span><b>نام انگلیسی</b><span>${esc(b.name_en)}</span>
      <b>کاربرد</b><span>${esc(b.application)}</span><b>مشخصات فنی</b><span>${esc(b.specs)}</span>
      <b>گرید / مدل</b><span>${esc(b.grade_model)}</span><b>واحد خرید</b><span>${esc(b.unit)}</span>
      <b>مشتری هدف</b><span>${esc(b.target_customer)}</span><b>مقدار سفارش</b><span>${esc(b.qty_hint)}</span>
      <b>گروه محصول</b><span>${esc(b.product_category_label || "—")}</span>
      <b>مبدأهای جستجو</b><span>${esc((b.origin_strategy || []).join("، "))}</span>
      <b>ویژگی‌های مؤثر بر HS</b><span>${esc((b.classification_attributes || []).join(" | "))}</span>
      <b>کد HS کاندید</b><span>${esc(b.hs_primary || "—")}</span>
      <b>کدهای جایگزین</b><span>${esc((b.hs_alternatives || []).join(" ، ") || "—")}</span>
    </div>
    <div class="notice amber" style="margin-top:12px"><strong>دلیل انتخاب HS</strong>${esc(b.hs_reason)}</div>
    <p class="muted">${esc(b.description_web)}</p>
    <h3>هشدارهای کیفیت ورودی</h3>
    <ul>${((b.input_quality || {}).warnings || []).map((x) => `<li>${esc(x)}</li>`).join("") || "<li>هشدار مهمی ثبت نشد.</li>"}</ul>
    <h3>عبارات جستجوی Sourcing</h3><ol>${(b.search_phrases || []).map((p) => `<li class="mono">${esc(p)}</li>`).join("")}</ol>
  </div>`;
}

function rMarket(d) {
  const m = d.market || {};
  const riskCards = (m.regulatory_risks || []).map((r) => {
    const verified = r.verified === true;
    const web = r.triggered_by_web === true || /اشاره در منابع وب/.test(String(r.level || ""));
    const status = verified ? "تأییدشده رسمی" : web ? "هشدار اولیه" : "کنترل رسمی نشده";
    const cls = verified ? "ok" : web ? "warn" : "pending";
    return `<div class="card" style="margin-bottom:12px"><div class="section-head"><h3>${esc(r.title || "ریسک مقرراتی")}</h3><span class="badge ${cls}">${esc(status)}</span></div>
      <div class="kv"><b>این مورد چیست؟</b><span>${esc(r.detail || "—")}</span><b>سطح فعلی</b><span>${esc(r.level || "نامشخص")}</span><b>اقدام لازم</b><span>${esc(r.verification || "—")}</span></div></div>`;
  }).join("");
  return `<div class="card">
    <div class="section-head"><div><h2>فرصت واردات به ایران</h2></div></div>
    <p>${esc(m.imported_statement)}</p>
    <div class="notice"><strong>راهنمای این بخش</strong>این موارد حکم قطعی نیستند؛ فهرست کنترل مقرراتی‌اند. وضعیت هر مورد مشخص می‌کند فقط در وب اشاره شده یا واقعاً در مرجع رسمی تأیید شده است.</div>
    <h3>شواهد پذیرفته‌شده وب</h3>
    <ul>${(m.imported_evidence || []).map((e) => `<li>${link(e.url, e.claim)} <span class="muted">— درجه ${esc(e.authority_grade || "C")} · ${esc(e.domain)} · ${esc(e.checked_on)}</span><br><span class="muted">${esc(e.snippet)}</span></li>`).join("") || "<li>شاهد قابل قبول ثبت نشد.</li>"}</ul>
  </div>
  <div class="card"><h2>چک‌لیست ریسک‌های مقرراتی</h2>${riskCards || "<p class='muted'>ریسکی ثبت نشده است.</p>"}</div>
  <div class="card"><h2>مراجع رسمی برای کنترل نهایی</h2>
    <div class="table-wrap"><table><thead><tr><th>مرجع</th><th>چه چیزی بررسی شود</th><th>وضعیت</th><th>لینک</th></tr></thead>
    <tbody>${(m.official_portals || []).map((p) => `<tr><td><strong>${esc(p.name)}</strong></td><td>${esc(p.check)}</td><td><span class="badge pending">${esc(p.status || "کنترل دستی")}</span></td><td>${link(p.url, "بازکردن")}</td></tr>`).join("") || "<tr><td colspan=4>مرجعی ثبت نشده.</td></tr>"}</tbody></table></div>
    <div class="notice green"><strong>نتیجه‌ای که کارشناس باید ثبت کند</strong>پس از مراجعه به سامانه رسمی، وضعیت «مجاز/مشروط/ممنوع»، مجوز، استاندارد، تعرفه و محدودیت ارزی را با تاریخ و شاهد ثبت کنید.</div>
  </div>`;
}

function filterToolbar(opts, label) {
  return `<div class="filter-bar"><input type="search" placeholder="جستجو در جدول…" />
    <select data-key="country"><option value="all">همه کشورها</option>${opts}</select>
    <button type="button" class="btn btn-sm apply">فیلتر</button><span class="muted" style="font-size:12px">${label}</span></div>`;
}

function rSuppliers(d) {
  const s = d.sourcing || {}; const ll = s.longlist || [];
  const countries = [...new Set(ll.map((x) => x.country).filter(Boolean))].sort();
  const rows = ll.map((x, i) => {
    const gr = x.candidate_grade || "C";
    return `<tr data-country="${esc(x.country || "")}" data-search="${esc((x.name + " " + (x.legal_name || "") + " " + (x.country || "") + " " + (x.source_channel || "")).toLowerCase())}">
      <td>${i + 1}</td><td><strong>${esc(x.name)}</strong><br><span class="muted">${esc(x.legal_name || "نام حقوقی تأییدنشده")}</span></td>
      <td>${esc(x.country)}</td><td><span class="badge ${gr === "A" ? "ok" : gr === "B" ? "warn" : "pending"}">${gr}</span></td>
      <td class="score-cell">${x.product_match ?? "—"}</td><td>${esc(x.source_channel)}</td>
      <td>${esc(x.identity_status || "—")}</td><td class="mono">${esc(x.contact || "—")}</td><td>${link(x.official_website || x.url, "منبع")}</td></tr>`;
  }).join("");
  return `<div class="card"><h2>استراتژی تأمین‌کننده‌یابی و Persona</h2>
    <div class="kv">${Object.entries(s.persona || {}).map(([k, v]) => `<b>${esc(k)}</b><span>${esc(v)}</span>`).join("")}</div>
    <p class="muted">کانال‌ها: ${esc((s.channels_used || []).join("، "))} · Longlist: ${ll.length} · موتورهای جستجو: ${esc((d.tool_log || []).find((r) => r.stage === "مرحله ۳")?.queries?.length || "")}</p>
    <div class="notice ${s.requirement_met ? "green" : "amber"}">${esc(s.requirement_status)}</div>
  </div>
  <div class="card" data-table="tbl-long"><h2>Longlist تأمین‌کنندگان</h2>
    ${filterToolbar(countries.map((c) => `<option value="${esc(c)}">${esc(c)}</option>`).join(""), `${ll.length} رکورد`)}
    <div class="table-wrap"><table><thead><tr><th>#</th><th>نام / نام حقوقی</th><th>کشور</th><th>درجه</th><th class="sortable" data-sort="grade">تطابق</th><th>کانال</th><th>وضعیت هویت</th><th>تماس</th><th>لینک</th></tr></thead>
    <tbody class="tbl-rows">${rows || `<tr><td colspan=9><div class="empty">هیچ تأمین‌کننده‌ای از فیلتر عبور نکرد — به بخش «خلاصه» برای برنامه اقدام بروید.</div></td></tr>`}</tbody></table></div>
  </div>
  <div class="card"><h3>نمونه موارد حذف‌شده</h3><ul>${(s.rejected || []).slice(0, 15).map((r) => `<li>${esc(r.reason)} — ${esc(r.title || "")}</li>`).join("")}</ul></div>`;
}

function rScoring(d) {
  const sc = d.scoring || {}; const crit = sc.criteria || [];
  const rows = (sc.scored || []).map((s, i) => `<tr data-country="${esc(s.country || "")}" data-search="${esc((s.name + (s.country || "")).toLowerCase())}">
    <td>${i + 1}</td><td><strong>${esc(s.name)}</strong></td><td class="score-cell">${s.total}</td>
    ${crit.map((c) => `<td>${(s.scores || {})[c.id] ?? "—"}</td>`).join("")}<td>${esc(s.country)}</td></tr>`).join("");
  const top = (sc.top5 || []).map((s) => {
    const bars = Object.entries(s.scores || {}).map(([k, v]) => {
      const c = crit.find((x) => x.id === k); const max = c ? c.max : 10;
      return `<div class="row"><span>${esc(c ? c.title : k)}</span><div class="track"><i style="width:${(v / max) * 100}%"></i></div><span>${v}</span></div>`;
    }).join("");
    return `<div class="card"><h3>${esc(s.name)} <span class="score-cell">${s.total}/100</span></h3><div class="bars">${bars}</div><ul>${Object.values(s.reasons || {}).map((r) => `<li>${esc(r)}</li>`).join("")}</ul></div>`;
  }).join("");
  return `<div class="card"><h2>مدل امتیازدهی شواهدمحور</h2><p>${esc(sc.model_note)}</p><div class="notice amber">${esc(sc.top5_status)}</div></div>
  <div class="card" data-table="tbl-score"><h2>ماتریس امتیاز</h2>
    <div class="filter-bar"><input type="search" placeholder="جستجو در جدول…" /><button class="btn btn-sm apply">فیلتر</button><span class="muted" style="font-size:12px">${(sc.scored || []).length} رکورد</span></div>
    <div class="table-wrap"><table><thead><tr><th>#</th><th>نام</th><th>جمع</th>${crit.map((c) => `<th>${esc(c.title)}</th>`).join("")}<th>کشور</th></tr></thead>
    <tbody class="tbl-rows">${rows || `<tr><td colspan="${crit.length + 4}"><div class="empty">رکوردی ثبت نشده.</div></td></tr>`}</tbody></table></div>
  </div>
  <div class="card"><h2>دلیل امتیاز پنج گزینه برتر</h2>${top}</div>`;
}

function rDiligence(d) {
  return (d.cards || []).map((c) => `
    <div class="card"><div class="section-head"><h2>${esc(c.name)} <span class="score-cell">${c.total || ""}</span></h2>
      <span class="badge ${c.rfq_eligible ? "ok" : "warn"}">RFQ: ${c.rfq_eligible ? "آماده بازبینی" : "توقف تا تأیید هویت"}</span></div>
      <p><span class="badge teal">${esc(c.citation_grade || "درجه استناد")}</span></p>
      <div class="kv">
        <b>نام حقوقی</b><span>${esc(c.legal_name || "تأیید نشد")}</span>
        <b>وب‌سایت رسمی</b><span>${c.official_website ? link(c.official_website, c.official_website) : "تأیید نشد"}</span>
        <b>پروفایل</b><span>${link(c.profile_url, c.profile_url)}</span><b>کشور</b><span>${esc(c.country)}</span>
        <b>ایمیل</b><span>${esc(c.email)}</span><b>تلفن</b><span>${esc(c.phone)}</span>
        <b>تأسیس</b><span>${esc(c.year_founded)}</span><b>آدرس</b><span>${esc(c.address)}</span>
        <b>ثبتی</b><span>${esc(c.registry)}</span>
        <b>گواهی ادعایی</b><span>${esc((c.certs_claimed || []).join("، ") || "—")} (verify نشده)</span>
      </div>
      <div class="flags" style="margin-top:10px">${(c.green_flags || []).map((g) => `<span class="flag g">${esc(g)}</span>`).join("")}</div>
      <div class="flags" style="margin-top:8px">${(c.red_flags || []).map((g) => `<span class="flag r">${esc(g)}</span>`).join("")}</div>
      ${(c.contradictions || []).length ? `<p class="warn">${(c.contradictions || []).map(esc).join(" | ")}</p>` : ""}
    </div>`).join("") || `<div class="card"><div class="empty">هیچ گزینه‌ای از Hard Gate عبور نکرد تا اعتبارسنجی شود.</div></div>`;
}

function rCompare(d) {
  const dec = d.decision || {}; const cards = d.cards || [];
  const maxTotal = Math.max(1, ...(dec.comparison || []).map((r) => r.total || 0));
  const cardsHtml = cards.map((c) => {
    const t = c.total || 0; const p = Math.round((t / 100) * 100);
    const tag = c.name === dec.first_choice ? "گزینه اول" : c.name === dec.second_choice ? "گزینه دوم" : "";
    return `<div class="comp-card"><div class="comp-head"><div><strong>${esc(c.name)}</strong><div class="muted" style="font-size:12px">${esc(c.country)} ${tag ? `<span class="badge gold">${tag}</span>` : ""}</div></div>
      <div class="score-ring" style="--p:${p}%"><span>${t}</span></div></div>
      <p class="muted" style="font-size:12px">${esc(c.citation_grade || "")}</p>
      <div class="flags">${(c.green_flags || []).slice(0, 4).map((g) => `<span class="flag g">${esc(g)}</span>`).join("")}</div>
      <div class="flags" style="margin-top:6px">${(c.red_flags || []).slice(0, 4).map((g) => `<span class="flag r">${esc(g)}</span>`).join("")}</div>
      <div class="copy-row"><button class="btn btn-sm" data-copy="${esc(c.email || "")}">📧 کپی ایمیل</button></div></div>`;
  }).join("");
  const rows = (dec.comparison || []).map((r) => {
    const w = Math.round(((r.total || 0) / maxTotal) * 100);
    const role = r.name === dec.first_choice ? "اول" : r.name === dec.second_choice ? "دوم" : "";
    return `<tr data-search="${esc((r.name + (r.country || "")).toLowerCase())}"><td><span class="badge ${role ? "gold" : "pending"}">${role || "—"}</span></td><td><strong>${esc(r.name)}</strong></td>
      <td><span class="score-cell">${r.total}</span><div class="mini-bar"><i style="width:${w}%"></i></div></td><td>${esc(r.country)}</td>
      <td>${esc((r.strengths || []).join(" | "))}</td><td>${esc((r.weaknesses || []).join(" | "))}</td></tr>`;
  }).join("");
  return `<div class="card"><h2>مقایسه رو‌در‌روی تأمین‌کنندگان</h2>
    <p class="muted">امتیاز پیش از RFQ و درجه استناد؛ امتیاز پاسخ‌گویی هنوز صفر/N/A است.</p>
    <div class="notice ${dec.recommendation_status === "ready_for_initial_negotiation" ? "green" : "amber"}">${esc(dec.recommendation_status_fa)}</div></div>
    ${cardsHtml || `<div class="card"><div class="empty">گزینه‌ای برای مقایسه در دسترس نیست.</div></div>`}
    <div class="card" data-table="tbl-cmp"><h3>جدول مقایسه</h3>
      <div class="filter-bar"><input type="search" placeholder="جستجو…" /><button class="btn btn-sm apply">فیلتر</button></div>
      <div class="table-wrap"><table><thead><tr><th>نقش</th><th>نام</th><th>امتیاز</th><th>کشور</th><th>قوت</th><th>ضعف</th></tr></thead>
      <tbody class="tbl-rows">${rows || `<tr><td colspan=6><div class="empty">موردی ثبت نشده.</div></td></tr>`}</tbody></table></div></div>`;
}

function rRfq(d) {
  const r = d.rfq || {};
  const mails = (r.personalized || []).map((p) => `
    <div class="card"><div class="section-head"><h2>${esc(p.supplier)}</h2>
      <span class="badge ${p.send_status === "ready_for_manual_review" ? "ok" : "warn"}">${p.send_status === "ready_for_manual_review" ? "آماده بازبینی دستی" : "پیش‌نویس — ارسال ممنوع تا تأیید هویت"}</span></div>
      <p class="muted">شخصی‌سازی: ${esc(JSON.stringify(p.personalization_facts))}</p>
      <div class="email-box">${esc(p.final_email)}</div>
      <div class="copy-row"><button class="btn btn-sm" data-copy="${esc(p.final_email)}">📋 کپی ایمیل</button></div></div>`).join("");
  return `<div class="card"><h2>پرامپت‌ها و نسخه اولیه</h2>
    ${Object.entries(r.prompts || {}).map(([k, v]) => `<h3>${esc(k)}</h3><div class="email-box" style="background:#fafaf7;border-style:dashed">${esc(v)}</div>`).join("")}
    <h3>سؤال فنی</h3><ol>${(r.technical_questions || []).map((q) => `<li class="mono">${esc(q)}</li>`).join("")}</ol>
    <h3>سؤال اعتبارسنجی</h3><ol>${(r.dd_questions || []).map((q) => `<li class="mono">${esc(q)}</li>`).join("")}</ol>
    <h3>بهبودهای AI</h3><ul>${(r.improvements || []).map((i) => `<li>${esc(i)}</li>`).join("")}</ul></div>${mails}`;
}

function rDecision(d) {
  const dec = d.decision || {};
  const rows = (dec.comparison || []).map((r) => `<tr data-search="${esc((r.name + (r.country || "")).toLowerCase())}">
    <td><strong>${esc(r.name)}</strong></td><td class="score-cell">${r.total}</td><td>${esc(r.country)}</td>
    <td>${esc((r.strengths || []).join(" | "))}</td><td>${esc((r.weaknesses || []).join(" | "))}</td></tr>`).join("");
  return `<div class="card"><div class="notice ${dec.recommendation_status === "ready_for_initial_negotiation" ? "green" : "amber"}"><strong>${esc(dec.recommendation_status_fa)}</strong></div></div>
  <div class="decision-pair">
    <div class="choice first"><h4>گزینه اول</h4><strong>${esc(dec.first_choice || "انتخاب نشد")}</strong>
      <ul>${(dec.first_reasons || []).map((x) => `<li>${esc(x)}</li>`).join("")}</ul></div>
    <div class="choice"><h4>گزینه دوم</h4><strong>${esc(dec.second_choice || "انتخاب نشد")}</strong>
      <ul>${(dec.second_reasons || []).map((x) => `<li>${esc(x)}</li>`).join("")}</ul></div>
  </div>
  <div class="card" data-table="tbl-cmp"><h3>جدول مقایسه</h3><div class="table-wrap"><table><thead><tr><th>نام</th><th>امتیاز</th><th>کشور</th><th>قوت</th><th>ضعف</th></tr></thead>
  <tbody class="tbl-rows">${rows || `<tr><td colspan=5><div class="empty">موردی ثبت نشده.</div></td></tr>`}</tbody></table></div></div>
  <div class="card"><h3>موارد باز برای بررسی کارشناس</h3><ul>${(dec.open_items || []).map((o) => `<li>${esc(o)}</li>`).join("")}</ul></div>`;
}

function rCost(d) {
  const cards = d.cards || [];
  const opt = cards.map((c) => `<option value="${esc(c.name)}">${esc(c.name)}</option>`).join("");
  return `<div class="card"><div class="section-head"><div><h2>ماشین‌حساب تعاملی هزینه نهایی (Landed Cost)</h2>
    <p class="muted">تخمین اولیه برای مقایسه سناریوها؛ ارقام نهایی باید از Quote و منابع رسمی همان سال گرفته شود.</p></div></div>
  <div class="lc-grid"><div>
    <div class="lc-input"><label>تأمین‌کننده (اختیاری)</label><select id="lcSupplier"><option value="">— انتخاب —</option>${opt}</select></div>
    <div class="lc-input"><label>قیمت واحد FOB (ارز)</label><input id="lcPrice" type="number" inputmode="decimal" placeholder="مثلاً 0.85" value="" /></div>
    <div class="lc-input"><label>مقدار (واحد)</label><input id="lcQty" type="number" inputmode="decimal" placeholder="مثلاً 20000" value="" /></div>
    <div class="lc-input"><label>کرایه بین‌المللی</label><input id="lcFreight" type="number" inputmode="decimal" placeholder="مثلاً 3000" value="" /></div>
    <div class="lc-input"><label>بیمه</label><input id="lcInsurance" type="number" inputmode="decimal" placeholder="مثلاً 150" value="" /></div>
  </div><div>
    <div class="lc-input"><label>حقوق ورودی (٪)</label><input id="lcDuty" type="number" inputmode="decimal" placeholder="مثلاً 10" value="" /></div>
    <div class="lc-input"><label>مالیات / عوارض (٪)</label><input id="lcTax" type="number" inputmode="decimal" placeholder="مثلاً 9" value="" /></div>
    <div class="lc-input"><label>هزینه‌های محلی / ترخیص</label><input id="lcLocal" type="number" inputmode="decimal" placeholder="مثلاً 800" value="" /></div>
    <div class="lc-total" style="margin-top:8px"><small>CIF (ارزش گمرکی سناریو)</small><div class="big" id="lcCif">—</div><small>هزینه نهایی هر واحد</small><div class="big per" id="lcPerUnit">—</div></div>
  </div></div>
  <div class="notice amber"><strong>هشدار</strong>فقط برای مقایسه اولیه؛ مبنای ارزش گمرکی، نرخ حقوق ورودی و مالیات باید از منبع رسمی همان سال کنترل شود.</div></div>`;
}

function rTools(d) {
  const rows = (d.tool_log || []).map((r) => `<tr><td>${esc(r.stage)}</td><td><strong>${esc(r.tool)}</strong></td><td>${esc(r.how || r.method || "")}</td><td>${esc(r.hits)}</td><td class="mono">${esc((r.queries || []).slice(0, 3).join(" | "))}</td></tr>`).join("");
  const cat = Object.values(d.tool_catalog || {}).map((v) => `<li><strong>${esc(v.name)}</strong> — ${esc(v.role)}<br><span class="muted">${esc(v.method)}</span></li>`).join("");
  return `<div class="card"><h2>در هر مرحله از کدام ابزار و چگونه استفاده شد</h2><p class="muted">عبارت site:domain فقط جستجوی عمومی در آن دامنه است، نه استفاده از API آن سرویس.</p></div>
  <div class="card"><div class="table-wrap"><table><thead><tr><th>مرحله</th><th>ابزار</th><th>چگونه</th><th>نتایج</th><th>نمونه پرس‌وجو</th></tr></thead>
  <tbody>${rows || `<tr><td colspan=5><div class="empty">ثبت نشده</div></td></tr>`}</tbody></table></div></div>
  <div class="card"><h3>کاتالوگ ابزار</h3><ul>${cat}</ul></div>`;
}

function rSources(d) {
  const rows = (d.sources || []).map((s) => {
    const g = s.authority_grade || "C";
    return `<tr data-search="${esc(((s.title || "") + " " + (s.domain || "") + " " + (s.claim || "")).toLowerCase())}">
      <td>${esc(s.checked_on)}</td><td>${esc(s.used_for)}</td>
      <td><span class="badge ${g === "A" ? "ok" : g === "B" ? "warn" : "pending"}">${g}</span>/${esc(s.source_type || "open_web")}</td>
      <td>${link(s.url, s.title || s.domain)}<br><span class="muted">${esc(s.claim || "")}</span></td>
      <td>${esc(s.relevance ?? "—")}</td><td class="mono">${esc(s.query)}</td></tr>`;
  }).join("");
  return `<div class="card" data-table="tbl-src"><h2>Source Log</h2>
    <div class="filter-bar"><input type="search" placeholder="جستجو در منابع…" /><button class="btn btn-sm apply">فیلتر</button><span class="muted" style="font-size:12px">${(d.sources || []).length} منبع</span></div>
    <div class="table-wrap"><table><thead><tr><th>تاریخ</th><th>کاربرد</th><th>درجه/نوع</th><th>منبع و ادعا</th><th>ارتباط</th><th>پرس‌وجو</th></tr></thead>
    <tbody class="tbl-rows">${rows || `<tr><td colspan=6><div class="empty">منبعی ثبت نشده.</div></td></tr>`}</tbody></table></div></div>`;
}

/* ---------------- Report interactions ---------------- */
function bindReportInteractions() {
  $$("[data-copy]").forEach((b) => b.addEventListener("click", () => {
    const v = b.dataset.copy;
    if (!v || v === "یافت نشد") return toast("ایمیل در دسترس نیست", "err");
    copyText(v, "ایمیل کپی شد");
  }));
  ["tbl-long", "tbl-score", "tbl-src", "tbl-cmp"].forEach((id) => initTable(`[data-table="${id}"]`));
  initCostCalc();
}
function initTable(sel) {
  const root = document.querySelector(sel);
  if (!root || root.dataset.bound) return;
  root.dataset.bound = "1";
  const btn = root.querySelector(".apply");
  if (btn) btn.addEventListener("click", applyFilter);
  root.querySelectorAll("input[type=search]").forEach((inp) => inp.addEventListener("input", applyFilter));
  root.querySelectorAll("select").forEach((selEl) => selEl.addEventListener("change", applyFilter));
  root.querySelectorAll("th.sortable").forEach((th) => th.addEventListener("click", () => {
    const key = th.dataset.sort; const tb = root.querySelector(".tbl-rows"); const rows = [...tb.querySelectorAll("tr")];
    const dir = th.dataset.dir === "asc" ? "desc" : "asc"; th.dataset.dir = dir;
    rows.sort((a, b) => { const av = a.dataset[key] || "", bv = b.dataset[key] || ""; const cmp = av.localeCompare(bv, "fa", { numeric: true }); return dir === "asc" ? cmp : -cmp; });
    rows.forEach((r) => tb.appendChild(r));
    root.querySelectorAll("th.sortable .caret").forEach((x) => x.remove());
    th.insertAdjacentHTML("beforeend", `<span class="caret"> ${dir === "asc" ? "▲" : "▼"}</span>`);
  }));
}
function applyFilter(e) {
  const root = e.currentTarget.closest("[data-table]");
  const q = (root.querySelector("input[type=search]").value || "").toLowerCase().trim();
  const country = root.querySelector("select[data-key=country]")?.value || "all";
  root.querySelectorAll(".tbl-rows tr").forEach((tr) => {
    let ok = true;
    if (q && !(tr.dataset.search || "").includes(q)) ok = false;
    if (ok && country && country !== "all" && tr.dataset.country !== country) ok = false;
    tr.style.display = ok ? "" : "none";
  });
}
function initCostCalc() {
  const inputs = ["#lcPrice", "#lcQty", "#lcFreight", "#lcInsurance", "#lcDuty", "#lcTax", "#lcLocal"];
  const num = (s) => parseFloat($(s)?.value) || 0;
  const compute = () => {
    const cif = num("#lcPrice") * num("#lcQty") + num("#lcFreight") + num("#lcInsurance");
    const duty = cif * (num("#lcDuty") / 100);
    const tax = (cif + duty) * (num("#lcTax") / 100);
    const landed = cif + duty + tax + num("#lcLocal");
    const q = num("#lcQty");
    $("#lcCif").textContent = q > 0 ? cif.toLocaleString("en-US", { maximumFractionDigits: 2 }) : "—";
    $("#lcPerUnit").textContent = q > 0 ? (landed / q).toLocaleString("en-US", { maximumFractionDigits: 4 }) : "—";
  };
  inputs.forEach((s) => { const el = $(s); if (el) el.addEventListener("input", compute); });
}

/* ---------------- Scrollspy ---------------- */
function bindScrollspy() {
  const nav = $("#reportNav");
  const links = $$("#reportNav a[data-sec]");
  let activeId = "overview";
  const io = new IntersectionObserver((entries) => {
    entries.forEach((en) => { if (en.isIntersecting) activeId = en.target.dataset.sec; });
    links.forEach((a) => a.classList.toggle("on", a.dataset.sec === activeId));
  }, { rootMargin: "-120px 0px -60% 0px", threshold: 0 });
  $$("#reportMount .report-section").forEach((s) => io.observe(s));
  nav.querySelectorAll("a").forEach((a) => a.addEventListener("click", () => {
    activeId = a.dataset.sec;
    links.forEach((x) => x.classList.toggle("on", x.dataset.sec === activeId));
  }));
}

/* ---------------- Reset / resume ---------------- */
function bindReset() {
  $("#resetBtn").addEventListener("click", () => {
    clearInterval(state.timer); stopTimer();
    state.jobId = null; state.token = null; state.dossier = null;
    $("#downloadBar").hidden = true;
    $("#pageTitle").textContent = "ایجاد پرونده ارزیابی واردات";
    $("#pageSub").textContent = "مشخصات تجاری را وارد کنید؛ تجارت‌یار هفت مرحله تحلیل شواهدمحور را اجرا می‌کند.";
    markStages("form", []); show("form");
    window.scrollTo({ top: 0 });
  });
}
function saveLocal() {
  try { localStorage.setItem(LS_KEY, JSON.stringify({ jobId: state.jobId, token: state.token })); } catch (e) {}
}
function loadLocal() {
  try {
    const raw = localStorage.getItem(LS_KEY);
    if (!raw) return;
    const data = JSON.parse(raw);
    if (!data || !data.jobId || !data.token) return;
    $("#resumeCard").hidden = false;
    $("#resumeBtn").onclick = async () => {
      state.jobId = data.jobId; state.token = data.token; state.startedAt = Date.now();
      const res = await apiGet(`/api/job/${encodeURIComponent(state.jobId)}`);
      const job = await res.json();
      if (!res.ok || !job.ok) { toast("پرونده قبلی دیگر در دسترس نیست", "err"); return; }
      if (job.status === "done") {
        state.dossier = job.dossier; bindDownloads(job.id); renderReport(job.dossier);
        show("result"); $("#downloadBar").hidden = false;
        const meta = job.dossier.meta || {};
        $("#pageTitle").textContent = (job.dossier.brief || {}).name_fa || "پرونده";
        $("#pageSub").textContent = `پرونده قبلی بازیابی شد — ${meta.owner_fa || ""} — ${meta.generated_on || ""}`;
      } else if (job.status === "running") { state.startedAt = Date.now(); startRunUI(); }
      else toast("وضعیت پرونده: " + (job.status || "نامشخص"), "err");
      saveLocal();
    };
  } catch (e) {}
}

/* ---------------- Init ---------------- */
function init() {
  buildWizardBar(); renderChips(); wizardRender();
  $("#prevBtn").addEventListener("click", () => goTo(state.curStep - 1));
  $("#nextBtn").addEventListener("click", () => {
    if (state.curStep < 3) { if (validateStep(state.curStep)) goTo(state.curStep + 1); }
    else submitForm();
  });
  bindReset(); loadLocal();
}
document.addEventListener("DOMContentLoaded", init);
