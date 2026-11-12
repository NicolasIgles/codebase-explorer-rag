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
  resultsTitle: $("resultsTitle"),
  resultsQuestion: $("resultsQuestion"),
  comparisonSummary: $("comparisonSummary"),
  laneSwitch: $("laneSwitch"),
  resultFoot: $("resultFoot"),
  sourceDialog: $("sourceDialog"),
  sourceKind: $("sourceKind"),
  sourceTitle: $("sourceTitle"),
  sourceLocation: $("sourceLocation"),
  sourceCode: $("sourceCode"),
  closeSource: $("closeSource"),
  closeSourceTop: $("closeSourceTop")
};

const MODES = ["acotado", "completo"];
const LANE_NAME = { acotado: "Por palabras", completo: "Híbrida" };
const LANE_SHORT = { acotado: "Por palabras", completo: "Híbrida" };

function newLane(mode) {
  return {
    mode, status: "empty", collectionId: null, queryId: null, pending: null,
    sources: [], seconds: 0, matchQuestion: null, translated: null,
    answer: null, answerStatus: "none", animate: false, animateAnswer: false, error: ""
  };
}

const session = {
  selectedOrigin: "ejemplo", origin: null, question: "",
  modelAvailable: false, indexAvailable: false, busy: false, suggestions: [],
  lanes: { acotado: newLane("acotado"), completo: newLane("completo") },
  lastLane: "acotado", visibleLane: "acotado"
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

function button(className, text, onClick) {
  const node = el("button", className, text);
  node.type = "button";
  if (onClick) node.addEventListener("click", onClick);
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

function formatSeconds(seconds) {
  const value = Number(seconds || 0);
  if (value < 1) return Math.max(1, Math.round(value * 1000)).toLocaleString("es-AR") + " ms";
  return value.toLocaleString("es-AR", { maximumFractionDigits: 1 }) + " s";
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

function stopIntro() { ui.stages.classList.remove("intro"); }

/* Las etapas de arriba muestran la búsqueda con la que se trabajó por última vez. */
function renderStages() {
  const lane = session.lanes[session.lastLane];
  const prefix = LANE_SHORT[lane.mode] + ": ";
  const count = lane.sources.length;
  if (lane.status === "empty" || lane.status === "preparing" || lane.status === "authorizing") return;
  if (lane.status === "loading") {
    setStage("recuperar", "active", prefix + (lane.mode === "completo" ? "buscando por palabras y por significado…" : "buscando en el código y los documentos…"));
    setStage("contexto", "idle");
    setStage("responder", "idle");
    return;
  }
  if (lane.status === "error") { resetStages(); return; }
  setStage("recuperar", "done", prefix + (count ? plural(count, "fragmento encontrado", "fragmentos encontrados") : "ningún fragmento coincide"));
  if (!count) {
    setStage("contexto", "skipped", "Sin fragmentos, no hay nada que armar");
    setStage("responder", "abstained", "No respondió, por falta de evidencia");
    return;
  }
  if (!session.modelAvailable) {
    setStage("contexto", "done", "Tu pregunta y " + plural(count, "fragmento") + ", listos para el modelo");
    setStage("responder", "skipped", "Necesita una clave de OpenAI en el servidor");
    return;
  }
  if (lane.answerStatus === "none") {
    setStage("contexto", "waiting", prefix + "revisá lo que recibiría el modelo");
    setStage("responder", "idle");
  } else {
    setStage("contexto", "done", prefix + "enviaste tu pregunta y " + plural(count, "fragmento"));
    if (lane.answerStatus === "loading") setStage("responder", "active", prefix + "generando la respuesta y comprobando las citas…");
    else if (lane.answer.abstencion) setStage("responder", "abstained", prefix + "no respondió, por falta de evidencia");
    else setStage("responder", "done", prefix + "usó " + lane.answer.citas.length + " de los " + plural(count, "fragmento"));
  }
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

function serverPlace(source) {
  const place = source.ubicacion || {};
  const base = place.tipo === "pagina" ? source.ruta + ":página " + place.pagina : source.ruta + ":" + source.inicio + "-" + source.fin;
  return place.columna_inicio != null ? base + ":columnas " + place.columna_inicio + "-" + place.columna_fin : base;
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

/* Cómo cambió cada fragmento entre la búsqueda por palabras y la híbrida. */
function comparisonFor(mode) {
  const lexical = session.lanes.acotado;
  const hybrid = session.lanes.completo;
  if (lexical.status !== "ready" || hybrid.status !== "ready") return null;
  const rank = lane => new Map(lane.sources.map((source, index) => [sourceKey(source), index + 1]));
  return { own: mode === "completo" ? rank(lexical) : rank(hybrid) };
}

function diffBadge(mode, source, position, comparison) {
  if (!comparison) return null;
  const other = comparison.own.get(sourceKey(source));
  if (mode === "completo") {
    if (!other) return el("span", "insignia insignia-nueva", "Nuevo");
    if (other > position) return el("span", "insignia insignia-sube", "Subió " + (other - position));
    if (other < position) return el("span", "insignia insignia-baja", "Bajó " + (position - other));
    return null;
  }
  return other ? null : el("span", "insignia insignia-afuera", "No está en la híbrida");
}

function sourceCard(mode, source, index, top, comparison) {
  const lane = session.lanes[mode];
  const number = index + 1;
  const card = el("article", "fragmento");
  card.id = "frag-" + mode + "-" + number;
  card.style.setProperty("--i", index);
  if (!lane.animate) card.style.animation = "none";
  card.setAttribute("aria-label", "Fragmento " + number + ": " + source.ruta + ", " + placeOf(source));

  const answered = lane.answerStatus === "ready" && !lane.answer.abstencion;
  const cited = answered && lane.answer.citas.includes(number);
  if (answered) card.classList.add(cited ? "citado" : "no-citado");

  const head = el("div", "fragmento-cabeza");
  const path = el("span", "fragmento-ruta", source.ruta + " ");
  path.append(el("span", "", placeOf(source)));
  const badges = el("span", "insignias");
  if (answered) badges.append(cited ? el("span", "insignia insignia-citado", "Citado") : el("span", "insignia", "No citado"));
  const diff = diffBadge(mode, source, number, comparison);
  if (diff) badges.append(diff);
  if (!lane.animate && !lane.animateAnswer) badges.querySelectorAll(".insignia").forEach(node => { node.style.animation = "none"; });
  head.append(path, badges);

  const name = el("p", "fragmento-simbolo", "[" + number + "] " + kindOf(source) + " " + (source.titulo || source.simbolo));
  const isText = source.tipo_fuente === "documento";
  const allLines = parseLines(source);
  const preview = isText ? allLines.filter(line => line.text.trim()) : allLines;
  const block = codeBlock(preview, isText, isText ? 3 : 5);
  if (cited) {
    const lines = block.querySelectorAll(".linea");
    if (lane.animateAnswer) requestAnimationFrame(() => requestAnimationFrame(() => lines.forEach(line => line.classList.add("marcada"))));
    else lines.forEach(line => { line.style.transition = "none"; line.classList.add("marcada"); });
  }

  const reason = el("p", "razon");
  const terms = matchedTerms(lane.matchQuestion || session.question, source);
  if (terms.length) {
    reason.append("Por qué apareció: coincide con ");
    terms.slice(0, 4).forEach((term, i, list) => {
      if (i > 0) reason.append(i === list.length - 1 ? " y " : ", ");
      reason.append(el("mark", "termino", term));
    });
  } else {
    reason.append(mode === "completo" ? "Por qué apareció: se parece en significado a tu pregunta" : "Por qué apareció: coincide con partes del nombre o la ruta");
  }

  const ratio = top > 0 ? (Number(source.puntuacion) || 0) / top : 0;
  const meter = el("div", "relevancia");
  const track = el("div", "relevancia-pista");
  const bar = el("div", "relevancia-barra" + (ratio < 0.3 ? " baja" : ""));
  const width = Math.max(4, Math.round(ratio * 100)) + "%";
  if (lane.animate) {
    bar.style.setProperty("--i", index);
    requestAnimationFrame(() => requestAnimationFrame(() => { bar.style.width = width; }));
  } else {
    bar.style.transition = "none";
    bar.style.width = width;
  }
  track.append(bar);
  meter.append(track, el("span", "relevancia-texto", relevanceText(index, ratio)));

  const more = button("boton-texto ver-completo", "Ver el fragmento completo", () => openSource(mode, number));
  card.append(head, name, block, reason, meter, more);
  return card;
}

/* ---------- el contexto que recibe el modelo ---------- */

const MODEL_INSTRUCTIONS =
  "Decidí si alguno de los fragmentos realmente contiene evidencia para responder. " +
  "Un nombre parecido no alcanza. Si hay evidencia, respondé en español de forma breve " +
  "y poné en fuentes solo los números que respaldan la respuesta; no agregues citas al texto. " +
  "Si no hay evidencia suficiente, usá hay_evidencia=false, respuesta vacía y fuentes vacías. " +
  "No inventes comportamiento que no figure en los fragmentos.";

/* Mismo formato que preparar_consulta (validar_evidencia.py). */
function contextText(lane) {
  const blocks = lane.sources.map((source, index) => {
    const name = [source.contenedor, source.simbolo].filter(Boolean).join(".");
    return "[" + (index + 1) + "] " + serverPlace(source) + " (" + name + ")\n" + (source.codigo || "");
  });
  return "Pregunta: " + session.question + "\n\nFuentes:\n" + blocks.join("\n\n");
}

function disclosure(summary, text, label) {
  const details = el("details", "desplegable");
  details.append(el("summary", "", summary));
  const body = el("div", "contexto-texto", text);
  body.tabIndex = 0;
  body.setAttribute("aria-label", label);
  details.append(body);
  return details;
}

function chip(mode, source, number) {
  const node = button("ficha", "", () => focusSource(mode, number));
  node.append(el("b", "", "[" + number + "]"), source.ruta.split("/").pop() + " " + shortPlace(source));
  node.setAttribute("aria-label", "Fragmento " + number + ": " + source.ruta + ", " + placeOf(source) + ". Mostrarlo");
  return node;
}

function contextPackage(mode) {
  const lane = session.lanes[mode];
  const text = contextText(lane);
  const box = el("div", "paquete");
  const questionRow = el("div", "paquete-fila");
  questionRow.append(el("span", "paquete-rotulo", "Tu pregunta"), el("p", "paquete-pregunta", session.question));
  const chipsRow = el("div", "paquete-fila");
  const chips = el("div", "paquete-fragmentos");
  lane.sources.forEach((source, index) => chips.append(chip(mode, source, index + 1)));
  chipsRow.append(el("span", "paquete-rotulo", plural(lane.sources.length, "fragmento")), chips);
  box.append(questionRow, chipsRow, el("p", "paquete-tamano", "En total, " + text.length.toLocaleString("es-AR") + " caracteres: la pregunta y estos fragmentos completos. Nada más del proyecto."));
  return [box,
    disclosure("Ver la pregunta y los fragmentos tal cual se envían", text, "Pregunta y fragmentos que se envían al modelo"),
    disclosure("Ver las instrucciones fijas que acompañan cada consulta", MODEL_INSTRUCTIONS, "Instrucciones fijas para el modelo")];
}

function contextBlock(mode) {
  const lane = session.lanes[mode];
  const block = el("div", "contexto");
  block.append(el("h4", "bloque-titulo", session.modelAvailable ? "Esto es lo que recibirá el modelo" : "Esto es lo que recibiría el modelo"));
  block.append(...contextPackage(mode));
  if (!session.modelAvailable) {
    block.append(el("p", "contexto-nota", "En esta demo no se envía: el servidor no tiene una clave de OpenAI."));
    return block;
  }
  block.append(el("p", "contexto-nota", "Nada sale de este servidor hasta que tocás el botón."));
  const send = button("boton-principal", lane.answerStatus === "loading" ? "Generando la respuesta…" : "Enviar a OpenAI y responder", () => generateAnswer(mode));
  send.disabled = session.busy;
  block.append(send);
  return block;
}

/* ---------- respuesta ---------- */

function abstentionBox(title, text, withActions) {
  const box = el("div", "abstencion");
  box.append(el("h4", "", title), el("p", "", text));
  if (withActions) {
    const actions = el("div", "botonera");
    actions.append(button("boton-secundario", "Hacer otra pregunta", () => { ui.question.focus(); ui.question.select(); }));
    const good = session.suggestions.find(item => item.id === "codigo");
    if (good && session.origin === "ejemplo") actions.append(button("boton-texto", "Ver una que sí tiene respuesta", () => runSuggestion(good)));
    box.append(actions);
  }
  return box;
}

function answerBlock(mode) {
  const lane = session.lanes[mode];
  const data = lane.answer;
  const wrap = el("div", "respuesta-cuerpo");
  if (!lane.animateAnswer) wrap.style.animation = "none";
  if (data.abstencion) {
    wrap.append(abstentionBox("No hay evidencia para responder esto",
      "Ninguno de los fragmentos encontrados contesta la pregunta. En lugar de inventar, el modelo prefirió no responder: es lo que tiene que hacer un buen sistema RAG.", true));
  } else {
    const heading = el("h4", "", "Respuesta");
    heading.id = "answer-" + mode;
    heading.tabIndex = -1;
    const total = lane.sources.length;
    const text = el("p", "respuesta-texto", data.respuesta);
    const chips = el("p", "citas");
    chips.append(el("span", "", data.citas.length === 1 ? "Fuente citada" : "Fuentes citadas"));
    data.citas.forEach((number, i) => {
      const source = lane.sources[number - 1];
      const node = button("cita", source.ruta.split("/").pop() + " " + shortPlace(source), () => focusSource(mode, number));
      node.style.setProperty("--i", i);
      node.setAttribute("aria-label", "Cita " + number + ": " + source.ruta + ", " + placeOf(source) + ". Mostrar el fragmento");
      if (lane.animateAnswer) requestAnimationFrame(() => requestAnimationFrame(() => node.classList.add("marcada")));
      else { node.style.transition = "none"; node.classList.add("marcada"); }
      chips.append(node);
    });
    wrap.append(heading, text, chips,
      el("p", "respuesta-resumen", "Usó " + data.citas.length + " de los " + plural(total, "fragmento") + " que recibió."));
  }
  const sent = el("details", "desplegable");
  sent.append(el("summary", "", "Ver lo que recibió el modelo"));
  const inner = el("div", "contexto");
  inner.append(...contextPackage(mode));
  sent.append(inner);
  wrap.append(sent);
  if (data.tiempos && Number(data.tiempos.modelo || 0) > 0)
    wrap.append(el("p", "contexto-nota", "El modelo tardó " + formatSeconds(data.tiempos.modelo) + "."));
  return wrap;
}

/* ---------- columnas ---------- */

function laneHeader(mode) {
  const lane = session.lanes[mode];
  const head = el("div", "carril-cabeza");
  const title = el("h3", "", LANE_NAME[mode]);
  title.id = "lane-" + mode + "-title";
  title.tabIndex = -1;
  let detail = mode === "acotado" ? "Busca palabras en común con tu pregunta, en este servidor." : "Busca por palabras y también por significado, con OpenAI.";
  if (lane.status === "ready") {
    detail = (mode === "acotado" ? "Palabras en común, en este servidor. " : "Palabras y significado, con OpenAI. ") +
      "Tardó " + formatSeconds(lane.seconds) + ".";
    if (lane.translated) detail += " Buscó con la pregunta traducida: «" + lane.translated + "».";
  }
  head.append(title, el("p", "", detail));
  return head;
}

function hybridEmpty() {
  const box = el("div", "carril-vacio");
  if (!session.modelAvailable) {
    box.append(el("p", "", "La búsqueda híbrida necesita una clave de OpenAI en el servidor. En esta demo no está disponible."));
    return box;
  }
  box.append(el("p", "", "Busca también por significado, así encuentra fragmentos que dicen lo mismo con otras palabras. Cuando termine, vas a poder comparar las dos columnas: qué fragmentos trajo cada una y qué respondió el modelo con cada una."));
  const start = button("boton-secundario boton-hibrida", "Probar la búsqueda híbrida (usa OpenAI)", prepareHybrid);
  start.disabled = session.busy;
  start.id = "hybridStart";
  box.append(start);
  return box;
}

function hybridAuthorize() {
  const lane = session.lanes.completo;
  const prepared = session.origin === "ejemplo" && session.indexAvailable;
  const box = el("div", "contexto");
  box.append(el("h4", "bloque-titulo", "Antes de buscar"));
  box.append(el("p", "", prepared ?
    "El índice del ejemplo ya está preparado: solo se envía tu pregunta a OpenAI para calcular su vector. Los archivos no se envían." :
    "Para comparar por significado se envía a OpenAI el texto permitido de tus archivos, para calcular sus vectores, y tu pregunta."));
  const details = el("details", "desplegable");
  details.append(el("summary", "", prepared ? "Ver la pregunta que se envía" : "Ver la pregunta y los archivos que se envían"));
  const scope = el("div", "alcance");
  scope.append(el("p", "", "Pregunta: «" + session.question + "»"));
  const info = lane.pending && lane.pending.alcance;
  if (info && !prepared) {
    scope.append(el("p", "", plural(info.cantidad_fragmentos, "fragmento") + " de " + plural(info.rutas.length, "archivo") + ", unos " + Number(info.bytes_aproximados).toLocaleString("es-AR") + " bytes de texto."));
    const list = el("ul");
    info.rutas.forEach(path => list.append(el("li", "", path)));
    scope.append(list);
    const excluded = Object.keys(info.excluidos || {});
    if (excluded.length) scope.append(el("p", "", plural(excluded.length, "archivo excluido", "archivos excluidos") + " por el filtro de privacidad."));
  }
  details.append(scope);
  const actions = el("div", "botonera");
  const go = button("boton-principal", prepared ? "Enviar la pregunta y buscar" : "Enviar los archivos y buscar", runHybrid);
  go.id = "hybridGo";
  actions.append(go, button("boton-texto", "Cancelar", cancelHybrid));
  box.append(details, actions);
  return box;
}

function lexicalEmpty(lane) {
  const parts = [abstentionBox("No hay evidencia para responder esto",
    "Ninguna parte del proyecto comparte palabras con tu pregunta. Sin evidencia, el sistema no responde: prefiere no inventar." +
    (session.modelAvailable ? " Si creés que la respuesta sí está, probá la búsqueda híbrida, que también busca por significado." : " Probá con otras palabras."),
    !session.modelAvailable)];
  if (session.modelAvailable && !lane.translated && session.question.includes("¿")) {
    const box = el("div", "contexto");
    box.append(el("h4", "bloque-titulo", "Probar con la pregunta en inglés"),
      el("p", "", "El código del proyecto está escrito en inglés, así que una pregunta en castellano puede no compartir palabras con él. Podés traducirla con OpenAI y buscar de nuevo en esta columna. Solo se envía tu pregunta, ningún archivo."),
      disclosure("Ver lo que se envía", session.question, "Pregunta que se envía para traducir"));
    const go = button("boton-secundario", "Traducir la pregunta y buscar de nuevo", translateQuestion);
    go.disabled = session.busy;
    box.append(go);
    parts.push(box);
  }
  return parts;
}

function renderLane(mode) {
  const lane = session.lanes[mode];
  const container = $("lane-" + mode);
  const nodes = [laneHeader(mode)];

  if (lane.status === "loading") nodes.push(el("p", "carril-espera", mode === "completo" ? "Buscando por palabras y por significado…" : "Buscando en el código y los documentos…"));
  else if (lane.status === "preparing") nodes.push(el("p", "carril-espera", "Preparando la búsqueda híbrida…"));
  else if (lane.status === "error") nodes.push(el("p", "fragmentos-vacio", lane.error));
  else if (mode === "completo" && lane.status === "empty") nodes.push(hybridEmpty());
  else if (mode === "completo" && lane.status === "authorizing") nodes.push(hybridAuthorize());
  else if (lane.status === "ready") {
    if (!lane.sources.length) {
      if (mode === "acotado") nodes.push(...lexicalEmpty(lane));
      else nodes.push(abstentionBox("No hay evidencia para responder esto", "La búsqueda híbrida no encontró nada que se parezca lo suficiente a tu pregunta. Sin evidencia, el sistema no responde.", false));
    } else {
      if (!session.modelAvailable && mode === "acotado") {
        const notice = el("div", "aviso");
        const link = el("a", "", "Cómo correrlo en tu máquina");
        link.href = "https://github.com/NicolasIgles/codebase-explorer-rag#probar-en-local";
        link.target = "_blank";
        link.rel = "noopener noreferrer";
        notice.append(el("strong", "", "Ya viste la primera mitad de RAG"),
          el("p", "", "Esta demo está en modo solo búsqueda: no tiene una clave de OpenAI configurada. Estos fragmentos son los que recibiría el modelo para responder."), link);
        nodes.push(notice);
      }
      nodes.push(lane.answerStatus === "ready" ? answerBlock(mode) : contextBlock(mode));
      const list = el("div", "fragmentos");
      list.setAttribute("aria-label", "Fragmentos de la búsqueda " + LANE_NAME[mode].toLowerCase());
      const top = Math.max(...lane.sources.map(s => Number(s.puntuacion) || 0), 0);
      const comparison = comparisonFor(mode);
      lane.sources.forEach((source, index) => list.append(sourceCard(mode, source, index, top, comparison)));
      nodes.push(el("h4", "bloque-titulo", "Fragmentos que encontró (" + lane.sources.length + ")"), list);
    }
  }
  container.replaceChildren(...nodes);
  lane.animate = false;
  lane.animateAnswer = false;
}

function renderComparisonSummary() {
  const lexical = session.lanes.acotado;
  const hybrid = session.lanes.completo;
  if (lexical.status !== "ready" || hybrid.status !== "ready") { ui.comparisonSummary.hidden = true; return; }
  const before = lexical.sources, after = hybrid.sources;
  const beforeRank = new Map(before.map((s, i) => [sourceKey(s), i + 1]));
  const afterKeys = new Set(after.map(sourceKey));
  const added = after.filter(s => !beforeRank.has(sourceKey(s))).length;
  const dropped = before.filter(s => !afterKeys.has(sourceKey(s))).length;
  const kept = after.length - added;
  const moved = after.some((s, i) => beforeRank.has(sourceKey(s)) && beforeRank.get(sourceKey(s)) !== i + 1);
  let text;
  if (!before.length && !after.length) text = "Ninguna de las dos búsquedas encontró fragmentos.";
  else if (!before.length) text = "La búsqueda por palabras no encontró nada; la híbrida trajo " + plural(after.length, "fragmento") + ".";
  else if (!added && !dropped) text = "Las dos búsquedas trajeron los mismos " + plural(after.length, "fragmento") + (moved ? ", en otro orden." : ", en el mismo orden.");
  else {
    const parts = [];
    if (added) parts.push("trajo " + plural(added, "fragmento nuevo", "fragmentos nuevos"));
    if (kept) parts.push("mantuvo " + kept);
    if (dropped) parts.push("dejó afuera " + dropped);
    text = "Comparada con la búsqueda por palabras, la híbrida " + parts.join(", ").replace(/, ([^,]*)$/, " y $1") + ". Cada fragmento de la columna híbrida indica si es nuevo, si subió o si bajó de posición.";
  }
  ui.comparisonSummary.textContent = text;
  ui.comparisonSummary.hidden = false;
}

function renderLaneSwitch() {
  ui.laneSwitch.querySelectorAll(".carril-boton").forEach(node => {
    node.setAttribute("aria-pressed", String(node.dataset.lane === session.visibleLane));
  });
  MODES.forEach(mode => { $("lane-" + mode).dataset.visible = String(mode === session.visibleLane); });
}

function renderAll() {
  if (!session.question) { ui.results.hidden = true; return; }
  ui.results.hidden = false;
  ui.resultsQuestion.textContent = session.question;
  MODES.forEach(renderLane);
  renderComparisonSummary();
  renderLaneSwitch();
  renderStages();
  const anyAnswer = MODES.some(mode => session.lanes[mode].answerStatus === "ready" && !session.lanes[mode].answer.abstencion);
  ui.resultFoot.textContent = anyAnswer ? "Una cita dice de dónde salió algo, no garantiza que esté bien: revisá las líneas citadas." : "";
  ui.resultFoot.hidden = !anyAnswer;
}

function focusLaneElement(mode, id) {
  session.visibleLane = mode;
  renderLaneSwitch();
  const node = $(id);
  if (!node) return;
  node.focus({ preventScroll: true });
  const box = node.getBoundingClientRect();
  if (box.top < 0 || box.bottom > window.innerHeight) node.scrollIntoView({ behavior: scrollBehavior(), block: "nearest" });
}

function focusSource(mode, number) {
  session.visibleLane = mode;
  renderLaneSwitch();
  const card = $("frag-" + mode + "-" + number);
  if (!card) return;
  card.scrollIntoView({ behavior: scrollBehavior(), block: "nearest" });
  card.classList.remove("destello");
  void card.offsetWidth;
  card.classList.add("destello");
}

/* ---------- diálogo de fragmento ---------- */

let lastFocus = null;
async function openSource(mode, number) {
  const lane = session.lanes[mode];
  if (!lane.collectionId || !lane.queryId) return;
  try {
    const data = await api("/colecciones/" + lane.collectionId + "/consultas/" + lane.queryId + "/fuentes/" + number);
    const source = data.fuente;
    const cited = lane.answerStatus === "ready" && !lane.answer.abstencion && lane.answer.citas.includes(number);
    ui.sourceKind.textContent = LANE_NAME[mode] + ", fragmento " + number + (cited ? ", citado en la respuesta" : "");
    ui.sourceTitle.textContent = source.titulo || source.simbolo;
    ui.sourceLocation.textContent = source.ruta + ", " + placeOf(source);
    const isText = source.tipo_fuente === "documento";
    ui.sourceCode.replaceChildren(...codeBlock(parseLines(source), isText).childNodes);
    ui.sourceCode.classList.toggle("codigo-texto", isText);
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

/* ---------- colecciones en el servidor ---------- */

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

function collectionIds() {
  const ids = [];
  MODES.forEach(mode => {
    const lane = session.lanes[mode];
    if (lane.collectionId) ids.push(lane.collectionId);
    if (lane.pending && lane.pending.coleccion_id !== lane.collectionId) ids.push(lane.pending.coleccion_id);
  });
  return ids;
}

async function releaseCollections() {
  const ids = collectionIds();
  await Promise.all(ids.map(id => api("/colecciones/" + id, { method: "DELETE" }).catch(() => { /* puede haber vencido */ })));
}

window.addEventListener("pagehide", () => {
  collectionIds().forEach(id => {
    try { fetch("/colecciones/" + id, { method: "DELETE", keepalive: true }); }
    catch { /* el servidor la libera al vencer */ }
  });
});

function resetLanes() {
  session.lanes = { acotado: newLane("acotado"), completo: newLane("completo") };
  session.lastLane = "acotado";
  session.visibleLane = "acotado";
}

async function clearAll() {
  await releaseCollections();
  resetLanes();
  session.question = "";
  ui.deleteUpload.hidden = true;
  if (session.origin === "carga") ui.uploadSummary.textContent = filesSummary();
  resetStages();
  status("", false);
  renderAll();
}

/* ---------- acciones ---------- */

function setBusy(value) {
  session.busy = value;
  [ui.searchButton, ui.question, ui.uploadFiles, ui.useExample, ui.useUpload]
    .forEach(node => { node.disabled = value; });
  ui.suggestions.querySelectorAll("button").forEach(node => { node.disabled = value; });
  document.querySelectorAll(".carril button").forEach(node => {
    if (!node.classList.contains("ficha") && !node.classList.contains("cita") && !node.classList.contains("ver-completo")) node.disabled = value;
  });
  ui.searchButton.textContent = value ? "Buscando…" : "Buscar en el proyecto";
}

function filesSummary() {
  const files = Array.from(ui.uploadFiles.files);
  return files.length ? files.map(file => file.name).join(", ") : "Todavía no elegiste archivos.";
}

async function search() {
  if (session.busy) return;
  const question = ui.question.value.trim();
  stopIntro();
  if (!question) { status("Escribí una pregunta para buscar en el proyecto.", true); ui.question.focus(); return; }
  setBusy(true);
  status("", false);
  await releaseCollections();
  resetLanes();
  session.question = question;
  session.origin = session.selectedOrigin;
  const lane = session.lanes.acotado;
  lane.status = "loading";
  ui.stages.classList.add("con-resultado");
  renderAll();
  revealIfNeeded(ui.stages);
  try {
    const created = await createCollection("acotado");
    lane.collectionId = created.coleccion_id;
    if (session.origin === "carga") {
      ui.deleteUpload.hidden = false;
      ui.uploadSummary.textContent = filesSummary() + ". Ya están en el servidor; se borran en menos de 24 horas.";
    }
    const query = await api("/colecciones/" + lane.collectionId + "/consultas", {
      method: "POST", body: JSON.stringify({ pregunta: question })
    });
    Object.assign(lane, { status: "ready", queryId: query.consulta_id, sources: query.fuentes, seconds: query.tiempos.recuperacion, animate: true });
    renderAll();
    focusLaneElement("acotado", "lane-acotado-title");
    announce(query.fuentes.length ? plural(query.fuentes.length, "fragmento encontrado", "fragmentos encontrados") + " con la búsqueda por palabras." : "La búsqueda por palabras no encontró fragmentos. El sistema no responde sin evidencia.");
  } catch (error) {
    Object.assign(lane, { status: "error", error: "No se pudo buscar: " + error.message });
    renderAll();
    status("No se pudo buscar: " + error.message, true);
  } finally {
    setBusy(false);
  }
}

async function generateAnswer(mode) {
  const lane = session.lanes[mode];
  if (session.busy || !lane.queryId || !lane.sources.length) return;
  session.lastLane = mode;
  lane.answerStatus = "loading";
  setBusy(true);
  renderAll();
  try {
    const data = await api("/colecciones/" + lane.collectionId + "/consultas/" + lane.queryId + "/respuesta", {
      method: "POST", body: JSON.stringify({ autorizacion: mode === "completo" ? "INDEXAR" : "ENVIAR" })
    });
    data.citas = (data.citas || []).filter(n => n >= 1 && n <= lane.sources.length);
    Object.assign(lane, { answer: data, answerStatus: "ready", animateAnswer: true });
    setBusy(false);
    renderAll();
    focusLaneElement(mode, data.abstencion ? "lane-" + mode + "-title" : "answer-" + mode);
    announce(data.abstencion ? LANE_NAME[mode] + ": el modelo no respondió porque los fragmentos no alcanzan." : LANE_NAME[mode] + ": respuesta lista. " + data.respuesta);
  } catch (error) {
    lane.answerStatus = "none";
    setBusy(false);
    renderAll();
    status("No se pudo generar la respuesta: " + error.message, true);
  }
}

async function translateQuestion() {
  const lane = session.lanes.acotado;
  if (session.busy || !lane.queryId || lane.sources.length) return;
  session.lastLane = "acotado";
  setBusy(true);
  lane.status = "loading";
  renderAll();
  try {
    const data = await api("/colecciones/" + lane.collectionId + "/consultas/" + lane.queryId + "/traduccion", {
      method: "POST", body: JSON.stringify({ autorizacion: "ENVIAR" })
    });
    Object.assign(lane, {
      status: "ready", sources: data.fuentes, seconds: data.tiempos.recuperacion, animate: true,
      matchQuestion: data.consulta_ingles || null, translated: data.consulta_ingles || "sin traducción utilizable",
      answer: null, answerStatus: "none"
    });
  } catch (error) {
    lane.status = "ready";
    status("No se pudo traducir la pregunta: " + error.message, true);
  } finally {
    setBusy(false);
    renderAll();
    focusLaneElement("acotado", "lane-acotado-title");
  }
}

async function prepareHybrid() {
  const lane = session.lanes.completo;
  if (session.busy || !session.modelAvailable || !session.question) return;
  setBusy(true);
  lane.status = "preparing";
  renderAll();
  try {
    lane.pending = await createCollection("completo");
    lane.status = "authorizing";
  } catch (error) {
    lane.status = "empty";
    status("No se pudo preparar la búsqueda híbrida: " + error.message, true);
  } finally {
    setBusy(false);
    renderAll();
    if (lane.status === "authorizing") focusLaneElement("completo", "hybridGo");
  }
}

async function cancelHybrid() {
  const lane = session.lanes.completo;
  if (session.busy) return;
  if (lane.pending) api("/colecciones/" + lane.pending.coleccion_id, { method: "DELETE" }).catch(() => {});
  lane.pending = null;
  lane.status = "empty";
  renderAll();
  focusLaneElement("completo", "hybridStart");
  announce("Búsqueda híbrida cancelada. No se envió nada a OpenAI.");
}

async function runHybrid() {
  const lane = session.lanes.completo;
  if (session.busy || !lane.pending) return;
  session.lastLane = "completo";
  setBusy(true);
  lane.status = "loading";
  renderAll();
  try {
    const query = await api("/colecciones/" + lane.pending.coleccion_id + "/consultas", {
      method: "POST", body: JSON.stringify({ pregunta: session.question, autorizacion: "INDEXAR" })
    });
    Object.assign(lane, {
      status: "ready", collectionId: lane.pending.coleccion_id, pending: null,
      queryId: query.consulta_id, sources: query.fuentes, seconds: query.tiempos.recuperacion, animate: true
    });
    setBusy(false);
    renderAll();
    focusLaneElement("completo", "lane-completo-title");
    announce(ui.comparisonSummary.hidden ? "Búsqueda híbrida lista." : ui.comparisonSummary.textContent);
  } catch (error) {
    if (lane.pending) api("/colecciones/" + lane.pending.coleccion_id, { method: "DELETE" }).catch(() => {});
    Object.assign(lane, { status: "empty", pending: null });
    setBusy(false);
    renderAll();
    status("No se pudo hacer la búsqueda híbrida: " + error.message, true);
  }
}

function runSuggestion(item) {
  if (session.busy) return;
  ui.question.value = item.pregunta;
  updateCounter();
  search();
}

/* ---------- origen: ejemplo o archivos propios ---------- */

async function chooseOrigin(origin) {
  if (session.busy) return;
  session.selectedOrigin = origin;
  ui.uploadPanel.hidden = origin !== "carga";
  ui.suggestionsWrap.hidden = origin !== "ejemplo";
  ui.questionLabel.textContent = origin === "carga" ? "Tu pregunta sobre tus archivos" : "Tu pregunta sobre el proyecto de ejemplo";
  ui.collectionHint.textContent = origin === "carga" ?
    "La búsqueda se hace en este servidor. Nada se envía a OpenAI sin que lo autorices." :
    "Un gestor de tareas ficticio, con código Python y documentos de texto.";
  ui.useExample.setAttribute("aria-pressed", String(origin === "ejemplo"));
  ui.useUpload.setAttribute("aria-pressed", String(origin === "carga"));
  ui.question.value = "";
  updateCounter();
  await clearAll();
}

ui.useExample.addEventListener("click", () => chooseOrigin("ejemplo"));
ui.useUpload.addEventListener("click", () => chooseOrigin("carga"));
ui.uploadFiles.addEventListener("change", () => {
  ui.uploadSummary.textContent = filesSummary();
  clearAll();
});
ui.deleteUpload.addEventListener("click", async () => {
  if (session.busy || session.origin !== "carga") return;
  await clearAll();
  ui.uploadFiles.value = "";
  ui.uploadSummary.textContent = filesSummary();
  status("Tus archivos se borraron del servidor.", false);
  ui.question.focus();
});

/* ---------- formulario y navegación ---------- */

function updateCounter() {
  const length = ui.question.value.length;
  ui.counter.hidden = length < 400;
  ui.counter.textContent = length + " de 500 caracteres";
}

ui.queryForm.addEventListener("submit", event => { event.preventDefault(); search(); });
ui.question.addEventListener("input", updateCounter);
ui.laneSwitch.addEventListener("click", event => {
  const target = event.target.closest(".carril-boton");
  if (!target) return;
  session.visibleLane = target.dataset.lane;
  renderLaneSwitch();
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
      const node = button("sugerencia" + (item.id === "abstencion" ? " sugerencia-sin" : ""), item.pregunta, () => runSuggestion(item));
      node.title = item.descripcion;
      if (item.id === "abstencion") node.append(" ", el("span", "", "(no está en el proyecto)"));
      ui.suggestions.append(node);
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
    row.querySelector(".barra").dataset.width = (value / metric.count) * 100 + "%";
    row.querySelector(".barra").style.width = benchmarkSeen ? (value / metric.count) * 100 + "%" : "0%";
  });
  document.querySelectorAll(".metrica").forEach(node => {
    node.setAttribute("aria-pressed", String(node.dataset.metric === metricKey));
  });
}

function revealBenchmark() {
  benchmarkSeen = true;
  document.querySelectorAll("#benchmarkChart .barra").forEach(bar => { bar.style.width = bar.dataset.width; });
}

document.querySelectorAll(".metrica").forEach(node => {
  node.addEventListener("click", () => renderBenchmark(node.dataset.metric));
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
