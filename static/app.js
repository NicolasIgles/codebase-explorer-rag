"use strict";

const $ = id => document.getElementById(id);
const ui = {
  apiState: $("apiState"),
  menuButton: $("menuButton"),
  mainNav: $("mainNav"),
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
  contextList: $("contextList"),
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
    ui.status.scrollIntoView({ behavior: scrollBehavior(), block: "nearest" });
    ui.status.focus({ preventScroll: true });
  }
}

function revealIfNeeded(node) {
  const box = node.getBoundingClientRect();
  if (box.top < 0 || box.top > window.innerHeight * 0.75)
    node.scrollIntoView({ behavior: scrollBehavior(), block: "start" });
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
}

function resetStages() {
  ["recuperar", "contexto", "responder"].forEach(name => setStage(name, "idle"));
}

function stopIntro() {
  ui.stages.classList.remove("intro");
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
  ui.resultFoot.textContent = "La búsqueda tardó " + formatSeconds(seconds) + " en este servidor.";
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
}

function focusSource(number) {
  const card = $("fragmento-" + number);
  if (!card) return;
  card.scrollIntoView({ behavior: scrollBehavior(), block: "nearest" });
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
      "No hay evidencia para responder esto",
      "Ninguno de los fragmentos encontrados contesta la pregunta. En lugar de inventar, el modelo prefirió no responder: es lo que tiene que hacer un buen sistema RAG."
    ));
    ui.sourcesTitle.firstChild.textContent = "Lo más cercano que encontró ";
    markCited([]);
    setStage("responder", "abstained", "No respondió, por falta de evidencia");
    announce("El modelo no respondió porque los fragmentos no alcanzan.");
  } else {
    const citas = (data.citas || []).filter(n => n >= 1 && n <= total);
    ui.answerTitle.textContent = "Respuesta";
    ui.resultSummary.hidden = false;
    ui.resultSummary.textContent = "Basada en " + citas.length + " de " + plural(total, "fragmento encontrado", "fragmentos encontrados") + ". Tocá una cita para ver las líneas que la sostienen.";
    const text = el("p", "respuesta-texto", data.respuesta);
    const chips = el("p", "citas");
    chips.append(el("span", "", citas.length === 1 ? "Fuente citada" : "Fuentes citadas"));
    citas.forEach((number, i) => {
      const source = session.sources[number - 1];
      const chip = el("button", "cita", source.ruta.split("/").pop() + " " + shortPlace(source));
      chip.type = "button";
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
  ui.answer.hidden = false;
  ui.answerStage.focus({ preventScroll: true });
  revealIfNeeded(ui.answerStage);
  if (data.tiempos && Number(data.tiempos.modelo || 0) > 0)
    ui.resultFoot.textContent += " El modelo tardó " + formatSeconds(data.tiempos.modelo) + ".";
}

/* ---------- contexto para el modelo ---------- */

function showContext() {
  ui.contextList.replaceChildren();
  const addRow = (label, value, isPath) => {
    const item = el("li");
    item.append(el("span", "rotulo", label), el("span", isPath ? "ruta" : "", value));
    ui.contextList.append(item);
  };
  addRow("Pregunta", session.question);
  session.sources.forEach((source, index) => addRow("Fragmento " + (index + 1), source.ruta + ", " + placeOf(source), true));
  addRow("Instrucción", "Responder solo con estos fragmentos e indicar cuáles usó. Si no alcanzan, no responder.");

  /* Mismo formato que preparar_consulta y las instrucciones de validar_evidencia.py. */
  const blocks = session.sources.map((source, index) => {
    const name = [source.contenedor, source.simbolo].filter(Boolean).join(".");
    return "[" + (index + 1) + "] " + serverPlace(source) + " (" + name + ")\n" + (source.codigo || "");
  });
  ui.sendPreview.textContent =
    "Instrucciones para el modelo:\n" + MODEL_INSTRUCTIONS +
    "\n\nConsulta:\nPregunta: " + session.question + "\n\nFuentes:\n" + blocks.join("\n\n");
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
  box.append(el("h3", "", title), el("p", "", text));
  const actions = el("div", "botonera");
  const again = el("button", "boton-principal", "Hacer otra pregunta");
  again.type = "button";
  again.addEventListener("click", () => { ui.question.focus(); ui.question.select(); });
  actions.append(again);
  const good = session.suggestions.find(item => item.id === "codigo");
  if (good && session.selectedOrigin === "ejemplo") {
    const example = el("button", "boton-secundario", "Ver una que sí tiene respuesta");
    example.type = "button";
    example.addEventListener("click", () => runSuggestion(good));
    actions.append(example);
  }
  box.append(actions);
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
  ui.sources.replaceChildren();
  ui.resultFoot.textContent = "";
  ui.resultSummary.hidden = false;
  session.queryId = null;
  session.sources = [];
  session.cited = [];
  session.question = "";
  session.matchQuestion = null;
  session.previousActions = null;
  session.previousKeys = null;
  ui.answerButton.hidden = false;
  resetStages();
  status("", false);
}

function showNextSteps() {
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
  ui.stages.classList.add("con-resultado");

  if (count) {
    setStage("recuperar", "done", plural(count, "fragmento encontrado", "fragmentos encontrados") + (hybrid ? ", con palabras y significado" : ", en este servidor"));
    ui.answerTitle.textContent = "Encontró " + plural(count, "fragmento");
    showContext();
    ui.sendPanel.hidden = false;
    if (session.modelAvailable) {
      setStage("contexto", "waiting", "Revisá lo que recibiría el modelo");
      ui.resultSummary.textContent = "Antes de responder, mirá qué recibiría el modelo y decidí si lo enviás.";
      ui.contextTitle.textContent = "Esto es lo que recibirá el modelo";
      ui.contextNote.textContent = "Nada sale de este servidor hasta que tocás el botón.";
      ui.answerButton.hidden = false;
    } else {
      setStage("contexto", "done", "Tu pregunta y " + plural(count, "fragmento") + ", listos para el modelo");
      setStage("responder", "skipped", "Necesita una clave de OpenAI en el servidor");
      ui.resultSummary.hidden = true;
      ui.noModelPanel.hidden = false;
      ui.contextTitle.textContent = "Esto es lo que recibiría el modelo";
      ui.contextNote.textContent = "En esta demo no se envía: el servidor no tiene una clave de OpenAI.";
      ui.answerButton.hidden = true;
    }
    announce(plural(count, "fragmento encontrado", "fragmentos encontrados") + ".");
  } else {
    /* Sin fragmentos el servidor se abstiene sin llamar al modelo (generar_respuesta). */
    setStage("recuperar", "done", "Ningún fragmento coincide");
    setStage("contexto", "skipped", "Sin fragmentos, no hay nada que armar");
    setStage("responder", "abstained", "No respondió, por falta de evidencia");
    ui.answerTitle.textContent = "Respuesta";
    ui.resultSummary.hidden = true;
    let text = (hybrid ?
      "La búsqueda híbrida no encontró nada que se parezca lo suficiente a tu pregunta." :
      "La búsqueda por palabras no encontró ninguna parte del proyecto que comparta palabras con tu pregunta.") +
      " Sin evidencia, el sistema no responde: prefiere no inventar.";
    if (!hybrid && session.modelAvailable) text += " Si creés que la respuesta sí está, probá la búsqueda híbrida, que también busca por significado.";
    ui.answer.replaceChildren(abstentionBox("No hay evidencia para responder esto", text));
    ui.answer.hidden = false;
    ui.sourcesTitle.firstChild.textContent = "Lo que encontró la búsqueda ";
    if (!hybrid && session.modelAvailable && session.question.includes("¿")) {
      ui.translatePreview.textContent = session.question;
      ui.translatePanel.hidden = false;
    }
    announce("No se encontraron fragmentos. El sistema no responde sin evidencia.");
  }
  revealIfNeeded(ui.stages);
  ui.answerStage.focus({ preventScroll: true });
}

/* ---------- acciones ---------- */

function setBusy(value) {
  session.busy = value;
  [ui.searchButton, ui.question, ui.uploadFiles, ui.useExample, ui.useUpload, ui.answerButton, ui.translateButton, ui.hybridButton, ui.indexButton, ui.cancelIndex]
    .forEach(node => { node.disabled = value; });
  ui.suggestions.querySelectorAll("button").forEach(node => { node.disabled = value; });
  ui.searchButton.textContent = value ? "Buscando…" : "Buscar en el proyecto";
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
  if (origin === "carga") ui.uploadSummary.textContent = filesSummary() + ". Ya están en el servidor; se borran en menos de 24 horas.";
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
  const files = Array.from(ui.uploadFiles.files);
  return files.length ? files.map(file => file.name).join(", ") : "Todavía no elegiste archivos.";
}

async function search() {
  if (session.busy) return;
  const question = ui.question.value.trim();
  stopIntro();
  if (!question) { status("Escribí una pregunta para buscar en el proyecto.", true); ui.question.focus(); return; }
  clearResults();
  setBusy(true);
  setStage("recuperar", "active", session.selectedOrigin === "carga" ? "Preparando tus archivos y buscando…" : "Buscando en el código y los documentos…");
  try {
    await ensureCollection("acotado");
    const query = await api("/colecciones/" + session.id + "/consultas", {
      method: "POST", body: JSON.stringify({ pregunta: question })
    });
    session.question = question;
    session.queryId = query.consulta_id;
    renderSources(query.fuentes, query.tiempos.recuperacion);
    showNextSteps();
  } catch (error) {
    resetStages();
    status(error.message, true);
  } finally { setBusy(false); }
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
    setStage("contexto", "waiting", "Revisá lo que recibiría el modelo");
    setStage("responder", "idle");
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
    ui.indexButton.textContent = prepared ? "Enviar la pregunta y buscar" : "Enviar los archivos y buscar";
    ui.hybridSummary.textContent = prepared ?
      "La búsqueda híbrida suma la comparación por significado. El índice del ejemplo ya está preparado: solo se envía tu pregunta a OpenAI para calcular su vector, los archivos no." :
      "La búsqueda híbrida suma la comparación por significado. Para eso se envía a OpenAI el texto permitido de tus archivos, para calcular sus vectores, y tu pregunta. Revisá el detalle antes de autorizar.";
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
    if (!ui.hybridPanel.hidden) ui.indexButton.focus();
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
  const previousKeys = new Set(session.sources.map(sourceKey));
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
    showNextSteps();
    const added = query.fuentes.filter(source => !previousKeys.has(sourceKey(source))).length;
    if (added) ui.resultSummary.textContent = "La búsqueda híbrida trajo " + plural(added, "fragmento nuevo", "fragmentos nuevos") + ". " + ui.resultSummary.textContent;
    else if (query.fuentes.length) ui.resultSummary.textContent = "La búsqueda híbrida encontró los mismos fragmentos, quizás en otro orden. " + ui.resultSummary.textContent;
    if (oldId) api("/colecciones/" + oldId, { method: "DELETE" }).catch(() => {});
  } catch (error) {
    setStage("recuperar", "done", plural(session.sources.length, "fragmento encontrado", "fragmentos encontrados") + ", en este servidor");
    status("No se pudo hacer la búsqueda híbrida: " + error.message, true);
  } finally { setBusy(false); }
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
  updateCounter();
  search();
}

/* ---------- origen: ejemplo o archivos propios ---------- */

function chooseOrigin(origin) {
  if (session.busy) return;
  discardPendingHybrid();
  session.selectedOrigin = origin;
  ui.uploadPanel.hidden = origin !== "carga";
  ui.suggestionsWrap.hidden = origin !== "ejemplo";
  ui.questionLabel.textContent = origin === "carga" ? "Tu pregunta sobre tus archivos" : "Tu pregunta sobre el proyecto de ejemplo";
  ui.collectionHint.textContent = origin === "carga" ?
    "La búsqueda se hace en este servidor. Nada se envía a OpenAI sin que lo autorices." :
    "Un gestor de tareas ficticio, con código Python y documentos de texto.";
  ui.searchButton.textContent = "Buscar en el proyecto";
  ui.useExample.setAttribute("aria-pressed", String(origin === "ejemplo"));
  ui.useUpload.setAttribute("aria-pressed", String(origin === "carga"));
  ui.question.value = "";
  updateCounter();
  clearResults();
}

ui.useExample.addEventListener("click", () => chooseOrigin("ejemplo"));
ui.useUpload.addEventListener("click", () => chooseOrigin("carga"));
ui.uploadFiles.addEventListener("change", () => {
  ui.uploadSummary.textContent = filesSummary();
  if (session.origin === "carga") session.mode = null;
  discardPendingHybrid();
  clearResults();
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
    ui.uploadSummary.textContent = filesSummary();
    clearResults();
    status("Tus archivos se borraron del servidor.", false);
    ui.question.focus();
  } catch (error) { status(error.message, true); }
});

/* ---------- formulario y navegación ---------- */

function updateCounter() {
  const length = ui.question.value.length;
  ui.counter.hidden = length < 400;
  ui.counter.textContent = length + " de 500 caracteres";
}

ui.queryForm.addEventListener("submit", event => { event.preventDefault(); search(); });
ui.answerButton.addEventListener("click", generateAnswer);
ui.translateButton.addEventListener("click", translateQuestion);
ui.hybridButton.addEventListener("click", prepareHybrid);
ui.indexButton.addEventListener("click", runHybrid);
ui.cancelIndex.addEventListener("click", cancelHybrid);
ui.question.addEventListener("input", () => {
  updateCounter();
  if (session.question && ui.question.value.trim() !== session.question) {
    discardPendingHybrid();
    clearResults();
  }
});

ui.menuButton.addEventListener("click", () => {
  const open = ui.menuButton.getAttribute("aria-expanded") !== "true";
  ui.menuButton.setAttribute("aria-expanded", String(open));
  ui.mainNav.classList.toggle("abierta", open);
});
ui.mainNav.addEventListener("click", event => {
  if (event.target.closest("a")) {
    ui.menuButton.setAttribute("aria-expanded", "false");
    ui.mainNav.classList.remove("abierta");
  }
});
document.querySelector(".skip-link").addEventListener("click", event => {
  event.preventDefault();
  ui.question.focus();
  ui.question.scrollIntoView({ behavior: scrollBehavior(), block: "center" });
});

/* ---------- inicio ---------- */

const SUGERENCIAS_VISIBLES = ["codigo", "cruce", "politica", "abstencion"];

async function initialize() {
  if (!reduceMotion.matches) {
    ui.stages.classList.add("intro");
    window.setTimeout(stopIntro, 2600);
  }
  try {
    const [state, questions] = await Promise.all([api("/estado"), api("/preguntas-ejemplo")]);
    session.modelAvailable = state.modelo_disponible;
    session.indexAvailable = state.indice_ejemplo_preparado;
    session.suggestions = questions;
    ui.apiState.dataset.model = state.modelo_disponible ? "si" : "no";
    ui.apiState.textContent = state.modelo_disponible ? "Esta demo responde con OpenAI" : "Esta demo está en modo solo búsqueda";
    const visible = questions.filter(item => SUGERENCIAS_VISIBLES.includes(item.id));
    (visible.length ? visible : questions).forEach(item => {
      const button = el("button", "sugerencia" + (item.id === "abstencion" ? " sugerencia-sin" : ""), item.pregunta);
      button.type = "button";
      button.title = item.descripcion;
      if (item.id === "abstencion") button.append(" ", el("span", "", "(no está en el proyecto)"));
      button.addEventListener("click", () => runSuggestion(item));
      ui.suggestions.append(button);
    });
  } catch (error) {
    ui.apiState.dataset.model = "no";
    ui.apiState.textContent = "Sin conexión con el servidor";
    status("No se pudo conectar con el servidor: " + error.message + ". Recargá la página en un momento.", true);
  }
}
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
