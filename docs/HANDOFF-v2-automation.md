# CHAPPIE COMPANION — Handoff v2 (Automation-First)

> Substitui o HANDOFF v1 como plano de execução. As especificações visuais,
> o contrato FaceState, o modelo químico e a personalidade permanecem os do
> v1 + SYSTEM-PROMPT-chappie.md (anexar ambos ao contexto do Claude Code).
> Este documento define COMO construir com intervenção humana mínima.

## 0. Princípio operacional

O Claude Code desenvolve, testa e valida TUDO em ambiente de dev (container/
desktop) usando mocks e testes automatizados. O Note 8 é tratado como alvo de
deploy, não como ambiente de desenvolvimento. O humano só executa ações
fisicamente impossíveis de automatizar, todas concentradas no final e
descritas num checklist único.

Regra de decisão para o Claude Code: "posso verificar isso sozinho com um
teste, mock ou script?" → se sim, faça e não pergunte. Só escale ao humano
o que exigir dedo na tela do aparelho ou um segredo (API key).

---

## 1. Estrutura do repositório (Claude Code gera 100%)

```
chappie/
├── server/
│   ├── main.py            # FastAPI: WS /face, POST /say, GET /neuro, GET / (renderer)
│   ├── engine.py          # wrapper do kindalive (ou engine próprio se lib falhar)
│   ├── interpreter.py     # Claude API (Messages) + parse defensivo
│   ├── persona.py         # SYSTEM-PROMPT-chappie embutido como constante
│   ├── persistence.py     # snapshot JSON estado+histórico (atomic write)
│   └── config.py          # env: ANTHROPIC_API_KEY, MODEL, PORT, MOCK_LLM
├── renderer/
│   └── index.html         # porta 1:1 da v8 p/ vanilla JS, consome WS
├── tests/
│   ├── test_engine.py     # decay, clamps, persistência de emoção 15-20s
│   ├── test_projections.py# separação medo×empolgação, raiva×medo (bugs v4!)
│   ├── test_interpreter.py# parse JSON, fences, malformed, timeout → fallback
│   ├── test_contract.py   # FaceState schema (pydantic) em todos os endpoints
│   └── scenarios.yaml     # cenários de calibração (ver §3)
├── deploy/
│   ├── bootstrap.sh       # setup Termux completo em UM comando
│   ├── chappie.service    # termux-services (runit) p/ autostart
│   └── update.sh          # git pull + restart (updates futuros = 1 comando)
├── dev/
│   ├── run_local.sh       # sobe server+renderer no desktop c/ MOCK_LLM=1
│   └── mock_llm.py        # respostas determinísticas p/ dev offline
└── docs/                  # este handoff + v1 + system prompt
```

## 2. O que o Claude Code automatiza (não perguntar, fazer)

1. **Todo o código** (server, renderer, deploy) com os specs do v1.
2. **MOCK_LLM mode**: interpreter com respostas determinísticas mapeadas por
   keyword ("susto"→adrenalina+cortisol etc.) — desenvolvimento e testes
   rodam sem API key e sem custo.
3. **Suite de testes** executada a cada mudança (pytest). Os bugs que o
   protótipo encontrou viram testes de regressão permanentes:
   - decay: após impulso 0.6 de adrenalina, emoção dominante persiste ≥12s
     e ≤30s (clock simulado, sem sleep real);
   - projeções: cenário "susto" ⇒ fear > excitement e fear > anger;
     "provocação" ⇒ anger dominante; "carinho" ⇒ affection dominante;
   - boca: curve > 0 quando happiness domina (∪), curve < 0 sadness (∩),
     width < 7vw quando anger > 0.5 (testar a função de geometria exportada
     como módulo JS puro, executável via node);
   - contrato: todo payload do WS valida contra o schema pydantic.
4. **Renderer testável**: extrair `face_math.js` (puro, sem DOM) com todas as
   funções de geometria — testado via `node --test`. O DOM fica burro.
5. **Smoke test E2E local**: script que sobe o server com MOCK_LLM, abre
   headless chromium (se disponível no ambiente) ou faz asserts via
   websocket client: envia "que susto!", verifica FaceState reagindo.
6. **bootstrap.sh idempotente** (pode rodar 2x sem quebrar): pkg install,
   pip install, clone/copy do repo, prompt interativo pedindo a API key
   (única entrada humana do script), grava .env, registra serviço runit,
   termux-wake-lock, imprime URL final e QR code ASCII do localhost.
7. **Self-check no boot do server**: valida API key com uma chamada mínima,
   testa TTS/portas, e expõe GET /health com diagnóstico legível — se algo
   estiver errado, o próprio rosto exibe o erro (olhos cinza + mensagem).
8. **Calibração automatizada**: `scenarios.yaml` com ~15 cenários
   (frase → emoção dominante esperada + faixa de intensidade). Um runner
   valida o pipeline completo com MOCK_LLM; com API key presente, roda
   opcionalmente contra o Claude real e reporta divergências em tabela.
9. **Anti-burn-in, kiosk meta tags, wake lock JS** (NoSleep pattern),
   reconexão automática do WS, tudo já embutido.
10. **README de operação** gerado: como ver logs, reiniciar, atualizar.

## 3. Critérios de aceite por milestone (auto-verificáveis)

- **M1 (dev local)**: `dev/run_local.sh` sobe tudo; pytest 100% verde;
  smoke E2E passa; renderer abre no desktop e reage a POST /say mockado.
  *Zero envolvimento humano.*
- **M2 (engine real)**: kindalive integrado OU flag documentada de fallback
  p/ engine próprio se a lib divergir do esperado; persistência sobrevive a
  restart (teste automatizado mata e resobe o processo).
  *Zero envolvimento humano.*
- **M3 (deploy)**: bootstrap.sh testado em container Ubuntu simulando os
  passos (exceto os específicos de Android, marcados e pulados via flag
  `--dry-android`). Só então o humano entra.

## 4. Checklist humano (TUDO que sobra pra você)

Uma única sessão, ~20 minutos, com o Note 8 na mão:

1. Instalar **F-Droid** e, por ele, **Termux** + **Termux:Boot** (APKs —
   impossível automatizar).
2. Abrir o Termux e colar **um comando** (o curl/git do bootstrap.sh).
3. Colar a **ANTHROPIC_API_KEY** quando o script pedir.
4. Aceitar os **dialogs de permissão** que o Android mostrar (armazenamento;
   depois mic no Chrome).
5. Configurações → Bateria → **desativar otimização** para Termux e Chrome
   (o script imprime o caminho exato do menu).
6. Abrir a URL que o script imprimir no Chrome → **"Adicionar à tela
   inicial"** → abrir pelo ícone (kiosk).
7. Tocar no botão do mic e **permitir o microfone**.
8. Falar com ele. (Este passo é obrigatório e intransferível.)

Tudo fora desta lista que aparecer durante o build é bug do plano — o
Claude Code deve resolver, não delegar.

## 5. Loop de iteração pós-deploy

Ajustes futuros nunca exigem refazer o setup: você descreve a mudança ao
orquestrador → Claude Code altera + testes → você roda `bash deploy/update.sh`
no Termux (ou o server expõe POST /admin/update que faz git pull + restart,
protegido por token local — incluir no M3). Intervenção humana em updates: 0
a 1 comando.
