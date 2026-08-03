# Fase 0 — Auditoría de arquitectura real (sin suposiciones)

Fecha: 2026-08-03 · Commit desplegado: `ea33d2f` · Ambiente: producción única (no existe staging)

## Flujo real observado

```
POST /api/preguntar {pregunta, modo}
  → servidor.py:api_preguntar
  → forma_ir_recuperar.recuperar()            [adaptador]
    → (lazy, 1ª vez) preparar_indice()         ~3.4s local / ~30-40s Render frío
    → comparar_con_produccion.responder_consulta()
       → corrección tipeo (SOLO local, no desplegada)
       → pre-filtro índice invertido           [generación de candidatos]
       → calcular_vector_evidencia (BM25F+cobertura+compacidad+ancla)  [evidencia léxica]
       → p_valor_calibrado (nulo dividido por familia)                 [calibración]
       → agregar_documentos (Bonferroni m_d)                           [corrección documental]
       → rankear_unidades_de_documento                                 [ranking]
       → empaquetar_por_cobertura_submodular (epsilon, presupuesto)    [packing]
  → (opcional generar:true) proveedor.generar → LLM → verificar_citas  [generación final]
```

## Tabla de componentes

| Componente | Archivo | Estado | Instrumentación disponible | Riesgo |
|---|---|---|---|---|
| Endpoint consulta | `servidor.py:api_preguntar` | desplegado | `ms_recuperacion` total; sin request_id | Medio: sin timings por etapa |
| Adaptador FORMA-IR | `forma_ir_recuperar.py` | desplegado | avisos de calibración débil | Bajo |
| Candidatos (índice invertido) | `forma_ir/comparar_con_produccion.py` | desplegado (ea33d2f) | ninguna separada | Bajo |
| Evidencia léxica | `forma_ir/evidencia.py` | desplegado | ninguna separada | Bajo |
| Calibración nulo dividido | `forma_ir/calibracion.py` | desplegado | avisos fallback univariante | Medio: 22 familias calibradas, resto fallback |
| Bonferroni documental | `forma_ir/documento.py` | desplegado | p_doc expuesto internamente, NO en API | Bajo |
| Packing submodular | `forma_ir/empaquetado.py` | desplegado | tokens_totales, fraccion_retenida internos | Bajo |
| Generación LLM | `proveedor.py` | desplegado | uso{entrada,salida,ms,proveedor} | Alto: cuota/límites del proveedor |
| Corrección tipeo | `comparar_con_produccion.py:corregir_terminos_query` | **SOLO local, sin desplegar** | correcciones_tipeo | Delta local/prod documentado |
| Worker HTTP | Render + gunicorn | desplegado | logs Render (no accesibles por API) | **Alto: WEB_CONCURRENCY=1 → cola serial** |

## Decisiones de seguridad tomadas

1. **Solo existe producción** (3 usuarios reales) → carga incremental con fail-fast, duraciones reducidas respecto al plan ideal, tope global `MAX_REQUESTS`.
2. Pruebas de **calidad profunda** (p-valores, procedencia a nivel unidad, epsilon sweep) se ejecutan **localmente contra el mismo código** (los campos internos no se exponen por API — regla: no inventar endpoints). El endpoint desplegado se usa para E2E, carga y contrato público.
3. **Sin credenciales requeridas**: la API no tiene auth. `.env.stress` existe solo para URLs/límites; `.gitignore` ya cubre `.env.*`.
4. LLM limitado por `MAX_LLM_REQUESTS` (default 6) — la cuota del proveedor es compartida con usuarios reales.
5. No se modifica código de producción para instrumentar (riesgo > beneficio durante la evaluación); la falta de timings por etapa se reporta como hallazgo.
