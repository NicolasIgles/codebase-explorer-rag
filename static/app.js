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
  resultCount: document.getElementById("resultCount"),
  sources: document.getElementById("sources"),
  answer: document.getElementById("answer"),
  resultFoot: document.getElementById("resultFoot"),
  consentDialog: document.getElementById("ragApprovalLayer"),
  consentTitle: document.getElementById("consentTitle"),
  consentText: document.getElementById("consentText"),
  consentDetails: document.getElementById("consentDetails"),
  confirmConsent: document.getElementById("confirmConsent"),
  cancelConsent: document.getElementById("cancelConsent"),
  cancelConsentTop: document.getElementById("cancelConsentTop"),
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

let session = { id: null, mode: null, origin: null, selectedOrigin: "ejemplo", queryId: null, sources: [], modelAvailable: false, indexAvailable: false, busy: false };
let consentResolve = null;
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
  const overlay = [ui.consentDialog, ui.sourceDialog].find(item => !item.hidden);
  if (!overlay) return;
  if (event.key === "Escape") {
    event.preventDefault();
    if (overlay === ui.consentDialog) finishConsent(false);
    else hideOverlay(overlay);
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

function selectedMode() {
  return document.querySelector('input[name="modo"]:checked').value;
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

function status(message, error) {
  ui.status.textContent = message;
  ui.status.classList.toggle("error", Boolean(error));
  ui.status.hidden = !message;
}

function setBusy(value) {
  session.busy = value;
  ui.searchButton.disabled = value;
  ui.searchButton.firstChild.textContent = value ? "Consultando… " : "Buscar fuentes ";
  document.querySelectorAll('input[name="modo"]').forEach(input => { input.disabled = value; });
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
  ui.scope.hidden = true;
  ui.answer.hidden = true;
  ui.sources.replaceChildren();
  ui.resultFoot.textContent = "";
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
  ui.scope.hidden = false;
}

function askConsent(title, message, details, confirmLabel) {
  ui.consentTitle.textContent = title;
  ui.consentText.textContent = message;
  ui.consentDetails.replaceChildren();
  const list = document.createElement("ul");
  details.forEach(detail => {
    const item = document.createElement("li");
    item.textContent = detail;
    list.append(item);
  });
  ui.consentDetails.append(list);
  ui.confirmConsent.firstChild.textContent = confirmLabel + " ";
  showOverlay(ui.consentDialog);
  return new Promise(resolve => { consentResolve = resolve; });
}

function finishConsent(value) {
  if (consentResolve) {
    const resolve = consentResolve;
    consentResolve = null;
    hideOverlay(ui.consentDialog);
    resolve(value);
  }
}
ui.confirmConsent.addEventListener("click", () => finishConsent(true));
ui.cancelConsent.addEventListener("click", () => finishConsent(false));
ui.cancelConsentTop.addEventListener("click", () => finishConsent(false));
ui.consentDialog.addEventListener("click", event => {
  if (event.target === ui.consentDialog) finishConsent(false);
});

async function ensureCollection(mode) {
  const origin = session.selectedOrigin;
  if (session.id && session.mode === mode && session.origin === origin) return null;
  if (session.id) {
    try { await api("/colecciones/" + session.id, { method: "DELETE" }); }
    catch { /* La colección también puede haber vencido. */ }
    session.id = null;
  }
  let created;
  if (origin === "carga") {
    const files = Array.from(ui.uploadFiles.files);
    if (!files.length) throw new Error("Elegí archivos antes de consultar tu colección.");
    if (files.length > 5 || files.some(file => file.size > 10_000_000))
      throw new Error("Se admiten hasta cinco archivos de 10 MB cada uno.");
    const form = new FormData();
    form.append("modo", mode);
    files.forEach(file => form.append("archivos", file));
    status("Preparando la colección temporal…", false);
    created = await api("/cargas/colecciones", { method: "POST", body: form });
  } else {
    created = await api("/ejemplo/colecciones", {
      method: "POST", body: JSON.stringify({ modo: mode })
    });
  }
  session.id = created.coleccion_id;
  session.mode = mode;
  session.origin = origin;
  session.queryId = null;
  ui.deleteUpload.hidden = origin !== "carga";
  if (origin === "carga") ui.uploadSummary.textContent = filesSummary() + " · Colección lista; se borra antes de 24 horas o si el servicio se duerme o reinicia.";
  return created;
}

function filesSummary() {
  const files = Array.from(ui.uploadFiles.files);
  return files.length ? files.map(file => file.name).join(" · ") : "No hay archivos seleccionados.";
}

function chooseOrigin(origin) {
  if (session.busy) return;
  session.selectedOrigin = origin;
  ui.uploadPanel.hidden = origin !== "carga";
  ui.suggestions.hidden = origin !== "ejemplo";
  ui.collectionHint.textContent = origin === "carga" ?
    "La pregunta queda en este servidor salvo que autorices un modo con OpenAI." :
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
});
ui.deleteUpload.addEventListener("click", async () => {
  if (!session.id || session.origin !== "carga") return;
  try {
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
  ui.resultCount.textContent = sources.length + " / 5";
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
  ui.resultFoot.textContent = "Recuperación: " + Number(seconds || 0).toFixed(3) + " s · Las citas son fuentes consultadas, no una garantía de veracidad.";
}

function renderAnswer(data) {
  ui.answer.replaceChildren();
  ui.answer.classList.toggle("abstain", Boolean(data.abstencion));
  const heading = document.createElement("h4");
  heading.textContent = data.abstencion ? "Sin evidencia suficiente" : "Respuesta con fuentes";
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
  if (Number(data.tiempos.modelo || 0) > 0)
    ui.resultFoot.textContent += " · Modelo: " + Number(data.tiempos.modelo).toFixed(3) + " s";
}

async function search() {
  if (session.busy) return;
  const question = ui.question.value.trim();
  if (!question) { status("Escribí una pregunta para buscar fuentes.", true); ui.question.focus(); return; }
  clearResults();
  setBusy(true);
  const mode = selectedMode();
  try {
    const created = await ensureCollection(mode);
    if (created && mode === "completo") showScope(created.alcance);
    let permission = null;
    if (mode === "completo") {
      const scope = created ? created.alcance : await api("/colecciones/" + session.id + "/alcance");
      showScope(scope);
      if (!session.modelAvailable) {
        status("El servidor no tiene OPENAI_API_KEY para la búsqueda híbrida.", true);
        return;
      }
      const prepared = session.selectedOrigin === "ejemplo" && session.indexAvailable;
      const approved = await askConsent(
        prepared ? "Buscar con el índice preparado" : "Indexar la colección",
        prepared ?
          "El índice del ejemplo ya está preparado. Solo se enviará tu pregunta a OpenAI para calcular su vector; el código y los documentos no se reenviarán en este paso." :
          "Se enviarán a OpenAI el código y la documentación permitidos para calcular embeddings. La pregunta también se enviará para su vector.",
        scope.rutas,
        prepared ? "Buscar con OpenAI" : "INDEXAR y buscar"
      );
      if (!approved) { status("Indexación cancelada. No se envió contenido.", false); return; }
      permission = "INDEXAR";
    }
    status("Buscando fragmentos y ubicaciones…", false);
    const query = await api("/colecciones/" + session.id + "/consultas", {
      method: "POST",
      body: JSON.stringify({ pregunta: question, autorizacion: permission })
    });
    session.queryId = query.consulta_id;
    renderSources(query.fuentes, query.tiempos.recuperacion);
    let sources = query.fuentes;
    if (mode === "acotado" && !sources.length && question.includes("¿") && session.modelAvailable) {
      const approved = await askConsent(
        "Ampliar la búsqueda",
        "La pregunta se enviará a OpenAI para traducirla. No se enviará código en este paso.",
        [question],
        "ENVIAR pregunta"
      );
      if (approved) {
        status("Traduciendo la pregunta…", false);
        const translated = await api("/colecciones/" + session.id + "/consultas/" + session.queryId + "/traduccion", {
          method: "POST",
          body: JSON.stringify({ autorizacion: "ENVIAR" })
        });
        sources = translated.fuentes;
        renderSources(sources, translated.tiempos.recuperacion);
      }
    }
    if (!sources.length) {
      renderAnswer({ abstencion: true, tiempos: { modelo: 0 } });
      status("No se encontraron fuentes para una respuesta respaldada.", false);
      return;
    }
    if (mode === "local") { status("Se mostraron fuentes sin llamar a OpenAI.", false); return; }
    if (!session.modelAvailable) {
      status("El servidor no tiene OPENAI_API_KEY. Podés revisar las fuentes sin generación.", true);
      return;
    }
    const approved = await askConsent(
      "Generar respuesta",
      "Se enviarán la pregunta y los fragmentos mostrados a OpenAI. El modelo responderá con citas o se abstendrá.",
      sources.map(source => locationOf(source)),
      mode === "completo" ? "INDEXAR y responder" : "ENVIAR y responder"
    );
    if (!approved) { status("Respuesta cancelada. Las fuentes siguen disponibles.", false); return; }
    status("Validando la respuesta con las fuentes…", false);
    const answer = await api("/colecciones/" + session.id + "/consultas/" + session.queryId + "/respuesta", {
      method: "POST",
      body: JSON.stringify({ autorizacion: mode === "completo" ? "INDEXAR" : "ENVIAR" })
    });
    renderAnswer(answer);
    status(answer.abstencion ? "El modelo se abstuvo por falta de evidencia." : "Respuesta lista. Abrí las citas para revisar las fuentes.", false);
  } catch (error) {
    status(error.message, true);
  } finally {
    setBusy(false);
  }
}

ui.searchButton.addEventListener("click", search);
ui.question.addEventListener("input", () => { ui.counter.textContent = ui.question.value.length + " / 500"; });
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
