# Pruebas de CERES-Omega

Suite de evaluación del motor de recuperación. Mide velocidad, estabilidad,
el gate de alcance y la contribución de cada señal.

```
python pruebas/evaluar_motor.py                       # todo, motor local
python pruebas/evaluar_motor.py --url https://…       # contra un despliegue
python pruebas/evaluar_motor.py --solo gate           # un bloque
python pruebas/evaluar_motor.py --json resultado.json
```

## Qué mide cada bloque

| Bloque | Responde a |
|---|---|
| `[1] estres` | ¿aguanta una clase entera usándolo a la vez? |
| `[2] gate` | ¿responde lo del curso y rechaza lo ajeno? |
| `[3] invariantes` | ¿sigue cumpliendo las propiedades estructurales? |
| `[3b] adversarial` | ¿se rompe con entradas hostiles o malformadas? |
| `[4] ablacion` | ¿qué señal de la frontera híbrida se gana su coste? |

## Resultados medidos (2026-08-04)

Banco: 49 preguntas del temario + 28 ajenas = 77.

| Métrica | Local | Producción (Render) |
|---|---|---|
| Latencia p50 | 44 ms | 637 ms |
| Latencia p95 | 187 ms | 1126 ms |
| Fallos | 0/154 | 0/77 |
| Concurrencia | 8 hilos, 0 errores | 4 hilos, 0 errores |

| Calidad del gate | Resultado |
|---|---|
| Responde lo del curso | **48/49 (98,0%)** |
| Rechaza lo ajeno | **13/28 (46,4%)** |
| Global | 61/77 (79,2%) · F1 0,857 |
| Invariantes | 5/5 |
| Adversarial | 12/12 sin romper |

## La limitación principal

El gate falla en **historia peruana que el curso no cubre**: 0/8 rechazadas.
"¿Qué fue el gobierno de Velasco Alvarado?" devuelve 10 fragmentos sobre
corporaciones de los años 40.

La causa no es un umbral mal puesto. El gate mide **presencia de términos**, y
una pregunta de historia peruana ajena usa el mismo vocabulario que una del
temario:

```
"reforma agraria 1969"      frac = 1.000   (fuera del corpus)
"colapso población andina"  frac = 1.000   (del curso)
```

Ningún umbral separa 1.000 de 1.000. Arreglarlo exige decidir con la evidencia
realmente recuperada — si los bloques top tratan el tema o solo comparten
palabras — no con estadística de términos sobre el corpus entero.

## Lo que esta suite NO puede decirte

**Si la evidencia recuperada es la correcta.** Eso exige anotar, por pregunta,
qué bloques son los de oro (sección 8.3 del paper: anotación previa, splits por
documento, varios conjuntos mínimos válidos). Ese banco se borró junto con
FORMA-IR en `c724b66` y no se ha reconstruido.

Un motor puede aprobar todo lo anterior y recuperar mal. Ya pasó una vez:
FORMA-IR parecía bueno y perdía contra BM25 puro (96,5% vs 98,5% Recall@1).

## Sobre la ablación

Mide el solape de Jaccard entre la evidencia con y sin cada señal:

| Señal apagada | Solape | Preguntas idénticas |
|---|---|---|
| sin bm25 | 0,663 | 8/49 |
| sin denso | 0,668 | 9/49 |
| sin estructura | 0,855 | 40/49 |
| sin título | 0,878 | 27/49 |
| sin entidad | 0,910 | 36/49 |

BM25 y el denso son los que más cambian la evidencia. Pero **"cambia" no es
"mejora"**: decidir cuál versión es mejor exige los bloques de oro anotados.

Una advertencia metodológica: la primera versión de esta ablación medía la
*decisión* del gate y daba delta 0 en todas las señales, sugiriendo que ninguna
aportaba. Era un error de medición — el gate decide antes de construir la
frontera. Medir la evidencia en vez de la decisión cambió por completo la
conclusión.
