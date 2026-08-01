# Agente educativo — Historia Crítica del Perú (122005-A, 2026-1)

Sistema de recuperación de evidencia sobre los materiales autorizados de un curso
universitario, con generación citada y orientación de Alfabetización Mediática e
Informacional (AMI).

Curso: Historia Crítica del Perú · sección A · periodo 2026-1 · prof. Juan Fonseca
Universidad del Pacífico · Departamento de Humanidades · 4 créditos

---

## Estado

| Fase | Componente | Estado |
|---|---|---|
| 1 | Ingesta y anclaje a la fuente | funcionando |
| 2 | Índices léxico + estructural | funcionando |
| 3 | Recuperación con expansión post-consulta | funcionando |
| 4 | Generación con citas + verificación | funcionando (requiere API key para generar) |
| 5 | Banco de evaluación comparativa | funcionando |
| — | Anotación de evidencia gold | **pendiente, manual** |
| — | Embeddings semánticos | **decisión abierta a propósito** |

---

## El corpus

**39 documentos lógicos** (de 52 archivos) · **738.363 tokens** · **1.348 bloques anclados**

| Tipo | Docs | Tokens | Autoridad |
|---|---|---|---|
| lectura | 21 | 671.048 | académica |
| clase | 12 | 41.986 | docente |
| rector (sílabo, cronograma) | 2 | 12.827 | oficial |
| evaluación | 2 | 7.823 | oficial |
| guion de actividad | 2 | 4.679 | oficial |

Cuatro hechos que condicionan el diseño:

- **El curso son las lecturas.** Las diapositivas aportan el 5,7% del contenido textual, pese a
  pesar 640 MB en disco. Su peso es imagen: mapas, gráficos demográficos, reproducciones de
  documentos históricos. El peso en disco no predice el contenido.
- **Un 26% del curso estaba invisible.** Cinco documentos eran escaneos sin texto extraíble —
  210 páginas. El corpus pasó de 587.601 a 738.363 tokens al incorporar el OCR. Sin ese paso el
  agente habría respondido "no tengo información" sobre semanas completas sin que nadie supiera
  por qué. Un caso, Sobrevilla, era un PDF *mixto*: tenía texto en algunas páginas (10.436 tokens)
  e imagen en el resto, y solo el OCR reveló los 38.251 reales.
- **Dos libros son el 33% del corpus.** Klarén (146k tokens) y Aldana-Pereyra (99k). Cualquier
  búsqueda por similitud tiende a devolver fragmentos suyos solo por su tamaño; el recuperador
  aplica un cupo por documento para contrarrestarlo.
- **El corpus cabe entero en contexto.** 738k tokens entran en una ventana de 1M. Por eso el
  modo `completo` no es un baseline teórico sino un competidor real.

---

## Instalación

```
python -m pip install pymupdf python-pptx python-docx tiktoken rank_bm25 scikit-learn numpy easyocr
```

Para generar respuestas además: `python -m pip install anthropic` y `ANTHROPIC_API_KEY` en el entorno.

## Construcción, en orden

```
python construir_corpus.py     # carpeta_documentos -> corpus/corpus.jsonl + manifiesto.json
python indexar_corpus.py       # corpus/ -> corpus/indice.pkl
```

`construir_corpus.py` incorpora automáticamente los textos OCR presentes en `corpus/_ocr/`.
Volver a correrlo tras completar el OCR actualiza el corpus.

## Uso

```
python recuperar.py "¿por qué colapsó la población andina en el siglo XVI?"
python recuperar.py --texto "¿qué dice Contreras sobre el centralismo?"

python agente.py "¿cuándo es el examen parcial?"
python agente.py --modo seccion --semana 2 "resume la semana"
python agente.py --modo completo "¿cómo se relacionan las dos unidades?"
python agente.py "..." --enviar          # llama a la API
python agente.py "..." --guardar p.json  # guarda el prompt sin enviarlo

python evaluar.py                        # compara las cuatro estrategias
python evaluar.py --estrato multihop --csv salida.csv
```

---

## Arquitectura

```
carpeta_documentos/            material original, intacto, fuente canónica
   Historia crítica del Perú/
      Unidad N. .../Semana N/  la jerarquía de carpetas ES metadato

construir_corpus.py   extracción + anclaje + resolución de duplicados
indexar_corpus.py     BM25 + TF-IDF + índices estructurales + vecindad
recuperar.py          análisis de pregunta, búsqueda híbrida, expansión, presupuesto
agente.py             prompt pedagógico AMI, tres modos, verificación de citas
evaluar.py            banco comparativo por estrato
texto_util.py         tokenizador compartido (el índice serializado lo referencia)

corpus/
   corpus.jsonl       1.117 bloques con texto y procedencia completa
   manifiesto.json    39 documentos con metadatos y estructura del curso
   indice.pkl         índices serializados
   _ocr/              textos reconocidos de los PDFs escaneados
   reporte.txt        resumen legible
```

### Decisiones de diseño y su porqué

**PDF como fuente canónica sobre PPTX.** Medido, no supuesto: en los 13 pares duplicados el PDF
conserva consistentemente más texto (5.827 vs 5.244 tokens en la misma clase). `python-pptx` no
alcanza el texto dentro de SmartArt ni de formas agrupadas. Se pierden las notas del presentador,
pero suman solo 2.824 tokens en todo el corpus.

**Bloques por página/diapositiva, no por cada N tokens.** Se usan los cortes que el documento ya
trae. Cada bloque conserva archivo, página y formato, de modo que toda cita es una coordenada
verificable contra el original.

**Metadatos derivados de la ruta, no de un modelo.** Unidad, semana, tipo, autor y año salen de la
estructura de carpetas y del cronograma oficial. Cero costo, cero alucinación, reproducible.

**Autoridad como campo de primera clase.** El sílabo y el cronograma son normativos para fechas y
evaluación; las lecturas lo son para el contenido histórico; las diapositivas son la versión del
profesor. Una pregunta sobre el examen filtra a `autoridad=oficial` antes de rankear.

**Sin embeddings todavía.** No es un olvido: es la decisión de no cerrar tecnología antes de medir.
El índice léxico + estructural ya responde y sirve de baseline honesto. Los embeddings se añaden
cuando la medición muestre qué aportan sobre esta base.

**Expansión estructural post-consulta.** Los bloques almacenados son finos; los límites del
fragmento entregado se deciden *después* de conocer la pregunta, creciendo por vecindad real del
documento. Radio 0 para preguntas locales, 1 para explicativas, 2 para globales. Esta es la única
pieza conceptualmente propia de la propuesta y es la que el banco de evaluación debe justificar.

**Presupuesto adaptativo.** No significa "usar pocos tokens" sino "los necesarios": 3.000 para una
pregunta local, 9.000 para una explicativa, 30.000 para una global.

---

## Resultados de la comparación

Tokens de entrada promedio por pregunta, sobre 57 preguntas estratificadas:

| estrato | completo | sección | recuperación | topk_fijo |
|---|---|---|---|---|
| local | 746.956 | 53.920 | 7.406 | 2.791 |
| adyacente | 746.966 | 72.933 | 7.413 | 2.700 |
| multihop | 746.967 | 76.406 | 11.168 | 2.597 |
| global | 746.960 | 42.374 | 6.835 | 3.515 |
| **promedio** | **746.962** | **62.410** | **8.376** | **2.868** |

Contexto completo cuesta **89x** más entrada por pregunta que recuperación. El presupuesto
adaptativo responde al tipo de pregunta: recuperación gasta 7.406 tokens en preguntas locales y
11.168 en multihop, mientras las otras estrategias tratan igual ambos casos.

El estrato global gasta poco (6.748) porque el filtro de pertinencia descarta bloques que no
comparten vocabulario con preguntas abstractas ("¿cuál es el hilo argumental del curso?"). Eso es
correcto en costo pero **sugiere que las preguntas globales deberían enrutarse a modo completo**,
no resolverse con recuperación. Es una hipótesis que la anotación gold debe confirmar.

### Diversidad de fuentes consultadas

Documentos distintos por pregunta — mide si la evidencia viene de varias fuentes o se concentra:

| estrato | recuperación | topk_fijo |
|---|---|---|
| local | 3,2 | 2,7 |
| adyacente | 2,7 | 2,1 |
| **multihop** | **4,9** | **2,9** |
| global | 2,3 | 3,9 |

En multihop la expansión estructural consulta casi el doble de documentos que el top-k ingenuo,
que es exactamente donde debía notarse. En global pierde, reforzando que ese estrato pertenece al
modo completo. Nótese que topk_fijo devuelve con frecuencia varios fragmentos del mismo documento
grande: es el fallo de redundancia del RAG por similitud, aquí medido.

**Lo que estos números NO dicen.** Miden costo y composición, no calidad. Falta la anotación de
evidencia gold, sin la cual no se puede calcular recall de evidencia ni afirmar que recuperar menos
sea recuperar mejor. Con prompt caching, además, la ventaja económica de recuperación se reduce
sustancialmente: el corpus es estable entre consultas, que es el escenario ideal para cachear.

---

## Limitaciones conocidas

- **La anotación gold no existe.** Es el cuello de botella del proyecto y es trabajo manual.
  Hasta tenerla, `evaluar.py` compara costo, no acierto.
- **OCR con errores.** Cinco lecturas eran escaneos sin texto (210 páginas). Son fotografías de
  libros físicos tomadas con CamScanner —la marca aparece en las 68 páginas de O'Phelan—, así que
  el texto llega con orden de palabras alterado dentro de las frases y errores en cifras y nombres
  propios. El constructor limpia marcas y líneas de ruido (~1,7% del texto), los bloques afectados
  quedan marcados como `ocr` y el prompt instruye al modelo a advertirlo al estudiante.
- **El contenido visual se pierde.** Mapas, gráficos demográficos y reproducciones de documentos
  históricos concentran buena parte del sentido en las clases y no se extraen. En un curso de
  historia con eje geográfico esto no es marginal.
- **La Unidad 2 no tiene diapositivas**, solo lecturas. Puede que aún no se haya dictado.
- **El análisis de pregunta es por reglas.** Clasificar el tipo con palabras clave es frágil ante
  preguntas mal formuladas. Sustituirlo por un modelo es una decisión a tomar con datos.

---

## Próximo paso

Anotar la evidencia gold de las 57 preguntas de `preguntas_evaluacion.json`. Es lo único que
convierte esta comparación de costos en una medición de calidad, y es lo que permitirá decidir si
la expansión estructural aporta lo suficiente como para justificar su complejidad frente a
contexto completo con caching.
