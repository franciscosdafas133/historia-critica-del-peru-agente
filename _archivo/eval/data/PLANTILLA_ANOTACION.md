# Plantilla de anotación de evidencia dorada

Este documento es para quien vaya a anotar evidencia gold (idealmente alguien
que conozca el curso — el profesor, un asistente, o el propio estudiante que
construyó el corpus). No se debe generar evidencia gold de forma automática:
el propósito de esta anotación es medir si el sistema de recuperación
encuentra lo mismo que encontraría un humano, y esa vara de comparación
tiene que ser humana.

## Proceso para anotar una pregunta existente (de las 57 del banco legado)

1. Abre `eval/data/golden_dataset.jsonl`, busca la línea con el `question_id`
   que vas a anotar (formato `legado-L01`, `legado-A03`, etc.).
2. Lee la pregunta y el campo `notes` (ya trae una pista de dónde está la
   respuesta, heredada del banco original).
3. Busca el documento y la página/diapositiva real donde está la evidencia.
   Puedes usar el HTML de depuración del backend
   (`https://historia-critica-del-peru-agente.onrender.com/`, o local con
   `python servidor.py`) para ver qué recupera el sistema hoy y verificar
   si es correcto o no — pero la anotación debe reflejar dónde está
   REALMENTE la evidencia en el corpus, no lo que el sistema ya devuelve
   (si anotas lo que el sistema ya encuentra, la evaluación deja de medir
   nada).
4. Completa el objeto `gold_evidence` (ver `ESQUEMA.md` para el formato
   exacto) con al menos un elemento; puede haber varios si la respuesta
   requiere más de un fragmento (típico en preguntas `adyacente`/`multihop`).
5. Si puedes, completa también `expected_document_ids` y
   `acceptable_answers` (una o dos formulaciones cortas de respuesta
   correcta, para poder medir *answer containment* automáticamente).
6. Cambia `annotation_status` de `"pending"` a `"annotated"` y pon tu
   nombre o iniciales en `annotator`.
7. Para calcular `text_hash`: normaliza el texto con las mismas reglas de
   `texto_util.normtxt()` (minúsculas, sin tildes) y calcula
   `sha256(texto_normalizado)`. Hay un script auxiliar:
   `python eval/data/calcular_hash.py "texto de la evidencia aquí"`.

## Categorías nuevas a agregar (fuera del banco legado)

El protocolo de esta auditoría pide cubrir, si el material lo permite,
estas categorías que el banco de 57 preguntas no distingue explícitamente:
factuales, de definición, cronológicas, causales, comparativas, de
síntesis, de evidencia dispersa, con negación, con paráfrasis, con nombres
y fechas, no respondibles con el corpus, con premisa falsa, y que
requieren distinguir documentos parecidos.

Varias de estas YA están cubiertas implícitamente por el banco legado:
- `local` ya cubre factuales/definición (ej. L06 "¿Qué es la transición
  demográfica?", L10 "¿Qué son las ecorregiones?").
- `adyacente` ya cubre causales (ej. A03 tesis+evidencia, A07 reducciones
  coloniales+propósito).
- `multihop` ya cubre comparativas y evidencia dispersa (ej. M01 compara
  dos crisis demográficas, M08 compara costa norte vs sur andino).
- `global` ya cubre síntesis (ej. G05 "hilo argumental del curso").

Las que **no** tienen ningún representante todavía y requieren preguntas
nuevas, anotadas desde cero:

| Categoría | Ejemplo sugerido (a verificar y completar por el anotador) | question_id sugerido |
|---|---|---|
| Negación | "¿Qué factores NO explican el colapso demográfico del siglo XVI según Contreras?" | `nuevo-NEG01` |
| Paráfrasis de una pregunta ya anotada | Reformular L06 con otras palabras: "¿A qué se refiere el concepto de cambio en la estructura de nacimientos y muertes de una población?" | `nuevo-PAR01` |
| Nombres y fechas específicos | "¿En qué año publicó Klarén su libro sobre las haciendas azucareras y el origen del APRA?" | `nuevo-FEC01` |
| No respondible con el corpus | Una pregunta genuinamente fuera de alcance del curso (ej. sobre historia de otro país, no como trampa de vocabulario compartido sino claramente ajena) | `nuevo-NORESP01` |
| Premisa falsa | Una pregunta que asume algo que el corpus contradice, ej. "¿Por qué el curso sostiene que la población andina CRECIÓ durante el siglo XVI?" (el corpus dice que colapsó) | `nuevo-FALSA01` |
| Distinguir documentos parecidos | Una pregunta que fuerce a elegir entre dos lecturas de Contreras (aparece 5 veces en el curso, según nota de G02) que tratan temas similares pero distintos | `nuevo-DISTING01` |

**Estas seis filas son plantillas, no preguntas ya validadas.** Quien
anote debe: (a) confirmar que la pregunta tiene sentido para el curso real,
(b) verificar la evidencia gold contra el corpus real, (c) marcar
`annotation_status: "annotated"` solo cuando ambos pasos estén hechos.
Hasta entonces, si se agregan al JSONL, deben ir con
`annotation_status: "provisional"` como máximo.

## Separación de splits

- Las 57 preguntas legado quedan en `split: "dev"` — se pueden usar para
  diagnosticar y ajustar el sistema (por ejemplo, si se decide tunear
  `COBERTURA_MIN` o los presupuestos de `recuperar.py`).
- Las preguntas nuevas que se anoten deberían dividirse: una porción a
  `dev` (para seguir diagnosticando) y una porción reservada a `test`
  que **no se mira** hasta la evaluación final, para poder reportar un
  número no contaminado por ajuste de parámetros.
