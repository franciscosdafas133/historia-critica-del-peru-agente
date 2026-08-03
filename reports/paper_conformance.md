# Conformidad con el paper BASIL

**Fecha de auditoría:** 2026-08-02
**Commit auditado:** `e02a74eceefe8107ca65ba46cd2c7f3b852bdac4`
**Archivo bajo evaluación:** `recuperar.py` (312 líneas), invocado desde `agente.py:380` y `servidor.py:100`.

## Conclusión

**BASIL (Budget-Aware Span Identification Layer), tal como lo describe el paper, no está implementado en este repositorio.** Búsqueda exhaustiva de `BASIL|basil|span identification|budget-aware|peak|phi\(|greedy|percentil|difusión` sobre todo el árbol del repositorio (código fuente, `.git`, `frontend/node_modules`): **0 coincidencias**.

Lo que existe es un método de recuperación distinto — híbrido BM25 + TF-IDF (solo *word-level*) con expansión de vecindad estructural real (página/diapositiva contigua) y presupuesto de tokens adaptativo por tipo de pregunta. Es un método razonado y documentado en su propio código, pero **no es una implementación de BASIL**, ni parcial ni con parámetros alternativos — los componentes algorítmicos centrales del paper simplemente no tienen contraparte en el código.

Esta conclusión reafirma con evidencia de código un hallazgo ya señalado en un audit de arquitectura anterior de este proyecto (naming mismatch: se usó el nombre "BASIL" en discusiones de diseño para referirse a la "construcción de contexto post-consulta con expansión de vecindad", que es una idea relacionada en espíritu — presupuesto adaptativo, construcción del paquete después de conocer la pregunta — pero no el algoritmo formal del paper).

## Tabla de conformidad, elemento por elemento

| Elemento del contrato del paper | Valor del paper | Implementado | Archivo:línea | Efecto probable | ¿Deliberado o ausencia? |
|---|---|---|---|---|---|
| TF-IDF a nivel de palabra | requerido, peso 0.75 | **Sí**, pero sin combinación con char-level | `indexar_corpus.py:63-64` (`TfidfVectorizer(analyzer="word", ...)`); usado en `recuperar.py:89` | Captura similitud léxica normal; sin el componente de caracteres pierde robustez ante errores tipográficos/OCR que el paper sí cubre | Ausencia — no hay ningún segundo vectorizador `analyzer="char"` en el repo |
| TF-IDF a nivel de carácter, peso 0.25 | requerido | **No existe** | — | Pérdida de robustez ante variaciones ortográficas/OCR mal transcrito, que es justamente uno de los escenarios reales del corpus (5 de 39 documentos tienen OCR, según `corpus/reporte.txt`) | Ausencia |
| Combinación 0.75/0.25 de las dos señales anteriores | fórmula fija | **No existe esa combinación**; en su lugar hay `0.6*z(BM25) + 0.4*z(TFIDF)` | `recuperar.py:95` | Es una combinación distinta, con z-score en vez de coseno normalizado, y BM25 en vez de TF-IDF de caracteres | Decisión de diseño explícita y documentada (comentario en línea 95 no existe pero la combinación es consistente y estable) |
| Difusión local δ=0.10 hacia oraciones vecinas | requerido | **No existe** | — | Sin difusión, un peak aislado no se refuerza por contexto inmediato antes de generar candidatos | Ausencia |
| Detección de máximos locales (peaks) como semillas, máx. 40 | requerido | **No existe el concepto de "peak"**; en su lugar, todos los N bloques del índice reciben un score y se ordenan (`np.argsort(-score)[:pool]`, `pool=60` por defecto) | `recuperar.py:84-88, 124` | El sistema real no selecciona semillas por detección de máximos — usa top-K directo sobre el corpus completo (K=60 por defecto vía `pool`) | Ausencia — arquitectura distinta desde la raíz |
| Intervalos alrededor del peak, radio h=7 (oraciones) | requerido | **No existe radio h=7**; existe expansión de vecindad con radio en **bloques de página/diapositiva**, no oraciones: `{"local":0,"explicativa":1,"global":2}` | `recuperar.py:176`, función `expandir` líneas 152-166 | Unidad de expansión completamente distinta (páginas vs oraciones), variable por tipo de pregunta en vez de fija en 7 | Decisión de diseño — el radio varía según necesidad detectada de la pregunta, no es un parámetro fijo del paper |
| Máximo 256 tokens por intervalo candidato | requerido | **No existe ese límite por intervalo**; el límite es un presupuesto **global** por respuesta (`{"local":3000,"explicativa":9000,"global":30000}`) | `recuperar.py:76`, aplicado en `construir_paquetes` líneas 210-221 | El sistema real no acota el tamaño individual de cada paquete de evidencia, solo el total acumulado | Ausencia |
| τ = percentil 60 de valores positivos | requerido | **No existe percentil**; existe un umbral fijo de cobertura léxica `COBERTURA_MIN = 0.0 if plan["filtros"] else 0.34` | `recuperar.py:198` | Umbral estático (0.34) en vez de adaptativo al percentil de la distribución de scores de esa consulta específica | Decisión de diseño explícita, con comentario extenso en el código (líneas 181-197) explicando el trade-off |
| Conservación de los 220 mejores intervalos antes del scoring directo | requerido | **No existe**; el pool de candidatos antes de filtrar es `pool=60` (parámetro de `buscar()`) | `recuperar.py:84` | Pool de trabajo mucho menor (60 vs 220), consistente con que no hay una segunda etapa de scoring densa que requiera ese volumen | Ausencia |
| φ(I): utilidad del intervalo con 8 términos ponderados (0.80, 0.60, 0.45, 0.55, 0.25, 0.10, 0.05, −0.01) | requerido | **No existe función de utilidad multi-término**; cada candidato tiene un `score` (combinación BM25+TFIDF ya descrita) y una `cobertura` (fracción de términos de la pregunta presentes) | `recuperar.py:95, 143` | Sin coherencia interna del span, sin score de bordes, sin penalización logarítmica de longitud — el sistema real solo pondera relevancia léxica y cobertura de términos | Ausencia |
| F(S): objetivo de selección con cobertura ponderada (η=0.55) y penalización de redundancia Jaccard (μ=0.18) | requerido | **No existe optimización combinatoria**; la selección es un bucle secuencial ordenado por score descendente con corte por presupuesto y cupo de diversidad por documento (`cupo = 3 if tipo != "global" else 5`) | `recuperar.py:200-235`, cupo en línea 207 | El "control de redundancia" real es un tope de cuántos fragmentos puede aportar un mismo documento, no una penalización de solapamiento Jaccard entre spans | Ausencia — mecanismo de diversidad distinto y más simple |
| Selección greedy con ganancia marginal / longitud^0.24 | requerido | **No existe selección greedy con esa fórmula** | — | Sin ese exponente de penalización por longitud, un fragmento largo con buen score no es penalizado relativo a uno corto | Ausencia |
| Máximo 8 spans seleccionados | requerido | **No existe ese límite fijo**; el límite es `plan["k"]` semillas: `{"local":4,"explicativa":10,"global":24}` | `recuperar.py:77` | Rango de fragmentos devueltos más amplio y variable (4–24) en vez de un tope fijo de 8 | Decisión de diseño — el límite depende del tipo de pregunta, no es constante |
| Retorno final en orden de aparición en la fuente | requerido | **Retorno en orden de score descendente**, no de aparición en el documento | `recuperar.py:200` (`for i, sc, crudo, cob in cand:`, `cand` ya viene ordenado por `-score`) | El lector recibe los fragmentos en orden de relevancia estimada, no en orden narrativo/cronológico del documento original | Ausencia — no hay un paso de reordenamiento posterior |
| No superposición entre spans | requerido | **Sí se cumple**, pero por un mecanismo distinto: `usados` (set de índices de bloque ya consumidos) evita reprocesar el mismo bloque | `recuperar.py:178, 210, 219` | Efecto equivalente (no hay solapamiento en la salida), aunque no es una regla explícita de "no overlap de spans" sino una consecuencia de no repetir bloques ya usados | Deliberado en efecto, aunque implementado como restricción distinta |
| Respeto estricto del presupuesto B | requerido | **Sí se cumple** — el bucle corta cuando `tokens + tk > plan["presupuesto"]` y no hay forma de exceder el total | `recuperar.py:214-217` | Cumple el espíritu del contrato (nunca se excede el presupuesto global) | Deliberado |

## Qué SÍ hace bien el método real (fuera del contrato del paper)

Para que este reporte no sea unilateral: el método implementado tiene decisiones de diseño explícitas y documentadas que el paper no contempla, porque resuelven problemas específicos de este corpus:

- **Filtrado estructural duro** por semana/unidad/autoridad/autor antes del ranking (`recuperar.py:112-122`) — el paper asume que el documento candidato ya fue encontrado por un router externo; aquí el propio sistema hace ese trabajo de forma explícita con reglas.
- **Presupuesto y número de semillas adaptativos por tipo de pregunta** (local/explicativa/global), en vez de una constante fija de 8 spans / percentil 60 para toda consulta.
- **Ajuste de presupuesto por modo de interacción** (`MULTIPLICADOR_MODO`, `recuperar.py:265`) — resumen, práctica y evaluación piden más evidencia que una pregunta puntual; el paper no modela "modos de interacción" en absoluto.
- **Exclusión de metadiscurso** (`METADISCURSO`, `recuperar.py:37-41`) del cálculo de cobertura en modo debate, para no penalizar tesis largas del estudiante — un ajuste muy específico de este dominio educativo que no tiene análogo en el paper.
- **Determinismo total**: verificado empíricamente (10/10 corridas idénticas para la misma consulta), sin ningún componente aleatorio en `buscar()`/`construir_paquetes()`.

## Alcance de esta evaluación

Dado que BASIL no existe, **el Track B del protocolo del paper (BASIL con documento correcto ya conocido, comparado contra Fixed-128/256, Paragraph, Sentence-top, QASC-lite) no es aplicable tal cual** — no hay una implementación de BASIL que comparar. La batería de pruebas de esta auditoría evalúa en su lugar:

1. **Track A (routing/recall)**: si el método real encuentra el documento/fragmento correcto — esto sí es directamente medible con el dataset existente.
2. **Comparación del método real contra baselines simples** (ventana fija, párrafo, top-k sin expansión — este último ya existe en `evaluar.py` como `estrategia_topk`), usando las mismas métricas que el paper define (answer recall, evidence F1, tokens, recall/100 tokens), pero **sin pretender que el método real "es BASIL"** en ningún reporte generado.

Ver `reports/routing_vs_basil.md` para los resultados de esa comparación.
