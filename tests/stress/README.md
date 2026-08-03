# Suite de estrés FORMA-IR

Mide la implementación **desplegada** de FORMA-IR: calidad de recuperación,
procedencia, calibración, packing, carga, resiliencia y aislamiento.

## Ejecutar
```bash
bash tests/stress/run_safe_suite.sh    # sin costo de LLM (recomendado)
bash tests/stress/run_full_suite.sh    # + breakpoint, spike y LLM acotado
```
En Windows: `powershell -File tests/stress/run_safe_suite.ps1`

## Configuración
Copia `.env.stress.example` a `.env.stress` (no contiene secretos: la API no
requiere autenticación). Variables clave: `BASE_URL`, `MAX_VUS`,
`MAX_REQUESTS`, `MAX_LLM_REQUESTS`.

## Seguridad
- Solo existe **producción** → carga incremental con **fail-fast** (>5 % errores
  o p95 > 3× baseline detiene la prueba).
- Las pruebas con LLM están limitadas por `MAX_LLM_REQUESTS` (default 6).
- No se modifican ni eliminan documentos del corpus.
- Nunca se imprimen claves ni secretos.

## Resultados
`results/*.json` (crudos) · `reports/FORMA_IR_STRESS_REPORT.{md,html}` (informe)

⚠️ El gold es **automático** (derivado de spans reales, sin validación humana):
las métricas de calidad son **preliminares**. Ver `datasets/queries_pending_human_review.jsonl`.
