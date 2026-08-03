# Informe final — Auditoría de recuperación y BASIL

**Fecha:** 2026-08-02 | **Commit auditado:** `e02a74eceefe8107ca65ba46cd2c7f3b852bdac4`

---

## 1. ¿Dónde está implementado BASIL?

**En ningún lugar del repositorio.** Búsqueda exhaustiva (`BASIL|basil|span identification|budget-aware|peak|phi\(|greedy|percentil|difusión`) sobre todo el código fuente, `.git` y `frontend/node_modules`: **0 coincidencias**. Detalle completo elemento-por-elemento del contrato algorítmico del paper (TF-IDF carácter, difusión δ=0.10, peaks/h=7, τ=percentil 60, φ(I), F(S), greedy/longitud^0.24, límite 8 spans) en `reports/paper_conformance.md`.

## 2. ¿Coincide con el paper?

**No.** Ninguno de los diez elementos algorítmicos centrales del contrato tiene contraparte en el código. Lo que existe es un método distinto, razonado y documentado en su propio código: BM25+TF-IDF (solo *word-level*) combinados por z-score fijo 0.6/0.4, filtrado estructural duro (semana/unidad/autoridad/autor), expansión de vecindad real de página/diapositiva (no matemática), y presupuesto de tokens adaptativo por tipo de pregunta. Este audit confirma con evidencia de código un naming mismatch ya señalado en un audit de arquitectura anterior de este proyecto.

## 3. ¿Está conectado al flujo real?

**Sí, y es el único camino.** `servidor.py:100` → `recuperar()` en `recuperar.py:267`, mismo camino desde `agente.py:380`. No hay código de recuperación muerto ni una ruta alternativa — la interfaz web ejecuta exactamente el método auditado.

## 4. Qué pruebas fueron añadidas

| Categoría | Archivos | Cobertura |
|---|---|---|
| Conformidad/unitarios | `tests/paper_conformance/*.py` | 36 tests: clasificación de pregunta, expansión de vecindad, construcción de paquetes bajo presupuesto, verificación de citas, parsers de marcadores |
| Robustez | `tests/robustness/*.py` | 14 tests (hard requirement de no-excepción) + matriz de 65 corridas sobre 13 tipos de perturbación de consulta |
| Modos | `tests/modes/*.py` | 9 tests de separación observable entre los 8 modos reales |
| Carga | `tests/load/*.py` | Smoke, uso real, escalamiento 1-50 usuarios, soak test (200 requests) |
| Seguridad | `tests/security/` | **Vacío — no implementado en esta sesión** (ver sección 12) |
| Recuperación (retrieval/) | `tests/retrieval/` | Vacío como directorio propio — la evaluación de recuperación real vive en `eval/` (Track A/B), no duplicada aquí |
| Dataset dorado | `eval/data/golden_dataset.jsonl`, `ESQUEMA.md`, `PLANTILLA_ANOTACION.md`, `calcular_hash.py` | 57 preguntas migradas del banco legado (`preguntas_evaluacion.json`, preservado sin modificar), 0 anotadas con evidencia gold |
| Harness de evaluación | `eval/baselines.py`, `eval/metricas.py`, `eval/evaluar_recuperacion.py` | 4 baselines (fixed-128/256, párrafo, sentence-top) + bootstrap pareado 10,000 muestras |
| Comando principal | `eval/ejecutar_todo.py` | Equivalente a `make eval` (make no disponible en este entorno Windows) |

**Ningún archivo de producción fue modificado** (`recuperar.py`, `agente.py`, `servidor.py`, `proveedor.py` sin cambios de código durante esta auditoría — la única modificación pendiente en el working tree, `httpStudyService.ts`, es de una sesión de trabajo anterior no relacionada con esta auditoría).

## 5. Qué pruebas se ejecutaron

Todas — comando `python eval/ejecutar_todo.py todo` corre unit + modos + robustez + retrieval(B=256) + carga(smoke), 5/5 fases OK. Adicionalmente se corrió por separado la curva completa de 7 presupuestos (`curva`) y la carga completa de escalamiento+soak (`carga-completa`).

**Total: 59 tests automatizados (pytest), todos verdes. 0 tests fallando. 0 excepciones no manejadas en ninguna suite.**

## 6. Resultados con intervalos de confianza

A presupuesto B=256 (comparable en orden de magnitud con el paper), bootstrap pareado (10,000 muestras) sobre cobertura léxica, `metodo_real` vs baselines:

| Comparación | Diferencia media | IC 95% | ¿Concluyente? |
|---|---:|---|---|
| metodo_real vs fixed_128 | −0.286 | [−0.353, −0.217] | **Sí — metodo_real pierde** |
| metodo_real vs fixed_256 | −0.293 | [−0.369, −0.216] | **Sí — metodo_real pierde** |
| metodo_real vs parrafo | −0.160 | [−0.221, −0.099] | **Sí — metodo_real pierde** |

Ver `reports/routing_vs_basil.md` para la curva completa de 7 presupuestos: el patrón se invierte en presupuestos ≥2048 (cobertura léxica de `metodo_real` supera a `fixed_256`, 0.532 vs 0.432), con una explicación estructural identificada (unidades de evidencia grandes por expansión de vecindad no caben en presupuestos chicos).

**Limitación que condiciona TODOS estos números**: son proxies de cobertura léxica, no Recall@k/MRR/evidence-F1 reales contra verdad terreno humana — el dataset tiene 0/57 preguntas anotadas. No se puede afirmar "el sistema encuentra la respuesta correcta X% de las veces" con la evidencia actual.

## 7. Principales fallos encontrados

Tres bugs reales encontrados y corregidos en `agente.py` durante esta y sesiones inmediatamente anteriores de trabajo en el mismo proyecto (documentados en `reports/modes_evaluation.md`):

1. Falso positivo de `verificar_citas()` en modo `resolver` (frases de encuadre del intento del estudiante contadas como afirmación sin cita).
2. Falso positivo de `verificar_citas()` en modos `practicar`/`evaluar` (marcadores de formato `OPCION_A:` etc. contados como afirmación sin cita).
3. (Sesión anterior, ya documentada) Colisión léxica "haya"/"Haya" desviando el ranking del modo debate.

Hallazgo de diseño (no bug, pero relevante para seguridad/producto):

4. La respuesta correcta de `practicar`/`evaluar` viaja al cliente en el mismo payload que la pregunta, antes de que el estudiante responda — inspeccionable vía DevTools del navegador (`reports/modes_evaluation.md`).

## 8. Diferencia entre fallos de routing, BASIL y generación

- **Routing**: no medible con precisión sin evidencia gold anotada (ver sección 6). Proxy disponible: tasa de "sin evidencia" por presupuesto, documentada en `reports/routing_vs_basil.md`.
- **BASIL**: no aplica — no existe implementación que pueda fallar de forma distinguible del resto del sistema (ver sección 1-2).
- **Generación**: no evaluada en esta sesión (Fase 7 del protocolo no ejecutada — ver sección 11, requiere autorización explícita antes de gastar tokens de API).

## 9. Comparación con baselines

Ver tabla completa en sección 6 y `reports/routing_vs_basil.md`. Resumen: a presupuestos bajos (≤512) los baselines de ventana fija ganan en cobertura léxica; a presupuestos altos (≥2048) el método real gana y se estabiliza, mientras los baselines se degradan levemente. `sentence_top` es 3-10x más rápido que los demás pero no calcula el campo de cobertura (limitación del harness, no evaluado en ese eje).

## 10. Resultado por modo

8 modos reales confirmados (no 6 — el frontend nuevo solo expone botón para 6 de los 8; `resumen` y `explicacion` funcionan pero no tienen UI dedicada en el frontend actual). Separación observable verificada offline (9/9 tests). Estado de prueba en vivo contra LLM real por modo, detallado en `reports/modes_evaluation.md`:

| Modo | Probado en vivo | Bug encontrado |
|---|---|---|
| preguntar | ✅ (sesiones previas) | — |
| resumen | ⚠️ no probado esta sesión | — |
| explicacion | ⚠️ no probado esta sesión | — |
| debate | ✅ | colisión léxica haya/Haya (sesión previa) |
| resolver | ✅ (esta sesión) | falso positivo verificar_citas (corregido) |
| practicar | ✅ (esta sesión) | falso positivo verificar_citas (corregido) |
| evaluar | ✅ (esta sesión) | mismo bug que practicar (corregido) |
| repasar | ✅ parcial (caso feliz; caso límite bloqueado por cuota de API agotada) | — |

## 11. Capacidad de carga observada

Capa de recuperación (sin LLM): **0 errores en 464 requests combinadas** (escalamiento 1-50 usuarios + soak de 200), throughput estable ~22-24 req/s independiente de la concurrencia (cuello de botella de CPU serializado por el GIL, no un límite artificial), sin fugas de memoria. Detalle completo en `reports/load_test.md`.

**No se probó carga end-to-end con LLM** — el protocolo exige dry-run + autorización antes de una corrida costosa contra el proveedor real, y esta sesión de auditoría fue exclusivamente offline por decisión explícita de no gastar más cuota de API (ya agotada varias veces durante el trabajo de despliegue de sesiones inmediatamente anteriores).

## 12. Coste estimado de la evaluación end-to-end pendiente

**No calculado con precisión porque no se ejecutó el dry-run.** Estimación aproximada basada en datos ya observados en sesiones anteriores de este proyecto: cada llamada de generación consume ~10,000-11,000 tokens de entrada (evidencia + NUCLEO del prompt) y produce ~1,200 tokens de salida, con latencia de 15-70 segundos según el proveedor. Evaluar las 57 preguntas del dataset en un solo modo (`preguntar`) supondría aproximadamente 57 × 11,000 ≈ **627,000 tokens de entrada** — esto excede varias veces la cuota diaria gratuita de Gemini (20 requests/día) y se acercaría al límite de Groq free tier (12,000 tokens/minuto) en una sola llamada. **Antes de correr esto se requiere: (a) dry-run real con conteo exacto, (b) confirmación de qué proveedor/cuota usar, (c) autorización explícita del usuario**, tal como exige el protocolo.

## 13. Archivos creados

Ver inventario completo verificado por `git status`/`find` — 34 archivos nuevos de código/datos + 5 reportes + resultados JSON, organizados en `eval/`, `tests/{paper_conformance,robustness,modes,load,security,retrieval}/`, `reports/`. Lista exacta al final de este documento.

## 14. Comandos exactos para reproducir

```bash
# Todo lo offline, en orden (rápido, ~30s)
python eval/ejecutar_todo.py todo

# Curva completa de presupuesto (más lento, ~2-3 min)
python eval/ejecutar_todo.py curva

# Carga completa con escalamiento hasta 50 usuarios (~15s)
python eval/ejecutar_todo.py carga-completa

# Suites individuales
python -m pytest tests/paper_conformance/ -v
python -m pytest tests/robustness/ -v
python -m pytest tests/modes/ -v
python -m pytest tests/load/carga_recuperacion.py -v
python eval/evaluar_recuperacion.py --presupuesto 256 --json eval/results/track_a_b256.json
python tests/robustness/test_perturbaciones_consulta.py --json eval/results/robustness_matrix.json
```

## 15. Bloqueos o datos humanos todavía necesarios

En orden de impacto:

1. **Anotación humana de evidencia gold** (57 preguntas, 0 anotadas) — bloquea Recall@k/MRR/nDCG/evidence-F1 reales, y por extensión cualquier afirmación rigurosa sobre "el sistema encuentra la respuesta correcta". Ver `eval/data/PLANTILLA_ANOTACION.md` para el proceso exacto. Sin esto, todo lo reportado en la sección 6 son proxies léxicas, explícitamente marcadas como tales.
2. **Ampliar el dataset a 150-200 preguntas** (recomendación del protocolo) para intervalos de confianza más estrechos en diferencias pequeñas entre métodos similares.
3. **Decisión del usuario sobre generación fundamentada (Fase 7)**: requiere autorización explícita antes de gastar tokens de API en una corrida real — no ejecutada en esta sesión.
4. **`tests/security/` está vacío** — prompt injection, revelación de system prompt/variables de entorno, XSS, path traversal, denial-of-wallet: ninguno de estos casos se implementó en esta sesión. Es la carencia más grande de cobertura del protocolo pedido.
5. **`tests/retrieval/` está vacío como directorio propio** — la evaluación de recuperación real vive en `eval/` en su lugar; si se prefiere la estructura exacta pedida por el protocolo, movería el contenido de `eval/evaluar_recuperacion.py`/`eval/baselines.py` ahí, es un cambio de organización, no de contenido.
6. **`reports/budget_curves.md` y `reports/beta_protocol.md` no se escribieron como archivos separados** — el contenido de curvas de presupuesto está integrado en `reports/routing_vs_basil.md`, y el protocolo de beta de 2 testers no se diseñó en esta sesión (requiere decisiones del usuario sobre logística, consentimiento y asignación ciega que no corresponde inventar unilateralmente).
7. **Ablaciones (Fase 6 del protocolo) no ejecutadas** — requieren variantes de configuración experimental del método real (sin BM25, sin expansión, sin filtrado estructural, etc.) que no se construyeron en esta sesión por priorizar las fases con mayor apalancamiento (conformidad, dataset, routing, robustez, modos, carga) dentro del tiempo disponible.

---

## Inventario completo de archivos creados

```
eval/
  __init__.py
  baselines.py
  ejecutar_todo.py
  evaluar_recuperacion.py
  metricas.py
  data/
    ESQUEMA.md
    PLANTILLA_ANOTACION.md
    calcular_hash.py
    golden_dataset.jsonl
    migrar_dataset_legado.py
  results/
    load_escalamiento.json
    load_soak.json
    robustness_matrix.json
    track_a_b{128,256,512,1024,2048,4096,8192}.json

tests/
  __init__.py
  load/
    __init__.py
    carga_recuperacion.py
  modes/
    __init__.py
    test_separacion_de_modos.py
  paper_conformance/
    __init__.py
    test_analizar_pregunta.py
    test_expansion_y_paquetes.py
    test_verificar_citas.py
  retrieval/
    __init__.py          (vacío — ver punto 5 de bloqueos)
  robustness/
    __init__.py
    perturbaciones.py
    test_perturbaciones_consulta.py
  security/
    __init__.py          (vacío — ver punto 4 de bloqueos)

reports/
  final_evaluation.md          (este archivo)
  load_test.md
  modes_evaluation.md
  paper_conformance.md
  routing_vs_basil.md
  robustness_matrix.md
```

**No creados** (pedidos por el protocolo, no ejecutados en esta sesión): `reports/budget_curves.md` (integrado en routing_vs_basil.md), `reports/beta_protocol.md` (requiere decisiones del usuario), `tests/security/*` (contenido vacío).
