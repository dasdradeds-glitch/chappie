import { test } from "node:test";
import assert from "node:assert/strict";
import {
  mouthVisual,
  browTransform,
  browRowGapVw,
  browRowMarginBottomVh,
  postureTransform,
  eyeGlow,
  browGlow,
  mouthGlowFilter,
} from "../renderer/face_math.js";

test("mouthVisual: curve positivo (felicidade) nao inverte o sinal (bug historico v7)", () => {
  const { path } = mouthVisual(15, 0);
  assert.match(path, /Q 100,45 190,30 Q 100,45/);
});

test("mouthVisual: curve negativo (tristeza) nao inverte o sinal", () => {
  const { path } = mouthVisual(-15, 0);
  assert.match(path, /Q 100,15 190,30 Q 100,15/);
});

test("mouthVisual: boca aberta (fala) separa as duas quadraticas em torno da curva", () => {
  const { path, isOpen } = mouthVisual(0, 0.5);
  // openPx = 0.5*42 = 21 -> top=30-21=9, bottom=30+21=51
  assert.match(path, /Q 100,9 190,30 Q 100,51/);
  assert.equal(isOpen, true);
});

test("mouthVisual: abaixo do limiar 0.12 nao conta como aberta (fill solido)", () => {
  const { isOpen } = mouthVisual(10, 0.1);
  assert.equal(isOpen, false);
});

test("browTransform: lado direito (m=1) usa angulo positivo e pivot no canto direito", () => {
  const t = browTransform(24, 1.2, 1);
  assert.match(t.transform, /rotate\(24deg\)/);
  assert.match(t.transform, /translateY\(-1\.2vh\)/);
  assert.equal(t.transformOrigin, "right center");
});

test("browTransform: lado esquerdo (m=-1) espelha o angulo e pivot no canto esquerdo", () => {
  const t = browTransform(24, 1.2, -1);
  assert.match(t.transform, /rotate\(-24deg\)/);
  assert.equal(t.transformOrigin, "left center");
});

test("browRowGapVw: sobrancelha mais curta (raiva) aumenta o gap entre elas", () => {
  const normal = browRowGapVw(17, 15);
  const angry = browRowGapVw(17, 13); // browLen encolhe com raiva
  assert.ok(angry > normal, `esperava gap maior com raiva: ${angry} > ${normal}`);
});

test("browRowMarginBottomVh: soma o offset fixo de 2.6vh ao lift emocional", () => {
  assert.equal(browRowMarginBottomVh(0), 2.6);
  assert.equal(browRowMarginBottomVh(5), 7.6);
});

test("postureTransform: monta a string de transform combinando os 4 eixos", () => {
  const css = postureTransform({ leanXVw: 1.5, dropYVh: -2, scale: 1.1, tiltDeg: 3 });
  assert.equal(css, "translate(1.5vw, -2vh) scale(1.1) rotate(3deg)");
});

test("eyeGlow e browGlow crescem com a intensidade", () => {
  const low = eyeGlow(0, "#fff");
  const high = eyeGlow(1, "#fff");
  assert.notEqual(low, high);
  assert.match(eyeGlow(0.5, "#abc"), /#abc/);
  const lowBrow = browGlow(0, "#fff");
  const highBrow = browGlow(1, "#fff");
  assert.notEqual(lowBrow, highBrow);
});

test("mouthGlowFilter monta um drop-shadow valido", () => {
  const f = mouthGlowFilter(0.5, "#ff0000");
  assert.match(f, /^drop-shadow\(0 0 \d+(\.\d+)?px #ff0000\)$/);
});
