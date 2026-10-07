"use strict";
/* DataOps AI v2.0 — SPA local. Sin dependencias externas: todo calculado desde la API. */
const $ = (s) => document.querySelector(s);
const $$ = (s) => Array.from(document.querySelectorAll(s));
const escapeHTML = (value) =>
  String(value ?? "").replace(/[&<>"']/g, (c) => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"})[c]);
const e = escapeHTML;
const num = (value) => Number(value || 0).toLocaleString("es-MX");
const dateFmt = (value) => value ? new Date(value).toLocaleString("es-MX", {dateStyle:"short", timeStyle:"short"}) : "—";
const qs = (o) => Object.entries(o).filter(([,v]) => v !== "" && v !== undefined && v !== null).map(([k,v]) => `${encodeURIComponent(k)}=${encodeURIComponent(v)}`).join("&");
const paths = {
  grid:"M3 3h7v7H3z M14 3h7v7h-7z M3 14h7v7H3z M14 14h7v7h-7z",
  folder:"M3 7a2 2 0 0 1 2-2h4l2 2h8a2 2 0 0 1 2 2v9a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V7z",
  data:"M4 6c0-4 16-4 16 0s-16 4-16 0v12c0 4 16 4 16 0V6 M4 12c0 4 16 4 16 0",
  run:"M8 5l11 7-11 7V5z", rule:"M8 6h13 M8 12h13 M8 18h13 M3 6h1 M3 12h1 M3 18h1",
  users:"M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2 M9 3a4 4 0 1 0 0 8 4 4 0 0 0 0-8 M20 21v-2a4 4 0 0 0-3-3.87 M16 3.13a4 4 0 0 1 0 7.75",
  upload:"M12 16V3 M7 8l5-5 5 5 M4 16v5h16v-5", arrow:"M5 12h14 M13 6l6 6-6 6",
  check:"M4 12l5 5L20 6", clock:"M12 8v4l3 2 M21 12a9 9 0 1 1-18 0 9 9 0 0 1 18 0",
  alert:"M12 3L2 21h20L12 3z M12 9v5 M12 17h.01",
  file:"M14 2H5v20h14V7l-5-5z M14 2v6h5 M8 12h8 M8 16h8",
  ai:"M12 3v3 M12 18v3 M3 12h3 M18 12h3 M7 7l-2-2 M17 17l2 2 M7 17l-2 2 M17 7l2-2 M8 8h8v8H8z",
  logout:"M9 21H3V3h6 M16 17l5-5-5-5 M21 12H9", close:"M6 6l12 12 M6 18L18 6",
  download:"M12 3v12 M7 10l5 5 5-5 M4 17v4h16v-4", bell:"M18 8a6 6 0 1 0-12 0c0 7-3 8-3 8h18s-3-1-3-8 M10 21a2 2 0 0 0 4 0",
  chart:"M3 3v18h18 M7 15l4-5 3 3 5-7", gear:"M12 15a3 3 0 1 0 0-6 3 3 0 0 0 0 6z M19 12a7 7 0 0 0-.1-1.2l2-1.6-2-3.4-2.4 1a7 7 0 0 0-2-1.2L14 3h-4l-.5 2.6a7 7 0 0 0-2 1.2l-2.4-1-2 3.4 2 1.6A7 7 0 0 0 5 12c0 .4 0 .8.1 1.2l-2 1.6 2 3.4 2.4-1a7 7 0 0 0 2 1.2L10 21h4l.5-2.6a7 7 0 0 0 2-1.2l2.4 1 2-3.4-2-1.6c.1-.4.1-.8.1-1.2z",
  hist:"M3 12a9 9 0 1 0 3-6.7 M3 4v5h5 M12 7v5l3 3", report:"M6 2h9l5 5v15H6V2z M14 2v6h6 M9 13h6 M9 17h6",
  menu:"M3 6h18 M3 12h18 M3 18h18", search:"M11 19a8 8 0 1 0 0-16 8 8 0 0 0 0 16z M21 21l-4.3-4.3",
};
const icon = (n) => `<svg class="icon" viewBox="0 0 24 24" aria-hidden="true"><path d="${paths[n]||paths.file}"/></svg>`;
const labels = {queued:"En cola",running:"En proceso",completed:"Completada",failed:"Fallida",invalid:"Inválido",anomaly:"Por revisar",loaded:"Cargado",existing:"Ya existente",rejected:"Rechazado",approved:"Aprobado",activo:"Activo",archivado:"Archivado",pendiente:"Pendiente",aprobada:"Aprobada",rechazada:"Rechazada",resuelta:"Resuelta"};
const roles = {admin:"Administrador",operator:"Data Engineer",viewer:"Usuario"};
const badge = (s) => `<span class="status ${e(s)}">${e(labels[s]||s)}</span>`;
const sevBadge = (s) => `<span class="sev ${e(s)}">${e(s)}</span>`;
const lvlBadge = (s) => `<span class="level ${e(s)}">${e(s)}</span>`;
const S = { user:null, page:"dashboard", projects:[], project:null, projectTab:"resumen", projectSummary:null,
  datasets:[], dsSearch:"", dsProject:"", dsOffset:0, runs:[], runTotal:0, runOffset:0, runFilter:"",
  summary:null, pipeline:null, pipelines:[], pipeProject:"", metrics:null, ready:null, detail:null, rowKind:"all", rowOffset:0, busy:false,
  dash:null, monitoring:null, rules:[], ruleDataset:"", qualityEval:null, anomalies:[], anomTotal:0, anomOffset:0, anomSev:"", anomStatus:"pendiente", anomSearch:"",
  alerts:[], alertTotal:0, unread:0, alertLevel:"", reports:[], activity:[], actTotal:0, actOffset:0, actSearch:"",
  aiProject:"", aiDataset:"", chat:[], aiHistory:[], aiStatus:null, profile:null, dquality:null, drows:null, projSearch:"", config:null, users:[] };
let toastTimer;
function toast(m, err=false){ const b=$("#toast"); b.textContent=m; b.className="toast"+(err?" error":""); b.hidden=false; clearTimeout(toastTimer); toastTimer=setTimeout(()=>b.hidden=true,5000); }
async function api(path, data, method){
  const opts = { credentials:"same-origin", headers:{"X-Requested-With":"DataOps"} };
  if (data !== undefined){ opts.method = method || "POST"; opts.headers["Content-Type"]="application/json"; opts.body = JSON.stringify(data); }
  else if (method && method !== "GET"){ opts.method = method; }
  let r; try { r = await fetch("/api"+path, opts); }
  catch { throw new Error("No se pudo conectar con el servicio. Comprueba que siga encendido."); }
  const ct = r.headers.get("content-type")||"";
  if (ct.includes("application/pdf") || ct.includes("text/csv")) return r;
  let v; try { v = await r.json(); } catch { throw new Error("El servicio devolvió una respuesta inesperada."); }
  if (!r.ok){ const er = new Error(typeof v.detail==="string"?v.detail:"No se pudo completar la solicitud."); er.status=r.status; throw er; }
  return v;
}
const apiPut = (p,d) => api(p,d,"PUT"); const apiPatch=(p,d)=>api(p,d,"PATCH"); const apiDel=(p)=>api(p,undefined,"DELETE");
const canEdit = () => S.user && S.user.role !== "viewer";
const isAdmin = () => S.user && S.user.role === "admin";
/* ---------- gráficas canvas (sin librerías, datos reales) ---------- */
const PALETTE = ["#9cc5b5","#8fb4d9","#d3bd8a","#d69a9e","#b9a8d9","#8a919a","#7fc4a8","#6aa8d8"];
function setupCanvas(cv){ const dpr=window.devicePixelRatio||1; const w=cv.clientWidth||300, h=cv.clientHeight||200; cv.width=w*dpr; cv.height=h*dpr; const c=cv.getContext("2d"); c.scale(dpr,dpr); return [c,w,h]; }
function drawBars(id, items, labelKey="label", valueKey="value"){
  const cv=document.getElementById(id); if(!cv) return; const [c,W,H]=setupCanvas(cv); c.clearRect(0,0,W,H);
  if(!items.length){ c.fillStyle="#6f7784"; c.font="12px Inter,system-ui"; c.fillText("Sin datos todavía",10,20); return; }
  const max=Math.max(...items.map(i=>Number(i[valueKey])||0),1); const n=items.length; const bw=Math.min(46,(W-20)/n-8);
  items.forEach((it,i)=>{ const v=Number(it[valueKey])||0; const bh=(H-52)*(v/max); const x=10+i*((W-20)/n)+( (W-20)/n-bw)/2; const y=H-28-bh;
    c.fillStyle=PALETTE[i%PALETTE.length]; c.beginPath(); c.roundRect?c.roundRect(x,y,bw,bh,4):c.rect(x,y,bw,bh); c.fill();
    c.fillStyle="#e8eaed"; c.font="bold 11px Inter,system-ui"; c.textAlign="center"; c.fillText(String(v),x+bw/2,y-4);
    c.fillStyle="#9aa3af"; c.font="10px Inter,system-ui"; const lb=String(it[labelKey]).slice(0,12); c.fillText(lb,x+bw/2,H-12); });
}
function drawDonut(id, items, labelKey="label", valueKey="value"){
  const cv=document.getElementById(id); if(!cv) return; const [c,W,H]=setupCanvas(cv); c.clearRect(0,0,W,H);
  const total=items.reduce((a,i)=>a+(Number(i[valueKey])||0),0);
  if(!total){ c.fillStyle="#6f7784"; c.font="12px Inter,system-ui"; c.fillText("Sin datos todavía",10,20); return; }
  const cx=W/2-40, cy=H/2, R=Math.min(W,H)/2-18; let a=-Math.PI/2;
  items.forEach((it,i)=>{ const v=Number(it[valueKey])||0; const ang=(v/total)*Math.PI*2; c.beginPath(); c.moveTo(cx,cy); c.arc(cx,cy,R,a,a+ang); c.closePath(); c.fillStyle=PALETTE[i%PALETTE.length]; c.fill(); a+=ang; });
  c.fillStyle="#15181d"; c.beginPath(); c.arc(cx,cy,R*0.58,0,Math.PI*2); c.fill();
  c.fillStyle="#e8eaed"; c.font="bold 15px Inter,system-ui"; c.textAlign="center"; c.fillText(String(total),cx,cy+5);
  let ly=16; c.textAlign="left";
  items.forEach((it,i)=>{ c.fillStyle=PALETTE[i%PALETTE.length]; c.fillRect(cx+R+14,ly-8,10,10); c.fillStyle="#9aa3af"; c.font="11px Inter,system-ui"; c.fillText(`${String(it[labelKey]).slice(0,14)} (${it[valueKey]})`,cx+R+28,ly); ly+=20; });
}
function drawLine(id, items, labelKey="label", valueKey="value"){
  const cv=document.getElementById(id); if(!cv) return; const [c,W,H]=setupCanvas(cv); c.clearRect(0,0,W,H);
  if(items.length<2){ c.fillStyle="#6f7784"; c.font="12px Inter,system-ui"; c.fillText(items.length?"Se necesita más historial":"Sin datos todavía",10,20); return; }
  const max=Math.max(...items.map(i=>Number(i[valueKey])||0),1); const pad=26;
  c.strokeStyle="#2e353f"; c.beginPath(); c.moveTo(pad,6); c.lineTo(pad,H-pad); c.lineTo(W-6,H-pad); c.stroke();
  const pts=items.map((it,i)=>[pad+i*((W-pad-10)/(items.length-1)), (H-pad)-((Number(it[valueKey])||0)/max)*(H-pad-16)]);
  c.strokeStyle="#9cc5b5"; c.lineWidth=2; c.beginPath(); pts.forEach(([x,y],i)=>i?c.lineTo(x,y):c.moveTo(x,y)); c.stroke();
  c.fillStyle="#9cc5b5"; pts.forEach(([x,y])=>{c.beginPath();c.arc(x,y,3,0,Math.PI*2);c.fill();});
  c.fillStyle="#9aa3af"; c.font="9px Inter,system-ui"; c.textAlign="center";
  items.forEach((it,i)=>{ if(i%Math.ceil(items.length/7)===0) c.fillText(String(it[labelKey]).slice(5),pts[i][0],H-10); });
}
/* ---------- auth ---------- */
function auth(needsSetup=false){ S.user=null; document.querySelectorAll("dialog[open]").forEach(d=>d.close());
  $("#root").innerHTML = `<main class="auth-layout"><aside class="auth-side"><div class="brand"><div class="brand-mark"><svg viewBox="0 0 48 48" aria-hidden="true"><path d="M12 30h9l4-8 4 12 4-9 3 5" fill="none" stroke="#9cc5b5" stroke-width="4" stroke-linecap="round" stroke-linejoin="round"/><circle cx="12" cy="30" r="4" fill="#e8eaed"/><circle cx="36" cy="30" r="4" fill="#e8eaed"/></svg></div><div>DataOps AI<small>PLATAFORMA DATAOPS</small></div></div><div><p class="eyebrow" style="color:#83bfcc">PLATAFORMA DE DATOS + IA</p><h2>Del archivo al dato confiable.</h2><p>Carga, valida, procesa, monitorea y pregunta a tus datos con inteligencia artificial.</p><div class="auth-flow"><div><span>01</span> Validar calidad y reglas</div><div><span>02</span> Detectar anomalías con IA</div><div><span>03</span> Monitorear, alertar y reportar</div></div></div><div class="auth-foot">100% local · Tus datos no salen de tu equipo · v2.0</div></aside><section class="auth-main"><div class="auth-form"><p class="eyebrow">${needsSetup?"CONFIGURACIÓN INICIAL":"BIENVENIDO A TU ESPACIO"}</p><h1>${needsSetup?"Crea tu cuenta inicial":"Iniciar sesión"}</h1><p>${needsSetup?"Esta cuenta será administradora y podrá crear al equipo.":"Accede para operar tus datos."}</p><form id="auth-form" class="form-grid">${needsSetup?'<label class="field">Nombre<input name="name" autocomplete="name" required maxlength="80" placeholder="Tu nombre"></label>':""}<label class="field">Usuario<input name="username" autocomplete="username" required minlength="3" maxlength="32" placeholder="usuario" autocapitalize="none" spellcheck="false"></label><label class="field">Contraseña<input type="password" name="password" autocomplete="${needsSetup?"new-password":"current-password"}" required ${needsSetup?'minlength="10"':""} maxlength="128" placeholder="${needsSetup?"Al menos 10 caracteres":"Tu contraseña"}"></label><p id="auth-error" class="form-error" role="alert"></p><button class="primary" type="submit">${needsSetup?"Crear cuenta e ingresar":"Ingresar"}</button></form><p class="auth-caption">Roles: Administrador · Data Engineer · Usuario. La primera cuenta es administradora.</p></div></section></main>`;
  $("#auth-form").addEventListener("submit", async (ev)=>{ ev.preventDefault(); const b=ev.target.querySelector("button"); b.disabled=true; $("#auth-error").textContent="";
    const vals=Object.fromEntries(new FormData(ev.target));
    try { if(needsSetup) await api("/setup", vals); await api("/login", vals); await boot(); }
    catch(err){ $("#auth-error").textContent=err.message; b.disabled=false; } });
}
/* ---------- shell ---------- */
const NAV = [["dashboard","grid","Dashboard"],["proyectos","folder","Proyectos"],["datasets","data","Datasets"],["pipelines","run","Pipelines"],["calidad","check","Calidad de Datos"],["anomalias","alert","Anomalías"],["ia","ai","IA / Asistente"],["monitoreo","chart","Monitoreo"],["alertas","bell","Alertas"],["reportes","report","Reportes"],["historial","hist","Historial"],["config","gear","Configuración"]];
function shell(){
  const nav = NAV.map(([p,i,t])=>`<button class="nav-button" data-page="${p}">${icon(i)}${t}${p==="alertas"&&S.unread?`<span class="bell-count">${S.unread}</span>`:""}</button>`).join("");
  const admin = isAdmin()?`<button class="nav-button" data-page="usuarios">${icon("users")}Usuarios</button>`:"";
  $("#root").innerHTML = `<div class="layout"><aside class="sidebar" id="sidebar"><div class="brand"><div class="brand-mark"><svg viewBox="0 0 48 48" aria-hidden="true"><path d="M12 30h9l4-8 4 12 4-9 3 5" fill="none" stroke="#9cc5b5" stroke-width="4" stroke-linecap="round" stroke-linejoin="round"/><circle cx="12" cy="30" r="4" fill="#e8eaed"/><circle cx="36" cy="30" r="4" fill="#e8eaed"/></svg></div><div>DataOps AI<small>PLATAFORMA LOCAL</small></div></div><div class="nav-label">Operación</div><nav aria-label="Navegación principal">${nav}${admin}</nav><div class="sidebar-bottom"><div class="person"><div class="avatar">${e((S.user.name||"?").slice(0,1).toUpperCase())}</div><div><div class="person-name">${e(S.user.name)}</div><div class="person-role">${roles[S.user.role]||S.user.role}</div></div></div><button class="subtle logout" data-action="logout">${icon("logout")}Cerrar sesión</button></div></aside><div class="workspace"><header class="topbar"><div class="breadcrumb"><button class="subtle small hamburger" data-action="menu" aria-label="Menú">${icon("menu")}</button><span>DataOps AI</span><span>/</span><b id="crumb">Dashboard</b></div><div class="top-meta"><button class="subtle small bell" data-page="alertas" title="Alertas">${icon("bell")}${S.unread?`<span class="bell-count">${S.unread}</span>`:""}</button><span class="date-meta">${e(new Date().toLocaleDateString("es-MX",{day:"numeric",month:"long",year:"numeric"}))}</span><span class="version">v2.0 local</span><button class="subtle small" data-action="logout" aria-label="Cerrar sesión">${icon("logout")}</button></div></header><div id="network" class="network" role="alert" hidden>No se pudo actualizar. Se reintentará automáticamente.</div><main id="view" tabindex="-1"></main></div></div>`;
  renderView();
}
async function refresh(light=false){
  const q = qs({search:S.dsSearch, project_id:S.dsProject, limit:100});
  const [projects, datasets, runs, summary, pipelines, metrics, ready, alerts] = await Promise.all([
    api("/projects?"+qs({search:S.projSearch, limit:50})).catch(()=>({items:[]})),
    api("/datasets?"+q).catch(()=>[]),
    api(`/runs?status=${S.runFilter}&offset=${S.runOffset}`).catch(()=>({items:[],total:0})),
    api("/summary").catch(()=>null), api("/pipelines?"+qs({project_id:S.pipeProject})).catch(()=>[]),
    api("/metrics/summary").catch(()=>null), api("/ready").catch(()=>null),
    api("/alerts?limit=1").catch(()=>({unread:0})),
  ]);
  Object.assign(S,{projects:projects.items||projects, datasets, runs:runs.items, runTotal:runs.total, summary, pipelines, metrics, ready, unread:alerts.unread||0});
  if(!light){
    const [dash] = await Promise.all([api("/dashboard").catch(()=>null)]);
    S.dash = dash;
  }
}
function pageHead(title, desc, action=""){ return `<div class="page-head"><div><p class="eyebrow">DATAOPS AI · LOCAL</p><h1>${title}</h1><p class="muted">${desc}</p></div>${action?`<div class="actions">${action}</div>`:""}</div>`; }
function empty(title, desc, button=""){ return `<div class="empty"><div class="empty-icon">${icon("data")}</div><h3>${title}</h3><p>${desc}</p>${button}</div>`; }
function skel(){ return `<div class="skeleton"></div>`; }
function projOptions(sel=""){ return `<option value="">Proyecto general</option>` + (S.projects||[]).map(p=>`<option value="${p.id}" ${sel===p.id?"selected":""}>${e(p.name)}</option>`).join(""); }
function dsOptions(sel=""){ return `<option value="">Seleccionar dataset</option>` + (S.datasets||[]).map(d=>`<option value="${d.id}" ${sel===d.id?"selected":""}>${e(d.filename)} (${num(d.row_count)})</option>`).join(""); }
/* ================= DASHBOARD ================= */
function vDashboard(){
  const d = S.dash;
  if(!d) return pageHead("Dashboard","Cargando métricas reales…") + skel();
  const t = d.totals;
  const kpis = [["Proyectos",t.projects,"grid"],["Datasets",t.datasets,"data"],["Registros",num(t.records),"file"],["Pipelines OK",`${t.runs_ok}/${t.runs}`,"check"],["Calidad prom.",(t.quality_avg||0)+"%","chart"]];
  return pageHead("Dashboard","Operación de datos en tiempo real. Todo calculado desde tu base local.",
    `${canEdit()?`<button class="primary" data-action="upload">${icon("upload")}Cargar archivo</button>`:""}<button data-page="proyectos">${icon("folder")}Ver proyectos</button>`)
  + `<section class="kpi-grid">${kpis.map(([l,v,ic])=>`<div class="card kpi"><div class="stat-label">${l}${icon(ic)}</div><div class="stat-value">${v}</div></div>`).join("")}</section>`
  + `<div class="charts-grid">
    <section class="card chart-box"><div class="card-head"><div><h2>Ejecuciones exitosas vs fallidas</h2><p class="muted">Estado real de runs</p></div></div><canvas id="ch-runs"></canvas></section>
    <section class="card chart-box"><div class="card-head"><div><h2>Calidad promedio por proyecto</h2><p class="muted">Score 0–100%</p></div></div><canvas id="ch-quality"></canvas></section>
    <section class="card chart-box"><div class="card-head"><div><h2>Anomalías pendientes por proyecto</h2><p class="muted">Requieren revisión</p></div></div><canvas id="ch-anom"></canvas></section>
    <section class="card chart-box"><div class="card-head"><div><h2>Ejecuciones por día</h2><p class="muted">Últimos 14 días</p></div></div><canvas id="ch-perday"></canvas></section></div>`
  + `<div class="split"><section class="card table-card"><div class="card-head"><div><h2>Últimos archivos cargados</h2><p class="muted">Carga real, no demo</p></div><button class="subtle small" data-page="datasets">Ver todos ${icon("arrow")}</button></div>`
  + (d.latest_files.length?`<div class="table-wrap"><table><thead><tr><th>Archivo</th><th>Proyecto</th><th>Registros</th><th>Calidad</th></tr></thead><tbody>${d.latest_files.map(f=>`<tr><td><div class="file-name">${e(f.filename)}</div><div class="meta">${dateFmt(f.created_at)}</div></td><td>${e(f.project||"—")}</td><td>${num(f.row_count)}</td><td>${(f.quality_score||0).toFixed(0)}%</td></tr>`).join("")}</tbody></table></div>`:empty("Sin archivos","Carga tu primer CSV o Excel para empezar.",canEdit()?`<button class="primary" data-action="upload">Cargar archivo</button>`:""))
  + `</section><section class="card"><div class="card-head"><div><h2>Alertas recientes</h2><p class="muted">Info · Advertencia · Error · Crítico</p></div><button class="subtle small" data-page="alertas">Ver todas ${icon("arrow")}</button></div>`
  + (d.recent_alerts.length?d.recent_alerts.map(a=>`<div class="rule"><div class="rule-num">${e(a.level.slice(0,2).toUpperCase())}</div><div><h3>${lvlBadge(a.level)} ${e(a.title)}</h3><p>${e(a.message)}</p><p class="meta">${dateFmt(a.created_at)}</p></div></div>`).join(""):empty("Sin alertas","El sistema avisará aquí ante fallos, calidad baja o anomalías."))
  + `</section></div>`;
}
function paintDashboard(){
  if(S.page!=="dashboard"||!S.dash) return;
  const c=S.dash.charts;
  drawDonut("ch-runs",(c.runs_by_status||[]).map(r=>({label:labels[r.status]||r.status,value:r.n})));
  drawBars("ch-quality",(c.quality_avg_project||[]).map(r=>({label:r.name,value:r.q})));
  drawBars("ch-anom",(c.anomalies_per_project||[]).map(r=>({label:r.name,value:r.n})));
  drawLine("ch-perday",(c.runs_per_day||[]).map(r=>({label:r.day,value:r.n})));
}
/* ================= PROYECTOS ================= */
function vProjects(){
  const items = S.projects||[];
  return pageHead("Proyectos","Organiza datasets, pipelines, calidad e IA por iniciativa.",
    canEdit()?`<button class="primary" data-action="new-project">${icon("folder")}Crear proyecto</button>`:"")
  + `<section class="card table-card"><div class="card-head"><div><h2>${items.length} proyectos</h2></div><label class="field"><span class="sr-only">Buscar</span><input id="proj-search" placeholder="Buscar proyectos…" value="${e(S.projSearch)}"></label></div>`
  + (items.length?`<div style="padding:1.25rem"><div class="proj-cards">${items.map(p=>`<div class="card proj-card" data-open-project="${p.id}"><p class="eyebrow">${e(p.status)}</p><h2>${e(p.name)}</h2><p class="muted">${e((p.description||"").slice(0,120))||"Sin descripción"}</p><div class="meta">${num(p.datasets||0)} datasets · ${num(p.pipelines||0)} pipelines · ${e(p.owner_name||"")}</div></div>`).join("")}</div></div>`:empty("No tienes proyectos todavía.","Crea tu primer proyecto para empezar a analizar datos.",canEdit()?`<button class="primary" data-action="new-project">Crear proyecto</button>`:""))
  + `</section>`;
}
function vProjectDetail(){
  const p = S.project; if(!p) return pageHead("Proyecto","No encontrado");
  const sum = S.projectSummary;
  const tabs = [["resumen","Resumen"],["datasets","Datasets"],["pipelines","Pipelines"],["calidad","Calidad"],["anomalias","Anomalías"],["ia","IA"],["reportes","Reportes"],["historial","Historial"],["config","Configuración"]];
  let body = `<div class="tabs">${tabs.map(([k,t])=>`<button data-ptab="${k}" class="${S.projectTab===k?"active":""}">${t}</button>`).join("")}</div><div id="ptab-body">${skel()}</div>`;
  return pageHead(`${e(p.name)}`,`${e(p.description||"")} · ${e(p.status)} · creado ${dateFmt(p.created_at)}`,
    `<button data-page="proyectos">${icon("arrow")}Volver</button>${canEdit()?`<button data-action="edit-project" data-id="${p.id}">Editar</button>`:""}${isAdmin()?`<button class="subtle" data-action="del-project" data-id="${p.id}">Eliminar</button>`:""}`)
  + `<section class="card"><div id="ptab-body-live"></div></section>` + `<div id="ptab-anchor">${body}</div>`;
}
async function paintProjectTab(){
  const host = $("#ptab-body-live") || $("#ptab-body"); if(!host||!S.project) return;
  const pid = S.project.id;
  if(S.projectTab==="resumen"){
    const s = S.projectSummary;
    if(!s){ host.innerHTML = skel(); S.projectSummary = await api(`/projects/${pid}/summary`); return paintProjectTab(); }
    host.innerHTML = `<div class="stats"><div class="card stat"><div class="stat-label">Datasets</div><div class="stat-value">${s.datasets.length}</div></div><div class="card stat"><div class="stat-label">Pipelines</div><div class="stat-value">${s.pipelines.length}</div></div><div class="card stat"><div class="stat-label">Calidad prom.</div><div class="stat-value">${s.quality_avg}%</div></div><div class="card stat"><div class="stat-label">Anomalías pendientes</div><div class="stat-value">${s.anomalies_pending}</div></div></div>
    <h3 style="margin-top:1rem">Datasets recientes</h3>${s.datasets.length?`<div class="table-wrap"><table><thead><tr><th>Archivo</th><th>Registros</th><th>Calidad</th><th></th></tr></thead><tbody>${s.datasets.slice(0,6).map(d=>`<tr><td>${e(d.filename)}</td><td>${num(d.row_count)}</td><td>${(d.quality_score||0).toFixed(0)}%</td><td><button class="small" data-preview="${d.id}">Ver</button></td></tr>`).join("")}</tbody></table></div>`:empty("Sin datasets","Carga archivos en este proyecto.")}`;
  } else if(S.projectTab==="datasets"){
    const ds = S.datasets.filter(d=>(d.project_id||"p_default")===pid);
    host.innerHTML = (canEdit()?`<button class="primary" data-action="upload" data-project="${pid}">${icon("upload")}Cargar en este proyecto</button>`:"")
    + (ds.length?`<div class="table-wrap"><table><thead><tr><th>Archivo</th><th>Registros</th><th>Calidad</th><th>Fecha</th><th></th></tr></thead><tbody>${ds.map(d=>`<tr><td><div class="file-name">${e(d.filename)}</div><div class="meta">${(d.columns||[]).join(", ").slice(0,80)}</div></td><td>${num(d.row_count)}</td><td>${(d.quality_score||0).toFixed(0)}%</td><td>${dateFmt(d.created_at)}</td><td><div class="actions"><button class="small" data-preview="${d.id}">Perfil</button>${canEdit()?`<button class="primary small" data-execute="${d.id}">${icon("run")}Ejecutar</button>`:""}</div></td></tr>`).join("")}</tbody></table></div>`:empty("Sin datasets","Arrastra un CSV o Excel para empezar."));
  } else if(S.projectTab==="pipelines"){
    const ps = S.pipelines.filter(p=>(p.project_id||"p_default")===pid||p.id==="p_ventas");
    host.innerHTML = (canEdit()?`<button class="primary" data-action="new-pipeline" data-project="${pid}">Nuevo pipeline</button>`:"")
    + (ps.length?`<div class="table-wrap"><table><thead><tr><th>Pipeline</th><th>Dataset</th><th>Ejecuciones</th><th></th></tr></thead><tbody>${ps.map(p=>`<tr><td><div class="file-name">${e(p.name)}</div><div class="meta">${e(p.id)}${p.description?" · "+e(p.description):""}</div></td><td>${e(p.filename||"—")}</td><td>${p.run_count||0}</td><td>${p.dataset_id&&canEdit()?`<button class="primary small" data-execute="${p.dataset_id}" data-pipeline="${p.id}">${icon("run")}Ejecutar</button>`:""}</td></tr>`).join("")}</tbody></table></div>`:empty("Sin pipelines","Crea una secuencia de operaciones sobre un dataset."));
  } else if(S.projectTab==="calidad"){
    host.innerHTML = `<div id="inline-quality"></div>`; await loadQuality(pid); host.innerHTML = qualityBlock();
  } else if(S.projectTab==="anomalias"){
    host.innerHTML = `<div id="inline-anom"></div>`; await loadAnomalies(pid); host.innerHTML = anomaliesBlock();
  } else if(S.projectTab==="ia"){
    host.innerHTML = iaBlock(pid);
  } else if(S.projectTab==="reportes"){
    await loadReports(pid); host.innerHTML = reportsBlock(pid);
  } else if(S.projectTab==="historial"){
    await loadActivity(pid); host.innerHTML = activityBlock();
  } else if(S.projectTab==="config"){
    host.innerHTML = `<form id="project-edit-form" class="form-grid"><input type="hidden" name="id" value="${pid}"><label class="field">Nombre<input name="name" value="${e(S.project.name)}" maxlength="120" required></label><label class="field">Descripción<input name="description" value="${e(S.project.description||"")}" maxlength="1000"></label><label class="field">Estado<select name="status"><option value="activo" ${S.project.status==="activo"?"selected":""}>Activo</option><option value="archivado" ${S.project.status==="archivado"?"selected":""}>Archivado</option></select></label><p class="form-error"></p>${canEdit()?`<button class="primary" type="submit">Guardar</button>`:""}</form>`;
  }
}
/* ================= DATASETS ================= */
function vDatasets(){
  return pageHead("Datasets","CSV y Excel (XLSX). Todo tabular compatible: ventas, inventarios, alumnos, producción, finanzas…",
    `${canEdit()?`<button class="primary" data-action="upload">${icon("upload")}Cargar archivo</button>`:""}<a class="button small" href="/api/template">${icon("download")}Plantilla</a>`)
  + `<section class="card table-card"><div class="searchbar" style="padding:0 1.25rem"><label class="field"><span class="sr-only">Buscar</span><input id="ds-search" placeholder="Buscar por nombre…" value="${e(S.dsSearch)}"></label><label class="field"><span class="sr-only">Proyecto</span><select id="ds-project"><option value="">Todos los proyectos</option>${(S.projects||[]).map(p=>`<option value="${p.id}" ${S.dsProject===p.id?"selected":""}>${e(p.name)}</option>`).join("")}</select></label></div>`
  + (S.datasets.length?`<div class="table-wrap"><table><thead><tr><th>Archivo</th><th>Proyecto</th><th>Registros</th><th>Calidad</th><th>Fecha</th><th>Acciones</th></tr></thead><tbody>${S.datasets.map(d=>`<tr><td><div class="file-name">${e(d.filename)}</div><div class="meta">${(d.columns||[]).join(", ").slice(0,90)}</div></td><td>${e(d.project||"—")}</td><td>${num(d.row_count)}</td><td>${(d.quality_score||0).toFixed(0)}%</td><td>${dateFmt(d.created_at)}</td><td><div class="actions"><button class="small" data-preview="${d.id}">Perfil</button>${canEdit()?`<button class="primary small" data-execute="${d.id}">${icon("run")}Ejecutar</button><button class="small" data-action="del-dataset" data-id="${d.id}">Eliminar</button>`:""}</div></td></tr>`).join("")}</tbody></table></div>`:empty("No hay archivos cargados","Arrastra tu archivo aquí o usa Seleccionar archivo. Soportamos cualquier tabla: alumnos, inventario, producción, ahorros…",canEdit()?`<button class="primary" data-action="upload">Seleccionar archivo</button>`:""))
  + `<div class="notice-foot">Límites locales: 10 MiB · 20,000 registros · 1–30 columnas. La vista previa pagina de 50 en 50.</div></section>`;
}
/* ================= PIPELINES ================= */
const DEFAULT_STEPS = ["validar_estructura","eliminar_duplicados","tratar_nulos","convertir_tipos","ejecutar_reglas","detectar_anomalias","guardar_resultado"];
function vPipelines(){
  return pageHead("Data Pipelines","Secuencia de operaciones aplicadas sobre un dataset: validar → limpiar → reglas → anomalías → guardar.",
    canEdit()?`<button class="primary" data-action="new-pipeline">${icon("run")}Nuevo pipeline</button>`:"")
  + `<section class="card table-card"><div class="searchbar" style="padding:0 1.25rem"><label class="field"><select id="pipe-project"><option value="">Todos los proyectos</option>${(S.projects||[]).map(p=>`<option value="${p.id}" ${S.pipeProject===p.id?"selected":""}>${e(p.name)}</option>`).join("")}</select></label></div>`
  + (S.pipelines.length?S.pipelines.map(p=>{let steps=[];try{steps=JSON.parse(p.steps_json||"[]");}catch{} if(!steps.length)steps=DEFAULT_STEPS;
    return `<div style="padding:0 1.25rem 1.25rem"><div class="card"><div class="card-head"><div><h2>${e(p.name)}</h2><p class="muted">${e(p.id)}${p.description?" · "+e(p.description):""} · ${e(p.project||"")}</p></div><div class="actions">${p.dataset_id&&canEdit()?`<button class="primary small" data-execute="${p.dataset_id}" data-pipeline="${p.id}">${icon("run")}Ejecutar</button>`:""}<button class="small" data-pipe-history="${p.id}">Historial</button>${canEdit()?`<button class="small" data-action="edit-pipeline" data-id="${p.id}">Configurar</button><button class="subtle small" data-action="del-pipeline" data-id="${p.id}">Eliminar</button>`:""}</div></div><div class="steps-flow">${steps.map((s,i)=>`${i?'<span class="step-arrow">→</span>':""}<span class="step-node">${e(s.replace(/_/g," "))}</span>`).join("")}</div><p class="meta">Dataset: ${e(p.filename||"sin asignar")} · Frecuencia: ${p.interval_minutes?p.interval_minutes+" min":"manual"} · Ejecuciones: ${p.run_count||0}${p.last_run?" · Última: "+dateFmt(p.last_run):""}</p></div></div>`;}).join(""):empty("Sin pipelines","Crea tu primer pipeline para automatizar el procesamiento.",canEdit()?`<button class="primary" data-action="new-pipeline">Crear pipeline</button>`:""))
  + `</section>`;
}
/* ================= CALIDAD ================= */
async function loadQuality(project_id){ const q=qs({project_id:project_id||"", dataset_id:S.ruleDataset||""}); S.rules = await api("/quality/rules?"+q).catch(()=>[]); }
function qualityBlock(){
  const conds = {not_empty:"no puede estar vacío",unique:"debe ser único",gte:"≥ mayor o igual a",gt:"> mayor que",lte:"≤ menor o igual a",lt:"< menor que",eq:"= igual a",neq:"≠ distinto de",valid_format:"formato válido",contains:"contiene"};
  return `<div class="searchbar"><label class="field">Dataset<select id="rule-dataset"><option value="">Todos</option>${S.datasets.map(d=>`<option value="${d.id}" ${S.ruleDataset===d.id?"selected":""}>${e(d.filename)}</option>`).join("")}</select></label>${canEdit()?`<button class="primary" data-action="new-rule">Nueva regla</button><button data-action="eval-quality">Evaluar calidad</button>`:""}</div>`
  + `<div class="split"><div><h3>Reglas personalizadas (${S.rules.length})</h3>${S.rules.length?S.rules.map(r=>`<div class="rule"><div class="rule-num">${e(r.severity.slice(0,2).toUpperCase())}</div><div style="flex:1"><h3>${e(r.column_name)} ${e(conds[r.condition]||r.condition)} ${e(r.value)}</h3><p>${r.dataset_id?"dataset "+e(r.dataset_id.slice(0,8))+" · ":""}severidad ${sevBadge(r.severity)} · ${r.active?"activa":"pausada"}</p></div>${canEdit()?`<div class="actions"><button class="small" data-action="edit-rule" data-id="${r.id}">Editar</button><button class="subtle small" data-action="del-rule" data-id="${r.id}">Eliminar</button></div>`:""}</div>`).join(""):empty("Sin reglas","Crea reglas como «edad debe ser mayor o igual a 18» o «correo no puede estar vacío».",canEdit()?`<button class="primary" data-action="new-rule">Nueva regla</button>`:"")}</div>`
  + `<div><h3>Evaluación</h3><div id="quality-eval">${S.qualityEval?qualityEvalBlock(): '<p class="muted">Pulsa «Evaluar calidad» sobre un dataset para ver completitud, unicidad, validez, consistencia y problemas.</p>'}</div></div></div>`;
}
function qualityEvalBlock(){
  const qv = S.qualityEval; if(!qv) return "";
  const q = qv.quality;
  return `<div class="meter">${[["completitud","green",q.completitud],["unicidad","gray",q.unicidad],["validez","amber",q.validez],["consistencia","red",q.consistencia]].map(([k,c,v])=>`<span class="${c}" style="width:${v/4}%" title="${k} ${v}%"></span>`).join("")}</div>
  <div class="result-list">${[["Calidad general",q.general],["Completitud",q.completitud],["Unicidad",q.unicidad],["Validez",q.validez],["Consistencia",q.consistencia]].map(([t,v])=>`<div class="result-line"><span>${t}</span><b>${v}%</b></div>`).join("")}</div>
  <h3 style="margin-top:.8rem">Problemas (${(q.issues||[]).length})</h3>${(q.issues||[]).map(i=>`<div class="rule"><div class="rule-num">!</div><div><h3>${e(i.column)}</h3><p>${e(i.problem)} ${sevBadge(i.severity||"media")}</p></div></div>`).join("")||'<p class="muted">Sin problemas relevantes.</p>'}
  ${(qv.rules||[]).length?`<h3>Reglas evaluadas</h3>`+qv.rules.map(r=>`<div class="result-line"><span>${e(r.rule.column_name)} ${e(r.rule.condition)} ${e(r.rule.value)}</span><b>${r.failed?("❌ "+r.failed+" fallos"):"✔ OK"}</b></div>`).join(""):""}`;
}
function vQuality(){ return pageHead("Calidad de Datos","Completitud, unicidad, validez y consistencia + reglas personalizables por dataset.") + `<section class="card">${qualityBlock()}</section>`; }
/* ================= ANOMALÍAS ================= */
async function loadAnomalies(project_id){ S.anomalies = await api("/anomalies?"+qs({project_id:project_id||"", severity:S.anomSev, status:S.anomStatus, search:S.anomSearch, offset:S.anomOffset, limit:50})).catch(()=>({items:[],total:0})); }
function anomaliesBlock(){
  const a = S.anomalies||{items:[],total:0};
  return `<div class="searchbar"><label class="field"><input id="anom-search" placeholder="Buscar en motivo o valor…" value="${e(S.anomSearch)}"></label><label class="field"><select id="anom-sev"><option value="">Todas las severidades</option>${["baja","media","alta","critica"].map(s=>`<option ${S.anomSev===s?"selected":""}>${s}</option>`).join("")}</select></label><label class="field"><select id="anom-status"><option value="pendiente" ${S.anomStatus==="pendiente"?"selected":""}>Pendientes</option><option value="todas" ${S.anomStatus==="todas"?"selected":""}>Todas</option><option value="resuelta" ${S.anomStatus==="resuelta"?"selected":""}>Resueltas</option></select></label></div>`
  + (a.items.length?`<div class="table-wrap"><table><thead><tr><th>Dataset</th><th>Fila</th><th>Valor</th><th>Motivo</th><th>Severidad</th><th>Estado</th><th></th></tr></thead><tbody>${a.items.map(x=>`<tr><td>${e(x.filename||x.dataset_id.slice(0,8))}</td><td>${x.row_line}</td><td>${e((x.value||"").slice(0,80))}</td><td>${e((x.reason||"").slice(0,120))}</td><td>${sevBadge(x.severity)}</td><td>${badge(x.status)}</td><td>${x.status==="pendiente"&&canEdit()?`<button class="small" data-action="resolve-anom" data-id="${x.id}">Resolver</button>`:""}</td></tr>`).join("")}</tbody></table></div><div class="pagination"><span>${a.total?S.anomOffset+1:0}–${Math.min(S.anomOffset+50,a.total)} de ${a.total}</span><button class="small" data-anom-offset="${Math.max(0,S.anomOffset-50)}" ${S.anomOffset===0?"disabled":""}>Anterior</button><button class="small" data-anom-offset="${S.anomOffset+50}" ${S.anomOffset+50>=a.total?"disabled":""}>Siguiente</button></div>`:empty("Sin anomalías pendientes","Los valores atípicos detectados por IA aparecerán aquí con su motivo y severidad."));
}
function vAnomalies(){ return pageHead("Anomalías","Valores que se alejan del comportamiento normal (estadística + Isolation Forest). Toda alerta requiere revisión humana.") + `<section class="card table-card"><div style="padding:1.25rem 1.25rem 0">${anomaliesBlock()}</div></section>`; }
/* ================= IA ================= */
const QUICK = ["Resume este dataset","¿Qué problemas de calidad tiene mi archivo?","¿Qué columnas tienen más valores vacíos?","¿Existen datos duplicados?","¿Qué anomalías encontraste?","¿Qué debería corregir primero?"];
function iaBlock(project_id){
  const pid = project_id || S.aiProject;
  const ds = S.datasets.filter(d=>!pid||(d.project_id||"p_default")===pid);
  return `<div class="searchbar"><label class="field">Proyecto<select id="ai-project"><option value="">Todos</option>${(S.projects||[]).map(p=>`<option value="${p.id}" ${pid===p.id?"selected":""}>${e(p.name)}</option>`).join("")}</select></label><label class="field">Dataset<select id="ai-dataset">${ds.length?ds.map(d=>`<option value="${d.id}" ${S.aiDataset===d.id?"selected":""}>${e(d.filename)}</option>`).join(""):'<option value="">Sin datasets</option>'}</select></label><button class="primary" data-action="ai-summary">Generar resumen</button><button data-action="ai-recs">Recomendaciones</button></div>
  <div class="quick-prompts">${QUICK.map(q=>`<button class="small" data-ask="${e(q)}">${e(q)}</button>`).join("")}</div>
  <div class="chat-wrap" style="margin-top:.7rem"><div class="chat-log" id="chat-log">${S.chat.length?S.chat.map(m=>`<div class="chat-msg ${m.role}">${m.role==="user"?e(m.text):e(m.text)}${m.src?`<div class="src">Fuente: ${e(m.src)} · datos reales, sin invenciones</div>`:""}</div>`).join(""):'<p class="muted">Pregunta sobre tus datos. Ejemplo: «¿Cuál fue la categoría con mayores ventas?» o «¿Qué columnas tienen más valores vacíos?»</p>'}</div>
  <form id="chat-form" class="searchbar"><label class="field" style="flex:3"><span class="sr-only">Pregunta</span><input id="chat-input" placeholder="Pregunta sobre tus datos…" maxlength="1000" autocomplete="off"></label><button class="primary" type="submit">Preguntar</button></form></div>
  ${S.aiHistory.length?`<h3>Historial de consultas</h3><div class="table-wrap"><table><tbody>${S.aiHistory.slice(0,8).map(h=>`<tr><td><b>Q:</b> ${e(h.question.slice(0,120))}<br><span class="muted">${e(h.answer.slice(0,200))}…</span></td></tr>`).join("")}</tbody></table></div>`:""}`;
}
function vIA(){ return pageHead("Asistente de Datos","Pregunta en lenguaje natural. El backend genera una operación segura, consulta tus datos reales y explica el resultado.") + `<section class="card">${iaBlock()}</section>`; }
/* ================= MONITOREO / ALERTAS / REPORTES / HISTORIAL / CONFIG ================= */
function vMonitoring(){
  const m = S.monitoring;
  if(!m) return pageHead("Monitoreo","Cargando…")+skel();
  return pageHead("Monitoreo","Pipelines activos, terminados, fallidos y tiempos. Se actualiza solo.",
    `<span class="tag">⌀ ${(m.avg_duration_ms/1000).toFixed(2)}s promedio</span>`)
  + `<section class="stats"><div class="card stat"><div class="stat-label">Activos</div><div class="stat-value">${m.active.length}</div></div><div class="card stat"><div class="stat-label">Terminados</div><div class="stat-value">${m.finished.length}</div></div><div class="card stat"><div class="stat-label">Fallidos</div><div class="stat-value">${m.failed.length}</div></div><div class="card stat"><div class="stat-label">Errores totales</div><div class="stat-value">${m.errors}</div></div></section>`
  + `<div class="split"><section class="card table-card"><div class="card-head"><h2>Últimas ejecuciones</h2></div>${m.last_runs.length?`<div class="table-wrap"><table><thead><tr><th>Ejecución</th><th>Estado</th><th>Duración</th><th></th></tr></thead><tbody>${m.last_runs.map(r=>`<tr><td><div class="file-name">${e(r.filename)}</div><div class="meta">EJ-${e(r.id.slice(0,8))} · ${dateFmt(r.created_at)}</div></td><td>${badge(r.status)}</td><td>${r.duration_ms?(r.duration_ms/1000).toFixed(2)+"s":"—"}</td><td><button class="small" data-run="${r.id}">Ver</button></td></tr>`).join("")}</tbody></table></div>`:empty("Sin ejecuciones","Todavía no se ha ejecutado ningún pipeline.")}</section>`
  + `<section class="card"><h2>Alertas activas</h2>${m.alerts.length?m.alerts.map(a=>`<div class="rule"><div class="rule-num">!</div><div><h3>${lvlBadge(a.level)} ${e(a.title)}</h3><p>${e(a.message)}</p></div></div>`).join(""):"<p class='muted'>Sin errores ni alertas críticas.</p>"}</section></div>`;
}
function vAlerts(){
  const a = {items:S.alerts, total:S.alertTotal};
  return pageHead("Alertas","Pipeline fallido, calidad baja, archivo inválido, anomalía crítica, faltantes y duplicados.",
    `<button data-action="read-all">Marcar leídas</button>`)
  + `<section class="card table-card"><div class="searchbar" style="padding:0 1.25rem"><label class="field"><select id="alert-level"><option value="">Todos los niveles</option>${["info","advertencia","error","critico"].map(l=>`<option ${S.alertLevel===l?"selected":""}>${l}</option>`).join("")}</select></label></div>`
  + (a.items.length?a.items.map(x=>`<div style="padding:0 1.25rem .6rem"><div class="rule"><div class="rule-num">${x.read?"✓":"!"}</div><div style="flex:1"><h3>${lvlBadge(x.level)} ${e(x.title)}</h3><p>${e(x.message)}</p><p class="meta">${dateFmt(x.created_at)}</p></div><div class="actions">${!x.read?`<button class="small" data-action="read-alert" data-id="${x.id}">Leída</button>`:""}${isAdmin()?`<button class="subtle small" data-action="del-alert" data-id="${x.id}">Eliminar</button>`:""}</div></div></div>`).join(""):empty("Sin alertas","Todo en orden. Te avisaremos aquí cuando algo requiera atención."))
  + `</section>`;
}
async function loadReports(project_id){ S.reports = await api("/reports?"+qs({project_id:project_id||""})).catch(()=>[]); }
function reportsBlock(project_id){
  return `<div class="searchbar"><label class="field">Tipo<select id="rep-type"><option value="analisis">Análisis</option><option value="calidad">Calidad</option><option value="anomalias">Anomalías</option><option value="ejecucion">Ejecución</option></select></label><label class="field">Formato<select id="rep-format"><option value="json">Vista web</option><option value="csv">CSV</option><option value="pdf">PDF</option></select></label><label class="field">Dataset<select id="rep-dataset">${S.datasets.filter(d=>!project_id||(d.project_id||"p_default")===project_id).map(d=>`<option value="${d.id}">${e(d.filename)}</option>`).join("")}</select></label><button class="primary" data-action="gen-report" data-project="${e(project_id||"")}">Generar reporte</button></div>
  <div id="report-out"></div>
  <h3>Reportes generados (${S.reports.length})</h3>${S.reports.length?`<div class="table-wrap"><table><thead><tr><th>Título</th><th>Tipo</th><th>Formato</th><th>Fecha</th><th></th></tr></thead><tbody>${S.reports.map(r=>`<tr><td>${e(r.title)}</td><td>${e(r.type)}</td><td>${e(r.format)}</td><td>${dateFmt(r.created_at)}</td><td><div class="actions"><button class="small" data-view-report="${r.id}">Ver</button><a class="button small" href="/api/reports/${r.id}/download">Descargar</a></div></td></tr>`).join("")}</tbody></table></div>`:empty("Sin reportes","Genera tu primer reporte de análisis, calidad o anomalías.")}`;
}
function vReports(){ return pageHead("Reportes","Análisis, calidad, anomalías y ejecución. Descarga en PDF o CSV.") + `<section class="card">${reportsBlock("")}</section>`; }
async function loadActivity(project_id){ const r = await api("/activity?"+qs({project_id:project_id||"", search:S.actSearch, offset:S.actOffset, limit:50})).catch(()=>({items:[],total:0})); S.activity=r.items; S.actTotal=r.total; }
function activityBlock(){
  return `<div class="searchbar"><label class="field"><input id="act-search" placeholder="Buscar: usuario, acción, detalle…" value="${e(S.actSearch)}"></label></div>`
  + (S.activity.length?`<div class="table-wrap"><table><thead><tr><th>Fecha</th><th>Usuario</th><th>Acción</th><th>Detalle</th></tr></thead><tbody>${S.activity.map(a=>`<tr><td>${dateFmt(a.created_at)}</td><td>${e(a.username||"—")}</td><td>${e(a.action)}</td><td>${e((a.detail||a.entity_id||"").slice(0,140))}</td></tr>`).join("")}</tbody></table></div><div class="pagination"><span>${S.actTotal?S.actOffset+1:0}–${Math.min(S.actOffset+50,S.actTotal)} de ${S.actTotal}</span><button class="small" data-act-offset="${Math.max(0,S.actOffset-50)}" ${S.actOffset===0?"disabled":""}>Anterior</button><button class="small" data-act-offset="${S.actOffset+50}" ${S.actOffset+50>=S.actTotal?"disabled":""}>Siguiente</button></div>`:empty("Sin actividad","Las acciones importantes quedarán registradas aquí: cargas, ejecuciones, aprobaciones y reportes."));
}
function vHistory(){ return pageHead("Historial de Actividad","Quién hizo qué, en qué proyecto y cuándo. Auditoría completa.") + `<section class="card table-card"><div style="padding:1.25rem 1.25rem 0">${activityBlock()}</div></section>`; }
function vRuns(){
  return pageHead("Historial de Ejecuciones","Cada pipeline ejecutado: usuario, fecha, duración, estado y resultado.") +
  `<section class="card table-card"><div class="card-head"><div><h2>${num(S.runTotal)} ejecuciones</h2></div><label class="field"><select id="status-filter">${[["","Todos"],["queued","En cola"],["running","En proceso"],["completed","Completadas"],["failed","Fallidas"]].map(([v,t])=>`<option value="${v}" ${S.runFilter===v?"selected":""}>${t}</option>`).join("")}</select></label></div>`
  + (S.runs.length?`<div class="table-wrap"><table><thead><tr><th>Archivo</th><th>Estado</th><th>Cargados</th><th>Incidencias</th><th></th></tr></thead><tbody>${S.runs.map(r=>`<tr><td><div class="file-name">${e(r.filename)}</div><div class="meta">EJ-${e(r.id.slice(0,8))} · ${dateFmt(r.created_at)}</div></td><td>${badge(r.status)}</td><td>${r.status==="completed"?num(r.loaded):"—"}</td><td>${r.status==="completed"?num(r.anomalies+r.invalid):"—"}</td><td><button class="small" data-run="${r.id}">Ver detalle</button></td></tr>`).join("")}</tbody></table></div><div class="pagination"><span>${S.runTotal?S.runOffset+1:0}–${Math.min(S.runOffset+50,S.runTotal)} de ${num(S.runTotal)}</span><button class="small" data-history-offset="${Math.max(0,S.runOffset-50)}" ${S.runOffset===0?"disabled":""}>Anterior</button><button class="small" data-history-offset="${S.runOffset+50}" ${S.runOffset+50>=S.runTotal?"disabled":""}>Siguiente</button></div>`:empty("Sin ejecuciones","Procesa un dataset para ver su historial aquí."))
  + `</section>`;
}
function vConfig(){
  const c = S.config;
  return pageHead("Configuración","Preferencias, IA, límites y tu cuenta.") + `<div class="split"><section class="card"><h2>Inteligencia Artificial</h2>${c?`<div class="result-list"><div class="result-line"><span>Proveedor</span><b>${e(c.ai.mode)}</b></div><div class="result-line"><span>OpenAI configurado</span><b>${c.ai.openai_configured?"Sí":"No"}</b></div><div class="result-line"><span>Azure configurado</span><b>${c.ai.azure_configured?"Sí":"No"}</b></div></div><div class="info-note">El asistente funciona 100% local sin claves. Para usar OpenAI o Azure OpenAI, define <b>AI_PROVIDER</b> y las claves en el archivo <b>.env</b> (nunca en el código). Solo se envía contexto agregado + 8 filas de muestra.</div>`:"<p class='muted'>Cargando…</p>"}
  <h2 style="margin-top:1rem">Límites locales</h2>${c?`<div class="result-list"><div class="result-line"><span>Tamaño máx.</span><b>${c.limits.max_mb} MiB</b></div><div class="result-line"><span>Filas máx.</span><b>${num(c.limits.max_rows)}</b></div><div class="result-line"><span>Columnas</span><b>1–${c.limits.max_columns}</b></div><div class="result-line"><span>Formatos</span><b>${c.formats.join(", ")}</b></div></div>`:""}</section>
  <section class="card"><h2>Mi cuenta</h2><p class="muted">${e(S.user.name)} · ${roles[S.user.role]}</p><form id="pass-form" class="form-grid"><label class="field">Contraseña actual<input type="password" name="current" required maxlength="128"></label><label class="field">Nueva contraseña<input type="password" name="new" required minlength="10" maxlength="128"></label><p class="form-error"></p><button class="primary" type="submit">Cambiar contraseña</button></form><div class="info-note">Versión 2.0 local. Documentación de API en <b>/docs</b> (Swagger).</div></section></div>`;
}
async function vUsers(){
  return pageHead("Usuarios","Administra accesos: Administrador, Data Engineer y Usuario.") + `<div class="split"><section class="card table-card"><div class="card-head"><h2>Equipo (${S.users.length})</h2></div><div class="table-wrap"><table><thead><tr><th>Nombre</th><th>Usuario</th><th>Rol</th><th></th></tr></thead><tbody>${S.users.map(u=>`<tr><td>${e(u.name)}</td><td>${e(u.username)}</td><td>${roles[u.role]||u.role}</td><td>${u.id!==S.user.id?`<button class="small" data-action="edit-user" data-id="${u.id}">Editar</button> <button class="subtle small" data-action="del-user" data-id="${u.id}">Eliminar</button>`:'<span class="meta">tú</span>'}</td></tr>`).join("")}</tbody></table></div></section><section class="card"><h2>Crear usuario</h2><form id="user-form" class="form-grid"><label class="field">Nombre<input name="name" required maxlength="80"></label><label class="field">Usuario<input name="username" required minlength="3" maxlength="32" autocapitalize="none"></label><label class="field">Contraseña inicial<input name="password" type="password" autocomplete="new-password" required minlength="10" maxlength="128"><small>Al menos 10 caracteres.</small></label><label class="field">Rol<select name="role"><option value="viewer">Usuario (consulta)</option><option value="operator">Data Engineer</option><option value="admin">Administrador</option></select></label><p class="form-error"></p><button class="primary">Crear usuario</button></form><div class="info-note">Usuario: consulta proyectos autorizados, dashboards y reportes. Data Engineer: + cargar, pipelines, reglas. Administrador: todo + usuarios.</div></section></div>`;
}
/* ---------- render ---------- */
const TITLES = {dashboard:"Dashboard",proyectos:"Proyectos",proyecto:"Proyecto",datasets:"Datasets",pipelines:"Pipelines",calidad:"Calidad",anomalias:"Anomalías",ia:"Asistente IA",monitoreo:"Monitoreo",alertas:"Alertas",reportes:"Reportes",historial:"Historial",runs:"Ejecuciones",config:"Configuración",usuarios:"Usuarios"};
async function renderView(){
  if(!S.user) return;
  $$("[data-page]").forEach(b=>{ b.classList.toggle("active", b.dataset.page===S.page); });
  const crumb = $("#crumb"); if(crumb) crumb.textContent = TITLES[S.page]||S.page;
  const v = $("#view");
  if(S.page==="dashboard"){ v.innerHTML = vDashboard(); paintDashboard(); }
  else if(S.page==="proyectos"){ v.innerHTML = vProjects(); }
  else if(S.page==="proyecto"){ v.innerHTML = vProjectDetail(); paintProjectTab(); }
  else if(S.page==="datasets"){ v.innerHTML = vDatasets(); }
  else if(S.page==="pipelines"){ v.innerHTML = vPipelines(); }
  else if(S.page==="calidad"){ await loadQuality(""); v.innerHTML = vQuality(); }
  else if(S.page==="anomalias"){ await loadAnomalies(""); v.innerHTML = vAnomalies(); }
  else if(S.page==="ia"){ if(!S.aiHistory.length) S.aiHistory = await api("/ai/history?limit=10").catch(()=>[]); v.innerHTML = vIA(); }
  else if(S.page==="monitoreo"){ S.monitoring = await api("/monitoring").catch(()=>null); v.innerHTML = vMonitoring(); }
  else if(S.page==="alertas"){ const r = await api("/alerts?"+qs({level:S.alertLevel, limit:50})).catch(()=>({items:[],total:0,unread:0})); S.alerts=r.items; S.alertTotal=r.total; S.unread=r.unread; v.innerHTML = vAlerts(); shellBell(); }
  else if(S.page==="reportes"){ await loadReports(""); v.innerHTML = vReports(); }
  else if(S.page==="historial"){ await loadActivity(""); v.innerHTML = vHistory(); }
  else if(S.page==="runs"){ v.innerHTML = vRuns(); }
  else if(S.page==="config"){ S.config = await api("/config").catch(()=>null); v.innerHTML = vConfig(); }
  else if(S.page==="usuarios"){ S.users = await api("/users").catch(()=>[]); v.innerHTML = await vUsers(); }
}
function shellBell(){ $$(".bell-count").forEach(b=>{ b.textContent=S.unread; b.style.display=S.unread?"":"none"; }); }
/* ---------- diálogos ---------- */
function openGeneric(title, sub, bodyHtml){
  const d=$("#generic-dialog");
  d.innerHTML=`<div class="dialog-head"><div><h2 id="generic-title">${title}</h2><p class="muted">${sub}</p></div><button class="subtle icon-button" data-close="generic-dialog" aria-label="Cerrar">${icon("close")}</button></div>${bodyHtml}`;
  d.showModal();
}
let confirmFn=null;
function askConfirm(title, msg, fn){
  confirmFn=fn;
  const d=$("#confirm-dialog");
  d.innerHTML=`<div class="dialog-head"><div><h2 id="confirm-title">${title}</h2><p class="muted">${msg}</p></div></div><div class="form-actions"><button data-close="confirm-dialog">Cancelar</button><button class="primary" id="confirm-yes">Confirmar</button></div>`;
  d.showModal();
  $("#confirm-yes").onclick=async()=>{ d.close(); if(confirmFn) await confirmFn(); };
}
function openUpload(preset){
  const d=$("#upload-dialog");
  d.innerHTML=`<div class="dialog-head"><div><h2 id="upload-title">Cargar archivo</h2><p class="muted">Arrastra tu archivo aquí o usa Seleccionar archivo. Cualquier tabla: ventas, alumnos, inventario…</p></div><button class="subtle icon-button" data-close="upload-dialog" aria-label="Cerrar">${icon("close")}</button></div><form id="upload-form"><label class="field">Proyecto<select name="project_id">${projOptions(preset||S.dsProject||"")}</select></label><label class="upload-zone" id="drop-zone">${icon("upload")}<strong>Arrastra tu archivo aquí o haz clic para seleccionar</strong><small>CSV · Excel XLSX · SQL — Máximo 10 MiB · Hasta 20,000 registros</small><input id="csv-file" type="file" accept=".csv,.xlsx,.sql,text/csv,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet" required></label><div class="progress" id="up-progress" hidden><span style="width:30%"></span></div><p class="muted" style="font-size:.85rem">Validamos tipo, tamaño, extensión, vacío y corrupción antes de guardar. Columnas detectadas automáticamente.</p><a href="/api/template" class="button small">${icon("download")}Descargar plantilla</a><p id="upload-error" class="form-error" role="alert" style="margin-top:.6rem"></p><div class="form-actions"><button type="button" data-close="upload-dialog">Cancelar</button><button type="submit" class="primary">Cargar archivo</button></div></form>`;
  d.showModal();
  const zone=$("#drop-zone");
  ["dragover","dragenter"].forEach(n=>zone.addEventListener(n,(ev)=>{ev.preventDefault();zone.classList.add("drag");}));
  zone.addEventListener("dragleave",()=>zone.classList.remove("drag"));
  zone.addEventListener("drop",(ev)=>{ev.preventDefault();zone.classList.remove("drag"); if(ev.dataTransfer.files.length)$("#csv-file").files=ev.dataTransfer.files;});
}
async function openPreview(id){
  try{
    const [data, profile, quality] = await Promise.all([api("/datasets/"+id), api(`/datasets/${id}/profile`).catch(()=>null), api(`/datasets/${id}/quality`).catch(()=>null)]);
    S.profile=profile; S.dquality=quality;
    const d=$("#preview-dialog");
    const prof = profile?`<h3>Perfil del dataset — ${profile.column_count} columnas, ${num(profile.row_count)} filas, ${num(profile.nulls)} nulos, ${num(profile.duplicates)} duplicados</h3><div class="profile-grid">${profile.profiles.map(p=>`<div class="profile-card"><h4>${e(p.name)} <span class="tag">${e(p.type)}</span></h4><dl><dt>Nulos</dt><dd>${p.nulls} (${p.null_pct}%)</dd><dt>Únicos</dt><dd>${num(p.uniques)}</dd>${p.min!==undefined?`<dt>Mín</dt><dd>${e(p.min)}</dd><dt>Máx</dt><dd>${e(p.max)}</dd><dt>Prom</dt><dd>${e(p.avg)}</dd>`:""}${p.top_values?`<dt>Top</dt><dd>${e(p.top_values.slice(0,2).map(t=>t.value).join(", "))}</dd>`:""}</dl>${p.distribution?`<div class="dist">${p.distribution.map(v=>`<span style="height:${Math.max(3,v/Math.max(...p.distribution)*24)}px"></span>`).join("")}</div>`:""}</div>`).join("")}</div>`:"";
    const qual = quality?`<h3 style="margin-top:1rem">Calidad general: ${quality.general}%</h3><div class="meter">${[["green",quality.completitud],["gray",quality.unicidad],["amber",quality.validez],["red",quality.consistencia]].map(([c,v])=>`<span class="${c}" style="width:${v/4}%"></span>`).join("")}</div><div class="result-list">${[["Completitud",quality.completitud],["Unicidad",quality.unicidad],["Validez",quality.validez],["Consistencia",quality.consistencia]].map(([t,v])=>`<div class="result-line"><span>${t}</span><b>${v}%</b></div>`).join("")}</div>${(quality.issues||[]).slice(0,5).map(i=>`<div class="rule"><div class="rule-num">!</div><div><h3>${e(i.column)}</h3><p>${e(i.problem)}</p></div></div>`).join("")}`:"";
    d.innerHTML=`<div class="dialog-head"><div><h2 id="preview-title">${e(data.filename)}</h2><p class="muted">${num(data.row_count)} registros · ${(data.columns||[]).join(", ")}</p></div><button class="subtle icon-button" data-close="preview-dialog" aria-label="Cerrar">${icon("close")}</button></div><div class="table-wrap"><table><thead><tr>${(data.columns||[]).map(c=>`<th>${e(c)}</th>`).join("")}</tr></thead><tbody>${data.preview.map(r=>`<tr>${(data.columns||[]).map(c=>`<td>${e(r[c])}</td>`).join("")}</tr>`).join("")}</tbody></table></div><p class="info-note">Primeros 8 registros. El perfilado y la calidad se calcularon con tus datos reales.</p>${prof}${qual}${canEdit()?`<div class="form-actions"><button class="primary" data-execute="${id}">${icon("run")}Ejecutar pipeline</button></div>`:""}`;
    if(!d.open)d.showModal();
  }catch(err){ toast(err.message,true); }
}
async function openRun(id, reset=true){
  if(reset){ S.rowOffset=0; S.rowKind="all"; }
  try{ S.detail = await api(`/runs/${id}?offset=${S.rowOffset}&kind=${S.rowKind}`); renderDetail(); const d=$("#detail-dialog"); if(!d.open)d.showModal(); }
  catch(err){ toast(err.message,true); }
}
function renderDetail(){
  const r=S.detail, done=r.status==="completed";
  const steps=["validar_estructura","analizar_columnas","buscar_duplicados","evaluar_calidad","detectar_anomalias","guardar_resultado"];
  const stageIdx = done?steps.length:(r.status==="failed"?-1:Math.min(steps.length-1, (r.logs||[]).length));
  $("#detail-dialog").innerHTML=`<div class="dialog-head"><div><p class="eyebrow">EJECUCIÓN EJ-${e(r.id.slice(0,8))} · ${e({manual:"Manual",scheduled:"Programada",retry:"Repetida"}[r.trigger_kind]||r.trigger_kind||"")}</p><h2 id="detail-title">${e(r.filename)}</h2><p class="muted">${dateFmt(r.created_at)}${r.duration_ms?" · "+(r.duration_ms/1000).toFixed(2)+"s":""}</p></div><div class="actions">${badge(r.status)}<button class="subtle icon-button" data-close="detail-dialog" aria-label="Cerrar">${icon("close")}</button></div></div>
  ${!done&&r.status!=="failed"?`<div class="steps-flow">${steps.map((s,i)=>`<span class="step-node ${i<stageIdx?"done":i===stageIdx?"active":""}">${i<stageIdx?"✔ ":""}${e(s.replace(/_/g," "))}</span>`).join("")}</div><div class="progress"><span style="width:${Math.round(stageIdx/steps.length*100)}%"></span></div>`:""}
  ${r.error?`<p class="alert-inline">${e(r.error)}</p>`:""}
  <div class="detail-stats">${[["Total","total"],["Cargados","loaded"],["Inválidos","invalid"],["Alertas IA","anomalies"]].map(([t,k])=>`<div><span>${t}</span><b>${done?num(r[k]):"—"}</b></div>`).join("")}</div>
  <h3>Registro del proceso</h3>${r.logs.length?`<ol class="log-list">${r.logs.map(l=>`<li><time>${new Date(l.created_at).toLocaleTimeString("es-MX")}</time><span>${e(l.message)}</span></li>`).join("")}</ol>`:'<p class="muted">En cola, comenzará en segundos…</p>'}
  ${done?`${r.pending>0&&canEdit()?`<div class="card" style="margin:1rem 0"><h3>Revisión de anomalías (${r.pending} pendientes)</h3><p class="muted" style="font-size:.85rem">Aprobar carga al destino. Rechazar descarta con auditoría. Motivo obligatorio.</p><div class="form-grid" style="flex-direction:row;flex-wrap:wrap;align-items:flex-end;gap:.6rem"><label class="field" style="min-width:220px">Motivo<input id="review-motivo" maxlength="500" placeholder="Ej. Pico validado"></label><button class="primary small" data-approve-all>Aprobar visibles</button><button class="small" data-reject-all>Rechazar visibles</button></div></div>`:""}${r.approved||r.rejected?`<p class="info-note">Aprobadas: ${r.approved||0} · Rechazadas: ${r.rejected||0}</p>`:""}<div class="table-tools"><label class="field"><select id="row-kind"><option value="all" ${S.rowKind==="all"?"selected":""}>Todos</option><option value="pending" ${S.rowKind==="pending"?"selected":""}>Solo pendientes</option><option value="issues" ${S.rowKind==="issues"?"selected":""}>Inválidos y alertas</option></select></label><div class="actions"><a class="button small" href="/api/runs/${r.id}/export?kind=issues">${icon("download")}Incidencias</a><a class="button small" href="/api/runs/${r.id}/export?kind=all">Todo</a>${canEdit()?`<button class="small" data-repeat="${r.id}" data-dataset="${r.dataset_id}">Repetir</button>`:""}</div></div><div class="table-wrap"><table class="detail-table"><thead><tr><th>Fila</th><th>Datos</th><th>Estado</th><th>Motivo</th></tr></thead><tbody>${r.rows.map(row=>`<tr><td>${row.line}</td><td>${(r.columns||Object.keys(row.data)).map(c=>`<div><b>${e(c)}:</b> ${e(row.data[c])}</div>`).join("")}</td><td>${badge(row.status)}${row.score!=null?`<div class="meta">score ${Number(row.score).toFixed(3)}</div>`:""}</td><td>${e(row.reason||"—")}${row.status==="anomaly"&&canEdit()?`<div class="actions" style="margin-top:.3rem"><button class="primary small" data-approve="${row.line}">Aprobar</button><button class="small" data-reject="${row.line}">Rechazar</button></div>`:""}</td></tr>`).join("")}</tbody></table></div><div class="pagination"><span>${r.row_total?S.rowOffset+1:0}–${Math.min(S.rowOffset+100,r.row_total)} de ${r.row_total}</span><button class="small" data-row-offset="${Math.max(0,S.rowOffset-100)}" ${S.rowOffset===0?"disabled":""}>Anterior</button><button class="small" data-row-offset="${S.rowOffset+100}" ${S.rowOffset+100>=r.row_total?"disabled":""}>Siguiente</button></div>`:""}`;
}
async function reviewAnomaly(lines, action){
  if(!lines.length){ toast("No hay anomalías en esta vista. Filtra por pendientes."); return; }
  const motivo=(document.querySelector("#review-motivo")||{}).value||"";
  if(motivo.trim().length<3){ toast("Escribe un motivo de al menos 3 caracteres.",true); return; }
  try{ const ep=action==="approved"?"approve":"reject"; const r=await api(`/runs/${S.detail.id}/`+ep,{lines,motivo});
    await openRun(S.detail.id,false); await refresh(true); renderView(); toast(`Revisión lista: ${r.reviewed} ${action==="approved"?"aprobadas":"rechazadas"}.`); }
  catch(err){ toast(err.message,true); }
}
async function execute(datasetId, parent, pipelineId){
  if(S.busy) return; S.busy=true;
  try{ const r=await api("/runs",{dataset_id:datasetId, parent_id:parent||null, pipeline_id:pipelineId||null});
    try{$("#preview-dialog").close();}catch{} try{$("#generic-dialog").close();}catch{}
    await refresh(true); renderView(); await openRun(r.id); toast("Pipeline en ejecución. Verás el progreso en vivo."); }
  catch(err){ toast(err.message,true); } finally{ S.busy=false; }
}
/* ---------- IA acciones ---------- */
async function aiAsk(text){
  const q = (text||$("#chat-input")?.value||"").trim();
  if(!q) return;
  const dsId = $("#ai-dataset")?.value || S.aiDataset;
  const prId = $("#ai-project")?.value || S.aiProject || null;
  if(!dsId){ toast("Selecciona primero un dataset.",true); return; }
  S.chat.push({role:"user", text:q}); paintChat(); $("#chat-input").value="";
  try{
    const r = await api("/ai/ask",{dataset_id:dsId, project_id:prId, question:q});
    S.chat.push({role:"ai", text:r.answer, src:r.source});
    S.aiDataset=dsId; if(prId!==undefined) S.aiProject=prId||"";
  }catch(err){ S.chat.push({role:"ai", text:"No pudimos procesar tu pregunta. "+err.message, src:"error"}); }
  paintChat();
}
function paintChat(){ const log=$("#chat-log"); if(!log) return;
  log.innerHTML = S.chat.map(m=>`<div class="chat-msg ${m.role}">${e(m.text)}${m.src?`<div class="src">Fuente: ${e(m.src)} · datos reales</div>`:""}</div>`).join("");
  log.scrollTop=log.scrollHeight;
}
/* ---------- eventos ---------- */
document.addEventListener("click", async (ev)=>{
  const b=ev.target.closest("button,a"); if(!b) return;
  try{
    if(b.dataset.close){ $("#"+b.dataset.close).close(); return; }
    if(b.dataset.page){ S.page=b.dataset.page; S.runOffset=0; S.runFilter=""; $("#sidebar")?.classList.add("collapsed"); await refresh(S.page!=="dashboard"); renderView(); return; }
    if(b.dataset.ptab){ S.projectTab=b.dataset.ptab; $$("[data-ptab]").forEach(x=>x.classList.toggle("active",x.dataset.ptab===S.projectTab)); paintProjectTab(); return; }
    if(b.dataset.run){ await openRun(b.dataset.run); return; }
    if(b.dataset.preview){ await openPreview(b.dataset.preview); return; }
    if(b.dataset.execute){ await execute(b.dataset.execute,null,b.dataset.pipeline||null); return; }
    if(b.dataset.repeat){ await execute(b.dataset.dataset,b.dataset.repeat,null); return; }
    if(b.dataset.pipeHistory){ const h=await api(`/pipelines/${b.dataset.pipeHistory}/history`); openGeneric("Historial del pipeline",`${h.total} ejecuciones`,h.items.length?`<div class="table-wrap"><table><thead><tr><th>Ejecución</th><th>Estado</th><th>Cargados</th><th></th></tr></thead><tbody>${h.items.slice(0,10).map(r=>`<tr><td>EJ-${e(r.id.slice(0,8))} · ${dateFmt(r.created_at)}</td><td>${badge(r.status)}</td><td>${r.status==="completed"?num(r.loaded):"—"}</td><td><button class="small" data-run="${r.id}">Ver</button></td></tr>`).join("")}</tbody></table></div>`:empty("Sin ejecuciones","Aún no se ha ejecutado.")); return; }
    if(b.dataset.approve){ await reviewAnomaly([Number(b.dataset.approve)],"approved"); return; }
    if(b.dataset.reject){ await reviewAnomaly([Number(b.dataset.reject)],"rejected"); return; }
    if(b.dataset.approveAll!==undefined){ await reviewAnomaly(S.detail.rows.filter(r=>r.status==="anomaly").map(r=>r.line),"approved"); return; }
    if(b.dataset.rejectAll!==undefined){ await reviewAnomaly(S.detail.rows.filter(r=>r.status==="anomaly").map(r=>r.line),"rejected"); return; }
    if(b.dataset.rowOffset!==undefined){ S.rowOffset=Number(b.dataset.rowOffset); await openRun(S.detail.id,false); return; }
    if(b.dataset.historyOffset!==undefined){ S.runOffset=Number(b.dataset.historyOffset); await refresh(true); renderView(); return; }
    if(b.dataset.anomOffset!==undefined){ S.anomOffset=Number(b.dataset.anomOffset); if(S.page==="proyecto")paintProjectTab(); else { await loadAnomalies(""); renderView(); } return; }
    if(b.dataset.actOffset!==undefined){ S.actOffset=Number(b.dataset.actOffset); if(S.page==="proyecto")paintProjectTab(); else { await loadActivity(""); renderView(); } return; }
    if(b.dataset.openProject){ const p=await api("/projects/"+b.dataset.openProject); S.project=p; S.projectTab="resumen"; S.projectSummary=null; S.page="proyecto"; renderView(); return; }
    if(b.dataset.ask){ aiAsk(b.dataset.ask); return; }
    if(b.dataset.viewReport){ const r=await api("/reports/"+b.dataset.viewReport); const p=r.payload||{}; openGeneric(e(r.title),"Generado "+dateFmt(r.created_at),`<div class="result-list"><div class="result-line"><span>Registros</span><b>${p.registros??"—"}</b></div><div class="result-line"><span>Calidad</span><b>${(p.calidad||{}).general??"—"}%</b></div></div><h3>Resumen</h3><p style="white-space:pre-wrap">${e(p.resumen||"—")}</p><h3>Recomendaciones</h3><p style="white-space:pre-wrap">${e(p.recomendaciones||"—")}</p><div class="form-actions"><a class="button primary" href="/api/reports/${r.id}/download">${icon("download")}Descargar</a></div>`); return; }
    const act=b.dataset.action;
    if(act==="menu"){ $("#sidebar")?.classList.toggle("collapsed"); return; }
    if(act==="logout"){ await api("/logout",{}); auth(false); return; }
    if(act==="upload"){ openUpload(b.dataset.project||null); return; }
    if(act==="demo"){ if(S.busy)return; b.disabled=true; S.busy=true; try{ const dd=await api("/demo",{}); S.busy=false; await execute(dd.id); } finally{ S.busy=false; b.disabled=false; } return; }
    if(act==="new-project"){ openGeneric("Crear proyecto","Organiza datasets, pipelines y calidad por iniciativa.",`<form id="project-form" class="form-grid"><label class="field">Nombre<input name="name" required maxlength="120" placeholder="Ej. Ventas 2026"></label><label class="field">Descripción<input name="description" maxlength="1000" placeholder="Objetivo del proyecto"></label><p class="form-error"></p><div class="form-actions"><button type="button" data-close="generic-dialog">Cancelar</button><button class="primary" type="submit">Crear proyecto</button></div></form>`); return; }
    if(act==="edit-project"){ const p=S.project; openGeneric("Editar proyecto","",`<form id="project-edit-form" class="form-grid"><input type="hidden" name="id" value="${p.id}"><label class="field">Nombre<input name="name" value="${e(p.name)}" maxlength="120" required></label><label class="field">Descripción<input name="description" value="${e(p.description||"")}" maxlength="1000"></label><label class="field">Estado<select name="status"><option value="activo" ${p.status==="activo"?"selected":""}>Activo</option><option value="archivado" ${p.status==="archivado"?"selected":""}>Archivado</option></select></label><p class="form-error"></p><div class="form-actions"><button type="button" data-close="generic-dialog">Cancelar</button><button class="primary" type="submit">Guardar</button></div></form>`); return; }
    if(act==="del-project"){ askConfirm("Eliminar proyecto",`Se eliminará «${S.project.name}». Sus datasets se moverán al proyecto general. ¿Continuar?`,async()=>{ await apiDel(`/projects/${S.project.id}`); S.page="proyectos"; await refresh(); renderView(); toast("Proyecto eliminado."); }); return; }
    if(act==="del-dataset"){ askConfirm("Eliminar dataset","Se eliminará el archivo y sus reglas asociadas. ¿Continuar?",async()=>{ await apiDel(`/datasets/${b.dataset.id}`); await refresh(true); renderView(); toast("Archivo eliminado."); }); return; }
    if(act==="new-pipeline"){ openGeneric("Nuevo pipeline","Secuencia: validar → limpiar → reglas → anomalías → guardar.",`<form id="pipeline-create-form" class="form-grid"><label class="field">Nombre<input name="name" required maxlength="80" placeholder="Ej. Limpieza ventas"></label><label class="field">Descripción<input name="description" maxlength="500" placeholder="Opcional"></label><label class="field">Proyecto<select name="project_id">${projOptions(b.dataset.project||S.project?.id||"")}</select></label><label class="field">Dataset<select name="dataset_id"><option value="">Sin asignar (se asigna al ejecutar)</option>${S.datasets.map(d=>`<option value="${d.id}">${e(d.filename)}</option>`).join("")}</select></label><p class="form-error"></p><div class="form-actions"><button type="button" data-close="generic-dialog">Cancelar</button><button class="primary" type="submit">Crear pipeline</button></div></form>`); return; }
    if(act==="edit-pipeline"){ const p=await api("/pipelines/"+b.dataset.id); let steps=[]; try{steps=JSON.parse(p.steps_json||"[]");}catch{} if(!steps.length)steps=DEFAULT_STEPS;
      openGeneric("Configurar pipeline",e(p.name),`<form id="pipeline-edit-form" class="form-grid"><input type="hidden" name="id" value="${p.id}"><label class="field">Nombre<input name="name" value="${e(p.name)}" maxlength="80"></label><label class="field">Descripción<input name="description" value="${e(p.description||"")}" maxlength="500"></label><label class="field">Proyecto<select name="project_id">${projOptions(p.project_id||"")}</select></label><label class="field">Dataset<select name="dataset_id"><option value="">Sin asignar</option>${S.datasets.map(d=>`<option value="${d.id}" ${p.dataset_id===d.id?"selected":""}>${e(d.filename)}</option>`).join("")}</select></label><label class="field">Frecuencia<select name="interval_minutes">${[[0,"Solo manual"],[15,"Cada 15 minutos"],[60,"Cada hora"],[1440,"Cada 24 horas"]].map(([v,t])=>`<option value="${v}" ${p.interval_minutes===v?"selected":""}>${t}</option>`).join("")}</select></label><label class="field">Pasos (uno por línea)<textarea name="steps" rows="7">${e(steps.join("\n"))}</textarea></label><p class="form-error"></p><div class="form-actions"><button type="button" data-close="generic-dialog">Cancelar</button><button class="primary" type="submit">Guardar</button></div></form>`); return; }
    if(act==="del-pipeline"){ askConfirm("Eliminar pipeline","¿Eliminar este pipeline? No afecta a los datasets.",async()=>{ await apiDel(`/pipelines/${b.dataset.id}`); await refresh(true); renderView(); toast("Pipeline eliminado."); }); return; }
    if(act==="new-rule"){ const dsId=S.ruleDataset||S.datasets[0]?.id||""; openGeneric("Nueva regla","Ejemplo: edad ≥ 18, correo no vacío, precio > 0, ID único.",`<form id="rule-form" class="form-grid"><label class="field">Dataset<select name="dataset_id">${S.datasets.map(d=>`<option value="${d.id}" ${dsId===d.id?"selected":""}>${e(d.filename)}</option>`).join("")}</select></label><label class="field">Columna<input name="column" required maxlength="120" placeholder="Ej. edad"></label><label class="field">Condición<select name="condition"><option value="not_empty">no puede estar vacío</option><option value="unique">debe ser único</option><option value="gte">debe ser mayor o igual a (valor)</option><option value="gt">debe ser mayor que (valor)</option><option value="lte">debe ser menor o igual a (valor)</option><option value="lt">debe ser menor que (valor)</option><option value="eq">debe ser igual a (valor)</option><option value="neq">debe ser distinto de (valor)</option><option value="valid_format">formato válido</option><option value="contains">debe contener (texto)</option></select></label><label class="field">Valor<input name="value" maxlength="200" placeholder="Ej. 18 (vacío si no aplica)"></label><label class="field">Severidad<select name="severity"><option value="baja">Baja</option><option value="media" selected>Media</option><option value="alta">Alta</option><option value="critica">Crítica</option></select></label><p class="form-error"></p><div class="form-actions"><button type="button" data-close="generic-dialog">Cancelar</button><button class="primary" type="submit">Guardar regla</button></div></form>`); return; }
    if(act==="edit-rule"){ const r=(S.rules||[]).find(x=>x.id===b.dataset.id); if(!r) return; openGeneric("Editar regla","",`<form id="rule-edit-form" class="form-grid"><input type="hidden" name="id" value="${r.id}"><label class="field">Columna<input name="column" value="${e(r.column_name)}" maxlength="120"></label><label class="field">Valor<input name="value" value="${e(r.value||"")}" maxlength="200"></label><label class="field">Severidad<select name="severity">${["baja","media","alta","critica"].map(s=>`<option ${r.severity===s?"selected":""}>${s}</option>`).join("")}</select></label><label class="field">Activa<select name="active"><option value="1" ${r.active?"selected":""}>Sí</option><option value="0" ${!r.active?"selected":""}>No</option></select></label><p class="form-error"></p><div class="form-actions"><button type="button" data-close="generic-dialog">Cancelar</button><button class="primary" type="submit">Guardar</button></div></form>`); return; }
    if(act==="del-rule"){ askConfirm("Eliminar regla","¿Eliminar esta regla de calidad?",async()=>{ await apiDel(`/quality/rules/${b.dataset.id}`); await loadQuality(S.project?.id); renderView(); toast("Regla eliminada."); }); return; }
    if(act==="eval-quality"){ const dsId=S.ruleDataset||S.datasets[0]?.id; if(!dsId){toast("Primero carga un dataset.",true);return;} b.disabled=true; try{ S.qualityEval=await api("/quality/evaluate",{dataset_id:dsId}); renderView(); if(S.page==="proyecto")paintProjectTab(); toast("Calidad evaluada con datos reales."); }catch(err){toast(err.message,true);} finally{b.disabled=false;} return; }
    if(act==="resolve-anom"){ await apiPatch(`/anomalies/${b.dataset.id}`,{status:"resuelta"}); toast("Anomalía marcada como resuelta."); if(S.page==="proyecto")paintProjectTab(); else { await loadAnomalies(""); renderView(); } return; }
    if(act==="ai-summary"){ const dsId=$("#ai-dataset")?.value||S.aiDataset||S.datasets[0]?.id; if(!dsId){toast("Selecciona un dataset.",true);return;} b.disabled=true; try{ const r=await api("/ai/summary",{dataset_id:dsId}); S.chat.push({role:"ai",text:r.summary,src:"resumen"}); paintChat(); }catch(err){toast(err.message,true);} finally{b.disabled=false;} return; }
    if(act==="ai-recs"){ const dsId=$("#ai-dataset")?.value||S.aiDataset||S.datasets[0]?.id; if(!dsId){toast("Selecciona un dataset.",true);return;} b.disabled=true; try{ const r=await api("/ai/recommendations",{dataset_id:dsId}); S.chat.push({role:"ai",text:r.recommendations,src:"recomendaciones"}); paintChat(); }catch(err){toast(err.message,true);} finally{b.disabled=false;} return; }
    if(act==="read-alert"){ await api(`/alerts/${b.dataset.id}/read`,{}); if(S.page==="alertas"){renderViewRefreshAlerts();} else {await refresh(true);renderView();} return; }
    if(act==="del-alert"){ await apiDel(`/alerts/${b.dataset.id}`); renderViewRefreshAlerts(); return; }
    if(act==="read-all"){ await api("/alerts/read-all",{}); S.unread=0; shellBell(); renderView(); toast("Alertas marcadas como leídas."); return; }
    if(act==="gen-report"){ const type=$("#rep-type")?.value||"analisis"; const fmt=$("#rep-format")?.value||"json"; const dsId=$("#rep-dataset")?.value; if(!dsId){toast("Selecciona un dataset.",true);return;} b.disabled=true; try{ const r=await api("/reports",{dataset_id:dsId, project_id:b.dataset.project||S.project?.id||null, type, format:fmt}); const out=$("#report-out"); if(out){ const p=r.payload; out.innerHTML=`<div class="info-note"><b>Reporte generado.</b> Calidad ${(p.calidad||{}).general??"—"}% · ${num(p.registros)} registros.<div class="actions" style="margin-top:.5rem"><a class="button primary small" href="/api/reports/${r.id}/download">${icon("download")}Descargar ${fmt.toUpperCase()}</a><button class="small" data-view-report="${r.id}">Ver detalle</button></div></div>`; } await loadReports(b.dataset.project||""); toast("Reporte generado."); }catch(err){toast(err.message,true);} finally{b.disabled=false;} return; }
    if(act==="edit-user"){ const u=S.users.find(x=>x.id===Number(b.dataset.id)); openGeneric("Editar usuario",e(u.username),`<form id="user-edit-form" class="form-grid"><input type="hidden" name="id" value="${u.id}"><label class="field">Nombre<input name="name" value="${e(u.name)}" maxlength="80"></label><label class="field">Rol<select name="role">${["viewer","operator","admin"].map(r=>`<option value="${r}" ${u.role===r?"selected":""}>${roles[r]}</option>`).join("")}</select></label><label class="field">Nueva contraseña (opcional)<input name="password" type="password" minlength="10" maxlength="128" placeholder="Vacío = no cambiar"></label><p class="form-error"></p><div class="form-actions"><button type="button" data-close="generic-dialog">Cancelar</button><button class="primary" type="submit">Guardar</button></div></form>`); return; }
    if(act==="del-user"){ askConfirm("Eliminar usuario","¿Eliminar este usuario? No podrás deshacerlo.",async()=>{ await apiDel(`/users/${b.dataset.id}`); S.users=await api("/users"); renderView(); toast("Usuario eliminado."); }); return; }
  }catch(err){ toast(err.message,true); }
});
async function renderViewRefreshAlerts(){ const r=await api("/alerts?"+qs({level:S.alertLevel,limit:50})).catch(()=>({items:[],total:0,unread:0})); S.alerts=r.items; S.alertTotal=r.total; S.unread=r.unread; shellBell(); renderView(); }
document.addEventListener("change", async (ev)=>{
  try{
    if(ev.target.id==="status-filter"){ S.runFilter=ev.target.value; S.runOffset=0; await refresh(true); renderView(); }
    if(ev.target.id==="row-kind"){ S.rowKind=ev.target.value; S.rowOffset=0; await openRun(S.detail.id,false); }
    if(ev.target.id==="ds-project"){ S.dsProject=ev.target.value; await refresh(true); renderView(); }
    if(ev.target.id==="pipe-project"){ S.pipeProject=ev.target.value; await refresh(true); renderView(); }
    if(ev.target.id==="rule-dataset"){ S.ruleDataset=ev.target.value; if(S.page==="proyecto")paintProjectTab(); else renderView(); }
    if(ev.target.id==="anom-sev"){ S.anomSev=ev.target.value; S.anomOffset=0; if(S.page==="proyecto")paintProjectTab(); else { await loadAnomalies(""); renderView(); } }
    if(ev.target.id==="anom-status"){ S.anomStatus=ev.target.value; S.anomOffset=0; if(S.page==="proyecto")paintProjectTab(); else { await loadAnomalies(""); renderView(); } }
    if(ev.target.id==="alert-level"){ S.alertLevel=ev.target.value; renderViewRefreshAlerts(); }
    if(ev.target.id==="ai-project"){ S.aiProject=ev.target.value; S.aiDataset=""; renderView(); }
    if(ev.target.id==="ai-dataset"){ S.aiDataset=ev.target.value; S.aiHistory=await api("/ai/history?"+qs({dataset_id:S.aiDataset,limit:10})).catch(()=>[]); }
  }catch(err){ toast(err.message,true); }
});
document.addEventListener("input", async (ev)=>{
  if(ev.target.id==="ds-search"){ clearTimeout(window.__dsT); window.__dsT=setTimeout(async()=>{ S.dsSearch=ev.target.value; await refresh(true); if(S.page==="datasets")renderView(); },400); }
  if(ev.target.id==="proj-search"){ clearTimeout(window.__pT); window.__pT=setTimeout(async()=>{ S.projSearch=ev.target.value; await refresh(true); if(S.page==="proyectos")renderView(); },400); }
  if(ev.target.id==="anom-search"){ clearTimeout(window.__aT); window.__aT=setTimeout(async()=>{ S.anomSearch=ev.target.value; S.anomOffset=0; if(S.page==="proyecto")paintProjectTab(); else { await loadAnomalies(""); renderView(); } },500); }
  if(ev.target.id==="act-search"){ clearTimeout(window.__hT); window.__hT=setTimeout(async()=>{ S.actSearch=ev.target.value; S.actOffset=0; if(S.page==="proyecto")paintProjectTab(); else { await loadActivity(""); renderView(); } },500); }
});
document.addEventListener("submit", async (ev)=>{
  const form=ev.target; const id=form.id;
  if(!["upload-form","schedule-form","user-form","pipeline-create-form","project-form","project-edit-form","rule-form","rule-edit-form","pipeline-edit-form","chat-form","pass-form","user-edit-form"].includes(id)) return;
  ev.preventDefault();
  const button=form.querySelector('button[type="submit"],button.primary'); if(button)button.disabled=true;
  const error=form.querySelector(".form-error"); if(error)error.textContent="";
  try{
    if(id==="upload-form"){
      const file=$("#csv-file").files[0]; if(!file) throw new Error("Selecciona un archivo CSV, Excel o SQL.");
      if(file.size>10*1024*1024) throw new Error("El archivo supera el límite de 10 MiB.");
      const proj=form.project_id?.value||null;
      $("#up-progress").hidden=false;
      const fd=new FormData(); fd.append("project_id",proj||"");
      if(/\.xlsx$/i.test(file.name)){ const buf=await file.arrayBuffer(); let bin=""; const bytes=new Uint8Array(buf); for(let i=0;i<bytes.length;i++)bin+=String.fromCharCode(bytes[i]);
        const dd=await api("/datasets",{filename:file.name, content_b64:btoa(bin), project_id:proj}); $("#upload-dialog").close(); S.page="datasets"; await refresh(true); renderView(); toast("Excel guardado con perfil y calidad calculados."); await openPreview(dd.id); return; }
      const bytes=await file.arrayBuffer(); let content;
      try{ content=new TextDecoder("utf-8",{fatal:true}).decode(bytes); }catch{ throw new Error("Guarda el archivo como CSV UTF-8 e inténtalo de nuevo."); }
      const dd=await api("/datasets",{filename:file.name, content, project_id:proj});
      $("#upload-dialog").close(); S.page="datasets"; await refresh(true); renderView(); toast("Archivo guardado. Ya puedes ejecutarlo o ver su perfil."); await openPreview(dd.id);
    }
    if(id==="schedule-form"){ const data=Object.fromEntries(new FormData(form)); data.interval_minutes=Number(data.interval_minutes); await api("/pipeline",data); await refresh(true); renderView(); toast("Programación guardada."); }
    if(id==="user-form"){ await api("/users",Object.fromEntries(new FormData(form))); S.users=await api("/users"); renderView(); toast("Usuario creado."); }
    if(id==="user-edit-form"){ const d=Object.fromEntries(new FormData(form)); const uid=d.id; delete d.id; if(!d.password)delete d.password; await apiPut("/users/"+uid,d); try{$("#generic-dialog").close();}catch{} S.users=await api("/users"); renderView(); toast("Usuario actualizado."); }
    if(id==="pipeline-create-form"){ const d=Object.fromEntries(new FormData(form)); if(!d.dataset_id)delete d.dataset_id; await api("/pipelines",d); try{$("#generic-dialog").close();}catch{} await refresh(true); renderView(); toast("Pipeline creado con sus pasos."); }
    if(id==="pipeline-edit-form"){ const d=Object.fromEntries(new FormData(form)); const pid=d.id; const steps=String(d.steps||"").split("\n").map(s=>s.trim()).filter(Boolean); await api("/pipelines/"+pid,{name:d.name,description:d.description,dataset_id:d.dataset_id||null,project_id:d.project_id,interval_minutes:Number(d.interval_minutes),steps}); try{$("#generic-dialog").close();}catch{} await refresh(true); renderView(); if(S.page==="proyecto")paintProjectTab(); toast("Pipeline actualizado."); }
    if(id==="project-form"){ const r=await api("/projects",Object.fromEntries(new FormData(form))); try{$("#generic-dialog").close();}catch{} await refresh(); const p=await api("/projects/"+r.id); S.project=p; S.projectTab="resumen"; S.projectSummary=null; S.page="proyecto"; renderView(); toast("Proyecto creado."); }
    if(id==="project-edit-form"){ const d=Object.fromEntries(new FormData(form)); await apiPut("/projects/"+d.id,{name:d.name,description:d.description,status:d.status}); try{$("#generic-dialog").close();}catch{} S.project=await api("/projects/"+d.id); S.projectSummary=null; await refresh(true); renderView(); toast("Proyecto actualizado."); }
    if(id==="rule-form"){ const d=Object.fromEntries(new FormData(form)); const r=await api("/quality/rules",d); try{$("#generic-dialog").close();}catch{} await loadQuality(S.project?.id); S.ruleDataset=d.dataset_id; renderView(); if(S.page==="proyecto")paintProjectTab(); toast("Regla guardada. Se evaluará en cada ejecución."); }
    if(id==="rule-edit-form"){ const d=Object.fromEntries(new FormData(form)); await apiPut("/quality/rules/"+d.id,{column:d.column,value:d.value,severity:d.severity,active:Number(d.active)}); try{$("#generic-dialog").close();}catch{} await loadQuality(S.project?.id); renderView(); if(S.page==="proyecto")paintProjectTab(); toast("Regla actualizada."); }
    if(id==="chat-form"){ aiAsk(); return; }
    if(id==="pass-form"){ const d=Object.fromEntries(new FormData(form)); await api("/me/password",{current:d.current,new:d.new}); toast("Contraseña actualizada."); form.reset(); }
  }catch(err){ if(error)error.textContent=err.message; else toast(err.message,true); }
  finally{ if(button)button.disabled=false; }
});
async function boot(){
  try{
    const initial=await api("/setup");
    if(initial.needs_setup){ auth(true); return; }
    S.user=await api("/me");
    S.page="dashboard"; S.runFilter=""; S.runOffset=0;
    await refresh(false);
    if(!S.aiDataset&&S.datasets.length)S.aiDataset=S.datasets[0].id;
    shell();
  }catch(err){ if(err.status===401){ auth(false); }
    else{ $("#root").innerHTML=`<main class="boot"><h1>No se pudo conectar</h1><p class="muted">${e(err.message)}</p><button id="retry-boot">Volver a intentar</button></main>`; $("#retry-boot").onclick=boot; } }
}
let polling=false;
setInterval(async ()=>{
  if(!S.user||document.hidden||polling) return; polling=true;
  try{
    await refresh(true);
    if($("#network"))$("#network").hidden=true;
    if(["dashboard","monitoreo"].includes(S.page)&&!document.querySelector("select:focus")&&!document.querySelector("input:focus")) renderView();
    else if(["datasets","pipelines","proyectos"].includes(S.page)&&!document.querySelector("input:focus")) renderView();
    if(S.page==="alertas"){ /* no auto para no perder lectura */ }
    if($("#detail-dialog").open&&S.detail&&["queued","running"].includes(S.detail.status)) await openRun(S.detail.id,false);
    shellBell();
  }catch(err){ if(err.status===401)auth(false); else if($("#network"))$("#network").hidden=false; }
  finally{ polling=false; }
},4000);
boot();
