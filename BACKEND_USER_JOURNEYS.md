# Backend Integration Tests — User Journeys

Testes de fluxo real de usuário. Simula como um analista usaria o sistema via frontend (mas testamos apenas o backend).

---

## 🚀 Configuração Inicial

Antes de começar, defina essas variáveis no PowerShell:

```powershell
$BASE_URL = "http://localhost:8000"
$API_KEY = "dev-secret-key"
$headers = @{"X-API-Key" = $API_KEY; "Content-Type" = "application/json"}
```

---

## Jornada 1️⃣ — ONBOARDING (Primeiro Acesso)

**Cenário:** Um novo analista abre o dashboard pela primeira vez. Precisa verificar que o sistema está pronto, ver os modelos disponíveis e obter a predição atual.

### Passo 1.1 — Verificar se o sistema está saudável

```powershell
curl -Uri "$BASE_URL/health"
```

**Esperado:** `{"status":"ok"}`

**Por quê:** O frontend mostra um "Status: Online" se `/health` retorna ok.

---

### Passo 1.2 — Verificar readiness (BD, MLflow, modelos)

```powershell
curl -Uri "$BASE_URL/ready" -Headers @{"X-API-Key" = $API_KEY}
```

**Esperado:** `{"ready":true,"checks":{"postgres":"ok","mlflow":"ok","model":"ok"}}`

**Por quê:** O dashboard não permite ações até estar 100% pronto.

---

### Passo 1.3 — Listar modelos disponíveis

```powershell
curl -Uri "$BASE_URL/models" -Headers $headers
```

**Esperado:** Array com lgbm, lstm, nbeats, tft, ensemble — cada um com `"active": true/false` e métricas.

**Por quê:** O frontend mostra um dropdown "Modelo Ativo: ensemble" com opções para mudar.

---

### Passo 1.4 — Obter a última predição (ou criar uma nova)

```powershell
curl -Uri "$BASE_URL/predictions/history?limit=1" -Headers $headers
```

**Se vazio, criar uma:**

```powershell
curl -Uri "$BASE_URL/predictions" -Method POST -Headers $headers -Body '{"model_name":"ensemble","horizon_hours":24}'
```

**Esperado:** 
- GET history: `{"total":1,"items":[{id, created_at, target_time, q10, q50, q90, recommendation, confidence}]}`
- POST: Retorna o objeto da predição criado

**Por quê:** O dashboard exibe Q50, recomendação (BUY/SELL/HOLD) e intervalo de confiança (Q10-Q90).

---

### Passo 1.5 — Obter parâmetros padrão

```powershell
curl -Uri "$BASE_URL/parameters" -Headers $headers
```

**Esperado:** Lista com risk_level=moderate, history_days=90, confidence_threshold=0.6, active_model=ensemble, etc.

**Por quê:** O dashboard carrega essas configurações para preencher dropdowns e sliders.

---

## Jornada 2️⃣ — ANÁLISE DIÁRIA (Rotina de Trabalho)

**Cenário:** Analista chega de manhã, abre o dashboard, quer ver a situação atual em 5 minutos.

### Passo 2.1 — Check de saúde rápido (sem auth necessária)

```powershell
curl -Uri "$BASE_URL/health"
```

**Esperado:** `{"status":"ok"}` (instant)

---

### Passo 2.2 — Buscar últimas predições (últimas 5)

```powershell
curl -Uri "$BASE_URL/predictions/history?limit=5" -Headers $headers
```

**Esperado:** Array ordenado por `created_at DESC`, mostrando trend de recomendações (BUY → HOLD → SELL, etc.)

**Por quê:** O analista quer ver se o modelo mudou de opinião recentemente.

---

### Passo 2.3 — Obter dados de mercado (últimas 7 dias para gráfico)

```powershell
curl -Uri "$BASE_URL/klines?symbol=BTCUSDT&interval=1h&limit=168" -Headers $headers
```

**Esperado:** 168 candles (1h cada = 7 dias). Cada um com open, high, low, close, volume.

**Por quê:** O gráfico do dashboard mostra OHLCV + linha de predição.

---

### Passo 2.4 — Listar alertas ativos

```powershell
curl -Uri "$BASE_URL/alerts" -Headers $headers
```

**Esperado:** Array com todos os alertas (criados em Jornada 3), mostrando quais estão `"active": true/false` e `last_triggered_at`.

**Por quê:** O dashboard mostra badge "Alertas: 2 ativos" no canto superior.

---

## Jornada 3️⃣ — CONFIGURAÇÃO (Personalizar Dashboard)

**Cenário:** Analista quer ajustar suas preferências: mudar risco, criar um alerta, mudar quais features são importantes.

### Passo 3.1 — Ver configuração atual

```powershell
curl -Uri "$BASE_URL/parameters" -Headers $headers
```

**Esperado:** Lista completa (mesma da Jornada 1.5).

---

### Passo 3.2 — Atualizar nível de risco

```powershell
$body = '{"value":"aggressive","updated_by":"analyst"}'
curl -Uri "$BASE_URL/parameters/risk_level" -Method PUT -Headers $headers -Body $body
```

**Esperado:** `{"key":"risk_level","value":"aggressive","updated_at":"2026-05-16T...","updated_by":"analyst"}`

**Por quê:** Quando o modelo rodar backtest, usará este risco (afeta sinais de compra/venda).

---

### Passo 3.3 — Atualizar múltiplos parâmetros (bulk)

```powershell
$body = '{"parameters":{"history_days":180,"confidence_threshold":0.75,"alert_email":"analista@company.com"},"updated_by":"analyst"}'
curl -Uri "$BASE_URL/parameters" -Method PUT -Headers $headers -Body $body
```

**Esperado:** `{"message":"Updated 3 parameter(s)"}`

**Por quê:** O analista quer histórico de 6 meses no gráfico, confiança mínima maior, e email para alertas.

---

### Passo 3.4 — Criar um alerta customizado

```powershell
$alertBody = '{"name":"BTC acima de 100k","condition":{"type":"price_above","threshold":100000},"channel":"email","active":true}'
curl -Uri "$BASE_URL/alerts" -Method POST -Headers $headers -Body $alertBody
```

**Esperado:** `{"id":1,"name":"BTC acima de 100k","condition_json":{...},"channel":"email","active":true,"created_at":"...","last_triggered_at":null}`

**Por quê:** O analista quer ser notificado se BTC subir acima de $100k.

---

### Passo 3.5 — Criar mais um alerta (volatilidade alta)

```powershell
$alertBody = '{"name":"Volatilidade alta (RSI > 70)","condition":{"type":"rsi_above","threshold":70},"channel":"dashboard","active":true}'
curl -Uri "$BASE_URL/alerts" -Method POST -Headers $headers -Body $alertBody
```

**Esperado:** Novo alerta com `id=2`.

---

### Passo 3.6 — Listar alertas criados

```powershell
curl -Uri "$BASE_URL/alerts" -Headers $headers
```

**Esperado:** Array com 2+ alertas (os que acabou de criar).

---

### Passo 3.7 — Desativar um alerta sem deletar

```powershell
$updateBody = '{"active":false}'
curl -Uri "$BASE_URL/alerts/1" -Method PUT -Headers $headers -Body $updateBody
```

**Esperado:** Alerta 1 com `"active":false`.

**Por quê:** Às vezes o analista quer pausar um alerta temporariamente.

---

## Jornada 4️⃣ — BACKTESTING (Validar Estratégia)

**Cenário:** Analista quer testar como o modelo teria se comportado historicamente (2025-04-01 até 2026-04-30).

### Passo 4.1 — Submeter job de backtest

```powershell
$btBody = '{"model_name":"ensemble","start":"2025-04-01","end":"2026-04-30","capital":10000,"risk":"moderate"}'
curl -Uri "$BASE_URL/backtest" -Method POST -Headers $headers -Body $btBody
```

**Esperado:** `{"job_id":"uuid-string","status":"queued","message":"Job submitted"}`

**Salve o job_id para os próximos passos.**

**Por quê:** O analista vê um modal "Backtesting iniciado..." com uma barra de progresso.

---

### Passo 4.2 — Polling do status (repita a cada 10 segundos)

```powershell
# Substitua {JOB_ID} pelo uuid do passo anterior
curl -Uri "$BASE_URL/backtest/{JOB_ID}/status" -Headers $headers
```

**Esperado (primeiras 30s):** `{"job_id":"{JOB_ID}","status":"running","progress":0.15,"message":"Generating quantile predictions..."}`

**Esperado (após ~20 min):** `{"job_id":"{JOB_ID}","status":"done","progress":1.0,"message":""}`

**Por quê:** O frontend mostra barra de progresso em tempo real: "15% — Gerando previsões..."

---

### Passo 4.3 — Recuperar resultados completos

```powershell
# Só execute após status retornar "done"
curl -Uri "$BASE_URL/backtest/{JOB_ID}/results" -Headers $headers
```

**Esperado:** 
```json
{
  "job_id": "{JOB_ID}",
  "status": "done",
  "metrics": {
    "total_return_pct": 15.3,
    "buy_hold_return_pct": -27.8,
    "excess_return_pct": 43.1,
    "sharpe": 0.82,
    "max_drawdown_pct": -12.5,
    "win_rate_pct": 52.3,
    "profit_factor": 1.85,
    "n_trades": 142,
    ...
  }
}
```

**Por quê:** O dashboard exibe uma tabela de métricas e um gráfico de equity curve.

---

### Passo 4.4 — Testar outro parâmetro (aggressive)

```powershell
$btBody2 = '{"model_name":"ensemble","start":"2025-04-01","end":"2026-04-30","capital":10000,"risk":"aggressive"}'
curl -Uri "$BASE_URL/backtest" -Method POST -Headers $headers -Body $btBody2
```

**Esperado:** Novo `job_id`.

**Por quê:** Compara strategies: moderate (~43% excess return) vs aggressive (talvez -5% por muitos trades).

---

## Jornada 5️⃣ — ATIVAÇÃO DE MODELO (Trocar Modelo Ativo)

**Cenário:** Analista viu que o LightGBM tem melhor Sharpe ratio e quer ativá-lo para as próximas predições.

### Passo 5.1 — Listar modelos com métricas

```powershell
curl -Uri "$BASE_URL/models" -Headers $headers
```

**Esperado:** Array mostrando cada modelo com métricas. Exemplo:
```json
{
  "active_model": "ensemble",
  "models": [
    {"name": "lgbm", "active": false, "metrics": {"mae": 1496, "sharpe": 0.92, ...}},
    {"name": "lstm", "active": false, "metrics": {"mae": 2081, "sharpe": 0.55, ...}},
    {"name": "ensemble", "active": true, "metrics": {"mae": 1522, "sharpe": 0.82, ...}},
    ...
  ]
}
```

**Por quê:** O analista compara MAE, Sharpe, Coverage 80% para decidir qual usar.

---

### Passo 5.2 — Ativar o LightGBM

```powershell
curl -Uri "$BASE_URL/models/lgbm/activate" -Method POST -Headers $headers
```

**Esperado:** `{"model_name":"lgbm","message":"Active model set to 'lgbm'"}`

**Por quê:** A partir de agora, `/predictions` usará lgbm em vez de ensemble.

---

### Passo 5.3 — Criar predição com o novo modelo

```powershell
$predBody = '{"model_name":"lgbm","horizon_hours":24}'
curl -Uri "$BASE_URL/predictions" -Method POST -Headers $headers -Body $predBody
```

**Esperado:** Predição nova com `model_version: "lgbm"`.

**Por quê:** Valida que o modelo foi ativado e funciona.

---

### Passo 5.4 — Verificar que o modelo está realmente ativo

```powershell
curl -Uri "$BASE_URL/models" -Headers $headers
```

**Esperado:** `"active_model": "lgbm"` e `{"name": "lgbm", "active": true, ...}`

**Por quê:** Confirma no dashboard que o modelo mudou.

---

### Passo 5.5 — Voltar para ensemble

```powershell
curl -Uri "$BASE_URL/models/ensemble/activate" -Method POST -Headers $headers
```

**Esperado:** Ensemble ativado novamente.

---

## 📋 Resumo de Validação

| Jornada | O que testa | Endpoints | Tempo |
|---------|-------------|-----------|-------|
| 1 — Onboarding | Sistema pronto, modelos, primeira predição | `/health`, `/ready`, `/models`, `/predictions`, `/parameters` | 2 min |
| 2 — Análise Diária | Ver situação atual em 5 min | `/health`, `/predictions/history`, `/klines`, `/alerts` | 1 min |
| 3 — Configuração | Atualizar preferências e alertas | `PUT /parameters`, `POST/PUT /alerts` | 3 min |
| 4 — Backtesting | Testar estratégia historicamente | `POST /backtest`, `GET /{id}/status`, `GET /{id}/results` | 30 min |
| 5 — Ativação de Modelo | Trocar modelo ativo | `GET /models`, `POST /models/{name}/activate` | 2 min |

**Tempo total:** ~40 min (a maioria é backtest rodando)

---

## ✅ Critérios de Sucesso

- [ ] Jornada 1: Sistema pronto, predição criada, parâmetros carregados
- [ ] Jornada 2: Últimas predições visíveis, dados de mercado corretos, alertas listados
- [ ] Jornada 3: Parâmetros atualizados refletem no DB, alertas criados e gerenciados
- [ ] Jornada 4: Backtest submete, progride, retorna métricas realistas
- [ ] Jornada 5: Modelo mudado, nova predição usa modelo novo, listar reflete ativação

---

## 🔗 Ordem Recomendada

1. **Comece pela Jornada 1** (valida alicerces)
2. **Depois Jornada 2** (dados fluem)
3. **Depois Jornada 3** (CRUD funciona)
4. **Jornada 4** (roda backtest — pode deixar pra depois se quiser, demora ~20 min)
5. **Jornada 5** (última validação)
