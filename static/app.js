const $ = (s, r = document) => r.querySelector(s);
const $$ = (s, r = document) => [...r.querySelectorAll(s)];

const state = { jobId: null, token: null, timer: null, dossier: null };

const STAGE_LABEL = {
  form: "تعریف پرونده",
  init: "شروع",
  stage1: "تعریف محصول",
  stage2: "بازار ایران",
  stage3: "تأمین‌کننده‌یابی",
  stage4: "غربالگری",
  stage5: "اعتبارسنجی",
  stage6: "ایمیل RFQ",
  stage7: "انتخاب نهایی",
  done: "تحویل",
  error: "خطا",
};

function show(view) {
  $$(".view").forEach((v) => v.classList.remove("active"));
  $(`#view-${view}`).classList.add("active");
  const capabilities = $("#capabilityGrid");
  if (capabilities) capabilities.hidden = view !== "form";
}

function markStages(current, completed = []) {
  $$("#stageNav li").forEach((li) => {
    const st = li.dataset.stage;
    li.classList.toggle("done", completed.includes(st));
    li.classList.toggle("active", st === current || (current === "done" && st === "stage7"));
  });
}

$$("#quickChips button").forEach((btn) => {
  btn.addEventListener("click", () => {
    $$("#quickChips button").forEach((b) => b.classList.remove("selected"));
    btn.classList.add("selected");
    const f = $("#intake");
    f.product_fa.value = btn.dataset.fa || "";
    f.product_en.value = btn.dataset.en || "";
    f.application.value = btn.dataset.app || "";
    f.specs.value = btn.dataset.specs || "";
    f.unit.value = btn.dataset.unit || "";
    f.qty_hint.value = btn.dataset.qty || "";
    f.product_fa.focus();
  });
});

$("#intake").addEventListener("submit", async (e) => {
  e.preventDefault();
  const fd = new FormData(e.target);
  const payload = Object.fromEntries(fd.entries());
  payload.name_fa = (payload.product_fa || payload.name_fa || "").trim();
  payload.name_en = (payload.product_en || payload.name_en || "").trim();
  if (!payload.name_fa && !payload.name_en) {
    alert("نام کالا را وارد کنید یا یکی از سناریوهای نمونه را انتخاب کنید.");
    return;
  }
  const btn = $("#runBtn");
  btn.disabled = true;
  try {
    const res = await fetch("/api/run", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    const data = await res.json();
    if (!data.ok) throw new Error(data.error || "خطا در شروع");
    state.jobId = data.job_id;
    state.token = data.access_token;
    $("#logBox").innerHTML = "";
    $("#runBar").style.width = "2%";
    $("#runPct").textContent = "2%";
    $("#runStatus").textContent = "تجارت‌یار در حال تحلیل و تشکیل پرونده است…";
    show("run");
    markStages("stage1", []);
    poll();
  } catch (err) {
    alert(err.message);
    btn.disabled = false;
  }
});

function poll() {
  if (state.timer) clearInterval(state.timer);
  const tick = async () => {
    let job;
    try {
      const res = await fetch(`/api/job/${encodeURIComponent(state.jobId)}?token=${encodeURIComponent(state.token || "")}`);
      job = await res.json();
      if (!res.ok || !job.ok) throw new Error(job.error || "خطا در دریافت وضعیت");
    } catch (err) {
      $("#runNow").textContent = `ارتباط موقتاً برقرار نیست: ${err.message}`;
      return;
    }
    $("#runBar").style.width = `${job.progress || 0}%`;
    $("#runPct").textContent = `${job.progress || 0}%`;
    $("#runNow").textContent = (job.logs.at(-1) || {}).message || "…";
    markStages(job.current_stage, job.completed || []);
    renderLogs(job.logs || []);
    if (job.status === "done") {
      clearInterval(state.timer);
      state.dossier = job.dossier;
      bindDownloads(job.id, state.token);
      renderResult(job.dossier);
      show("result");
      $("#downloadBar").hidden = false;
      $("#pageTitle").textContent = `${job.dossier.brief.name_fa}`;
      const owner = job.dossier.meta.owner_fa || "تهیه‌کننده گزارش";
      const org = job.dossier.meta.organization ? ` — ${job.dossier.meta.organization}` : "";
      $("#pageSub").textContent = `پرونده آماده بازبینی است — ${owner}${org} — ${job.dossier.meta.generated_on}`;
      $("#runBtn").disabled = false;
    }
    if (job.status === "error") {
      clearInterval(state.timer);
      $("#runStatus").textContent = "خطا در اجرا";
      $("#runNow").textContent = job.error || "خطای ناشناخته";
      $("#runBtn").disabled = false;
    }
  };
  tick();
  state.timer = setInterval(tick, 1600);
}

function renderLogs(logs) {
  const box = $("#logBox");
  box.innerHTML = logs
    .map(
      (l) =>
        `<div><time>${esc(l.t)}</time><em>${esc(STAGE_LABEL[l.stage] || l.stage)}</em><span>${esc(l.message)}</span></div>`
    )
    .join("");
  box.scrollTop = box.scrollHeight;
}

function bindDownloads(id, token) {
  const map = {
    dlReport: "report",
    dlExcel: "excel",
    dlRfq: "rfq",
    dlPrompts: "prompts",
  };
  Object.entries(map).forEach(([el, kind]) => {
    $(`#${el}`).href = `/api/job/${encodeURIComponent(id)}/file/${kind}?token=${encodeURIComponent(token || "")}`;
  });
}

function esc(s) {
  return String(s ?? "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;");
}

function link(url, label) {
  if (!url || !/^https?:\/\//i.test(String(url))) return "—";
  return `<a href="${esc(url)}" target="_blank" rel="noopener noreferrer">${esc(label || url)}</a>`;
}

$$("#tabs button").forEach((b) => {
  b.addEventListener("click", () => {
    $$("#tabs button").forEach((x) => x.classList.remove("on"));
    b.classList.add("on");
    if (state.dossier) paintTab(b.dataset.tab, state.dossier);
  });
});

$("#resetBtn").addEventListener("click", () => {
  state.jobId = null;
  state.token = null;
  state.dossier = null;
  $("#downloadBar").hidden = true;
  $("#pageTitle").textContent = "ایجاد پرونده ارزیابی واردات";
  $("#pageSub").textContent = "مشخصات تجاری را وارد کنید؛ تجارت‌یار هفت مرحله تحلیل شواهدمحور را اجرا می‌کند.";
  markStages("form", []);
  show("form");
});

function renderResult(d) {
  paintTab("overview", d);
}

function paintTab(tab, d) {
  const el = $("#resultMount");
  const painters = {
    overview: tabOverview,
    s1: tab1,
    s2: tab2,
    s3: tab3,
    s4: tab4,
    s5: tab5,
    s6: tab6,
    s7: tab7,
    tools: tabTools,
    src: tabSrc,
  };
  el.innerHTML = (painters[tab] || tabOverview)(d);
}

function tabOverview(d) {
  const dec = d.decision || {};
  const qa = d.quality_assurance || { checks: [] };
  const meta = d.meta || {};
  const longCount = (d.sourcing.longlist || []).length;
  const topCount = (d.scoring.top5 || []).length;
  const sourceCount = (d.sources || []).length;
  const choice1 = dec.first_choice || "هنوز گزینه قابل دفاعی انتخاب نشده";
  const choice2 = dec.second_choice || "نیازمند تحقیق تکمیلی";
  return `
    <div class="executive-head card">
      <div>
        <span class="eyebrow">EXECUTIVE IMPORT DOSSIER</span>
        <h3>${esc(meta.project_title || "پرونده تصمیم‌گیری واردات")}</h3>
        <p>${esc(meta.report_purpose || "ارزیابی اولیه فرصت واردات و تأمین‌کنندگان")}</p>
      </div>
      <div class="executive-meta">
        <span>${esc(meta.owner_fa || "تهیه‌کننده گزارش")}</span>
        <small>${esc(meta.organization || "بدون نام سازمان")}</small>
      </div>
    </div>
    <div class="kpi-grid">
      <article><small>Longlist معتبر</small><strong>${longCount}</strong><span>رکورد عبورکرده از فیلتر</span></article>
      <article><small>Shortlist</small><strong>${topCount}</strong><span>گزینه عبورکرده از Hard Gate</span></article>
      <article><small>Evidence Log</small><strong>${sourceCount}</strong><span>منبع پذیرفته‌شده و قابل ردیابی</span></article>
      <article><small>QA Controls</small><strong>${qa.passed || 0}/${qa.total || 0}</strong><span>${esc(qa.status || "در انتظار کنترل")}</span></article>
    </div>
    <div class="card decision-status">
      <div><h3>وضعیت تصمیم</h3><p>${esc(dec.recommendation_status_fa || "وضعیت نامشخص")}</p></div>
      <span class="status-pill ${dec.recommendation_status === "ready_for_initial_negotiation" ? "ok" : "warning"}">${esc(dec.recommendation_status || "not_ready")}</span>
    </div>
    <div class="decision">
      <div class="choice first">
        <h4>گزینه اول برای شروع مذاکره</h4>
        <strong>${esc(choice1)}</strong>
        <ul>${(dec.first_reasons || []).map((r) => `<li>${esc(r)}</li>`).join("")}</ul>
      </div>
      <div class="choice">
        <h4>گزینه دوم (پشتیبان)</h4>
        <strong>${esc(choice2)}</strong>
        <ul>${(dec.second_reasons || []).map((r) => `<li>${esc(r)}</li>`).join("")}</ul>
      </div>
    </div>
    <div class="card">
      <h3>کنترل کیفیت پرونده</h3>
      <div class="qa-list">${(qa.checks || []).map(c => `<p class="${c.passed ? "qa-pass" : "qa-open"}"><strong>${c.passed ? "✓" : "!"} ${esc(c.check)}</strong><br><span class="muted">${esc(c.detail)}</span></p>`).join("")}</div>
    </div>
    <div class="card">
      <h3>مشخصات و دامنه پرونده</h3>
      <div class="kv">
        <b>محصول</b><span>${esc(d.brief.name_fa)} / ${esc(d.brief.name_en)}</span>
        <b>گروه محصول</b><span>${esc(d.brief.product_category_label || "—")}</span>
        <b>کیفیت ورودی</b><span>${esc((d.brief.input_quality || {}).score || 0)}٪</span>
        <b>HS کاندید</b><span>${esc(d.brief.hs_primary || "تأیید نشد")} — کد ملی باید رسمی کنترل شود</span>
        <b>وضعیت بازار</b><span>${esc(d.market.imported_statement)}</span>
        <b>مبدأهای هدف</b><span>${esc((d.brief.origin_strategy || []).join("، "))}</span>
      </div>
      <p class="warn">${esc(dec.disclaimer)}</p>
    </div>`;
}

function tab1(d) {
  const b = d.brief;
  return `
    <div class="card">
      <h3>Product Brief</h3>
      <div class="kv">
        <b>نام فارسی</b><span>${esc(b.name_fa)}</span>
        <b>نام انگلیسی</b><span>${esc(b.name_en)}</span>
        <b>کاربرد</b><span>${esc(b.application)}</span>
        <b>مشخصات</b><span>${esc(b.specs)}</span>
        <b>گرید/مدل</b><span>${esc(b.grade_model)}</span>
        <b>واحد خرید</b><span>${esc(b.unit)}</span>
        <b>مشتری هدف</b><span>${esc(b.target_customer)}</span>
        <b>مقدار سفارش</b><span>${esc(b.qty_hint)}</span>
        <b>گروه محصول</b><span>${esc(b.product_category_label || "—")}</span>
        <b>مبدأهای جستجو</b><span>${esc((b.origin_strategy || []).join("، "))}</span>
        <b>ویژگی‌های مؤثر بر HS</b><span>${esc((b.classification_attributes || []).join(" | "))}</span>
        <b>کد HS کاندید</b><span>${esc(b.hs_primary || "—")}</span>
        <b>کدهای جایگزین</b><span>${esc((b.hs_alternatives || []).join(" ، ") || "—")}</span>
      </div>
      <p class="warn">${esc(b.hs_reason)}</p>
      <p class="muted">${esc(b.description_web)}</p>
      <h3>هشدارهای کیفیت ورودی</h3>
      <ul>${((b.input_quality || {}).warnings || []).map(x => `<li>${esc(x)}</li>`).join("") || "<li>هشدار مهمی ثبت نشد.</li>"}</ul>
      <h3>عبارات جستجوی Sourcing</h3>
      <ol>${(b.search_phrases || []).map((p) => `<li dir="ltr">${esc(p)}</li>`).join("")}</ol>
    </div>`;
}

function tab2(d) {
  const m = d.market || {};
  const risks = m.regulatory_risks || [];
  const portals = m.official_portals || [];
  const riskCards = risks.map((r) => {
    const officiallyVerified = r.verified === true;
    const webMention = r.triggered_by_web === true || /اشاره در منابع وب/.test(String(r.level || ""));
    const status = officiallyVerified
      ? "تأییدشده در مرجع رسمی"
      : webMention
        ? "هشدار اولیه؛ اشاره در منابع وب"
        : "کنترل رسمی انجام نشده";
    const cls = officiallyVerified ? "ok" : webMention ? "warning" : "pending";
    return `<article class="reg-card">
      <div class="reg-card-head">
        <h4>${esc(r.title || "ریسک مقرراتی")}</h4>
        <span class="status-pill ${cls}">${esc(status)}</span>
      </div>
      <dl class="reg-details">
        <div><dt>این مورد چیست؟</dt><dd>${esc(r.detail || "توضیح ثبت نشده است.")}</dd></div>
        <div><dt>سطح فعلی</dt><dd>${esc(r.level || "نامشخص تا زمان کنترل رسمی")}</dd></div>
        <div><dt>اقدام لازم</dt><dd>${esc(r.verification || "در مرجع رسمی مرتبط بررسی و نتیجه ثبت شود.")}</dd></div>
      </dl>
    </article>`;
  }).join("");
  const portalRows = portals.map((p) => `<tr>
    <td><strong>${esc(p.name)}</strong></td>
    <td>${esc(p.check)}</td>
    <td><span class="status-pill pending">${esc(p.status || "کنترل دستی الزامی")}</span></td>
    <td>${link(p.url, "بازکردن مرجع رسمی")}</td>
  </tr>`).join("");
  return `
    <div class="card">
      <h3>Import Opportunity Snapshot</h3>
      <p>${esc(m.imported_statement)}</p>
      <div class="reg-notice">
        <strong>راهنمای این بخش</strong>
        <p>موارد زیر «حکم قطعی» نیستند؛ فهرست کنترل مقرراتی‌اند. وضعیت هر مورد مشخص می‌کند که فقط در وب به آن اشاره شده یا واقعاً در مرجع رسمی تأیید شده است.</p>
      </div>
      <h3>شواهد پذیرفته‌شده وب</h3>
      <ul class="evidence-list">${(m.imported_evidence || []).map((e) => `<li>${link(e.url, e.claim)} <span class="muted">— درجه ${esc(e.authority_grade || "C")} — ${esc(e.domain)} — ${esc(e.checked_on)}</span><br><span class="muted">${esc(e.snippet)}</span></li>`).join("") || "<li>شاهد قابل قبول ثبت نشد.</li>"}</ul>
    </div>
    <div class="card">
      <h3>چک‌لیست ریسک‌های مقرراتی</h3>
      <p class="muted">برای هر ردیف، «توضیح»، «وضعیت فعلی» و «اقدام لازم» جدا شده است.</p>
      <div class="reg-grid">${riskCards || "<p>ریسکی ثبت نشده است.</p>"}</div>
    </div>
    <div class="card">
      <h3>مراجع رسمی برای کنترل نهایی</h3>
      <p class="muted">این جدول فقط می‌گوید در هر سامانه چه چیزی باید بررسی شود؛ درج نام سامانه به معنی انجام‌شدن کنترل نیست.</p>
      <div class="table-wrap portal-table"><table>
        <thead><tr><th>مرجع رسمی</th><th>چه چیزی بررسی شود؟</th><th>وضعیت فعلی</th><th>لینک</th></tr></thead>
        <tbody>${portalRows || "<tr><td colspan=4>مرجعی ثبت نشده است.</td></tr>"}</tbody>
      </table></div>
      <div class="reg-notice final">
        <strong>نتیجه‌ای که کارشناس باید ثبت کند</strong>
        <p>پس از مراجعه به سامانه رسمی، وضعیت «مجاز/مشروط/ممنوع»، مجوز لازم، استاندارد، تعرفه و محدودیت ارزی را همراه تاریخ بررسی و لینک/تصویر شاهد در گزارش نهایی وارد کنید.</p>
      </div>
    </div>`;
}

function tab3(d) {
  const s = d.sourcing;
  const persona = Object.entries(s.persona || {}).map(([k, v]) => `<div><b>${esc(k)}</b><span>${esc(v)}</span></div>`).join("");
  const rows = (s.longlist || [])
    .map(
      (x, i) => `<tr>
        <td>${i + 1}</td><td>${esc(x.name)}<br><span class="muted">${esc(x.legal_name || "نام حقوقی تأییدنشده")}</span></td><td>${esc(x.country)}</td>
        <td>${esc(x.candidate_grade || "C")}</td><td>${esc(x.product_match ?? "—")}</td>
        <td>${esc(x.source_channel)}</td><td>${esc(x.identity_status || "—")}</td>
        <td>${esc(x.contact || "—")}</td><td>${link(x.official_website || x.url, "منبع")}</td>
      </tr>`
    )
    .join("");
  return `
    <div class="card">
      <h3>Supplier Persona</h3>
      <div class="kv">${persona}</div>
      <p>کانال‌ها: ${esc((s.channels_used || []).join("، "))} · Longlist: ${(s.longlist || []).length}</p>
      <p class="warn">${esc(s.requirement_status || "")}</p>
    </div>
    <div class="table-wrap"><table>
      <thead><tr><th>#</th><th>نام / نام حقوقی</th><th>کشور</th><th>درجه کاندید</th><th>تطابق محصول</th><th>کانال</th><th>وضعیت هویت</th><th>تماس</th><th>لینک</th></tr></thead>
      <tbody>${rows}</tbody>
    </table></div>
    <div class="card">
      <h3>نمونه حذف‌شده‌ها</h3>
      <ul>${(s.rejected || []).slice(0, 15).map((r) => `<li>${esc(r.reason)} — ${esc(r.title || "")}</li>`).join("")}</ul>
    </div>`;
}

function tab4(d) {
  const crit = d.scoring.criteria || [];
  const rows = (d.scoring.scored || [])
    .map((s, i) => {
      const cells = crit.map((c) => `<td>${(s.scores || {})[c.id] ?? "—"}</td>`).join("");
      return `<tr><td>${i + 1}</td><td>${esc(s.name)}</td><td class="score">${s.total}</td>${cells}<td>${esc(s.country)}</td></tr>`;
    })
    .join("");
  const top = (d.scoring.top5 || [])
    .map((s) => {
      const bars = Object.entries(s.scores || [])
        .map(([k, v]) => {
          const c = crit.find((x) => x.id === k);
          const max = c ? c.max : 10;
          return `<div class="row"><span>${esc(c ? c.title : k)}</span><div class="track"><i style="width:${(v / max) * 100}%"></i></div><span>${v}</span></div>`;
        })
        .join("");
      const reasons = Object.values(s.reasons || {})
        .map((r) => `<li>${esc(r)}</li>`)
        .join("");
      return `<div class="card"><h3>${esc(s.name)} <span class="score">${s.total}/100</span></h3><div class="bars">${bars}</div><ul>${reasons}</ul></div>`;
    })
    .join("");
  return `
    <div class="card"><p>${esc(d.scoring.model_note)}</p></div>
    <div class="table-wrap"><table>
      <thead><tr><th>#</th><th>نام</th><th>جمع</th>${crit.map((c) => `<th>${esc(c.title)}</th>`).join("")}<th>کشور</th></tr></thead>
      <tbody>${rows}</tbody>
    </table></div>
    ${top}`;
}

function tab5(d) {
  return (d.cards || [])
    .map(
      (c) => `
      <div class="card">
        <h3>${esc(c.name)} <span class="score">${c.total || ""}</span></h3>
        <p><strong>${esc(c.citation_grade || "درجه استناد محاسبه نشده")}</strong> · RFQ: ${c.rfq_eligible ? "آماده بازبینی دستی" : "توقف تا تأیید هویت"}</p>
        <div class="kv">
          <b>نام حقوقی</b><span>${esc(c.legal_name || "تأیید نشد")}</span>
          <b>وب‌سایت رسمی</b><span>${c.official_website ? link(c.official_website, c.official_website) : "تأیید نشد"}</span>
          <b>پروفایل</b><span>${link(c.profile_url, c.profile_url)}</span>
          <b>کشور</b><span>${esc(c.country)}</span>
          <b>ایمیل</b><span>${esc(c.email)}</span>
          <b>تلفن</b><span>${esc(c.phone)}</span>
          <b>تأسیس</b><span>${esc(c.year_founded)}</span>
          <b>آدرس</b><span>${esc(c.address)}</span>
          <b>ثبتی</b><span>${esc(c.registry)}</span>
          <b>گواهی ادعایی</b><span>${esc((c.certs_claimed || []).join("، ") || "—")} (verify نشده)</span>
        </div>
        <div class="flags">${(c.green_flags || []).map((g) => `<span class="flag g">${esc(g)}</span>`).join("")}</div>
        <div class="flags" style="margin-top:8px">${(c.red_flags || []).map((g) => `<span class="flag r">${esc(g)}</span>`).join("")}</div>
        ${(c.contradictions || []).length ? `<p class="warn">${(c.contradictions || []).map(esc).join(" | ")}</p>` : ""}
      </div>`
    )
    .join("");
}

function tab6(d) {
  const r = d.rfq;
  const prompts = Object.entries(r.prompts || [])
    .map(([k, v]) => `<h3>${esc(k)}</h3><div class="prompt">${esc(v)}</div>`)
    .join("");
  const mails = (r.personalized || [])
    .map(
      (p) => `<div class="card"><h3>${esc(p.supplier)}</h3>
        <p class="warn">وضعیت ارسال: ${esc(p.send_status || "نیازمند بازبینی")}</p>
        <p class="muted">شخصی‌سازی: ${esc(JSON.stringify(p.personalization_facts))}</p>
        <div class="email">${esc(p.final_email)}</div></div>`
    )
    .join("");
  return `
    <div class="card">
      <h3>پرامپت‌ها</h3>${prompts}
      <h3>نسخه اولیه</h3>
      <div class="email">${esc(r.initial_email)}</div>
      <h3>سؤال فنی</h3><ol>${(r.technical_questions || []).map((q) => `<li dir="ltr">${esc(q)}</li>`).join("")}</ol>
      <h3>سؤال اعتبارسنجی</h3><ol>${(r.dd_questions || []).map((q) => `<li dir="ltr">${esc(q)}</li>`).join("")}</ol>
      <h3>بهبودهای AI</h3><ul>${(r.improvements || []).map((i) => `<li>${esc(i)}</li>`).join("")}</ul>
    </div>
    ${mails}`;
}

function tab7(d) {
  const dec = d.decision;
  const rows = (dec.comparison || [])
    .map(
      (r) => `<tr>
        <td>${esc(r.name)}</td><td class="score">${r.total}</td><td>${esc(r.country)}</td>
        <td>${esc((r.strengths || []).join(" | "))}</td>
        <td>${esc((r.weaknesses || []).join(" | "))}</td>
      </tr>`
    )
    .join("");
  return `
    <div class="card"><p class="warn"><strong>${esc(dec.recommendation_status_fa || "")}</strong></p></div>
    <div class="decision">
      <div class="choice first"><h4>اول</h4><strong>${esc(dec.first_choice || "انتخاب نشد")}</strong>
        <ul>${(dec.first_reasons || []).map((x) => `<li>${esc(x)}</li>`).join("")}</ul></div>
      <div class="choice"><h4>دوم</h4><strong>${esc(dec.second_choice || "انتخاب نشد")}</strong>
        <ul>${(dec.second_reasons || []).map((x) => `<li>${esc(x)}</li>`).join("")}</ul></div>
    </div>
    <div class="table-wrap"><table>
      <thead><tr><th>نام</th><th>امتیاز</th><th>کشور</th><th>قوت</th><th>ضعف</th></tr></thead>
      <tbody>${rows}</tbody>
    </table></div>
    <div class="card">
      <h3>موارد باز برای بررسی کارشناس</h3>
      <ul>${(dec.open_items || []).map((o) => `<li>${esc(o)}</li>`).join("")}</ul>
    </div>`;
}

function tabTools(d) {
  const rows = (d.tool_log || [])
    .map(
      (r) => `<tr>
        <td>${esc(r.stage)}</td><td><strong>${esc(r.tool)}</strong></td>
        <td>${esc(r.how || r.method || "")}</td>
        <td>${esc(r.hits)}</td>
        <td dir="ltr">${esc((r.queries || []).slice(0, 3).join(" | "))}</td>
      </tr>`
    )
    .join("");
  const cat = Object.values(d.tool_catalog || {})
    .map((v) => `<li><strong>${esc(v.name)}</strong> — ${esc(v.role)}<br><span class="muted">${esc(v.method)}</span></li>`)
    .join("");
  return `
    <div class="card">
      <h3>در هر مرحله از کدام ابزار و چطور استفاده شد</h3>
      <p class="muted">ابزار واقعی هر مرحله ثبت شده است. عبارت site:domain فقط جستجوی عمومی در آن دامنه است و به معنای استفاده از API آن سرویس نیست.</p>
    </div>
    <div class="table-wrap"><table>
      <thead><tr><th>مرحله</th><th>ابزار</th><th>چگونه</th><th>نتایج</th><th>نمونه پرس‌وجو</th></tr></thead>
      <tbody>${rows || "<tr><td colspan=5>هنوز ثبت نشده</td></tr>"}</tbody>
    </table></div>
    <div class="card"><h3>کاتالوگ ابزار</h3><ul>${cat}</ul></div>`;
}

function tabSrc(d) {
  const rows = (d.sources || [])
    .map(
      (s) => `<tr>
        <td>${esc(s.checked_on)}</td><td>${esc(s.used_for)}</td>
        <td>${esc(s.authority_grade || "C")} / ${esc(s.source_type || "open_web")}</td>
        <td>${link(s.url, s.title || s.domain)}<br><span class="muted">${esc(s.claim || "")}</span></td>
        <td>${esc(s.relevance ?? "—")}</td><td>${esc(s.query)}</td>
      </tr>`
    )
    .join("");
  return `<div class="table-wrap"><table>
    <thead><tr><th>تاریخ</th><th>کاربرد</th><th>درجه/نوع</th><th>منبع و ادعا</th><th>ارتباط</th><th>پرس‌وجو</th></tr></thead>
    <tbody>${rows}</tbody>
  </table></div>`;
}
