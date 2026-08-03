# Esquema del dataset dorado (`golden_dataset.jsonl`)

Formato: JSONL, un objeto JSON por línea. Cada línea es una pregunta.

## Campos

| Campo | Tipo | Descripción |
|---|---|---|
| `question_id` | string | Identificador único. Prefijo `legado-` para preguntas migradas de `preguntas_evaluacion.json`; prefijo `nuevo-` para preguntas agregadas por esta auditoría. |
| `question` | string | Texto de la pregunta, tal cual se enviaría a `/api/preguntar`. |
| `question_type` | string | Categoría. Para preguntas legado: `local`/`adyacente`/`multihop`/`global` (categorías reales del curso, definidas en el propio `preguntas_evaluacion.json`). Para preguntas nuevas: además puede tomar valores de la lista de tipos pedida en la auditoría (`factual`, `definicion`, `cronologica`, `causal`, `comparativa`, `sintesis`, `evidencia_dispersa`, `negacion`, `parafrasis`, `nombres_fechas`, `no_respondible`, `premisa_falsa`, `distincion_documentos_similares`). |
| `difficulty` | string\|null | `facil`/`media`/`dificil`, o `null` si no se ha evaluado. |
| `expected_document_ids` | array de string | IDs o nombres de archivo de los documentos donde debería estar la respuesta. Vacío si no se ha anotado. |
| `gold_evidence` | array de objeto | Ver "Formato de `gold_evidence`" abajo. Vacío si no se ha anotado. |
| `acceptable_answers` | array de string | Respuestas o fragmentos de respuesta aceptables, para verificación de *answer containment*. Vacío si no se ha anotado. |
| `unanswerable` | bool | `true` si la pregunta está diseñada para NO tener respuesta en el corpus (para medir si el sistema declara el límite en vez de inventar). |
| `required_mode` | string | Uno de los 8 modos reales del backend: `preguntar`/`resumen`/`explicacion`/`debate`/`resolver`/`practicar`/`evaluar`/`repasar`. |
| `notes` | string | Notas del anotador o heredadas del banco legado. |
| `annotator` | string\|null | Nombre o identificador de quien anotó. `null` si no se ha anotado. |
| `split` | string | `dev` o `test`. Ningún parámetro del sistema debe ajustarse mirando resultados del split `test`. |
| `annotation_status` | string | `annotated` (evidencia gold completa y verificada), `provisional` (asistida, sin verificación humana), o `pending` (sin anotar). |
| `source` | string | Archivo de origen de la pregunta, para trazabilidad. |

## Formato de `gold_evidence`

Cada elemento es un objeto:

```json
{
  "document": "Contreras_2020_Crisisdemografica_sigloXVI",
  "page_or_slide": "7-9",
  "sentence_or_offset": "La población andina se redujo drásticamente entre 1520 y 1620...",
  "normalized_text": "poblacion andina redujo drasticamente 1520 1620...",
  "text_hash": "sha256:xxxxx..."
}
```

- `document`: nombre del documento tal como aparece en `idx["docs"]` (campo `titulo` o `archivo`).
- `page_or_slide`: página o diapositiva, como string (puede ser rango, ej. `"7-9"`).
- `sentence_or_offset`: el texto literal de la evidencia, o un offset si se prefiere.
- `normalized_text`: el mismo texto pasado por `texto_util.normtxt()`, para que las comparaciones automáticas sean insensibles a mayúsculas/tildes.
- `text_hash`: hash del texto normalizado (`sha256` del `normalized_text`), para detectar si el corpus cambió desde que se anotó esta evidencia (si se reconstruye el índice y el hash ya no aparece en ningún bloque, la anotación quedó obsoleta).

## Estado actual del dataset (2026-08-02)

- **57 preguntas migradas** desde `preguntas_evaluacion.json`, banco original del proyecto. **0 anotadas** — todas con `annotation_status: "pending"` y `gold_evidence: []`, heredado del estado `"PENDIENTE"` ya declarado en el archivo original.
- Todas las 57 preguntas legado tienen `split: "dev"`. No existe todavía un split `test` separado — construirlo requiere etiquetado humano nuevo, para no contaminar con las mismas 57 preguntas que ya se usaron para diagnosticar el sistema.
- `unanswerable` se asignó `false` a las 57 por diseño original del banco (ninguna se pensó como trampa "sin respuesta"), no por verificación.
- **No se generaron automáticamente preguntas de categorías nuevas** (negación, premisa falsa, no-respondible, etc.) como filas anotadas — eso requeriría inventar evidencia gold, lo cual el protocolo de esta auditoría prohíbe explícitamente. En su lugar, ver `PLANTILLA_ANOTACION.md` para el proceso de agregarlas con etiquetado humano real.

## Recomendación de tamaño (según protocolo)

- 50-80 preguntas: suficiente para diagnóstico dirigido (esto ya se cumple: 57).
- 150-200 preguntas representativas: preferible para una evaluación rigurosa con intervalos de confianza estrechos. **No se cumple todavía** — haría falta casi triplicar el banco actual, con anotación humana real.
- 2 estudiantes (fase beta, ver `reports/beta_protocol.md`): validan funcionamiento y experiencia de uso, no constituyen evidencia estadística de mejora educativa.
