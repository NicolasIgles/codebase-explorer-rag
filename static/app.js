"use strict";

const ui = {
  apiState: document.getElementById("apiState"),
  suggestions: document.getElementById("suggestions"),
  question: document.getElementById("question"),
  counter: document.getElementById("counter"),
  searchButton: document.getElementById("searchButton"),
  emptyState: document.getElementById("emptyState"),
  status: document.getElementById("status"),
  scope: document.getElementById("scope"),
  results: document.getElementById("results"),
  answerStage: document.getElementById("answerStage"),
  resultSummary: document.getElementById("resultSummary"),
  sourcesSection: document.getElementById("sourcesSection"),
  resultCount: document.getElementById("resultCount"),
  sources: document.getElementById("sources"),
  answer: document.getElementById("answer"),
  resultFoot: document.getElementById("resultFoot"),
  sendPanel: document.getElementById("sendPanel"),
  sendSummary: document.getElementById("sendSummary"),
  sendDetails: document.getElementById("sendDetails"),
  sendPreview: document.getElementById("sendPreview"),
  answerButton: document.getElementById("answerButton"),
  translatePanel: document.getElementById("translatePanel"),
  translatePreview: document.getElementById("translatePreview"),
  translateButton: document.getElementById("translateButton"),
  hybridArea: document.getElementById("hybridArea"),
  hybridButton: document.getElementById("hybridButton"),
  hybridPanel: document.getElementById("hybridPanel"),
  hybridTitle: document.getElementById("hybridTitle"),
  hybridSummary: document.getElementById("hybridSummary"),
  hybridDetailsLabel: document.getElementById("hybridDetailsLabel"),
  hybridQuestion: document.getElementById("hybridQuestion"),
  indexButton: document.getElementById("indexButton"),
  cancelIndex: document.getElementById("cancelIndex"),
  sourceDialog: document.getElementById("sourceDialog"),
  sourceKind: document.getElementById("sourceKind"),
  sourceTitle: document.getElementById("sourceTitle"),
  sourceLocation: document.getElementById("sourceLocation"),
  sourceCode: document.getElementById("sourceCode"),
  closeSource: document.getElementById("closeSource"),
  closeSourceTop: document.getElementById("closeSourceTop")
  ,useExample: document.getElementById("useExample")
  ,useUpload: document.getElementById("useUpload")
  ,uploadPanel: document.getElementById("uploadPanel")
  ,uploadFiles: document.getElementById("uploadFiles")
  ,uploadSummary: document.getElementById("uploadSummary")
  ,deleteUpload: document.getElementById("deleteUpload")
  ,collectionHint: document.getElementById("collectionHint")
};

let session = { id: null, mode: null, origin: null, selectedOrigin: "ejemplo", queryId: null, sources: [], question: "", pendingHybrid: null, previousActions: null, modelAvailable: false, indexAvailable: false, busy: false };
const modalFocus = new WeakMap();

function showOverlay(overlay) {
  modalFocus.set(overlay, document.activeElement);
  overlay.hidden = false;
  overlay.querySelector(".rag-close").focus();
}

function hideOverlay(overlay) {
  overlay.hidden = true;
  const previous = modalFocus.get(overlay);
  if (previous && previous.isConnected && !previous.disabled) previous.focus();
  else ui.question.focus();
}

document.addEventListener("keydown", event => {
  const overlay = ui.sourceDialog.hidden ? null : ui.sourceDialog;
  if (!overlay) return;
  if (event.key === "Escape") {
    event.preventDefault();
    hideOverlay(overlay);
    return;
  }
  if (event.key !== "Tab") return;
  const buttons = Array.from(overlay.querySelectorAll("button:not([disabled])"));
  if (!buttons.includes(document.activeElement)) {
    event.preventDefault();
    buttons[0].focus();
  } else if (event.shiftKey && document.activeElement === buttons[0]) {
    event.preventDefault();
    buttons[buttons.length - 1].focus();
  } else if (!event.shiftKey && document.activeElement === buttons[buttons.length - 1]) {
    event.preventDefault();
    buttons[0].focus();
  }
});

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

function status(message, error) {
  ui.status.textContent = message;
  ui.status.classList.toggle("error", Boolean(error));
  ui.status.hidden = !message;
}

function setBusy(value) {
  session.busy = value;
  ui.searchButton.disabled = value;
  ui.question.disabled = value;
  ui.uploadFiles.disabled = value;
  ui.useExample.disabled = value;
  ui.useUpload.disabled = value;
  ui.searchButton.firstChild.textContent = value ? "Consultando… " : "Buscar fuentes ";
  [ui.answerButton, ui.translateButton, ui.hybridButton, ui.indexButton, ui.cancelIndex].forEach(button => { button.disabled = value; });
}

function locationOf(source) {
  const place = source.ubicacion || {};
  const base = place.tipo === "pagina" ?
    source.ruta + " · página " + place.pagina :
    source.ruta + " · líneas " + source.inicio + "–" + source.fin;
  return place.columna_inicio ? base + " · columnas " + place.columna_inicio + "–" + place.columna_fin : base;
}

function clearResults() {
  ui.emptyState.hidden = true;
  ui.results.hidden = true;
  ui.hybridArea.hidden = true;
  ui.hybridPanel.hidden = true;
  ui.hybridButton.hidden = false;
  ui.hybridQuestion.textContent = "";
  ui.sendPanel.hidden = true;
  ui.translatePanel.hidden = true;
  ui.answer.hidden = true;
  ui.sendDetails.open = false;
  ui.sourcesSection.open = false;
  ui.sources.replaceChildren();
  ui.resultFoot.textContent = "";
  session.queryId = null;
  session.sources = [];
  session.question = "";
  session.previousActions = null;
  status("", false);
}

function showScope(scope) {
  if (!scope) {
    ui.scope.hidden = true;
    return;
  }
  ui.scope.replaceChildren();
  const heading = document.createElement("h4");
  heading.textContent = "Alcance de la indexación";
  const summary = document.createElement("p");
  summary.textContent = scope.cantidad_fragmentos + " fragmentos de " + scope.rutas.length + " archivos; aproximadamente " + scope.bytes_aproximados + " bytes de texto.";
  const list = document.createElement("ul");
  scope.rutas.forEach(path => {
    const item = document.createElement("li");
    item.textContent = path;
    list.append(item);
  });
  ui.scope.append(heading, summary, list);
  const excluded = Object.keys(scope.excluidos || {});
  if (excluded.length) {
    const note = document.createElement("p");
    note.textContent = excluded.length + " archivo(s) excluido(s) por el filtro de privacidad.";
    ui.scope.append(note);
  }
}

async function ensureCollection(mode) {
  const origin = session.selectedOrigin;
  if (session.id && session.mode === mode && session.origin === origin) return null;
  await discardPendingHybrid();
  if (session.id) {
    try { await api("/colecciones/" + session.id, { method: "DELETE" }); }
    catch { /* La colección también puede haber vencido. */ }
    session.id = null;
  }
  const created = await createCollection(mode);
  session.id = created.coleccion_id;
  session.mode = mode;
  session.origin = origin;
  session.queryId = null;
  ui.deleteUpload.hidden = origin !== "carga";
  if (origin === "carga") ui.uploadSummary.textContent = filesSummary() + " · Colección lista; se borra antes de 24 horas o si el servicio se duerme o reinicia.";
  return created;
}

async function createCollection(mode) {
  const origin = session.selectedOrigin;
  if (origin === "carga") {
    const files = Array.from(ui.uploadFiles.files);
    if (!files.length) throw new Error("Elegí archivos antes de consultar tu colección.");
    if (files.length > 5 || files.some(file => file.size > 10_000_000))
      throw new Error("Se admiten hasta cinco archivos de 10 MB cada uno.");
    const form = new FormData();
    form.append("modo", mode);
    files.forEach(file => form.append("archivos", file));
    status("Preparando la colección temporal…", false);
    return api("/cargas/colecciones", { method: "POST", body: form });
  } else {
    return api("/ejemplo/colecciones", {
      method: "POST", body: JSON.stringify({ modo: mode })
    });
  }
}

async function discardPendingHybrid() {
  if (!session.pendingHybrid) return;
  const id = session.pendingHybrid.coleccion_id;
  session.pendingHybrid = null;
  try { await api("/colecciones/" + id, { method: "DELETE" }); }
  catch { /* Puede haber vencido mientras se revisaba el alcance. */ }
}

function filesSummary() {
  const files = Array.from(ui.uploadFiles.files);
  return files.length ? files.map(file => file.name).join(" · ") : "No hay archivos seleccionados.";
}

function chooseOrigin(origin) {
  if (session.busy) return;
  discardPendingHybrid();
  session.selectedOrigin = origin;
  ui.uploadPanel.hidden = origin !== "carga";
  ui.suggestions.hidden = origin !== "ejemplo";
  ui.collectionHint.textContent = origin === "carga" ?
    "La pregunta queda en este servidor hasta que autorices un envío a OpenAI." :
    "El ejemplo es ficticio y no contiene datos personales.";
  ui.useExample.classList.toggle("active", origin === "ejemplo");
  ui.useUpload.classList.toggle("active", origin === "carga");
  ui.useExample.setAttribute("aria-pressed", String(origin === "ejemplo"));
  ui.useUpload.setAttribute("aria-pressed", String(origin === "carga"));
  ui.question.value = "";
  ui.counter.textContent = "0 / 500";
  clearResults();
  ui.emptyState.hidden = false;
}

ui.useExample.addEventListener("click", () => chooseOrigin("ejemplo"));
ui.useUpload.addEventListener("click", () => chooseOrigin("carga"));
ui.uploadFiles.addEventListener("change", () => {
  ui.uploadSummary.textContent = filesSummary();
  if (session.origin === "carga") session.mode = null;
  discardPendingHybrid();
  clearResults();
  ui.emptyState.hidden = false;
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
    ui.emptyState.hidden = false;
    status("Colección y archivos eliminados.", false);
  } catch (error) { status(error.message, true); }
});

async function openSource(number) {
  if (!session.id || !session.queryId) return;
  try {
    const data = await api("/colecciones/" + session.id + "/consultas/" + session.queryId + "/fuentes/" + number);
    const source = data.fuente;
    ui.sourceKind.textContent = source.tipo_fuente === "documento" ? "Documento" : "Código";
    ui.sourceTitle.textContent = source.titulo || source.simbolo;
    ui.sourceLocation.textContent = locationOf(source);
    ui.sourceCode.textContent = source.codigo;
    showOverlay(ui.sourceDialog);
  } catch (error) {
    status(error.message, true);
  }
}
ui.closeSource.addEventListener("click", () => hideOverlay(ui.sourceDialog));
ui.closeSourceTop.addEventListener("click", () => hideOverlay(ui.sourceDialog));
ui.sourceDialog.addEventListener("click", event => {
  if (event.target === ui.sourceDialog) hideOverlay(ui.sourceDialog);
});

function renderSources(sources, seconds) {
  session.sources = sources;
  ui.results.hidden = false;
  ui.resultCount.textContent = "(" + sources.length + ")";
  ui.sources.replaceChildren();
  if (!sources.length) {
    const message = document.createElement("p");
    message.className = "status-message";
    message.textContent = "No encontré fragmentos relacionados. Podés reformular la pregunta.";
    ui.sources.append(message);
  }
  sources.forEach((source, index) => {
    const button = document.createElement("button");
    button.type = "button";
    button.className = "source-card";
    const top = document.createElement("span");
    top.className = "source-top";
    const kind = document.createElement("span");
    kind.className = "source-kind";
    kind.textContent = source.tipo_fuente === "documento" ? "Documento" : "Código";
    const number = document.createElement("span");
    number.className = "source-number";
    number.textContent = String(index + 1).padStart(2, "0") + " ↗";
    top.append(kind, number);
    const title = document.createElement("strong");
    title.textContent = source.titulo || source.simbolo;
    const place = document.createElement("small");
    place.textContent = locationOf(source);
    const excerpt = document.createElement("p");
    excerpt.textContent = source.texto || source.codigo;
    button.append(top, title, place, excerpt);
    button.addEventListener("click", () => openSource(index + 1));
    ui.sources.append(button);
  });
  ui.resultFoot.textContent = "Recuperación: " + Number(seconds || 0).toFixed(3) + " s · Revisá cada cita antes de usar la respuesta.";
}

function renderAnswer(data) {
  ui.answer.replaceChildren();
  ui.answer.classList.toggle("abstain", Boolean(data.abstencion));
  const heading = document.createElement("h4");
  heading.textContent = data.abstencion ? "Sin evidencia suficiente" : "Respuesta";
  const paragraph = document.createElement("p");
  paragraph.textContent = data.abstencion ?
    "Las fuentes recuperadas no alcanzan para responder con seguridad." :
    data.respuesta;
  ui.answer.append(heading, paragraph);
  if (!data.abstencion) {
    (data.citas || []).forEach(number => {
      const citation = document.createElement("button");
      citation.type = "button";
      citation.className = "citation";
      citation.textContent = "[" + number + "]";
      citation.setAttribute("aria-label", "Abrir fuente " + number);
      citation.addEventListener("click", () => openSource(number));
      paragraph.append(citation);
    });
  }
  ui.answer.hidden = false;
  ui.resultSummary.textContent = data.abstencion ? "El asistente se abstuvo de responder." : "Respuesta generada a partir de " + session.sources.length + " fuentes.";
  ui.sendPanel.hidden = true;
  ui.translatePanel.hidden = true;
  ui.answerStage.focus({ preventScroll: true });
  ui.answerStage.scrollIntoView({ behavior: "smooth", block: "start" });
  if (Number(data.tiempos.modelo || 0) > 0)
    ui.resultFoot.textContent += " · Modelo: " + Number(data.tiempos.modelo).toFixed(3) + " s";
}

function showSendPreview() {
  ui.sendPreview.replaceChildren();
  const questionTitle = document.createElement("strong");
  questionTitle.textContent = "Pregunta";
  const questionText = document.createElement("pre");
  questionText.textContent = session.question;
  ui.sendPreview.append(questionTitle, questionText);
  session.sources.forEach((source, index) => {
    const title = document.createElement("strong");
    title.textContent = "Fuente " + (index + 1) + " · " + (source.titulo || source.simbolo) + " · " + locationOf(source);
    const code = document.createElement("pre");
    code.textContent = source.codigo;
    ui.sendPreview.append(title, code);
  });
}

function showNextSteps() {
  const count = session.sources.length;
  session.previousActions = null;
  ui.results.hidden = false;
  ui.answer.hidden = true;
  ui.sendPanel.hidden = true;
  ui.translatePanel.hidden = true;
  ui.hybridArea.hidden = !session.modelAvailable || session.mode === "completo";
  ui.hybridButton.hidden = session.mode === "completo";
  if (count) {
    ui.resultSummary.textContent = "Encontré " + count + " fuente" + (count === 1 ? "" : "s") + ". Podés generar una respuesta o revisar los fragmentos debajo.";
    ui.sourcesSection.open = false;
    if (session.modelAvailable) {
      ui.sendSummary.textContent = "Para responder, se enviarán tu pregunta y estos " + count + " fragmentos a OpenAI. Podés ver el texto exacto antes de enviarlo.";
      showSendPreview();
      ui.sendPanel.hidden = false;
    } else {
      ui.resultSummary.textContent += " La generación no está disponible ahora.";
    }
  } else {
    ui.resultSummary.textContent = "No encontré fuentes suficientes para responder. Podés reformular la pregunta.";
    ui.sourcesSection.open = false;
    if (session.mode === "acotado" && session.modelAvailable && session.question.includes("¿")) {
      ui.translatePreview.textContent = session.question;
      ui.translatePanel.hidden = false;
    }
  }
  ui.answerStage.focus({ preventScroll: true });
  ui.answerStage.scrollIntoView({ behavior: "smooth", block: "start" });
}

async function search() {
  if (session.busy) return;
  const question = ui.question.value.trim();
  if (!question) { status("Escribí una pregunta para buscar fuentes.", true); ui.question.focus(); return; }
  clearResults();
  setBusy(true);
  try {
    await ensureCollection("acotado");
    status("Buscando fuentes en este servidor…", false);
    const query = await api("/colecciones/" + session.id + "/consultas", {
      method: "POST", body: JSON.stringify({ pregunta: question })
    });
    session.question = question;
    session.queryId = query.consulta_id;
    renderSources(query.fuentes, query.tiempos.recuperacion);
    showNextSteps();
    status("Búsqueda local lista. No se llamó a OpenAI.", false);
  } catch (error) { status(error.message, true); }
  finally { setBusy(false); }
}

async function generateAnswer() {
  if (session.busy || !session.queryId || !session.sources.length) return;
  setBusy(true);
  try {
    status("Generando y verificando la respuesta…", false);
    const answer = await api("/colecciones/" + session.id + "/consultas/" + session.queryId + "/respuesta", {
      method: "POST", body: JSON.stringify({ autorizacion: session.mode === "completo" ? "INDEXAR" : "ENVIAR" })
    });
    renderAnswer(answer);
    status(answer.abstencion ? "El modelo se abstuvo por falta de evidencia." : "Respuesta lista. Abrí las citas para revisar las fuentes.", false);
  } catch (error) { status(error.message, true); }
  finally { setBusy(false); }
}

async function translateQuestion() {
  if (session.busy || !session.queryId || session.sources.length) return;
  setBusy(true);
  try {
    status("Traduciendo la pregunta y buscando fuentes…", false);
    const translated = await api("/colecciones/" + session.id + "/consultas/" + session.queryId + "/traduccion", {
      method: "POST", body: JSON.stringify({ autorizacion: "ENVIAR" })
    });
    renderSources(translated.fuentes, translated.tiempos.recuperacion);
    showNextSteps();
    if (!translated.fuentes.length) ui.translatePanel.hidden = true;
    status(translated.fuentes.length ? "Búsqueda ampliada lista." : "La traducción tampoco encontró fuentes; probá otra pregunta.", false);
  } catch (error) { status(error.message, true); }
  finally { setBusy(false); }
}

async function prepareHybrid() {
  if (session.busy || !session.queryId || !session.modelAvailable) return;
  setBusy(true);
  try {
    const created = await createCollection("completo");
    session.pendingHybrid = created;
    showScope(created.alcance);
    const prepared = session.selectedOrigin === "ejemplo" && session.indexAvailable;
    ui.hybridTitle.textContent = prepared ? "Usar el índice del ejemplo" : "Preparar la búsqueda híbrida";
    ui.hybridDetailsLabel.textContent = prepared ? "Ver la pregunta y el índice usado" : "Ver la pregunta y los archivos que se indexarán";
    ui.hybridQuestion.textContent = "Pregunta que se enviará: “" + session.question + "”";
    ui.indexButton.firstChild.textContent = prepared ? "Enviar pregunta y buscar con IA " : "Enviar texto y buscar con IA ";
    ui.hybridSummary.textContent = prepared ?
      "El índice del ejemplo ya está preparado. Al autorizar, solo se enviará tu pregunta a OpenAI para calcular su vector; los archivos no se reenviarán." :
      "Al autorizar, se enviarán a OpenAI el texto permitido de estos archivos para calcular embeddings y tu pregunta para buscar. Revisá el alcance debajo.";
    session.previousActions = {
      send: !ui.sendPanel.hidden,
      translate: !ui.translatePanel.hidden,
      summary: ui.resultSummary.textContent
    };
    ui.sendPanel.hidden = true;
    ui.translatePanel.hidden = true;
    ui.resultSummary.textContent = "Revisá qué se enviará para mejorar la búsqueda. Después podrás generar una respuesta con las nuevas fuentes.";
    ui.hybridPanel.hidden = false;
    ui.hybridButton.hidden = true;
    status("Revisá el alcance y decidí si querés enviar el contenido.", false);
  } catch (error) { status(error.message, true); }
  finally {
    setBusy(false);
    if (!ui.hybridPanel.hidden) ui.indexButton.focus();
  }
}

async function runHybrid() {
  if (session.busy || !session.pendingHybrid) return;
  setBusy(true);
  const next = session.pendingHybrid;
  try {
    status("Buscando con el índice…", false);
    const query = await api("/colecciones/" + next.coleccion_id + "/consultas", {
      method: "POST", body: JSON.stringify({ pregunta: session.question, autorizacion: "INDEXAR" })
    });
    const oldId = session.id;
    session.id = next.coleccion_id;
    session.mode = "completo";
    session.queryId = query.consulta_id;
    session.pendingHybrid = null;
    ui.hybridPanel.hidden = true;
    renderSources(query.fuentes, query.tiempos.recuperacion);
    showNextSteps();
    status("Búsqueda híbrida lista. Para generar respuesta, revisá el contenido y autorizá el siguiente envío.", false);
    if (oldId) api("/colecciones/" + oldId, { method: "DELETE" }).catch(() => {});
  } catch (error) { status(error.message, true); }
  finally { setBusy(false); }
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
    ui.translatePanel.hidden = !previous.translate;
    ui.resultSummary.textContent = previous.summary;
  }
  setBusy(false);
  ui.hybridButton.focus();
  status("Búsqueda híbrida cancelada. No se envió contenido a OpenAI.", false);
}

ui.searchButton.addEventListener("click", search);
ui.answerButton.addEventListener("click", generateAnswer);
ui.translateButton.addEventListener("click", translateQuestion);
ui.hybridButton.addEventListener("click", prepareHybrid);
ui.indexButton.addEventListener("click", runHybrid);
ui.cancelIndex.addEventListener("click", cancelHybrid);
ui.question.addEventListener("input", () => {
  ui.counter.textContent = ui.question.value.length + " / 500";
  if (session.question && ui.question.value.trim() !== session.question) {
    discardPendingHybrid();
    clearResults();
    ui.emptyState.hidden = false;
  }
});
ui.question.addEventListener("keydown", event => {
  if (event.key === "Enter" && event.ctrlKey) { event.preventDefault(); search(); }
});

async function initialize() {
  try {
    const [state, questions] = await Promise.all([
      api("/estado"),
      api("/preguntas-ejemplo")
    ]);
    session.modelAvailable = state.modelo_disponible;
    session.indexAvailable = state.indice_ejemplo_preparado;
    ui.apiState.textContent = state.modelo_disponible ? "Modelo disponible" : "Solo búsqueda";
    if (!state.modelo_disponible) ui.apiState.classList.add("offline");
    questions.forEach(item => {
      const button = document.createElement("button");
      button.type = "button";
      button.className = "suggestion";
      button.textContent = item.categoria + " · " + item.pregunta;
      button.title = item.descripcion;
      button.addEventListener("click", () => {
        ui.question.value = item.pregunta;
        ui.counter.textContent = ui.question.value.length + " / 500";
        discardPendingHybrid();
        clearResults();
        ui.emptyState.hidden = false;
        ui.question.focus();
      });
      ui.suggestions.append(button);
    });
  } catch (error) {
    ui.apiState.textContent = "Sin conexión";
    ui.apiState.classList.add("offline");
    status("No se pudo conectar con la API: " + error.message, true);
  }
}
initialize();


const benchmarkData = [
  { name: "Búsqueda local", detail: "Coincidencia léxica", first: 6, coverage: 5, negative: 2 },
  { name: "Embeddings OpenAI", detail: "Búsqueda semántica", first: 6, coverage: 7, negative: 0 },
  { name: "Búsqueda híbrida", detail: "Léxica + semántica", first: 6, coverage: 7, negative: 0 }
];
const benchmarkMetrics = {
  first: { title: "La fuente esperada aparece primera", count: 7, denominator: "7 preguntas respondibles", note: "Los tres modos aciertan 6 de 7 y fallan en la misma pregunta. Este empate no significa que recuperen las mismas fuentes después del primer puesto." },
  coverage: { title: "Todas las fuentes esperadas entre cinco", count: 7, denominator: "7 preguntas respondibles", note: "En cada pregunta, cuenta solo si todas las fuentes esperadas aparecen entre los cinco primeros resultados. Aquí se ve la diferencia: 5/7 en léxico y 7/7 en semántico e híbrido." },
  negative: { title: "Ninguna fuente cuando no había respuesta", count: 2, denominator: "2 preguntas sin respuesta", note: "Mide solo la recuperación: la búsqueda léxica no devolvió fuentes en las 2 preguntas; semántica e híbrida sí devolvieron candidatos en ambas y por eso marcan 0/2. El modelo puede abstenerse después, aunque el buscador haya devuelto fuentes." }
};
function renderBenchmark(metricKey) {
  const metric = benchmarkMetrics[metricKey];
  const chart = document.getElementById("benchmarkChart");
  if (!metric || !chart) return;
  document.getElementById("benchmarkTitle").textContent = metric.title;
  document.getElementById("benchmarkDenominator").textContent = metric.denominator;
  document.getElementById("benchmarkNote").textContent = metric.note;
  chart.replaceChildren();
  benchmarkData.forEach((mode) => {
    const row = document.createElement("div");
    row.className = "benchmark-row";
    const label = document.createElement("div");
    label.className = "benchmark-label";
    label.textContent = mode.name;
    const small = document.createElement("small");
    small.textContent = mode.detail;
    label.append(small);
    const track = document.createElement("div");
    track.className = "benchmark-track";
    const bar = document.createElement("div");
    bar.className = "benchmark-bar";
    bar.style.width = `${(mode[metricKey] / metric.count) * 100}%`;
    track.append(bar);
    const value = document.createElement("span");
    value.className = "benchmark-value";
    value.textContent = `${mode[metricKey]}/${metric.count}`;
    row.append(label, track, value);
    chart.append(row);
  });
  const axis = document.createElement("div");
  axis.className = "benchmark-axis";
  const axisInner = document.createElement("div");
  axisInner.className = "benchmark-axis-inner";
  ["0%", "25%", "50%", "75%", "100%"].forEach((tick) => {
    const span = document.createElement("span");
    span.textContent = tick;
    axisInner.append(span);
  });
  axis.append(axisInner);
  chart.append(axis);
  document.querySelectorAll(".metric-choice").forEach((button) => {
    const active = button.dataset.metric === metricKey;
    button.classList.toggle("is-active", active);
    button.setAttribute("aria-pressed", String(active));
  });
}
document.querySelectorAll(".metric-choice").forEach((button) => {
  button.addEventListener("click", () => renderBenchmark(button.dataset.metric));
});
renderBenchmark("coverage");
