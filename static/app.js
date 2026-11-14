"use strict";

const $ = id => document.getElementById(id);
const ui = {
  app: document.querySelector(".app"),
  main: $("main"),
  sidebar: $("sidebar"),
  scrim: $("scrim"),
  closeSidebar: $("closeSidebar"),
  newChat: $("newChat"),
  dropZone: $("dropZone"),
  fileList: $("fileList"),
  touchedWrap: $("touchedWrap"),
  touchedFiles: $("touchedFiles"),
  touchedNote: $("touchedNote"),
  openGuide: $("openGuide"),
  openGuideTop: $("openGuideTop"),
  guideDialog: $("guideDialog"),
  closeGuide: $("closeGuide"),
  projectName: $("projectName"),
  thread: $("thread"),
  welcome: $("welcome"),
  uploadHint: $("uploadHint"),
  history: $("history"),
  turn: $("turn"),
  turnQuestion: $("turnQuestion"),
  searchLabel: $("searchLabel"),
  process: $("process"),
  processText: $("processText"),
  hybridNote: $("hybridNote"),
  sourcesButton: $("sourcesButton"),
  sourcesButtonLabel: $("sourcesButtonLabel"),
  showContext: $("showContext"),
  evidence: $("evidence"),
  evidenceBody: $("evidenceBody"),
  evidenceTitle: $("evidenceTitle"),
  evidenceSub: $("evidenceSub"),
  evidenceLive: $("evidenceLive"),
  evidenceArchive: $("evidenceArchive"),
  closeEvidence: $("closeEvidence"),
  contextSection: $("contextSection"),
  contextHeading: $("contextHeading"),
  composerHelp: $("composerHelp"),
  consentNote: $("consentNote"),
  revokeConsent: $("revokeConsent"),
  apiState: $("apiState"),
  menuButton: $("menuButton"),
  useExample: $("useExample"),
  useUpload: $("useUpload"),
  uploadPanel: $("uploadPanel"),
  uploadFiles: $("uploadFiles"),
  uploadSummary: $("uploadSummary"),
  deleteUpload: $("deleteUpload"),
  queryForm: $("queryForm"),
  questionLabel: $("questionLabel"),
  collectionHint: $("collectionHint"),
  question: $("question"),
  searchButton: $("searchButton"),
  counter: $("counter"),
  suggestionsWrap: $("suggestionsWrap"),
  suggestions: $("suggestions"),
  stages: $("stages"),
  status: $("status"),
  announcer: $("announcer"),
  results: $("results"),
  answerStage: $("answerStage"),
  answerTitle: $("answerTitle"),
  resultSummary: $("resultSummary"),
  answer: $("answer"),
  sendPanel: $("sendPanel"),
  contextTitle: $("contextTitle"),
  contextNote: $("contextNote"),
  contextQuestion: $("contextQuestion"),
  contextCount: $("contextCount"),
  contextChips: $("contextChips"),
  contextSize: $("contextSize"),
  comparison: $("comparison"),
  comparisonTitle: $("comparisonTitle"),
  comparisonSummary: $("comparisonSummary"),
  comparisonRows: $("comparisonRows"),
  backToLexical: $("backToLexical"),
  sendDetails: $("sendDetails"),
  sendPreview: $("sendPreview"),
  answerButton: $("answerButton"),
  noModelPanel: $("noModelPanel"),
  translatePanel: $("translatePanel"),
  translatePreview: $("translatePreview"),
  translateButton: $("translateButton"),
  modeRow: $("modeRow"),
  modeTag: $("modeTag"),
  hybridButton: $("hybridButton"),
  hybridPanel: $("hybridPanel"),
  hybridTitle: $("hybridTitle"),
  hybridSummary: $("hybridSummary"),
  hybridDetailsLabel: $("hybridDetailsLabel"),
  hybridQuestion: $("hybridQuestion"),
  scope: $("scope"),
  indexButton: $("indexButton"),
  cancelIndex: $("cancelIndex"),
  sourcesTitle: $("sourcesTitle"),
  resultCount: $("resultCount"),
  sources: $("sources"),
  resultFoot: $("resultFoot"),
  sourceDialog: $("sourceDialog"),
  sourceKind: $("sourceKind"),
  sourceTitle: $("sourceTitle"),
  sourceLocation: $("sourceLocation"),
  sourceCode: $("sourceCode"),
  closeSource: $("closeSource"),
  closeSourceTop: $("closeSourceTop")
};

const session = {
  id: null, mode: null, origin: null, selectedOrigin: "ejemplo",
  queryId: null, sources: [], cited: [], question: "", matchQuestion: null, pendingHybrid: null,
  previousActions: null, previousKeys: null, modelAvailable: false,
  indexAvailable: false, busy: false, suggestions: []
};
const reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)");
const scrollBehavior = () => (reduceMotion.matches ? "auto" : "smooth");

/* ---------- permiso para enviar a OpenAI ----------
   Se pide la primera vez en la sesión del navegador. Vale por separado para el ejemplo y para
   tus archivos, y se vuelve a pedir si cambiás los archivos: es otro contenido el que sale. */

const CONSENT_KEY = "codebase-explorer:envio-autorizado";

function consentGiven(origin) {
  try { return sessionStorage.getItem(CONSENT_KEY + ":" + origin) === "si"; }
  catch { return false; }
}

function setConsent(origin, value) {
  try {
    if (value) sessionStorage.setItem(CONSENT_KEY + ":" + origin, "si");
    else sessionStorage.removeItem(CONSENT_KEY + ":" + origin);
  } catch { /* Sin sessionStorage, se pregunta cada vez. */ }
  updateConsentNote();
}

function updateConsentNote() {
  if (!ui.consentNote) return;
  const given = session.modelAvailable && consentGiven(session.selectedOrigin);
  ui.consentNote.hidden = !given;
  if (session.modelAvailable) ui.apiState.textContent = given ? "Responde con OpenAI" : "Responde con OpenAI cuando lo autorizás";
}

/* ---------- utilidades ---------- */

function el(tag, className, text) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text !== undefined) node.textContent = text;
  return node;
}

function plural(n, singular, pluralForm) {
  return n + " " + (n === 1 ? singular : (pluralForm || singular + "s"));
}

async function api(path, options) {
  const settings = Object.assign({}, options || {});
  if (!(settings.body instanceof FormData)) settings.headers = { "Content-Type": "application/json" };
  const response = await fetch(path, settings);
  if (response.status === 204) return null;
  let data;
  try { data = await response.json(); }
  catch { data = {}; }
  if (!response.ok) {
    const detail = Array.isArray(data.detail) ? data.detail.map(item => item.msg).join("; ") : data.detail;
    throw new Error(detail || "La solicitud no pudo completarse.");
  }
  return data;
}

function announce(message) {
  ui.announcer.textContent = "";
  window.setTimeout(() => { ui.announcer.textContent = message; }, 30);
}

function status(message, error) {
  ui.status.textContent = message || "";
  ui.status.classList.toggle("error", Boolean(error));
  ui.status.setAttribute("role", error ? "alert" : "status");
  ui.status.hidden = !message;
  if (message && error) {
    ui.status.focus({ preventScroll: true });
  }
}

/* Desplaza solo el contenedor indicado (el hilo, el panel o la guía), nunca la página:
   scrollIntoView también movería los contenedores de afuera. */
function scrollInside(container, node, block) {
  const view = container.getBoundingClientRect();
  const box = node.getBoundingClientRect();
  if (block === "nearest" && box.top >= view.top && box.bottom <= view.bottom) return;
  let top = container.scrollTop + (box.top - view.top) - 12;
  if (block === "nearest" && box.bottom > view.bottom && box.height < view.height)
    top = container.scrollTop + (box.bottom - view.bottom) + 12;
  container.scrollTo({ top: Math.max(0, top), behavior: scrollBehavior() });
}

function revealIfNeeded(node) {
  const box = node.getBoundingClientRect();
  const view = ui.thread.getBoundingClientRect();
  if (box.top < view.top || box.top > view.top + view.height * 0.7) scrollInside(ui.thread, node, "start");
}

function replay(node, className) {
  node.classList.remove(className);
  void node.offsetWidth;
  node.classList.add(className);
}

/* ---------- etapas ---------- */

function setStage(name, state, text) {
  const stage = ui.stages.querySelector('[data-stage="' + name + '"]');
  const label = stage.querySelector(".etapa-texto");
  stage.dataset.state = state;
  label.textContent = text || label.dataset.default;
  updateProcess();
}

function resetStages() {
  ["recuperar", "contexto", "responder"].forEach(name => setStage(name, "idle"));
  ui.process.open = false;
}

/* En el chat las tres etapas se resumen en una línea: la que está en curso, la que espera
   tu autorización o la última que terminó. Al expandirla se ven las tres. */
function updateProcess() {
  const stages = Array.from(ui.stages.querySelectorAll(".etapa"));
  let pick = stages.find(stage => stage.dataset.state === "active") || stages.find(stage => stage.dataset.state === "waiting");
  if (!pick) pick = stages.filter(stage => !["idle", "skipped"].includes(stage.dataset.state)).pop();
  if (!pick) pick = stages.filter(stage => stage.dataset.state === "skipped").pop();
  ui.process.dataset.state = pick ? pick.dataset.state : "idle";
  ui.processText.textContent = pick ? pick.querySelector(".etapa-texto").textContent : "Esperando la búsqueda";
}

/* ---------- fragmentos: líneas, coincidencias y relevancia ---------- */

const COMUNES = new Set(("a al algo alguien como con cual cuales cuando de del donde el en es esta este funcion hay la las lo los para por que quien se si su un una y " +
  "an and are by class does for from function how in into is method of the to where which with").split(" "));
const ALIAS = { entero: "int", enteros: "int", integer: "int", integers: "int", urls: "url", timed: "timestamp", timestamps: "timestamp" };

function normalize(text) {
  return text.normalize("NFD").replace(/[̀-ͯ]/g, "").toLowerCase();
}

function words(text) {
  const split = String(text || "")
    .replace(/([A-Z]+)([A-Z][a-z])/g, "$1 $2")
    .replace(/([a-z0-9])([A-Z])/g, "$1 $2")
    .replace(/_/g, " ");
  return (normalize(split).match(/[a-z0-9]+/g) || [])
    .filter(word => word.length >= 3 && !COMUNES.has(word))
    .map(word => ALIAS[word] || word);
}

function sameWord(a, b) {
  return a === b || (a.length >= 5 && b.length >= 5 && a.slice(0, 5) === b.slice(0, 5));
}

/* Replica la comparación de la búsqueda por palabras para explicar por qué apareció cada fragmento. */
function matchedTerms(question, source) {
  const original = {};
  (question.match(/[\p{L}\p{N}_]+/gu) || []).forEach(token => {
    words(token).forEach(word => { if (!original[word]) original[word] = token.toLowerCase(); });
  });
  const terms = Array.from(new Set(words(question)));
  const pool = words([source.contenedor, source.simbolo, source.descripcion, source.codigo, source.ruta].join(" "));
  return terms.filter(term => pool.some(word => sameWord(term, word))).map(term => original[term] || term);
}

function parseLines(source) {
  const raw = String(source.codigo || source.texto || "").split("\n");
  const start = Number(source.inicio) || 1;
  return raw.map((line, index) => {
    const match = line.match(/^(\d+): ?(.*)$/);
    return match ? { n: Number(match[1]), text: match[2] } : { n: start + index, text: line };
  });
}

function placeOf(source) {
  const place = source.ubicacion || {};
  if (place.tipo === "pagina") return "página " + place.pagina;
  if (source.inicio === source.fin) return "línea " + source.inicio;
  return "líneas " + source.inicio + "–" + source.fin;
}

function shortPlace(source) {
  const place = source.ubicacion || {};
  if (place.tipo === "pagina") return "p. " + place.pagina;
  return source.inicio === source.fin ? String(source.inicio) : source.inicio + "–" + source.fin;
}

function kindOf(source) {
  if (source.tipo_fuente === "documento") return "Documento";
  const kinds = { funcion: "Función", metodo: "Método", clase: "Clase", variable: "Variable" };
  return kinds[source.tipo] || "Código";
}

function sourceKey(source) {
  return source.ruta + ":" + source.inicio + "-" + source.fin;
}

function relevanceText(index, ratio) {
  if (index === 0) return "La más relevante";
  if (ratio >= 0.6) return "Casi tan relevante";
  if (ratio >= 0.3) return "Menos relevante";
  return "Mucho menos relevante";
}

function codeBlock(lines, isText, limit) {
  const block = el("div", "codigo" + (isText ? " codigo-texto" : ""));
  const shown = limit ? lines.slice(0, limit) : lines;
  shown.forEach((line, j) => {
    const row = el("div", "linea");
    row.style.setProperty("--j", j);
    row.append(el("span", "ln", String(line.n)), el("span", "lc", line.text || " "));
    block.append(row);
  });
  if (limit && lines.length > limit)
    block.append(el("div", "codigo-mas", plural(lines.length - limit, "línea más", "líneas más")));
  return block;
}

function renderSources(sources, seconds) {
  session.sources = sources;
  session.cited = [];
  ui.results.hidden = false;
  ui.sourcesTitle.firstChild.textContent = "Lo que encontró la búsqueda ";
  ui.resultCount.textContent = sources.length ? "(" + sources.length + ")" : "";
  ui.sources.replaceChildren();
  if (!sources.length) {
    ui.sources.append(el("p", "fragmentos-vacio", "Ningún fragmento del proyecto coincide con tu pregunta."));
  }
  const top = Math.max(...sources.map(s => Number(s.puntuacion) || 0), 0);
  const previous = session.previousKeys;
  sources.forEach((source, index) => {
    const card = el("article", "fragmento");
    card.id = "fragmento-" + (index + 1);
    card.dataset.n = index + 1;
    card.style.setProperty("--i", index);
    card.setAttribute("aria-label", "Fragmento " + (index + 1) + ": " + source.ruta + ", " + placeOf(source));

    const head = el("div", "fragmento-cabeza");
    const path = el("span", "fragmento-ruta", source.ruta + " ");
    path.append(el("span", "", placeOf(source)));
    const badges = el("span", "insignias");
    if (previous && !previous.has(sourceKey(source))) badges.append(el("span", "insignia insignia-nueva", "Nueva con la híbrida"));
    head.append(path, badges);

    const name = el("p", "fragmento-simbolo", "Fragmento " + (index + 1) + ". " + kindOf(source) + " " + (source.titulo || source.simbolo));
    const isText = source.tipo_fuente === "documento";
    const allLines = parseLines(source);
    const previewLines = isText ? allLines.filter(line => line.text.trim()) : allLines;
    const block = codeBlock(previewLines, isText, isText ? 3 : 6);
    const reason = el("p", "razon");
    const terms = matchedTerms(session.matchQuestion || session.question, source);
    if (terms.length) {
      reason.append("Por qué apareció: coincide con ");
      terms.slice(0, 4).forEach((term, i, list) => {
        if (i > 0) reason.append(i === list.length - 1 ? " y " : ", ");
        reason.append(el("mark", "termino", term));
      });
    } else {
      reason.append(session.mode === "completo" ? "Por qué apareció: se parece en significado a tu pregunta" : "Por qué apareció: coincide con partes del nombre o la ruta");
    }

    const ratio = top > 0 ? (Number(source.puntuacion) || 0) / top : 0;
    const meter = el("div", "relevancia");
    const track = el("div", "relevancia-pista");
    const bar = el("div", "relevancia-barra" + (ratio < 0.3 ? " baja" : ""));
    bar.style.setProperty("--i", index);
    bar.dataset.width = Math.max(4, Math.round(ratio * 100)) + "%";
    track.append(bar);
    meter.append(track, el("span", "relevancia-texto", relevanceText(index, ratio)));

    const more = el("button", "boton-texto ver-completo", "Ver el fragmento completo");
    more.type = "button";
    more.addEventListener("click", () => openSource(index + 1));

    card.append(head, name, block, reason, meter, more);
    ui.sources.append(card);
  });
  requestAnimationFrame(() => requestAnimationFrame(() => {
    ui.sources.querySelectorAll(".relevancia-barra").forEach(bar => { bar.style.width = bar.dataset.width; });
  }));
  ui.resultFoot.textContent = session.mode === "completo" ?
    "La búsqueda híbrida tardó " + formatSeconds(seconds) + ", incluido el cálculo del vector de tu pregunta en OpenAI." :
    "La búsqueda tardó " + formatSeconds(seconds) + " en este servidor.";
  updateTouched();
  updateSourcesButton();
}

/* Columna: los archivos que tocó la última búsqueda, con los citados resaltados. */
function updateTouched() {
  const sources = session.sources;
  if (!sources.length) { ui.touchedWrap.hidden = true; ui.touchedFiles.replaceChildren(); return; }
  const cited = new Set(session.cited);
  const files = new Map();
  sources.forEach((source, index) => {
    const file = files.get(source.ruta) || { count: 0, first: index + 1, cited: false };
    file.count += 1;
    if (cited.has(index + 1)) file.cited = true;
    files.set(source.ruta, file);
  });
  ui.touchedFiles.replaceChildren(...Array.from(files, ([path, file]) => {
    const item = el("li");
    const button = el("button", "tocado" + (file.cited ? " citado" : ""));
    button.type = "button";
    button.title = path;
    button.setAttribute("aria-label", path + ", " + plural(file.count, "fragmento") + (file.cited ? ", citado en la respuesta" : "") + ". Mostrar");
    button.append(el("span", "tocado-ruta", path.split("/").pop()), el("span", "tocado-veces", String(file.count)));
    button.addEventListener("click", () => { setSidebar(false); focusSource(file.first); });
    item.append(button);
    return item;
  }));
  ui.touchedNote.hidden = !session.cited.length;
  ui.touchedWrap.hidden = false;
}

function formatSeconds(seconds) {
  const value = Number(seconds || 0);
  if (value < 1) return Math.max(1, Math.round(value * 1000)).toLocaleString("es-AR") + " ms";
  return value.toLocaleString("es-AR", { maximumFractionDigits: 1 }) + " s";
}

function markCited(numbers) {
  session.cited = numbers;
  const cited = new Set(numbers);
  ui.sources.querySelectorAll(".fragmento").forEach((card, index) => {
    const isCited = cited.has(index + 1);
    card.classList.toggle("citado", isCited);
    card.classList.toggle("no-citado", !isCited);
    const badges = card.querySelector(".insignias");
    badges.querySelectorAll(".insignia-citado, .insignia-sin").forEach(node => node.remove());
    badges.prepend(isCited ? el("span", "insignia insignia-citado", "Citado") : el("span", "insignia insignia-sin", "No citado"));
    if (isCited) card.querySelectorAll(".linea").forEach(line => line.classList.add("marcada"));
  });
  updateTouched();
  updateSourcesButton();
}

function focusSource(number) {
  const card = $("fragmento-" + number);
  if (!card) return;
  openEvidence();
  scrollInside(ui.evidenceBody, card, "start");
  replay(card, "destello");
  card.querySelectorAll(".linea").forEach(line => line.classList.remove("marcada"));
  void card.offsetWidth;
  card.querySelectorAll(".linea").forEach(line => line.classList.add("marcada"));
}

/* ---------- diálogo de fragmento ---------- */

let lastFocus = null;
async function openSource(number) {
  if (!session.id || !session.queryId) return;
  try {
    const data = await api("/colecciones/" + session.id + "/consultas/" + session.queryId + "/fuentes/" + number);
    const source = data.fuente;
    const cited = session.cited.includes(number);
    ui.sourceKind.textContent = "Fragmento " + number + (cited ? ", citado en la respuesta" : "");
    ui.sourceTitle.textContent = source.titulo || source.simbolo;
    ui.sourceLocation.textContent = source.ruta + ", " + placeOf(source);
    ui.sourceCode.replaceChildren(...codeBlock(parseLines(source), source.tipo_fuente === "documento").childNodes);
    ui.sourceCode.classList.toggle("codigo-texto", source.tipo_fuente === "documento");
    lastFocus = document.activeElement;
    ui.sourceDialog.showModal();
    ui.closeSourceTop.focus();
    if (cited) requestAnimationFrame(() => ui.sourceCode.querySelectorAll(".linea").forEach(line => line.classList.add("marcada")));
  } catch (error) {
    status(error.message, true);
  }
}

function closeSource() { ui.sourceDialog.close(); }
ui.closeSource.addEventListener("click", closeSource);
ui.closeSourceTop.addEventListener("click", closeSource);
ui.sourceDialog.addEventListener("click", event => { if (event.target === ui.sourceDialog) closeSource(); });
ui.sourceDialog.addEventListener("close", () => {
  if (lastFocus && lastFocus.isConnected && !lastFocus.disabled) lastFocus.focus();
});

/* ---------- respuesta ---------- */

function renderAnswer(data) {
  ui.answer.replaceChildren();
  ui.sendPanel.hidden = true;
  ui.translatePanel.hidden = true;
  const total = session.sources.length;
  if (data.abstencion) {
    ui.answerTitle.textContent = "Respuesta";
    ui.resultSummary.textContent = "";
    ui.resultSummary.hidden = true;
    ui.answer.append(abstentionBox(
      "No hay evidencia para responder esto.",
      "Ninguno de los fragmentos que encontró la búsqueda contesta la pregunta, así que el modelo prefirió no responder en lugar de inventar."
    ));
    ui.sourcesTitle.firstChild.textContent = "Lo más cercano que encontró ";
    markCited([]);
    setStage("responder", "abstained", "No respondió, por falta de evidencia");
    announce("El modelo no respondió porque los fragmentos no alcanzan.");
  } else {
    const citas = (data.citas || []).filter(n => n >= 1 && n <= total);
    ui.answerTitle.textContent = "Respuesta";
    ui.resultSummary.hidden = true;
    const text = el("p", "respuesta-texto", data.respuesta);
    const chips = el("p", "citas");
    chips.append(el("span", "", citas.length === 1 ? "Fuente" : "Fuentes"));
    citas.forEach((number, i) => {
      const source = session.sources[number - 1];
      const chip = el("button", "cita", source.ruta.split("/").pop() + " " + shortPlace(source));
      chip.type = "button";
      chip.dataset.n = number;
      chip.style.setProperty("--i", i);
      chip.setAttribute("aria-label", "Cita " + number + ": " + source.ruta + ", " + placeOf(source) + ". Mostrar el fragmento");
      chip.addEventListener("click", () => { focusSource(number); replay(chip, "marcada"); });
      chips.append(chip);
    });
    ui.answer.append(text, chips);
    markCited(citas);
    requestAnimationFrame(() => requestAnimationFrame(() => chips.querySelectorAll(".cita").forEach(chip => chip.classList.add("marcada"))));
    setStage("responder", "done", "Usó " + citas.length + " de los " + plural(total, "fragmento"));
    ui.resultFoot.textContent += " Una cita dice de dónde salió algo, no garantiza que esté bien: revisá las líneas citadas.";
    announce("Respuesta lista. " + data.respuesta);
  }
  ui.contextHeading.textContent = "Qué recibió el modelo";
  ui.answer.hidden = false;
  ui.answerStage.focus({ preventScroll: true });
  revealIfNeeded(ui.answerStage);
  if (data.tiempos && Number(data.tiempos.modelo || 0) > 0)
    ui.resultFoot.textContent += " El modelo tardó " + formatSeconds(data.tiempos.modelo) + ".";
}

/* ---------- contexto para el modelo ---------- */

function sourceChip(source, number) {
  const chip = el("button", "ficha");
  chip.type = "button";
  chip.append(el("b", "", "[" + number + "]"), source.ruta.split("/").pop() + " " + shortPlace(source));
  chip.setAttribute("aria-label", "Fragmento " + number + ": " + source.ruta + ", " + placeOf(source) + ". Mostrarlo");
  chip.addEventListener("click", () => focusSource(number));
  return chip;
}

function showContext() {
  const total = session.sources.length;
  ui.contextQuestion.textContent = session.question;
  ui.contextCount.textContent = plural(total, "fragmento");
  ui.contextChips.replaceChildren(...session.sources.map((source, index) => sourceChip(source, index + 1)));

  /* Mismo formato que preparar_consulta y las instrucciones de validar_evidencia.py. */
  const blocks = session.sources.map((source, index) => {
    const name = [source.contenedor, source.simbolo].filter(Boolean).join(".");
    return "[" + (index + 1) + "] " + serverPlace(source) + " (" + name + ")\n" + (source.codigo || "");
  });
  const text = "Pregunta: " + session.question + "\n\nFuentes:\n" + blocks.join("\n\n");
  ui.sendPreview.textContent = text;
  $("instructionsPreview").textContent = MODEL_INSTRUCTIONS;
  ui.contextSize.textContent = "En total, " + text.length.toLocaleString("es-AR") + " caracteres: la pregunta y estos fragmentos completos, con su archivo y sus líneas. Nada más del proyecto.";
}

/* ---------- comparación entre la búsqueda por palabras y la híbrida ---------- */

function renderComparison(before, after) {
  const beforeRank = new Map(before.map((source, index) => [sourceKey(source), index + 1]));
  const afterKeys = new Set(after.map(sourceKey));
  const added = after.filter(source => !beforeRank.has(sourceKey(source))).length;
  const dropped = before.filter(source => !afterKeys.has(sourceKey(source)));
  const kept = after.length - added;
  const moved = after.some((source, index) => beforeRank.has(sourceKey(source)) && beforeRank.get(sourceKey(source)) !== index + 1);

  let summary;
  if (!before.length) summary = "La búsqueda por palabras no había encontrado nada; la híbrida trajo " + plural(after.length, "fragmento") + ".";
  else if (!added && !dropped.length) summary = "Las dos búsquedas trajeron los mismos " + plural(after.length, "fragmento") + (moved ? ", pero en otro orden." : " y en el mismo orden.");
  else {
    const parts = [];
    if (added) parts.push("trajo " + plural(added, "fragmento nuevo", "fragmentos nuevos"));
    if (kept) parts.push("mantuvo " + kept);
    if (dropped.length) parts.push("dejó afuera " + dropped.length);
    summary = "Frente a la búsqueda por palabras, la híbrida " + parts.join(", ").replace(/, ([^,]*)$/, " y $1") + ".";
  }
  ui.comparisonSummary.textContent = summary;

  const rows = [];
  after.forEach((source, index) => {
    const position = index + 1;
    const previous = beforeRank.get(sourceKey(source));
    let note = null;
    if (!previous) note = ["cambio cambio-nuevo", "nuevo"];
    else if (previous > position) note = ["cambio cambio-sube", "sube " + (previous - position)];
    else if (previous < position) note = ["cambio cambio-baja", "baja " + (position - previous)];
    rows.push({ source, previous, position, note, cls: previous ? "" : "fila-nueva" });
  });
  dropped.forEach(source => rows.push({ source, previous: beforeRank.get(sourceKey(source)), position: null, note: ["cambio cambio-afuera", "quedó afuera"], cls: "fila-afuera" }));

  ui.comparisonRows.replaceChildren(...rows.map((row, i) => {
    const tr = el("tr", row.cls);
    tr.style.setProperty("--i", i);
    const name = el("td", "", row.source.ruta + " " + shortPlace(row.source));
    const lexical = el("td");
    lexical.append(row.previous ? el("span", "posicion", String(row.previous)) : el("span", "cambio-afuera", "no estaba"));
    const hybrid = el("td");
    if (row.position) hybrid.append(el("span", "posicion", String(row.position)));
    if (row.note) hybrid.append(el("span", row.note[0], row.note[1]));
    tr.append(name, lexical, hybrid);
    return tr;
  }));
  ui.comparison.hidden = false;
}

const MODEL_INSTRUCTIONS =
  "Decidí si alguno de los fragmentos realmente contiene evidencia para responder. " +
  "Un nombre parecido no alcanza. Si hay evidencia, respondé en español de forma breve " +
  "y poné en fuentes solo los números que respaldan la respuesta; no agregues citas al texto. " +
  "Si no hay evidencia suficiente, usá hay_evidencia=false, respuesta vacía y fuentes vacías. " +
  "No inventes comportamiento que no figure en los fragmentos.";

function serverPlace(source) {
  const place = source.ubicacion || {};
  const base = place.tipo === "pagina" ? source.ruta + ":página " + place.pagina : source.ruta + ":" + source.inicio + "-" + source.fin;
  return place.columna_inicio != null ? base + ":columnas " + place.columna_inicio + "-" + place.columna_fin : base;
}

function abstentionBox(title, text) {
  const box = el("div", "abstencion");
  box.append(el("p", "abstencion-titulo", title), el("p", "", text));
  const good = session.suggestions.find(item => item.id === "codigo");
  if (good && session.selectedOrigin === "ejemplo") {
    const actions = el("div", "acciones-turno");
    const example = el("button", "accion", "Probar con una que sí tiene respuesta");
    example.type = "button";
    example.addEventListener("click", () => runSuggestion(good));
    actions.append(example);
    box.append(actions);
  }
  return box;
}

/* ---------- después de cada búsqueda ---------- */

function clearResults() {
  ui.results.hidden = true;
  ui.answer.hidden = true;
  ui.answer.replaceChildren();
  ui.sendPanel.hidden = true;
  ui.noModelPanel.hidden = true;
  ui.translatePanel.hidden = true;
  ui.modeRow.hidden = true;
  ui.hybridPanel.hidden = true;
  ui.hybridQuestion.textContent = "";
  ui.sendDetails.open = false;
  ui.comparison.hidden = true;
  ui.sources.replaceChildren();
  ui.resultFoot.textContent = "";
  ui.resultSummary.hidden = false;
  ui.resultSummary.textContent = "";
  ui.hybridNote.hidden = true;
  ui.sourcesButton.hidden = true;
  ui.contextSection.hidden = true;
  ui.contextHeading.textContent = "Qué recibe el modelo";
  showLiveEvidence();
  session.queryId = null;
  session.sources = [];
  session.cited = [];
  session.question = "";
  session.matchQuestion = null;
  session.previousActions = null;
  session.previousKeys = null;
  session.autoAnswer = false;
  ui.answerButton.hidden = false;
  ui.touchedWrap.hidden = true;
  ui.touchedFiles.replaceChildren();
  resetStages();
  status("", false);
}

/* El turno en curso pasa al historial como copia de solo lectura: se puede releer y
   tocar sus citas, pero sus acciones (enviar, comparar, traducir) quedan en el turno nuevo. */
function archiveTurn() {
  if (ui.turn.hidden) return;
  const question = ui.turnQuestion.textContent;
  const copy = ui.turn.cloneNode(true);
  copy.removeAttribute("id");
  copy.removeAttribute("aria-labelledby");
  copy.setAttribute("aria-label", "Pregunta anterior: " + question);
  copy.classList.add("turno-archivado");
  copy.querySelectorAll("[hidden], .permiso, .aviso, .acciones-turno").forEach(node => node.remove());
  copy.querySelectorAll("[id]").forEach(node => node.removeAttribute("id"));
  copy.querySelectorAll("[tabindex='-1']").forEach(node => node.removeAttribute("tabindex"));
  const proceso = copy.querySelector(".proceso");
  if (proceso) proceso.open = false;

  /* La evidencia de esa pregunta queda guardada para volver a abrirla en el panel. */
  const cards = ui.sources.querySelectorAll(".fragmento").length;
  if (cards) {
    const snapshot = ui.sources.cloneNode(true);
    snapshot.removeAttribute("id");
    snapshot.querySelectorAll(".ver-completo").forEach(node => node.remove());
    snapshot.querySelectorAll("[id]").forEach(node => node.removeAttribute("id"));
    const show = number => {
      openArchivedEvidence(snapshot, question);
      const card = number && snapshot.querySelector('.fragmento[data-n="' + number + '"]');
      if (card) scrollInside(ui.evidenceBody, card, "start");
    };
    const actions = el("div", "acciones-turno");
    const button = el("button", "accion", cards === 1 ? "Ver el fragmento que encontró" : "Ver los " + cards + " fragmentos que encontró");
    button.type = "button";
    button.addEventListener("click", () => show(null));
    actions.append(button);
    copy.querySelector(".msg-asistente").append(actions);
    copy.querySelectorAll(".cita").forEach(chip => chip.addEventListener("click", () => show(chip.dataset.n)));
  }
  ui.history.append(copy);
}

/* ---------- panel de evidencia ---------- */

function showLiveEvidence() {
  ui.evidenceLive.hidden = false;
  ui.evidenceArchive.hidden = true;
  ui.evidenceArchive.replaceChildren();
  ui.evidenceSub.textContent = "De tu última pregunta";
}

function openEvidence(target, moveFocus) {
  if (ui.evidenceLive.hidden) showLiveEvidence();
  ui.evidence.hidden = false;
  ui.app.classList.add("panel-abierto");
  ui.sourcesButton.setAttribute("aria-expanded", "true");
  if (target) scrollInside(ui.evidenceBody, target, "start");
  if (moveFocus) ui.evidenceTitle.focus({ preventScroll: true });
}

function openArchivedEvidence(snapshot, question) {
  ui.evidenceLive.hidden = true;
  ui.evidenceArchive.hidden = false;
  ui.evidenceArchive.replaceChildren(snapshot);
  ui.evidenceSub.textContent = "De la pregunta «" + question + "»";
  ui.evidence.hidden = false;
  ui.app.classList.add("panel-abierto");
  ui.evidenceBody.scrollTop = 0;
}

function closeEvidence() {
  const hadFocus = ui.evidence.contains(document.activeElement);
  ui.evidence.hidden = true;
  ui.app.classList.remove("panel-abierto");
  ui.sourcesButton.setAttribute("aria-expanded", "false");
  showLiveEvidence();
  if (hadFocus) (ui.sourcesButton.hidden ? ui.question : ui.sourcesButton).focus();
}

function updateSourcesButton() {
  const count = session.sources.length;
  const cited = session.cited.length;
  ui.sourcesButton.hidden = !count;
  ui.sourcesButtonLabel.textContent = cited ?
    (cited === 1 ? "Ver la fuente citada" : "Ver las " + cited + " fuentes citadas") :
    (count === 1 ? "Ver el fragmento encontrado" : "Ver los " + count + " fragmentos encontrados");
}

function resetThread() {
  discardPendingHybrid();
  ui.history.replaceChildren();
  ui.turn.hidden = true;
  clearResults();
  ui.welcome.hidden = false;
  ui.composerHelp.hidden = false;
  closeEvidence();
  ui.thread.scrollTop = 0;
}

function showNextSteps(options) {
  const keepPosition = Boolean(options && options.keepPosition);
  const count = session.sources.length;
  const hybrid = session.mode === "completo";
  session.previousActions = null;
  ui.results.hidden = false;
  ui.answer.hidden = true;
  ui.sendPanel.hidden = true;
  ui.noModelPanel.hidden = true;
  ui.translatePanel.hidden = true;
  ui.resultSummary.hidden = false;
  ui.modeRow.hidden = false;
  ui.modeTag.dataset.mode = hybrid ? "completo" : "acotado";
  ui.modeTag.textContent = hybrid ? "Búsqueda híbrida: palabras y significado" : "Búsqueda por palabras";
  ui.hybridButton.hidden = !session.modelAvailable || hybrid;

  if (count) {
    setStage("recuperar", "done", plural(count, "fragmento encontrado", "fragmentos encontrados") + (hybrid ? ", con palabras y significado" : ", en este servidor"));
    ui.answerTitle.textContent = "Encontró " + plural(count, "fragmento");
    showContext();
    ui.contextSection.hidden = false;
    ui.resultSummary.hidden = true;
    if (session.modelAvailable && consentGiven(session.selectedOrigin)) {
      ui.contextHeading.textContent = "Qué recibe el modelo";
      ui.contextTitle.textContent = "Para responder, se envían a OpenAI tu pregunta y " + (count === 1 ? "el fragmento encontrado." : "los " + count + " fragmentos encontrados.");
      session.autoAnswer = true;
    } else if (session.modelAvailable) {
      setStage("contexto", "waiting", "Esperando tu autorización para enviar a OpenAI");
      ui.contextHeading.textContent = "Qué recibe el modelo";
      ui.contextTitle.textContent = "Para responder, se envían a OpenAI tu pregunta y " + (count === 1 ? "el fragmento encontrado." : "los " + count + " fragmentos encontrados.");
      ui.answerButton.hidden = false;
      ui.sendPanel.hidden = false;
    } else {
      setStage("contexto", "done", "Tu pregunta y " + plural(count, "fragmento") + ", listos para el modelo");
      setStage("responder", "skipped", "Necesita una clave de OpenAI en el servidor");
      ui.contextHeading.textContent = "Qué recibiría el modelo";
      ui.noModelPanel.hidden = false;
    }
    announce(plural(count, "fragmento encontrado", "fragmentos encontrados") + ".");
  } else {
    /* Sin fragmentos el servidor se abstiene sin llamar al modelo (generar_respuesta). */
    setStage("recuperar", "done", "Ningún fragmento coincide");
    setStage("contexto", "skipped", "Sin fragmentos, no hay nada que armar");
    setStage("responder", "abstained", "No respondió, por falta de evidencia");
    ui.answerTitle.textContent = "Respuesta";
    ui.resultSummary.hidden = true;
    let text = hybrid ?
      "Ninguna parte del proyecto se parece lo suficiente a tu pregunta, y sin evidencia prefiero no inventar." :
      "Ninguna parte del proyecto comparte palabras con tu pregunta, y sin evidencia prefiero no inventar.";
    if (!hybrid && session.modelAvailable) text += " Si creés que la respuesta está, la búsqueda híbrida también busca por significado.";
    ui.answer.replaceChildren(abstentionBox("No encontré evidencia para responder esto.", text));
    ui.answer.hidden = false;
    ui.sourcesTitle.firstChild.textContent = "Lo que encontró la búsqueda ";
    if (!hybrid && session.modelAvailable && session.question.includes("¿")) {
      ui.translatePreview.textContent = session.question;
      ui.translatePanel.hidden = false;
    }
    announce("No se encontraron fragmentos. El sistema no responde sin evidencia.");
  }
  if (!keepPosition) {
    revealIfNeeded(ui.turn);
    ui.answerStage.focus({ preventScroll: true });
  }
}

/* ---------- acciones ---------- */

function setBusy(value) {
  session.busy = value;
  [ui.searchButton, ui.backToLexical, ui.uploadFiles, ui.useExample, ui.useUpload, ui.newChat, ui.answerButton, ui.translateButton, ui.hybridButton, ui.indexButton, ui.cancelIndex]
    .forEach(node => { node.disabled = value; });
  ui.question.readOnly = value;
  ui.suggestions.querySelectorAll("button").forEach(node => { node.disabled = value; });
  ui.searchLabel.textContent = value ? "Buscando…" : "Buscar";
  ui.app.setAttribute("aria-busy", String(value));
}

async function ensureCollection(mode) {
  const origin = session.selectedOrigin;
  if (session.id && session.mode === mode && session.origin === origin) return null;
  await discardPendingHybrid();
  if (session.id) {
    const wasUpload = session.origin === "carga";
    try { await api("/colecciones/" + session.id, { method: "DELETE" }); }
    catch { /* La colección también puede haber vencido. */ }
    session.id = null;
    if (wasUpload) {
      ui.deleteUpload.hidden = true;
      ui.uploadSummary.textContent = filesSummary();
    }
  }
  const created = await createCollection(mode);
  session.id = created.coleccion_id;
  session.mode = mode;
  session.origin = origin;
  session.queryId = null;
  ui.deleteUpload.hidden = origin !== "carga";
  if (origin === "carga") ui.uploadSummary.textContent = plural(ui.uploadFiles.files.length, "archivo") + " en el servidor. Se borran en menos de 24 horas.";
  return created;
}

async function createCollection(mode) {
  if (session.selectedOrigin === "carga") {
    const files = Array.from(ui.uploadFiles.files);
    if (!files.length) throw new Error("Elegí al menos un archivo antes de buscar.");
    if (files.length > 5 || files.some(file => file.size > 10_000_000))
      throw new Error("Se admiten hasta cinco archivos de 10 MB cada uno.");
    const form = new FormData();
    form.append("modo", mode);
    files.forEach(file => form.append("archivos", file));
    return api("/cargas/colecciones", { method: "POST", body: form });
  }
  return api("/ejemplo/colecciones", { method: "POST", body: JSON.stringify({ modo: mode }) });
}

async function discardPendingHybrid() {
  if (!session.pendingHybrid) return;
  const id = session.pendingHybrid.coleccion_id;
  session.pendingHybrid = null;
  try { await api("/colecciones/" + id, { method: "DELETE" }); }
  catch { /* Puede haber vencido mientras se revisaba el alcance. */ }
}

function releaseCollections() {
  const ids = [session.id, session.pendingHybrid && session.pendingHybrid.coleccion_id].filter(Boolean);
  ids.forEach(id => {
    try { fetch("/colecciones/" + id, { method: "DELETE", keepalive: true }); }
    catch { /* El servidor la libera al vencer. */ }
  });
}
window.addEventListener("pagehide", releaseCollections);

function filesSummary() {
  const count = ui.uploadFiles.files.length;
  return count ? plural(count, "archivo elegido", "archivos elegidos") + ". Se suben cuando hagas la primera pregunta." : "Todavía no elegiste archivos.";
}

async function search() {
  if (session.busy) return;
  const question = ui.question.value.trim();
  if (!question) { status("Escribí una pregunta para buscar en el proyecto.", true); ui.question.focus(); return; }
  if (session.selectedOrigin === "carga" && !ui.uploadFiles.files.length && !(session.id && session.origin === "carga")) {
    status("Elegí al menos un archivo en la columna de la izquierda antes de preguntar.", true);
    setSidebar(true);
    return;
  }
  archiveTurn();
  clearResults();
  ui.welcome.hidden = true;
  ui.composerHelp.hidden = true;
  ui.turnQuestion.textContent = question;
  ui.turn.hidden = false;
  scrollInside(ui.thread, ui.turn, "start");
  setBusy(true);
  setStage("recuperar", "active", session.selectedOrigin === "carga" ? "Preparando tus archivos y buscando…" : "Buscando en el código y los documentos…");
  try {
    await ensureCollection("acotado");
    const query = await api("/colecciones/" + session.id + "/consultas", {
      method: "POST", body: JSON.stringify({ pregunta: question })
    });
    session.question = question;
    session.queryId = query.consulta_id;
    ui.question.value = "";
    autosize();
    updateCounter();
    renderSources(query.fuentes, query.tiempos.recuperacion);
    showNextSteps();
  } catch (error) {
    resetStages();
    setStage("recuperar", "skipped", "No se pudo buscar");
    status(error.message, true);
  } finally { setBusy(false); }
  answerIfAuthorized();
}

function answerIfAuthorized() {
  if (!session.autoAnswer) return;
  session.autoAnswer = false;
  generateAnswer();
}

async function generateAnswer() {
  if (session.busy || !session.queryId || !session.sources.length) return;
  setBusy(true);
  setStage("contexto", "done", "Enviaste tu pregunta y " + plural(session.sources.length, "fragmento") + " a OpenAI");
  setStage("responder", "active", "Generando la respuesta y comprobando las citas…");
  try {
    const answer = await api("/colecciones/" + session.id + "/consultas/" + session.queryId + "/respuesta", {
      method: "POST", body: JSON.stringify({ autorizacion: session.mode === "completo" ? "INDEXAR" : "ENVIAR" })
    });
    renderAnswer(answer);
  } catch (error) {
    setStage("contexto", "waiting", "Esperando tu autorización para enviar a OpenAI");
    setStage("responder", "idle");
    ui.answerButton.hidden = false;
    ui.sendPanel.hidden = false;
    status("No se pudo generar la respuesta: " + error.message, true);
  } finally { setBusy(false); }
}

async function translateQuestion() {
  if (session.busy || !session.queryId || session.sources.length) return;
  setBusy(true);
  setStage("recuperar", "active", "Traduciendo la pregunta y buscando de nuevo…");
  try {
    const translated = await api("/colecciones/" + session.id + "/consultas/" + session.queryId + "/traduccion", {
      method: "POST", body: JSON.stringify({ autorizacion: "ENVIAR" })
    });
    session.matchQuestion = translated.consulta_ingles || null;
    renderSources(translated.fuentes, translated.tiempos.recuperacion);
    showNextSteps();
    ui.translatePanel.hidden = true;
    if (translated.consulta_ingles) {
      const note = "Buscó con la pregunta traducida: «" + translated.consulta_ingles + "».";
      if (translated.fuentes.length) { ui.resultSummary.hidden = false; ui.resultSummary.textContent = note + " " + ui.resultSummary.textContent; }
      else status(note + " Tampoco encontró fragmentos.", false);
    }
  } catch (error) {
    setStage("recuperar", "done", "Ningún fragmento coincide");
    status("No se pudo traducir la pregunta: " + error.message, true);
  } finally { setBusy(false); }
  answerIfAuthorized();
}

async function prepareHybrid() {
  if (session.busy || !session.queryId || !session.modelAvailable) return;
  setBusy(true);
  try {
    const created = await createCollection("completo");
    session.pendingHybrid = created;
    showScope(created.alcance);
    const prepared = session.selectedOrigin === "ejemplo" && session.indexAvailable;
    ui.hybridTitle.textContent = prepared ? "Comparar con la búsqueda híbrida" : "Preparar la búsqueda híbrida";
    ui.hybridDetailsLabel.textContent = prepared ? "Ver la pregunta que se envía" : "Ver la pregunta y los archivos que se envían";
    ui.hybridQuestion.textContent = "Pregunta que se envía: «" + session.question + "»";
    ui.indexButton.textContent = prepared ? "Enviar la pregunta y comparar" : "Enviar los archivos y comparar";
    ui.hybridSummary.textContent = prepared ?
      "Busca por palabras y también por significado, y te muestra qué cambió. Solo se envía tu pregunta a OpenAI para calcular su vector; los archivos del ejemplo no." :
      "Busca por palabras y también por significado, y te muestra qué cambió. Para eso se envían a OpenAI tu pregunta y el texto permitido de tus archivos, para calcular sus vectores.";
    session.previousActions = {
      send: !ui.sendPanel.hidden,
      noModel: !ui.noModelPanel.hidden,
      translate: !ui.translatePanel.hidden,
      summary: ui.resultSummary.textContent
    };
    ui.sendPanel.hidden = true;
    ui.translatePanel.hidden = true;
    ui.hybridButton.hidden = true;
    ui.hybridPanel.hidden = false;
  } catch (error) { status(error.message, true); }
  finally {
    setBusy(false);
    if (!ui.hybridPanel.hidden) {
      ui.indexButton.focus({ preventScroll: true });
      scrollInside(ui.thread, ui.hybridPanel, "nearest");
    }
  }
}

function showScope(scope) {
  ui.scope.replaceChildren();
  if (!scope) { ui.scope.hidden = true; return; }
  ui.scope.hidden = false;
  ui.scope.append(el("p", "", plural(scope.cantidad_fragmentos, "fragmento") + " de " + plural(scope.rutas.length, "archivo") + ", unos " + Number(scope.bytes_aproximados).toLocaleString("es-AR") + " bytes de texto."));
  const list = el("ul");
  scope.rutas.forEach(path => list.append(el("li", "", path)));
  ui.scope.append(list);
  const excluded = Object.keys(scope.excluidos || {});
  if (excluded.length) ui.scope.append(el("p", "", plural(excluded.length, "archivo excluido", "archivos excluidos") + " por el filtro de privacidad."));
}

async function runHybrid() {
  if (session.busy || !session.pendingHybrid) return;
  setBusy(true);
  const next = session.pendingHybrid;
  const previousSources = session.sources.slice();
  const previousKeys = new Set(previousSources.map(sourceKey));
  setStage("recuperar", "active", "Buscando por palabras y por significado…");
  setStage("contexto", "idle");
  setStage("responder", "idle");
  try {
    const query = await api("/colecciones/" + next.coleccion_id + "/consultas", {
      method: "POST", body: JSON.stringify({ pregunta: session.question, autorizacion: "INDEXAR" })
    });
    const oldId = session.id;
    session.id = next.coleccion_id;
    session.mode = "completo";
    session.queryId = query.consulta_id;
    session.pendingHybrid = null;
    session.previousKeys = previousKeys;
    session.matchQuestion = null;
    ui.hybridPanel.hidden = true;
    renderSources(query.fuentes, query.tiempos.recuperacion);
    showNextSteps({ keepPosition: true });
    renderComparison(previousSources, query.fuentes);
    ui.hybridNote.textContent = ui.comparisonSummary.textContent + " El detalle, fragmento por fragmento, está en la evidencia.";
    ui.hybridNote.hidden = false;
    openEvidence(ui.comparison);
    ui.comparisonTitle.focus({ preventScroll: true });
    announce(ui.comparisonSummary.textContent);
    if (oldId) api("/colecciones/" + oldId, { method: "DELETE" }).catch(() => {});
  } catch (error) {
    await discardPendingHybrid();
    ui.hybridPanel.hidden = true;
    showNextSteps({ keepPosition: true });
    status("No se pudo hacer la búsqueda híbrida: " + error.message, true);
  } finally { setBusy(false); }
  answerIfAuthorized();
}

async function cancelHybrid() {
  if (session.busy || !session.pendingHybrid) return;
  setBusy(true);
  await discardPendingHybrid();
  const previous = session.previousActions;
  session.previousActions = null;
  ui.hybridPanel.hidden = true;
  ui.hybridButton.hidden = false;
  if (previous) {
    ui.sendPanel.hidden = !previous.send;
    ui.noModelPanel.hidden = !previous.noModel;
    ui.translatePanel.hidden = !previous.translate;
    ui.resultSummary.textContent = previous.summary;
  }
  setBusy(false);
  ui.hybridButton.focus();
  announce("Búsqueda híbrida cancelada. No se envió nada a OpenAI.");
}

function runSuggestion(item) {
  if (session.busy) return;
  ui.question.value = item.pregunta;
  autosize();
  updateCounter();
  search();
}

/* ---------- origen: ejemplo o archivos propios ---------- */

const ACEPTADOS = /\.(py|js|jsx|ts|tsx|mjs|cjs|md|markdown|txt|pdf)$/i;

function describeProject() {
  const upload = session.selectedOrigin === "carga";
  const names = Array.from(ui.uploadFiles.files).map(file => file.name);
  ui.projectName.textContent = upload ? "Mis archivos" : "Proyecto de ejemplo";
  ui.collectionHint.textContent = upload ?
    (names.length ? names.join(", ") : "La búsqueda se hace en este servidor. Nada se envía a OpenAI sin que lo autorices.") :
    "Un gestor de tareas ficticio, con código Python y documentos de texto.";
  ui.questionLabel.textContent = upload ? "Tu pregunta sobre tus archivos" : "Tu pregunta sobre el proyecto de ejemplo";
  ui.question.placeholder = upload ?
    (names.length ? "Preguntá sobre tus archivos" : "Primero elegí tus archivos") :
    "Escribí tu pregunta";
  ui.suggestionsWrap.hidden = upload;
  updateConsentNote();
  ui.uploadHint.hidden = !upload || names.length > 0;
  autosize();
}

function chooseOrigin(origin) {
  if (session.busy) return;
  session.selectedOrigin = origin;
  ui.uploadPanel.hidden = origin !== "carga";
  ui.useExample.setAttribute("aria-pressed", String(origin === "ejemplo"));
  ui.useUpload.setAttribute("aria-pressed", String(origin === "carga"));
  ui.question.value = "";
  autosize();
  updateCounter();
  resetThread();
  describeProject();
}

function formatBytes(bytes) {
  if (bytes < 1000) return bytes + " B";
  if (bytes < 1_000_000) return Math.round(bytes / 1000) + " KB";
  return (bytes / 1_000_000).toLocaleString("es-AR", { maximumFractionDigits: 1 }) + " MB";
}

function renderFileList() {
  const icon = '<svg width="16" height="16" viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M11.5 3H6a1.5 1.5 0 0 0-1.5 1.5v11A1.5 1.5 0 0 0 6 17h8a1.5 1.5 0 0 0 1.5-1.5V7z"/><path d="M11.5 3v4h4"/></svg>';
  ui.fileList.replaceChildren(...Array.from(ui.uploadFiles.files).map(file => {
    const item = el("li", "archivo");
    item.insertAdjacentHTML("afterbegin", icon);
    const name = el("span", "archivo-nombre", file.name);
    name.title = file.name;
    item.append(name, el("span", "archivo-peso", formatBytes(file.size)));
    return item;
  }));
}

/* Arrastrar y soltar: en la zona de la columna o en cualquier parte de la página. */
function takeFiles(list) {
  if (session.busy) return;
  const all = Array.from(list || []);
  const valid = all.filter(file => ACEPTADOS.test(file.name));
  if (!valid.length) {
    const names = all.map(file => file.name).join(", ");
    status((all.length === 1 ? names + " no se puede consultar" : "Esos archivos no se pueden consultar") + ". Se admiten código Python, JavaScript o TypeScript, Markdown, TXT y PDF.", true);
    return;
  }
  if (session.selectedOrigin !== "carga") chooseOrigin("carga");
  const transfer = new DataTransfer();
  valid.slice(0, 5).forEach(file => transfer.items.add(file));
  ui.uploadFiles.files = transfer.files;
  ui.uploadFiles.dispatchEvent(new Event("change"));
  const left = all.length - Math.min(valid.length, 5);
  if (left) status(plural(Math.min(valid.length, 5), "archivo agregado", "archivos agregados") + ". " + plural(left, "quedó afuera", "quedaron afuera") + " por el formato o por pasar de cinco.", false);
}

const hasFiles = event => Array.from((event.dataTransfer && event.dataTransfer.types) || []).includes("Files");
let dragDepth = 0;
function endDrag() { dragDepth = 0; ui.app.classList.remove("soltando"); ui.dropZone.classList.remove("arrastrando"); }
document.addEventListener("dragenter", event => {
  if (!hasFiles(event)) return;
  dragDepth += 1;
  ui.app.classList.add("soltando");
  ui.dropZone.classList.add("arrastrando");
});
document.addEventListener("dragover", event => { if (hasFiles(event)) event.preventDefault(); });
document.addEventListener("dragleave", event => {
  if (!hasFiles(event)) return;
  dragDepth = Math.max(0, dragDepth - 1);
  if (!dragDepth) endDrag();
});
document.addEventListener("drop", event => {
  if (!hasFiles(event)) return;
  event.preventDefault();
  endDrag();
  takeFiles(event.dataTransfer.files);
});

ui.useExample.addEventListener("click", () => chooseOrigin("ejemplo"));
ui.useUpload.addEventListener("click", () => chooseOrigin("carga"));
ui.uploadFiles.addEventListener("change", () => {
  if (session.origin === "carga") session.mode = null;
  setConsent("carga", false);
  resetThread();
  renderFileList();
  ui.uploadSummary.textContent = filesSummary();
  describeProject();
  if (ui.uploadFiles.files.length) ui.question.focus();
});
ui.deleteUpload.addEventListener("click", async () => {
  if (!session.id || session.origin !== "carga") return;
  try {
    await discardPendingHybrid();
    await api("/colecciones/" + session.id, { method: "DELETE" });
    session.id = null;
    session.mode = null;
    session.queryId = null;
    ui.deleteUpload.hidden = true;
    ui.uploadFiles.value = "";
    renderFileList();
    resetThread();
    ui.uploadSummary.textContent = "Tus archivos se borraron del servidor.";
    describeProject();
    status("Tus archivos se borraron del servidor.", false);
  } catch (error) { status(error.message, true); }
});

/* ---------- compositor ---------- */

function updateCounter() {
  const length = ui.question.value.length;
  ui.counter.hidden = length < 400;
  ui.counter.textContent = length + " de 500 caracteres";
}

function autosize() {
  ui.question.style.height = "auto";
  ui.question.style.height = Math.min(ui.question.scrollHeight, 200) + "px";
}

ui.queryForm.addEventListener("submit", event => { event.preventDefault(); search(); });
ui.question.addEventListener("keydown", event => {
  if (event.key === "Enter" && !event.shiftKey && !event.isComposing) {
    event.preventDefault();
    ui.queryForm.requestSubmit();
  }
});
ui.question.addEventListener("input", () => {
  updateCounter();
  autosize();
  if (!ui.status.hidden && !session.busy) status("", false);
});
ui.answerButton.addEventListener("click", () => {
  setConsent(session.selectedOrigin, true);
  generateAnswer();
});
ui.revokeConsent.addEventListener("click", () => {
  setConsent(session.selectedOrigin, false);
  announce("Antes de cada envío a OpenAI vas a ver qué se envía y confirmarlo.");
});
ui.translateButton.addEventListener("click", translateQuestion);
ui.hybridButton.addEventListener("click", prepareHybrid);
ui.indexButton.addEventListener("click", runHybrid);
ui.cancelIndex.addEventListener("click", cancelHybrid);
ui.backToLexical.addEventListener("click", () => {
  if (session.busy) return;
  ui.question.value = session.question;
  search();
});
ui.newChat.addEventListener("click", () => {
  if (session.busy) return;
  resetThread();
  setSidebar(false);
  ui.question.focus();
});

/* ---------- columna como cajón en pantallas chicas ---------- */

const narrow = window.matchMedia("(max-width: 900px)");

function syncInert() {
  const open = ui.app.classList.contains("lateral-abierta");
  ui.sidebar.inert = narrow.matches && !open;
  ui.main.inert = narrow.matches && open;
}

function setSidebar(open) {
  if (!narrow.matches) open = false;
  const wasOpen = ui.app.classList.contains("lateral-abierta");
  ui.app.classList.toggle("lateral-abierta", open);
  ui.menuButton.setAttribute("aria-expanded", String(open));
  ui.scrim.hidden = !open;
  syncInert();
  if (open && !wasOpen) ui.closeSidebar.focus();
  if (!open && wasOpen && ui.sidebar.contains(document.activeElement)) ui.menuButton.focus();
}

ui.menuButton.addEventListener("click", () => setSidebar(true));
ui.closeSidebar.addEventListener("click", () => setSidebar(false));
ui.scrim.addEventListener("click", () => setSidebar(false));
document.addEventListener("keydown", event => {
  if (event.key !== "Escape" || document.querySelector("dialog[open]")) return;
  if (ui.app.classList.contains("lateral-abierta")) setSidebar(false);
  else if (!ui.evidence.hidden) closeEvidence();
});

ui.sourcesButton.addEventListener("click", () => {
  if (!ui.evidence.hidden && !ui.evidenceLive.hidden) closeEvidence();
  else openEvidence(null, true);
});
ui.showContext.addEventListener("click", () => openEvidence(ui.contextSection, true));
ui.closeEvidence.addEventListener("click", closeEvidence);
narrow.addEventListener("change", () => { if (!narrow.matches) setSidebar(false); syncInert(); });
syncInert();

/* ---------- guía ---------- */

function openGuide() {
  setSidebar(false);
  ui.guideDialog.showModal();
  ui.closeGuide.focus();
}
ui.openGuide.addEventListener("click", openGuide);
ui.openGuideTop.addEventListener("click", openGuide);
ui.closeGuide.addEventListener("click", () => ui.guideDialog.close());
ui.guideDialog.addEventListener("click", event => { if (event.target === ui.guideDialog) ui.guideDialog.close(); });
ui.guideDialog.querySelectorAll(".guia-indice a").forEach(link => link.addEventListener("click", event => {
  event.preventDefault();
  const target = document.querySelector(link.getAttribute("href"));
  if (target) scrollInside(ui.guideDialog.querySelector(".guia-cuerpo"), target, "start");
}));

document.querySelector(".skip-link").addEventListener("click", event => {
  event.preventDefault();
  ui.question.focus();
});

/* ---------- inicio ---------- */

const SUGERENCIAS_VISIBLES = ["codigo", "cruce", "politica", "abstencion"];

async function initialize() {
  try {
    const [state, questions] = await Promise.all([api("/estado"), api("/preguntas-ejemplo")]);
    session.modelAvailable = state.modelo_disponible;
    session.indexAvailable = state.indice_ejemplo_preparado;
    session.suggestions = questions;
    ui.apiState.dataset.model = state.modelo_disponible ? "si" : "no";
    ui.apiState.textContent = state.modelo_disponible ? "Responde con OpenAI cuando lo autorizás" : "Solo búsqueda: el servidor no tiene clave de OpenAI";
    updateConsentNote();
    const visible = questions.filter(item => SUGERENCIAS_VISIBLES.includes(item.id));
    (visible.length ? visible : questions).forEach(item => {
      const without = item.id === "abstencion";
      const button = el("button", "sugerencia" + (without ? " sugerencia-sin" : ""));
      button.type = "button";
      button.title = item.descripcion;
      button.append(el("span", "sugerencia-tipo", without ? "No está en el proyecto" : item.categoria), el("span", "sugerencia-pregunta", item.pregunta));
      button.addEventListener("click", () => runSuggestion(item));
      ui.suggestions.append(button);
    });
  } catch (error) {
    ui.apiState.dataset.model = "no";
    ui.apiState.textContent = "Sin conexión con el servidor";
    status("No se pudo conectar con el servidor: " + error.message + ". Recargá la página en un momento.", true);
  }
}
describeProject();
initialize();

/* ---------- comparativa de búsquedas ---------- */

const benchmarkData = [
  { mode: "acotado", name: "Por palabras", first: 6, coverage: 5, negative: 2 },
  { mode: "semantica", name: "Por significado", first: 6, coverage: 7, negative: 0 },
  { mode: "completo", name: "Híbrida", first: 6, coverage: 7, negative: 0 }
];
const benchmarkMetrics = {
  coverage: { title: "¿Trajo todos los fragmentos necesarios entre los cinco primeros?", count: 7, note: "En 7 preguntas con respuesta. Acá está la diferencia: la búsqueda por palabras dejó afuera algún fragmento necesario en 2 preguntas; las otras dos los trajeron siempre." },
  first: { title: "¿Puso el fragmento correcto en primer lugar?", count: 7, note: "En 7 preguntas con respuesta. Las tres aciertan 6 y fallan en la misma. El empate no quiere decir que traigan los mismos fragmentos después del primero." },
  negative: { title: "Cuando la pregunta no tenía respuesta, ¿no trajo nada?", count: 2, note: "En 2 preguntas sin respuesta. La búsqueda por palabras no devolvió nada; las otras dos siempre devuelven candidatos parecidos. Igual el modelo puede no responder después, como debe." }
};
let benchmarkSeen = false;

function renderBenchmark(metricKey) {
  const metric = benchmarkMetrics[metricKey];
  const chart = $("benchmarkChart");
  if (!metric || !chart) return;
  $("benchmarkTitle").textContent = metric.title;
  $("benchmarkNote").textContent = metric.note;
  if (!chart.children.length) {
    benchmarkData.forEach(item => {
      const row = el("div", "barra-fila");
      row.dataset.mode = item.mode;
      const track = el("div", "barra-pista");
      track.append(el("div", "barra"));
      row.append(el("span", "barra-nombre", item.name), track, el("span", "barra-valor"));
      chart.append(row);
    });
  }
  benchmarkData.forEach((item, index) => {
    const row = chart.children[index];
    const value = item[metricKey];
    row.querySelector(".barra-valor").textContent = value + " de " + metric.count;
    row.setAttribute("aria-label", item.name + ": " + value + " de " + metric.count);
    row.querySelector(".barra").style.width = benchmarkSeen ? (value / metric.count) * 100 + "%" : "0%";
    row.querySelector(".barra").dataset.width = (value / metric.count) * 100 + "%";
  });
  document.querySelectorAll(".metrica").forEach(button => {
    button.setAttribute("aria-pressed", String(button.dataset.metric === metricKey));
  });
}

function revealBenchmark() {
  benchmarkSeen = true;
  document.querySelectorAll("#benchmarkChart .barra").forEach(bar => { bar.style.width = bar.dataset.width; });
}

document.querySelectorAll(".metrica").forEach(button => {
  button.addEventListener("click", () => renderBenchmark(button.dataset.metric));
});
renderBenchmark("coverage");
if ("IntersectionObserver" in window && !reduceMotion.matches) {
  const observer = new IntersectionObserver(entries => {
    if (entries.some(entry => entry.isIntersecting)) { revealBenchmark(); observer.disconnect(); }
  }, { threshold: 0.4 });
  observer.observe($("benchmarkChart"));
} else {
  revealBenchmark();
}
