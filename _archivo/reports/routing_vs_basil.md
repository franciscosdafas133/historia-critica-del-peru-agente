# Track A/B: método real vs baselines

**Fecha:** 2026-08-02 | **Commit:** `e02a74e` | **Dataset:** `eval/data/golden_dataset.jsonl` (57 preguntas, 0 anotadas con evidencia gold — ver limitación central abajo)

## Limitación central: no hay Recall@k / MRR / evidence-F1 reales

Ninguna de las 57 preguntas del dataset tiene `expected_document_ids` ni `gold_evidence` anotados por un humano (heredado del estado `PENDIENTE` ya declarado en `preguntas_evaluacion.json` desde antes de esta auditoría). Sin esa anotación, **no existe una verdad terreno contra la cual calcular Recall@1/3/5, MRR, nDCG o evidence-F1 reales**. El harness (`eval/evaluar_recuperacion.py`) está preparado para calcularlos automáticamente en cuanto existan filas con `annotation_status: "annotated"` — el código no necesita cambios, solo datos.

Lo que se reporta aquí son **proxies explícitamente declaradas como tales**, no sustitutos de recall real:

- **tasa_sin_evidencia**: fracción de preguntas donde el método devolvió cero fragmentos.
- **cobertura_lexica_media**: promedio de la fracción de términos de la pregunta presentes en el texto recuperado (campo `cobertura` que `recuperar.py` ya calcula internamente). Esto mide *coincidencia léxica superficial*, no si la respuesta correcta está presente.
- **tokens_promedio, latencia**: costo real, medible sin ambigüedad.

**Ningún número de este reporte debe leerse como "el sistema encuentra la respuesta correcta X% de las veces".** Para eso hace falta anotación humana — ver `eval/data/PLANTILLA_ANOTACION.md`.

## Métodos comparados

| Método | Descripción | Archivo |
|---|---|---|
| `metodo_real` | El sistema en producción: `recuperar()` en `recuperar.py` — BM25+TFIDF combinados 0.6/0.4, filtrado estructural, expansión de vecindad real página/diapositiva, presupuesto adaptativo por tipo de pregunta. **No es BASIL** — ver `reports/paper_conformance.md`. | `recuperar.py` |
| `fixed_128` / `fixed_256` | Ventana fija: mismo ranking híbrido, sin expansión ni filtrado, cada bloque recortado a 128/256 tokens. | `eval/baselines.py` |
| `parrafo` | Mismo ranking híbrido, bloques completos sin recortar ni expandir. | `eval/baselines.py` |
| `sentence_top` | Similaridad coseno TF-IDF pura (sin BM25, sin combinación), sin ningún mecanismo de diversidad. El baseline más simple posible. | `eval/baselines.py` |

Todos los métodos comparten: mismo corpus, mismo tokenizador (`texto_util.tokenizar`), mismo índice (`corpus/indice.pkl`, generado 2026-07-30), mismas 57 preguntas, mismo presupuesto por corrida.

## Resultados por presupuesto fijo (comparación justa — mismo B para todos)

### B = 256 (comparable en orden de magnitud con el paper)

| Método | sin_evidencia | cobertura léxica | tokens prom. | latencia p50 | latencia p95 |
|---|---:|---:|---:|---:|---:|
| **metodo_real** | **59.6%** | 0.458 | 69 | 0.047s | 0.065s |
| fixed_128 | 0.0% | 0.471 | 252 | 0.137s | 0.174s |
| fixed_256 | 0.0% | 0.478 | 252 | 0.135s | 0.180s |
| parrafo | 0.0% | 0.345 | 246 | 0.139s | 0.168s |
| sentence_top | 0.0% | n/d* | 252 | 0.013s | 0.015s |

*sentence_top no calcula el campo `cobertura` porque no pasa por `buscar()` — usa cosine similarity directo.

**A este presupuesto, el método real pierde claramente** frente a los tres baselines léxicos, con diferencia estadísticamente concluyente (bootstrap pareado, 10,000 muestras, IC95%):

- metodo_real vs fixed_128: diferencia de cobertura −0.286 (IC95% [−0.353, −0.217]) — **concluyente**
- metodo_real vs fixed_256: diferencia −0.293 (IC95% [−0.369, −0.216]) — **concluyente**
- metodo_real vs parrafo: diferencia −0.160 (IC95% [−0.221, −0.099]) — **concluyente**

### Causa raíz identificada (no es un artefacto del harness)

El método real construye paquetes por **expansión de vecindad estructural**: una semilla se expande a páginas/diapositivas contiguas completas antes de aplicar el presupuesto. Esto produce paquetes de tamaño muy variable — en una corrida de ejemplo, el primer paquete midió 152 tokens pero el segundo 2,312 tokens (contexto de página vecina completa). A presupuesto=256, ese segundo paquete no cabe en absoluto y se descarta entero, en vez de recortarse — a diferencia de los baselines, que operan a nivel de bloque individual y siempre pueden rellenar el presupuesto con más unidades pequeñas.

**Esto no es un bug de recuperación: es una decisión de diseño (unidades de evidencia grandes y coherentes en vez de fragmentos sueltos) que tiene un costo real a presupuestos pequeños.**

## Curva completa de presupuesto

| B (tokens) | metodo_real sin_ev | metodo_real cob.léx | fixed_256 sin_ev | fixed_256 cob.léx | metodo_real lat p50 | fixed_256 lat p50 |
|---:|---:|---:|---:|---:|---:|---:|
| 128 | 79.0% | 0.334 | 0.0% | 0.309 | 0.061s | 0.189s |
| 256 | 59.6% | 0.458 | 0.0% | 0.478 | 0.047s | 0.135s |
| 512 | 36.8% | 0.480 | 0.0% | 0.459 | 0.048s | 0.139s |
| 1024 | 19.3% | 0.530 | 0.0% | 0.447 | 0.044s | 0.139s |
| 2048 | 5.3% | 0.532 | 0.0% | 0.432 | 0.047s | 0.142s |
| 4096 | 3.5% | 0.534 | 0.0% | 0.422 | 0.046s | 0.137s |
| 8192 | 3.5% | 0.538 | 0.0% | 0.391 | 0.047s | 0.138s |

**Lectura del cruce:** el método real necesita **al menos ~1024 tokens de presupuesto** para que su tasa de "sin evidencia" caiga por debajo del 20%, y a partir de **~2048 tokens su cobertura léxica supera a `fixed_256`** (0.532 vs 0.432) y la ventaja se mantiene estable hasta 8192. `fixed_256` se mantiene siempre en 0% de "sin evidencia" (nunca descarta nada, siempre rellena con más bloques pequeños) pero su cobertura léxica se estanca e incluso **decae levemente** en presupuestos altos (0.478 en B=256 → 0.391 en B=8192) — señal de que rellenar con más bloques de baja relevancia diluye la cobertura promedio en vez de mejorarla.

**No se cumple la premisa de "más presupuesto siempre es mejor"** para ninguno de los dos métodos de forma simple: el método real mejora con más presupuesto hasta estabilizarse (~2048+), mientras que los baselines de ventana fija se degradan levemente al forzarlos a incluir más contenido de menor relevancia.

**Remanente irreducible de "sin evidencia" (~3.5%) desde B=4096 en adelante**: consistente con preguntas del estrato `global` (12 preguntas) que, por diseño, requieren visión del corpus completo o detectar ausencias — el propio banco de preguntas advierte esto explícitamente para G04 ("requiere detectar AUSENCIAS. Ningún score de similitud recupera una ausencia") y G03 ("la recuperación por similitud tiende a suprimir el desacuerdo"). Esto no se puede resolver con más presupuesto — es una limitación estructural de cualquier método basado en similitud léxica/semántica sobre pasajes, documentada también en el propio código (`comprobar_suficiencia`, aviso "pocas fuentes" para preguntas globales).

## Baseline `sentence_top`: más rápido, sin cobertura medible

`sentence_top` es consistentemente el método más rápido (p50 ~0.013-0.016s, 3-10x más rápido que los demás) porque hace una sola operación de similaridad coseno sin filtrado ni expansión. No calcula `cobertura` porque no pasa por la función `buscar()` compartida — sería necesario extenderlo para poder compararlo en ese eje; queda documentado como limitación del harness, no evaluado en esa dimensión.

## Qué falta para una comparación rigurosa completa

1. **Anotación humana de evidencia gold** (ver `PLANTILLA_ANOTACION.md`) — sin esto, todo lo anterior mide *coincidencia léxica*, no *si el sistema encuentra la respuesta correcta*. Es la única vía para calcular Recall@k/MRR/evidence-F1 reales.
2. **Answer recall / evidence F1 reales** requieren además `acceptable_answers` anotadas.
3. Ampliar el dataset a 150-200 preguntas (recomendación del protocolo) para intervalos de confianza más estrechos — con 57 preguntas el bootstrap ya produce intervalos razonablemente angostos para diferencias grandes (ver arriba), pero diferencias pequeñas entre métodos similares (ej. fixed_128 vs fixed_256) podrían no alcanzar significancia con esta muestra.

## Reproducir estos resultados

```bash
python eval/evaluar_recuperacion.py --presupuesto 256 --json eval/results/track_a_b256.json
python eval/evaluar_recuperacion.py --presupuesto 1024 --json eval/results/track_a_b1024.json
# ... etc para 128, 512, 2048, 4096, 8192
```

Los JSON crudos con resultado por-pregunta (no solo el resumen) están en `eval/results/track_a_b*.json`.
