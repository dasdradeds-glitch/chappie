// Geometria pura do rosto — sem DOM, sem estado, testavel via `node --test`.
// O servidor ja manda os campos de FaceState.face prontos (emocao -> numero);
// este modulo so converte esses numeros em CSS/SVG. Nao conhece quimicos
// nem emocoes (contrato do HANDOFF §4/§3: "o renderer nao conhece quimicos").
//
// mouthOpenFrac (0..1) e a UNICA coisa que NAO vem do servidor: e lip-sync
// local, dirigido pelo onboundary do speechSynthesis do navegador (ver
// docs/HANDOFF §7 fase 1) — combinado aqui com o mouthCurve emocional que
// o servidor manda.

export function mouthVisual(mouthCurve, mouthOpenFrac = 0) {
  const openPx = mouthOpenFrac * 42;
  // Bug historico v7: sinal invertido pelo y-down do SVG. + = ∪ sorriso, − = ∩ tristeza. Nao repetir.
  const path = `M 10,30 Q 100,${30 + mouthCurve - openPx} 190,30 Q 100,${30 + mouthCurve + openPx} 10,30 Z`;
  const isOpen = mouthOpenFrac > 0.12;
  return {
    path,
    isOpen,
    strokeWidth: isOpen ? 5 : 6,
    glowPx: 8 + mouthOpenFrac * 22,
  };
}

// side: 1 = sobrancelha direita (pivo no canto externo direito), -1 = esquerda.
export function browTransform(browAngleDeg, browCurveVh, side) {
  return {
    transform: `rotate(${side * browAngleDeg}deg) translateY(${-browCurveVh}vh)`,
    transformOrigin: side === 1 ? "right center" : "left center",
  };
}

export function browRowGapVw(eyeWidthVw, browLenVw) {
  return 13 + (eyeWidthVw - browLenVw);
}

export function browRowMarginBottomVh(browLiftVh) {
  return 2.6 + browLiftVh;
}

export function postureTransform({ leanXVw, dropYVh, scale, tiltDeg }) {
  return `translate(${leanXVw}vw, ${dropYVh}vh) scale(${scale}) rotate(${tiltDeg}deg)`;
}

export function eyeGlow(intensity, color) {
  return `0 0 ${25 + intensity * 80}px ${color}, 0 0 ${6 + intensity * 16}px ${color}`;
}

export function browGlow(intensity, color) {
  return `0 0 ${12 + intensity * 30}px ${color}`;
}

export function mouthGlowFilter(mouthOpenFrac, color) {
  return `drop-shadow(0 0 ${8 + mouthOpenFrac * 22}px ${color})`;
}

// Lip-sync local (client-side): energia por palavra falada, decaimento
// contínuo. Porte literal do mouthRef do v8 — nao mexe em quimicos/emocao.
export function decayMouthEnergy(current, dtSeconds, ratePerSecond = 5.5) {
  return Math.max(0, current - dtSeconds * ratePerSecond);
}

export function wordEnergy(word) {
  return Math.min(1, 0.55 + (word ? word.length : 0) * 0.08);
}
