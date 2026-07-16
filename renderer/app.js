// Renderer "burro": consome o WS /face e desenha. So conhece face_math.js
// (geometria pura) e as APIs de voz do navegador (STT/TTS — fase 1, ver
// docs/HANDOFF §7). Nao conhece quimicos nem emocoes por conta propria.
import {
  mouthVisual, browTransform, browRowGapVw, browRowMarginBottomVh,
  postureTransform, eyeGlow, browGlow, mouthGlowFilter,
} from "./face_math.js";

const PT = {
  happiness: "felicidade", excitement: "empolgação", affection: "afeto", calm: "calma",
  anger: "raiva", fear: "medo", sadness: "tristeza", curiosity: "curiosidade",
};
const CHEMS = ["dopamine", "serotonin", "oxytocin", "cortisol", "adrenaline", "endorphins", "testosterone", "gaba"];
const EMOTION_COLORS = {
  happiness: "#ffb545", excitement: "#ffd23e", affection: "#ff7ab8", calm: "#5fd4c4",
  anger: "#ff4b2e", fear: "#b48cff", sadness: "#5c8fd6", curiosity: "#7ee0ff",
};

const el = {
  faceWrap: document.getElementById("faceWrap"),
  browEyeRow: document.getElementById("browEyeRow"),
  browR: document.getElementById("browR"),
  browL: document.getElementById("browL"),
  browsRow: document.getElementById("browsRow"),
  eyesRow: document.getElementById("eyesRow"),
  eyeL: document.getElementById("eyeL"),
  eyeR: document.getElementById("eyeR"),
  mouthWrap: document.getElementById("mouthWrap"),
  mouthPath: document.getElementById("mouthPath"),
  emotionLabel: document.getElementById("emotionLabel"),
  busyDots: document.getElementById("busyDots"),
  neuroPanel: document.getElementById("neuroPanel"),
  micBtn: document.getElementById("micBtn"),
  fallbackInput: document.getElementById("fallbackInput"),
  errorBanner: document.getElementById("errorBanner"),
};

let latest = null;
let mouthEnergy = 0;
let lastMouthCurve = 0;
let micOn = false;
let speaking = false;
let recognizer = null;
let wsReconnectDelay = 1000;
// Audio real (TTS server-side + lip-sync por amplitude via AnalyserNode).
// AudioContext so pode ser criado/retomado a partir de um gesto do usuario
// (politica de autoplay do navegador) — por isso getAudioCtx() e chamado
// nos handlers de clique/enter, nao aqui no top-level.
let audioCtx = null;
let analyser = null;
let currentAudioSource = null;
let lipSyncRAF = null;
// Erro persistente de configuracao (ex: sem ANTHROPIC_API_KEY) — diferente
// de erro transiente de conexao WS, isso NAO deve ser limpo a cada frame
// pintado (o WS manda ~20 frames/s; sem essa flag o erro pisca e some).
let unhealthy = false;

// ---------- WS ----------
function connectWs() {
  const proto = location.protocol === "https:" ? "wss" : "ws";
  const ws = new WebSocket(`${proto}://${location.host}/face`);
  ws.onopen = () => { wsReconnectDelay = 1000; if (!unhealthy) setError(null); };
  ws.onmessage = (ev) => {
    latest = JSON.parse(ev.data);
    paintFace(latest);
  };
  ws.onclose = () => {
    setError("Sem conexão com o Chappie. Reconectando…");
    setTimeout(connectWs, wsReconnectDelay);
    wsReconnectDelay = Math.min(wsReconnectDelay * 1.5, 10000);
  };
  ws.onerror = () => ws.close();
}

function setError(msg) {
  if (!msg) { el.errorBanner.style.display = "none"; return; }
  el.errorBanner.textContent = msg;
  el.errorBanner.style.display = "block";
}

// ---------- pintura ----------
function paintFace(state) {
  const { face, color, intensity, dominant, speaking: srvSpeaking } = state;
  speaking = srvSpeaking;
  if (!unhealthy) setError(null);
  document.documentElement.style.setProperty("--emotion-color", color);

  el.browEyeRow.classList.toggle("speaking", speaking);
  el.faceWrap.style.transform = postureTransform(face);

  el.eyeL.style.width = el.eyeR.style.width = face.eyeWidthVw + "vw";
  el.eyeL.style.height = el.eyeR.style.height = face.eyeHeightVh + "vh";
  el.eyeL.style.background = el.eyeR.style.background = unhealthy ? "#3a4552" : color;
  el.eyeL.style.boxShadow = el.eyeR.style.boxShadow = unhealthy ? "none" : eyeGlow(intensity, color);

  el.browsRow.style.gap = browRowGapVw(face.eyeWidthVw, face.browLenVw) + "vw";
  el.browsRow.style.marginBottom = browRowMarginBottomVh(face.browLiftVh) + "vh";
  paintBrow(el.browR, face, color, intensity, 1);
  paintBrow(el.browL, face, color, intensity, -1);

  el.mouthWrap.style.width = face.mouthWidthVw + "vw";
  lastMouthCurve = face.mouthCurve;
  paintMouth(color);

  el.emotionLabel.textContent = PT[dominant] || dominant;
  el.emotionLabel.style.color = color;

  if (el.neuroPanel.dataset.open === "1") paintNeuro(state);
}

function paintBrow(elm, face, color, intensity, side) {
  const t = browTransform(face.browAngleDeg, face.browCurveVh, side);
  elm.style.width = face.browLenVw + "vw";
  elm.style.height = face.browThickVh + "vh";
  elm.style.background = color;
  elm.style.boxShadow = browGlow(intensity, color);
  elm.style.transform = t.transform;
  elm.style.transformOrigin = t.transformOrigin;
}

function paintMouth(color) {
  const { path, isOpen, strokeWidth } = mouthVisual(lastMouthCurve, mouthEnergy);
  el.mouthPath.setAttribute("d", path);
  el.mouthPath.setAttribute("fill", isOpen ? "#000" : color);
  el.mouthPath.setAttribute("stroke", color);
  el.mouthPath.setAttribute("stroke-width", String(strokeWidth));
  el.mouthPath.style.filter = mouthGlowFilter(mouthEnergy, color);
}

// ---------- painel neuroquímico ----------
function neuroRow(label, value, color) {
  const row = document.createElement("div");
  row.className = "neuro-row";
  const pct = Math.max(0, Math.min(100, value * 100));
  row.innerHTML = `<span class="neuro-label">${label}</span>` +
    `<div class="neuro-bar-bg"><div class="neuro-bar-fill" style="width:${pct}%;background:${color}"></div></div>` +
    `<span class="neuro-val">${value.toFixed(2)}</span>`;
  return row;
}

function paintNeuro(state) {
  el.neuroPanel.innerHTML = "";
  const chemTitle = document.createElement("div");
  chemTitle.className = "neuro-title";
  chemTitle.textContent = "NEUROQUÍMICA — LIVE";
  el.neuroPanel.appendChild(chemTitle);
  for (const k of CHEMS) el.neuroPanel.appendChild(neuroRow(k, state.chemicals[k], state.color));

  const emoTitle = document.createElement("div");
  emoTitle.className = "neuro-title";
  emoTitle.textContent = "EMOÇÕES";
  el.neuroPanel.appendChild(emoTitle);
  const sorted = Object.entries(state.emotions).sort((a, b) => b[1] - a[1]);
  for (const [k, v] of sorted) el.neuroPanel.appendChild(neuroRow(PT[k], v, EMOTION_COLORS[k]));
}

el.emotionLabel.addEventListener("click", () => {
  const open = el.neuroPanel.dataset.open === "1";
  el.neuroPanel.dataset.open = open ? "0" : "1";
  el.neuroPanel.style.display = open ? "none" : "block";
  if (!open && latest) paintNeuro(latest);
});
el.neuroPanel.addEventListener("click", () => {
  el.neuroPanel.dataset.open = "0";
  el.neuroPanel.style.display = "none";
});

// ---------- voz ----------
// AudioContext so pode nascer/retomar num gesto do usuario — chamado nos
// handlers de clique do mic / enter do fallback, nunca aqui direto.
function getAudioCtx() {
  if (!audioCtx) audioCtx = new (window.AudioContext || window.webkitAudioContext)();
  return audioCtx;
}

// Voz real: /tts (edge-tts + pos-processo ffmpeg no servidor, timbre
// "androide de cinema" aprovado pelo Jack 16/07). Lip-sync por amplitude
// real do audio via AnalyserNode, nao mais por heuristica de palavra.
async function speak(text) {
  stopRecog();
  try {
    const res = await fetch("/tts", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ text }),
    });
    if (!res.ok) throw new Error(`tts respondeu ${res.status}`);
    const arrayBuffer = await res.arrayBuffer();
    await playAudioBuffer(arrayBuffer);
  } catch (e) {
    speakFallback(text);
  }
}

async function playAudioBuffer(arrayBuffer) {
  const ctx = getAudioCtx();
  if (ctx.state === "suspended") { try { await ctx.resume(); } catch (e) { /* noop */ } }
  const audioBuffer = await ctx.decodeAudioData(arrayBuffer);

  if (!analyser) {
    analyser = ctx.createAnalyser();
    analyser.fftSize = 512;
    analyser.connect(ctx.destination);
  }
  const dataArray = new Uint8Array(analyser.frequencyBinCount);

  if (currentAudioSource) { try { currentAudioSource.stop(); } catch (e) { /* noop */ } }
  const source = ctx.createBufferSource();
  source.buffer = audioBuffer;
  source.connect(analyser);
  currentAudioSource = source;

  return new Promise((resolve) => {
    const finish = () => {
      mouthEnergy = 0;
      if (lipSyncRAF) cancelAnimationFrame(lipSyncRAF);
      lipSyncRAF = null;
      currentAudioSource = null;
      if (micOn) startRecog();
      resolve();
    };
    source.onended = finish;

    function tick() {
      analyser.getByteTimeDomainData(dataArray);
      let sumSquares = 0;
      for (let i = 0; i < dataArray.length; i++) {
        const v = (dataArray[i] - 128) / 128;
        sumSquares += v * v;
      }
      const rms = Math.sqrt(sumSquares / dataArray.length);
      mouthEnergy = Math.min(1, rms * 4.5);
      if (latest) paintMouth(latest.color);
      lipSyncRAF = requestAnimationFrame(tick);
    }
    source.start();
    tick();
  });
}

// Fallback se /tts falhar (rede fora, ffmpeg quebrado): TTS do navegador,
// pra nunca deixar o Chappie mudo.
function speakFallback(text) {
  try {
    window.speechSynthesis.cancel();
    const u = new SpeechSynthesisUtterance(text);
    const voices = window.speechSynthesis.getVoices();
    const br = voices.find((v) => v.lang && v.lang.toLowerCase().startsWith("pt"));
    if (br) u.voice = br;
    u.lang = "pt-BR"; u.rate = 1.02; u.pitch = 0.75;
    u.onstart = () => { mouthEnergy = 1; };
    const done = () => { mouthEnergy = 0; if (micOn) startRecog(); };
    u.onend = done;
    u.onerror = done;
    window.speechSynthesis.speak(u);
  } catch (e) {
    mouthEnergy = 0;
    if (micOn) startRecog();
  }
}

function stopRecog() {
  try { recognizer?.stop(); } catch (e) { /* noop */ }
}

function setListening(on) {
  el.micBtn.classList.toggle("listening", on);
}

function startRecog() {
  const SR = window.SpeechRecognition || window.webkitSpeechRecognition;
  if (!SR) { showFallback(true); return; }
  try {
    if (recognizer) { try { recognizer.abort(); } catch (e) { /* noop */ } }
    const r = new SR();
    r.lang = "pt-BR"; r.continuous = true; r.interimResults = false;
    r.onstart = () => setListening(true);
    r.onresult = (ev) => {
      const last = ev.results[ev.results.length - 1];
      if (last.isFinal) {
        const text = last[0].transcript.trim();
        if (text) sendSay(text);
      }
    };
    r.onend = () => {
      setListening(false);
      if (micOn && !speaking) setTimeout(() => { if (micOn && !speaking) startRecog(); }, 300);
    };
    r.onerror = (ev) => {
      setListening(false);
      if (ev.error === "not-allowed" || ev.error === "service-not-allowed") {
        micOn = false;
        el.micBtn.classList.remove("on");
        showFallback(true);
      }
    };
    recognizer = r;
    r.start();
  } catch (e) {
    showFallback(true);
  }
}

function showFallback(show) {
  el.fallbackInput.style.display = show ? "block" : "none";
}

function setThinking(on) {
  el.busyDots.style.display = on ? "block" : "none";
  el.eyesRow.classList.toggle("thinking", on);
}

async function sendSay(text) {
  setListening(false);
  setThinking(true);
  try {
    const res = await fetch("/say", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ text }),
    });
    const data = await res.json();
    if (data.reply) speak(data.reply);
  } catch (e) {
    speak("Interferência no sinal.");
  } finally {
    setThinking(false);
  }
}

el.micBtn.addEventListener("click", () => {
  getAudioCtx(); // gesto do usuario: destrava o AudioContext pra tocar /tts depois
  micOn = !micOn;
  el.micBtn.classList.toggle("on", micOn);
  if (micOn) { showFallback(false); startRecog(); } else { stopRecog(); }
});

el.fallbackInput.addEventListener("keydown", (ev) => {
  if (ev.key === "Enter" && el.fallbackInput.value.trim()) {
    getAudioCtx(); // gesto do usuario: destrava o AudioContext pra tocar /tts depois
    sendSay(el.fallbackInput.value.trim());
    el.fallbackInput.value = "";
  }
});

// ---------- wake lock (tela ligada, anti-burn-in via CSS/gaze ja cobre drift) ----------
async function requestWakeLock() {
  try {
    if ("wakeLock" in navigator) await navigator.wakeLock.request("screen");
  } catch (e) { /* nao critico */ }
}
document.addEventListener("visibilitychange", () => {
  if (document.visibilityState === "visible") requestWakeLock();
});
requestWakeLock();

// ---------- self-check no boot (HANDOFF §2.7): se o servidor subiu com
// problema (ex: sem ANTHROPIC_API_KEY), o rosto mostra isso — olhos cinza
// + mensagem — em vez de falhar calado na primeira vez que alguem falar.
async function checkHealthOnBoot() {
  try {
    const res = await fetch("/health");
    const data = await res.json();
    if (!data.ok) {
      unhealthy = true;
      setError(data.error || "Servidor subiu com erro de configuração.");
    }
  } catch (e) {
    unhealthy = true;
    setError("Não consegui checar a saúde do servidor.");
  }
}
checkHealthOnBoot();

connectWs();
