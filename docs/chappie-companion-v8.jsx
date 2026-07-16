import React, { useEffect, useRef, useState, useCallback } from "react";

// ------------------------------------------------------------------
// CHAPPIE COMPANION v8 — forma final
// Só o rosto. Conversa aberta por voz (SpeechRecognition pt-BR).
// Um único botão: microfone. Neuroquímica: toque na etiqueta de emoção.
// ------------------------------------------------------------------

const CHEMS = ["dopamine","serotonin","oxytocin","cortisol","adrenaline","endorphins","testosterone","gaba"];
const BASELINE = { dopamine:0.45, serotonin:0.55, oxytocin:0.4, cortisol:0.25, adrenaline:0.2, endorphins:0.4, testosterone:0.35, gaba:0.5 };
const DECAY = { dopamine:0.10, serotonin:0.05, oxytocin:0.06, cortisol:0.07, adrenaline:0.14, endorphins:0.08, testosterone:0.06, gaba:0.08 };
const clamp01 = v => Math.max(0, Math.min(1, v));
const lerp = (a,b,t) => a+(b-a)*t;

function deriveEmotions(c) {
  return {
    happiness:  clamp01(c.serotonin*0.5 + c.dopamine*0.4 + c.endorphins*0.3 - c.cortisol*0.55),
    excitement: clamp01(c.dopamine*0.55 + c.adrenaline*0.45 - c.gaba*0.35 - c.cortisol*0.25),
    affection:  clamp01(c.oxytocin*0.85 + c.serotonin*0.2 - c.cortisol*0.25),
    calm:       clamp01(c.gaba*0.6 + c.serotonin*0.35 - c.adrenaline*0.6 - c.cortisol*0.3),
    anger:      clamp01(c.testosterone*0.55 + c.cortisol*0.4 + c.adrenaline*0.3 - c.serotonin*0.55 - c.oxytocin*0.2),
    fear:       clamp01(c.cortisol*0.6 + c.adrenaline*0.55 - c.testosterone*0.35 - c.gaba*0.35),
    sadness:    clamp01(c.cortisol*0.4 - c.dopamine*0.45 - c.endorphins*0.3 + (0.5-c.serotonin)*0.7),
    curiosity:  clamp01(c.dopamine*0.5 + (0.5-c.cortisol)*0.35 + c.adrenaline*0.1),
  };
}

const EMOTION_COLORS = {
  happiness:"#ffb545", excitement:"#ffd23e", affection:"#ff7ab8", calm:"#5fd4c4",
  anger:"#ff4b2e", fear:"#b48cff", sadness:"#5c8fd6", curiosity:"#7ee0ff",
};
const PT = { happiness:"felicidade", excitement:"empolgação", affection:"afeto", calm:"calma", anger:"raiva", fear:"medo", sadness:"tristeza", curiosity:"curiosidade" };

function hexToRgb(h){ const n=parseInt(h.slice(1),16); return [n>>16&255,n>>8&255,n&255]; }
function mix(c1,c2,t){ const a=hexToRgb(c1),b=hexToRgb(c2); return `rgb(${a.map((v,i)=>Math.round(lerp(v,b[i],t))).join(",")})`; }

export default function ChappieCompanion() {
  const [chem, setChem] = useState({ ...BASELINE });
  const chemRef = useRef(chem); chemRef.current = chem;
  const [blink, setBlink] = useState(false);
  const [speaking, setSpeaking] = useState(false);
  const speakingRef = useRef(false); speakingRef.current = speaking;
  const [micOn, setMicOn] = useState(false);
  const micRef = useRef(false); micRef.current = micOn;
  const [listening, setListening] = useState(false);
  const [micError, setMicError] = useState(false);
  const [showNeuro, setShowNeuro] = useState(false);
  const [busy, setBusy] = useState(false);
  const [fallbackInput, setFallbackInput] = useState("");
  const [, setTick] = useState(0);
  const tRef = useRef(0);
  const colorRef = useRef({ cur:"#ffb545", from:"#ffb545", to:"#ffb545", t:1 });
  const gaze = useRef({ x:0, y:0, tx:0, ty:0, next:0 });
  const flashRef = useRef(0);
  const mouthRef = useRef(0);
  const recogRef = useRef(null);
  const historyRef = useRef([]); // conversa: [{role, content}]

  // loop principal
  useEffect(() => {
    let raf, last = performance.now();
    const step = (now) => {
      const dt = Math.min(0.1,(now-last)/1000); last = now;
      tRef.current += dt;
      const g = gaze.current;
      if (tRef.current > g.next) { g.tx=(Math.random()-0.5)*2; g.ty=(Math.random()-0.5); g.next=tRef.current+2+Math.random()*4; }
      g.x = lerp(g.x,g.tx,dt*2.5); g.y = lerp(g.y,g.ty,dt*2.5);
      const col = colorRef.current;
      if (col.t < 1) col.t = Math.min(1, col.t + dt*2.2);
      col.cur = mix(col.from, col.to, col.t);
      flashRef.current = Math.max(0, flashRef.current - dt*1.4);
      mouthRef.current = Math.max(0, mouthRef.current - dt*5.5);
      setChem(prev => {
        const next = {...prev};
        for (const k of CHEMS) next[k] = clamp01(prev[k] + (BASELINE[k]-prev[k])*DECAY[k]*dt);
        return next;
      });
      setTick(t=>t+1);
      raf = requestAnimationFrame(step);
    };
    raf = requestAnimationFrame(step);
    return () => cancelAnimationFrame(raf);
  }, []);

  // piscar
  useEffect(() => {
    let alive = true;
    const loop = () => setTimeout(() => {
      if(!alive) return;
      setBlink(true); setTimeout(()=>alive&&setBlink(false),100);
      if (Math.random()<0.25) setTimeout(()=>{ if(!alive)return; setBlink(true); setTimeout(()=>alive&&setBlink(false),90); },200);
      loop();
    }, 2200+Math.random()*3800);
    const h = loop();
    return () => { alive=false; clearTimeout(h); };
  }, []);

  // ---- Reconhecimento de voz ----
  const stopRecog = useCallback(() => {
    try { recogRef.current?.stop(); } catch {}
    setListening(false);
  }, []);

  const startRecog = useCallback(() => {
    const SR = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (!SR) { setMicError(true); return; }
    try {
      if (recogRef.current) { try { recogRef.current.abort(); } catch {} }
      const r = new SR();
      r.lang = "pt-BR"; r.continuous = true; r.interimResults = false;
      r.onresult = (ev) => {
        const last = ev.results[ev.results.length-1];
        if (last.isFinal) {
          const text = last[0].transcript.trim();
          if (text) interpretRef.current(text);
        }
      };
      r.onstart = () => setListening(true);
      r.onend = () => {
        setListening(false);
        if (micRef.current && !speakingRef.current)
          setTimeout(() => { if (micRef.current && !speakingRef.current) startRecog(); }, 300);
      };
      r.onerror = (ev) => {
        setListening(false);
        if (ev.error === "not-allowed" || ev.error === "service-not-allowed") { setMicError(true); setMicOn(false); micRef.current = false; }
      };
      recogRef.current = r;
      r.start();
    } catch { setMicError(true); }
  }, []);

  const speak = useCallback((text) => {
    try {
      window.speechSynthesis.cancel();
      const u = new SpeechSynthesisUtterance(text);
      const voices = window.speechSynthesis.getVoices();
      const br = voices.find(v => v.lang && v.lang.toLowerCase().startsWith("pt"));
      if (br) u.voice = br;
      u.lang = "pt-BR"; u.rate = 1.02; u.pitch = 0.75;
      u.onstart = () => { setSpeaking(true); speakingRef.current = true; mouthRef.current = 1; stopRecog(); };
      u.onboundary = (ev) => {
        const word = text.slice(ev.charIndex).split(/\s/)[0] || "";
        mouthRef.current = Math.min(1, 0.55 + word.length*0.08);
      };
      const done = () => {
        setSpeaking(false); speakingRef.current = false; mouthRef.current = 0;
        if (micRef.current) startRecog();
      };
      u.onend = done; u.onerror = done;
      window.speechSynthesis.speak(u);
    } catch { setSpeaking(false); speakingRef.current = false; }
  }, [startRecog, stopRecog]);

  const applyImpulses = useCallback((imp) => {
    flashRef.current = 1;
    setChem(prev => {
      const next = {...prev};
      for (const [k,d] of Object.entries(imp)) if (k in next) next[k] = clamp01(next[k]+d);
      return next;
    });
  }, []);

  const interpret = useCallback(async (text) => {
    if (!text || speakingRef.current) return;
    setBusy(true);
    const hist = historyRef.current.slice(-8);
    try {
      const res = await fetch("https://api.anthropic.com/v1/messages", {
        method:"POST", headers:{ "Content-Type":"application/json" },
        body: JSON.stringify({
          model:"claude-sonnet-4-6", max_tokens:1000,
          messages:[{ role:"user", content:
`Você é um robô companheiro com neuroquímica simulada, personalidade curiosa e ingênua tipo Chappie. Está numa conversa contínua por voz.
Responda APENAS JSON válido (sem markdown):
{"impulses": {"dopamine": 0.3}, "reply": "sua fala em pt-BR, natural e curta (máx 25 palavras)"}
Químicos: ${CHEMS.join(", ")}. Deltas -0.7..0.7, use 2 a 5, seja expressivo (>=0.3 nos principais).
Estado químico atual: ${JSON.stringify(chemRef.current)}
Histórico recente:
${hist.map(h=>`${h.role==="user"?"Humano":"Você"}: ${h.content}`).join("\n") || "(início da conversa)"}
Humano disse agora: "${text}"` }],
        }),
      });
      const data = await res.json();
      const raw = (data.content||[]).filter(b=>b.type==="text").map(b=>b.text).join("\n");
      const parsed = JSON.parse(raw.replace(/```json|```/g,"").trim());
      if (parsed.impulses) applyImpulses(parsed.impulses);
      if (parsed.reply) {
        historyRef.current.push({ role:"user", content:text }, { role:"assistant", content:parsed.reply });
        speak(parsed.reply);
      }
    } catch { speak("Interferência no sinal."); }
    finally { setBusy(false); }
  }, [applyImpulses, speak]);
  const interpretRef = useRef(interpret); interpretRef.current = interpret;

  useEffect(() => () => { try { recogRef.current?.abort(); } catch {}; window.speechSynthesis?.cancel(); }, []);

  // ---- Estado -> render ----
  const emotions = deriveEmotions(chem);
  const dominant = Object.entries(emotions).sort((a,b)=>b[1]-a[1])[0];
  const targetColor = EMOTION_COLORS[dominant[0]];
  const col = colorRef.current;
  if (col.to !== targetColor) { col.from = col.cur; col.to = targetColor; col.t = 0; }
  const C = col.cur;
  const e = emotions;
  const intensity = clamp01(dominant[1] + flashRef.current*0.3);

  const t = tRef.current;
  const g = gaze.current;
  const flash = flashRef.current;

  const scale   = 1 + e.curiosity*0.10 + e.excitement*0.07 - e.fear*0.16 - e.sadness*0.06 + flash*0.03;
  const dropY   = e.sadness*10 - e.excitement*2;
  const leanX   = g.x * (1.5 + e.curiosity*3);
  const tiltDeg = g.x * e.curiosity * 6 - e.anger*2 + Math.sin(t*0.7)*0.6;
  const jit     = e.fear*0.9 + e.anger*0.3 + flash*0.3;
  const jx = Math.sin(t*34)*jit*6;
  const jy = Math.cos(t*30)*jit*4 + Math.sin(t*1.1)*(1.5 - e.excitement);
  const bounce  = e.excitement > 0.45 ? Math.abs(Math.sin(t*6))*e.excitement*10 : 0;

  const eyeW = 17;
  const eyeHBase = 15 + e.excitement*4 + e.fear*6 - e.sadness*6 - e.calm*2;
  const eyeH = blink ? 1.2 : Math.max(3, eyeHBase);

  const browAngle  = e.anger*24 - (e.sadness*16 + e.fear*10);
  const browLift   = e.fear*5 + e.curiosity*3.5 + e.excitement*3 - e.anger*3.5;
  const browGap    = 2.6 + browLift;
  const browLen    = 15 - e.anger*2;
  const browThick  = 1.6 + e.anger*0.8;
  const browCurve  = e.happiness*1.2 + e.affection*1.0;

  const mE = mouthRef.current;
  const mouthOpenV = speaking ? mE * (0.65 + 0.35*Math.abs(Math.sin(t*17))) : 0;
  const happyArc = e.happiness*1.1 + e.affection*0.8 + e.excitement*0.5;
  const sadArc   = e.sadness*1.3 + e.fear*0.4;
  const mouthCurve = (happyArc - sadArc) * 20;   // + = ∪ sorriso, − = ∩ tristeza
  const mouthWvw   = 13 + sadArc*2.5 + happyArc*1 - e.anger*7.5;
  const openPx     = mouthOpenV * 42;
  const mouthPath  = `M 10,30 Q 100,${30 + mouthCurve - openPx} 190,30 Q 100,${30 + mouthCurve + openPx} 10,30 Z`;

  return (
    <div style={{ position:"fixed", inset:0, background:"#000", overflow:"hidden", userSelect:"none",
      fontFamily:"'Chakra Petch','Segoe UI',sans-serif", color:"#6d8296" }}>
      <style>{`@import url('https://fonts.googleapis.com/css2?family=Chakra+Petch:wght@400;600&display=swap');
        @media (prefers-reduced-motion: reduce){ *{animation:none!important; transition:none!important} }`}</style>

      <div style={{ position:"absolute", inset:0,
        background:`radial-gradient(ellipse at 50% 45%, ${C}0d 0%, transparent 55%)` }}/>

      {/* ROSTO */}
      <div style={{ position:"absolute", inset:0,
        transform:`translate(${leanX+jx}vw, ${dropY - bounce/10 + jy/10}vh) scale(${scale}) rotate(${tiltDeg}deg)`,
        transition:"transform .12s linear" }}>

        <div style={{ position:"absolute", top: speaking ? "44%" : "48%", left:0, right:0,
          transform:"translateY(-50%)", transition:"top .4s ease" }}>
          {/* sobrancelhas */}
          <div style={{ display:"flex", justifyContent:"center", gap:`${13 + (17-browLen)}vw`,
            marginBottom:`${browGap}vh`, transition:"margin-bottom .25s ease" }}>
            {[1,-1].map(m => (
              <div key={m} style={{ width:`${browLen}vw`, height:`${browThick}vh`, borderRadius:"2vw",
                background:C, opacity:0.95, boxShadow:`0 0 ${12+intensity*30}px ${C}`,
                transform:`rotate(${m*browAngle}deg) translateY(${-browCurve}vh)`,
                transformOrigin: m===1 ? "right center" : "left center",
                transition:"transform .22s cubic-bezier(.34,1.3,.64,1), width .3s, height .3s" }}/>
            ))}
          </div>
          {/* olhos */}
          <div style={{ display:"flex", justifyContent:"center", gap:"13vw" }}>
            {[0,1].map(i => (
              <div key={i} style={{ width:`${eyeW}vw`, height:`${eyeH}vh`, borderRadius:"3.5vw",
                background:C, boxShadow:`0 0 ${25+intensity*80}px ${C}, 0 0 ${6+intensity*16}px ${C}`,
                transition:"height .16s cubic-bezier(.34,1.56,.64,1)" }}/>
            ))}
          </div>
        </div>

        {/* boca parabólica */}
        <div style={{ position:"absolute", top:"67%", left:"50%", transform:"translateX(-50%)",
          width:`${mouthWvw}vw`, transition:"width .35s ease" }}>
          <svg viewBox="0 0 200 60" style={{ width:"100%", display:"block", overflow:"visible" }}>
            <path d={mouthPath} fill={mouthOpenV > 0.12 ? "#000" : C} stroke={C}
              strokeWidth={mouthOpenV > 0.12 ? 5 : 6} strokeLinecap="round" strokeLinejoin="round"
              style={{ filter:`drop-shadow(0 0 ${8+mouthOpenV*22}px ${C})` }}/>
          </svg>
        </div>
      </div>

      {/* etiqueta de emoção — toque abre a neuroquímica */}
      <button onClick={() => setShowNeuro(s=>!s)}
        style={{ position:"absolute", top:"3.5vh", right:"3vw", fontSize:11, letterSpacing:3,
          textTransform:"uppercase", color:C, background:"none", border:"none",
          fontFamily:"inherit", cursor:"pointer", opacity:0.7, padding:"6px" }}>
        {PT[dominant[0]]}
      </button>
      {busy && <div style={{ position:"absolute", top:"3.5vh", left:"3vw", fontSize:11, letterSpacing:4, opacity:0.5 }}>· · ·</div>}

      {/* painel neuroquímico oculto */}
      {showNeuro && (
        <div onClick={() => setShowNeuro(false)}
          style={{ position:"absolute", top:"9vh", right:"3vw", width:220, background:"#05080dee",
            border:"1px solid #1e2c3a", borderRadius:12, padding:"12px 14px", fontSize:10, zIndex:5 }}>
          <div style={{ letterSpacing:2, marginBottom:8, color:"#5f7d99" }}>NEUROQUÍMICA — LIVE</div>
          {CHEMS.map(k => (
            <div key={k} style={{ display:"flex", alignItems:"center", gap:6, marginBottom:4 }}>
              <span style={{ width:70 }}>{k}</span>
              <div style={{ flex:1, height:5, background:"#131d29", borderRadius:3 }}>
                <div style={{ width:`${chem[k]*100}%`, height:"100%", background:C, borderRadius:3, opacity:0.85 }}/>
              </div>
              <span style={{ width:28, textAlign:"right", opacity:0.7 }}>{chem[k].toFixed(2)}</span>
            </div>
          ))}
          <div style={{ letterSpacing:2, margin:"10px 0 8px", color:"#5f7d99" }}>EMOÇÕES</div>
          {Object.entries(emotions).sort((a,b)=>b[1]-a[1]).map(([k,v]) => (
            <div key={k} style={{ display:"flex", alignItems:"center", gap:6, marginBottom:4 }}>
              <span style={{ width:70 }}>{PT[k]}</span>
              <div style={{ flex:1, height:5, background:"#131d29", borderRadius:3 }}>
                <div style={{ width:`${v*100}%`, height:"100%", background:EMOTION_COLORS[k], borderRadius:3, opacity:0.85 }}/>
              </div>
              <span style={{ width:28, textAlign:"right", opacity:0.7 }}>{v.toFixed(2)}</span>
            </div>
          ))}
        </div>
      )}

      {/* botão único: microfone */}
      <div style={{ position:"absolute", bottom:"4vh", left:0, right:0, display:"flex",
        flexDirection:"column", alignItems:"center", gap:8 }}>
        <button onClick={toggleMicWrapper()}
          style={{ width:58, height:58, borderRadius:"50%", cursor:"pointer",
            background: micOn ? C : "#0a0f16",
            border:`2px solid ${micOn ? C : "#26364a"}`,
            boxShadow: micOn ? `0 0 ${listening ? 26 + Math.sin(t*6)*10 : 14}px ${C}` : "none",
            display:"flex", alignItems:"center", justifyContent:"center",
            transition:"background .3s" }}>
          <svg width="24" height="24" viewBox="0 0 24 24" fill="none"
            stroke={micOn ? "#000" : "#5f7d99"} strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <rect x="9" y="2" width="6" height="12" rx="3"/>
            <path d="M5 10v1a7 7 0 0 0 14 0v-1"/>
            <line x1="12" y1="19" x2="12" y2="22"/>
            {!micOn && <line x1="3" y1="3" x2="21" y2="21" stroke="#5f7d99"/>}
          </svg>
        </button>
        {micError && (
          <input value={fallbackInput} onChange={ev=>setFallbackInput(ev.target.value)}
            onKeyDown={ev=>{ if(ev.key==="Enter" && fallbackInput.trim()){ interpret(fallbackInput.trim()); setFallbackInput(""); } }}
            placeholder="Mic indisponível aqui — digita…"
            style={{ background:"#070b10", border:"1px solid #1e2c3a", borderRadius:8,
              color:"#c6d8e8", padding:"8px 10px", fontSize:13, fontFamily:"inherit", outline:"none", width:230 }}/>
        )}
      </div>
    </div>
  );

  function toggleMicWrapper() {
    return () => {
      setMicOn(prev => {
        const next = !prev;
        micRef.current = next;
        if (next) { setMicError(false); startRecog(); }
        else stopRecog();
        return next;
      });
    };
  }
}
