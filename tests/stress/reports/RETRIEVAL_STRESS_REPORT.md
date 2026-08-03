# Estrés de RECUPERACIÓN — calidad del motor bajo presión

**Fecha:** 2026-08-03 · **Corpus:** 36 documentos · 2906 unidades · índice en 10.87s
**Sin LLM, sin infraestructura:** mide si el motor **acierta**, no si aguanta.

## Veredicto: 9/9 pruebas superadas

| Prueba | Valor | Umbral | Estado |
|---|---|---|---|
| A · Acierto: Recall@1 con texto literal | **97.5%** | >=90% | ✅ PASS |
| A · Acierto: Recall@3 | **99.5%** | >=95% | ✅ PASS |
| A · Acierto: unidad exacta recuperada | **94.5%** | >=70% | ✅ PASS |
| A · El doc correcto NO aparece ni en top-5 | **0.5%** | <=5% | ✅ PASS |
| C · Robustez: caida por degradacion lexica | **1.7 pp** | <=15 pp | ✅ PASS |
| E · Estabilidad ante distintas ventanas del mismo doc | **92.1%** | >=80% | ✅ PASS |
| F · Eficiencia: latencia p95 por consulta | **397.8 ms** | <=1500 ms | ✅ PASS |
| G · Calibracion discrimina acierto vs fallo | **fallo/acierto = 16.0x** | >=2x | ✅ PASS |
| G · p_doc saturado en 1.0 (menos es mejor) | **0.0%** | <=10% | ✅ PASS |

## A · Acierto a escala (400 consultas de texto literal)

Cada consulta es una frase **copiada textualmente** de una unidad real del corpus.
Es el caso más favorable posible: si algo debe acertar, es esto.

| Métrica | Valor |
|---|---|
| Recall@1 | 97.5% |
| Recall@3 | 99.5% |
| Recall@5 | 99.5% |
| Unidad exacta recuperada | 94.5% |
| MRR | 0.985 |
| Documento correcto ausente del top-5 | 0.5% |

## C · Robustez léxica (degradación progresiva)

| Nivel | Escritura | Recall@3 | Latencia p50 |
|---|---|---|---|
| 0 | intacta | 100.0% | 132.3 ms |
| 1 | sin tildes | 99.2% | 190.5 ms |
| 2 | 1 typo | 98.3% | 312.2 ms |
| 3 | 2 typos | 97.5% | 423.9 ms |
| 4 | 3 typos+minusculas | 98.3% | 510.5 ms |

**Caída total:** 1.7 puntos porcentuales entre escritura intacta y degradada.

## D · Sensibilidad al tamaño del documento

| Unidades del doc | n | Recall@1 | Recall@3 | p_doc medio |
|---|---|---|---|---|
| 1-10 | 16 | 87.5% | 100.0% | 0.0032 |
| 11-50 | 30 | 90.0% | 96.7% | 0.0026 |
| 51-150 | 119 | 97.5% | 99.2% | 0.0032 |
| 151-400 | 120 | 99.2% | 100.0% | 0.0046 |
| 401-+ | 115 | 99.1% | 100.0% | 0.0055 |

> Si el acierto cae al crecer el documento, el ranking está sesgado por tamaño y no por evidencia.

## E · Estabilidad semántica

Tres ventanas distintas del **mismo documento** como consulta: ¿convergen al mismo top-1?
**92.1%** de los casos (89 documentos probados).

## F · Eficiencia

| Palabras en la consulta | p50 | p95 |
|---|---|---|
| 1 | 99.3 ms | 794.0 ms |
| 3 | 119.3 ms | 837.7 ms |
| 10 | 148.4 ms | 361.5 ms |
| 30 | 492.1 ms | 718.5 ms |
| 100 | 953.5 ms | 1244.5 ms |
| 300 | 1437.1 ms | 1887.9 ms |

**Global:** p50 = 147.8 ms · p95 = 397.8 ms

## G · ¿La calibración sirve para algo?

| Métrica | Valor |
|---|---|
| p_doc medio cuando ACIERTA | 0.0042 |
| p_doc medio cuando FALLA | 0.0673 |
| Separación (fallo − acierto) | **0.0631** |
| Consultas con p_doc saturado en 1.0 | **0.0%** |

p_doc BAJO deberia indicar acierto. Si la separacion es ~0 o negativa, la calibracion NO discrimina.

## Documentos más perjudicados

Veces que el texto literal de un documento **no** lo devolvió como top-1:

| Fallos | Unidades del doc | Documento |
|---|---|---|
| 2 | 25 | historia-critica-del-peru-122005-a-2026-01-pre |
| 1 | 7 | clase-s2-1-transiciones-demograficas-2026-1 |
| 1 | 16 | contreras-sf-concepto-nacion |
| 1 | 64 | aramburu-mendoza-2015-futuro-poblacion-peruana |
| 1 | 195 | rivasplatavarillas-2014-cambio-paisajes-costa-norte |
| 1 | 92 | cahill-1993-independencia-sociedad-fiscalidad |
| 1 | 1029 | klaren-1976-haciendas-azucareras-apra |
| 1 | 58 | amat-y-leon-2012-perunuestrodecadadia |
