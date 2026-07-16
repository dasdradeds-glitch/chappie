# Chappie Companion

Robô companheiro com neuroquímica simulada: um Samsung Galaxy Note 8 (rodando
Termux) como corpo, a tela como rosto, e o Claude como intérprete que traduz
conversa por voz em impulsos químicos. Emoções emergem de 8 químicos
simulados (dopamina, serotonina, oxitocina, cortisol, adrenalina,
endorfinas, testosterona, gaba) — nunca são labels diretas.

Design completo (specs visuais, contrato FaceState, modelo químico,
personalidade) em `docs/`. Este README é só operação.

## Rodando localmente (dev, sem custo)

```bash
bash dev/run_local.sh          # sobe em http://127.0.0.1:8000, MOCK_LLM=1
bash dev/run_local.sh 8080     # porta customizada
```

`MOCK_LLM=1` usa `dev/mock_llm.py` (respostas determinísticas por keyword)
em vez de chamar a API da Anthropic — desenvolvimento e testes rodam de
graça, sem `ANTHROPIC_API_KEY`.

## Testes

```bash
MOCK_LLM=1 .venv/Scripts/python -m pytest -q   # 61 testes (61 passam, 15 skip = live-API opt-in)
node --test tests/face_math.test.mjs           # 13 testes de geometria pura
```

Os 15 testes "skipped" só rodam com `CHAPPIE_LIVE_SCENARIOS=1` e uma
`ANTHROPIC_API_KEY` real — comparam o Claude de verdade contra os cenários
de calibração em `tests/scenarios.yaml` (gasta crédito de API, por isso é
opt-in).

## Deploy no Note 8 (checklist humano)

Uma sessão, ~20 minutos, com o celular na mão:

1. Instalar **F-Droid**, e por ele, **Termux** + **Termux:Boot**.
2. Abrir o Termux e colar:
   ```bash
   bash <(curl -sL https://raw.githubusercontent.com/dasdradeds-glitch/chappie/main/deploy/bootstrap.sh)
   ```
3. Colar a **ANTHROPIC_API_KEY** quando o script pedir.
4. Aceitar os dialogs de permissão (armazenamento; depois microfone no Chrome).
5. Configurações → Bateria → desativar otimização para **Termux** e
   **Chrome** (o script imprime o caminho exato).
6. Abrir a URL impressa (`http://127.0.0.1:8000`) no Chrome → **"Adicionar
   à tela inicial"** → abrir pelo ícone.
7. Tocar no microfone e permitir o acesso.
8. Falar com ele.

`deploy/bootstrap.sh` é idempotente — pode rodar de novo sem quebrar nada
(atualiza o repo, mantém a API key já salva, reinicia o serviço).

## Operação

**Ver logs:**
```bash
sv-status chappie                    # status do serviço
logcat -s chappie 2>/dev/null || true
tail -f "$PREFIX"/var/service/chappie/log/main/current 2>/dev/null
```
(`termux-services` loga via `logger`/svlogd; se preferir, rode
`dev/run_local.sh` direto no primeiro plano pra ver stdout ao vivo.)

**Reiniciar:**
```bash
sv restart chappie
```

**Atualizar código:**
```bash
bash deploy/update.sh
```
Faz `git pull` + reinstala deps + reinicia o serviço. Alternativa remota
(sem abrir o Termux, só código — não instala deps novas):
```bash
curl -X POST http://127.0.0.1:8000/admin/update \
  -H "X-Admin-Token: $CHAPPIE_ADMIN_TOKEN"
```
Requer `CHAPPIE_ADMIN_TOKEN` no `.env` (desabilitado por padrão — sem
token configurado, o endpoint sempre responde 403).

**Diagnóstico:** `GET /health` — se o servidor subiu com algum problema
(ex: API key ausente), o próprio rosto mostra isso (olhos cinza + banner),
sem precisar abrir o Termux pra descobrir.

## Estrutura

```
server/     FastAPI: engine químico, interpreter (Claude), persistência
renderer/   HTML/JS vanilla — consome o WS /face, não conhece química
tests/      pytest (engine, projeções emocionais, contrato, E2E) + node --test
deploy/     bootstrap.sh, chappie.service (runit), update.sh
dev/        run_local.sh, mock_llm.py (dev offline)
docs/       specs de design (handoff, system prompt, protótipo de referência)
```

## Limitações conhecidas

- `kindalive` (a lib de referência conceitual) não existe no PyPI —
  `server/engine.py` é um porte direto do engine calibrado do protótipo
  v8, documentado no próprio módulo.
- `deploy/bootstrap.sh` foi validado de verdade com `--dry-android` (roda
  toda a lógica portável: clone, venv, `.env`, idempotência) mas **não** em
  container Ubuntu real — esta máquina de dev não tem Docker instalado. Os
  passos específicos de Termux (`pkg`, `termux-services`, `termux-wake-lock`)
  só foram exercitados no Note 8 de verdade, não em CI.
