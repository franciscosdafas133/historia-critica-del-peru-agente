# Evaluación de modos del agente

**Fecha:** 2026-08-02 | **Commit:** `e02a74e`

## Modos reales, enumerados desde el código (no inventados)

Fuente: `agente.py:MODOS` (dict), confirmado por `tests/modes/test_separacion_de_modos.py` (9/9 tests pasan, incluyendo verificación de que existen exactamente estos 8 y ninguno más).

| # | Clave (`MODOS`) | Frontend que lo consume | ¿Es solo una etiqueta visual? |
|---|---|---|---|
| 1 | `preguntar` | `UnderstandMode` ("Entender") | **No** — system prompt propio, verificado distinto de los otros 7 |
| 2 | `resumen` | (no expuesto en el frontend nuevo; existía en el HTML embebido viejo) | No |
| 3 | `explicacion` | (no expuesto en el frontend nuevo; existía en el HTML embebido viejo) | No |
| 4 | `debate` | `DebateMode` ("Debatir") | No |
| 5 | `resolver` | `SolveMode` ("Resolver") | No |
| 6 | `practicar` | `PracticeMode` ("Practicar") | No |
| 7 | `evaluar` | `AssessMode` ("Evaluarme") | No |
| 8 | `repasar` | `ReviewMode` ("Repasar") | No |

**Hallazgo de alcance**: el frontend nuevo (React, en `frontend/src/features/study/`) expone 6 modos con botón propio (Entender/Resolver/Practicar/Evaluarme/Repasar/Debatir), pero el backend soporta 8. `resumen` y `explicacion` existen y funcionan (verificado: `sistema_para("resumen")`/`sistema_para("explicacion")` producen prompts propios, ver test `test_cada_modo_produce_system_prompt_distinto`), pero **no tienen botón dedicado en la interfaz de producción actual** — solo son alcanzables llamando a `/api/preguntar` con `modo=resumen`/`modo=explicacion` directamente, o desde el HTML de depuración embebido en `servidor.py`. No es un modo "etiqueta visual sin comportamiento" — es lo inverso: comportamiento real sin etiqueta visual en el frontend nuevo.

## Verificación de separación observable (offline, sin LLM)

`tests/modes/test_separacion_de_modos.py`, 9/9 tests pasan:

- Los 8 modos producen system prompts **todos distintos entre sí** (`test_cada_modo_produce_system_prompt_distinto`).
- Los 8 incluyen el `NUCLEO` común como prefijo literal — cambiar de modo nunca desactiva las reglas base de evidencia/citas/AMI (`test_todos_los_modos_incluyen_el_nucleo_comun`).
- Un nombre de modo inválido cae de forma segura a `preguntar`, sin excepción (`test_modo_invalido_cae_a_preguntar_sin_excepcion`).
- `practicar` y `evaluar` comparten el mismo parser de salida (`parsear_practica`) pero tienen prompts de sistema distintos — confirmando que son dos modos reales con propósito distinto (autopráctica repetible vs. microevaluación que discrimina comprensión), no el mismo modo duplicado.

## Contrato de comportamiento por modo

Construido a partir del texto real de cada `MODO_*` en `agente.py` (no inventado) y de las pruebas en vivo contra el LLM real ya ejecutadas en sesiones anteriores de este proyecto (antes de esta auditoría offline, con `gemini-flash-latest`).

### `preguntar`
- **Propósito**: responder una consulta puntual del estudiante.
- **Entrada esperada**: pregunta libre.
- **Salida**: respuesta con citas `[n]`, cierre con pregunta (regla 10 del NUCLEO, sin excepción).
- **Restricciones**: solo evidencia recuperada, nunca conocimiento externo.
- **Criterio de éxito**: `verificar_citas()` sin problemas; cierre en forma de pregunta.
- **Debe abstenerse cuando**: `recuperar()` devuelve 0 paquetes (`servidor.py` no llama al LLM en ese caso — ver `if not generar or not r["paquetes"]: return jsonify(salida)`).
- **Estado de prueba en vivo**: ✅ probado en múltiples sesiones anteriores contra LLM real; respuesta correcta y bien citada verificada manualmente (ej. pregunta sobre colapso demográfico del siglo XVI, ver historial de esta auditoría).

### `resumen`
- **Propósito**: condensar un tema/semana/conjunto de lecturas.
- **Entrada esperada**: tema a resumir.
- **Salida**: viñetas o sub-encabezados, cada afirmación citada.
- **Restricciones**: no disolver tensiones/desacuerdos entre autores solo para que el resumen quede "limpio" (regla explícita del modo).
- **Excepción única entre los 8 modos**: puede cerrar con síntesis en vez de pregunta abierta (verificado por test: única ocurrencia esperada de la palabra "EXCEPCION" ligada a esta regla).
- **Criterio de éxito**: señala explícitamente qué NO está cubierto si se pidió resumir más de lo que la evidencia entregada permite.
- **Estado de prueba en vivo**: ⚠️ no probado en esta sesión (no expuesto en frontend actual). Presupuesto de recuperación 1.6x mayor (`MULTIPLICADOR_MODO`), verificado por lectura de código, no por llamada real.

### `explicacion`
- **Propósito**: cadena causal completa ("el porqué"), no solo el hecho.
- **Entrada esperada**: proceso o hecho a explicar.
- **Salida**: pasos ordenados, cada uno citado; si dos fuentes divergen causalmente, presentarlas por separado sin fusionar.
- **Criterio de éxito**: cierre con pregunta que ponga a prueba la cadena causal completa.
- **Estado de prueba en vivo**: ⚠️ no probado en esta sesión (no expuesto en frontend actual).

### `debate`
- **Propósito**: confrontar una tesis del estudiante con evidencia a favor y en contra.
- **Entrada esperada**: tesis o postura.
- **Salida**: reconstrucción de la tesis en palabras del agente → evidencia que sostiene → evidencia que tensiona → pregunta que fuerza decidir entre lecturas en conflicto.
- **Restricciones**: nunca "dar la contraria por deporte"; si la tesis tiene respaldo real, decirlo con claridad.
- **Ajuste especial de recuperación**: exclusión de metadiscurso (`METADISCURSO`) del cálculo de cobertura, para no penalizar tesis largas del estudiante.
- **Estado de prueba en vivo**: ✅ probado extensamente en sesiones anteriores; **bug real encontrado y corregido en esta misma línea de trabajo**: colisión léxica entre "haya" (verbo) y "Haya" (apellido de Haya de la Torre) desviaba el ranking en tesis largas — documentado, no resuelto (limitación conocida del método léxico puro, ver conversación previa).
- **Falso positivo de `verificar_citas()` corregido**: el encuadre de reconstrucción de tesis ("Entiendo tu postura...") se excluye correctamente del chequeo de citas obligatorias (`INICIO_ENCUADRE`), verificado por `tests/paper_conformance/test_verificar_citas.py::test_encuadre_de_debate_no_se_penaliza`.

### `resolver`
- **Propósito**: retroalimentación sobre el intento de respuesta YA ESCRITO por el estudiante — nunca resolver el ejercicio.
- **Entrada esperada**: ejercicio + intento del estudiante.
- **Salida**: qué está bien encaminado (con cita), qué falta (con cita a lo que debería revisar), sin reescribir el intento.
- **Restricciones**: si el intento está vacío, máximo una pista orientadora, nunca la respuesta.
- **Estado de prueba en vivo**: ✅ probado en esta misma sesión de trabajo, caso feliz y caso límite (intento vacío) — ambos con comportamiento correcto observado manualmente. **Bug real encontrado y corregido**: `verificar_citas()` marcaba falso positivo sobre las frases de encuadre propias de este modo ("no has incluido un intento...") — corregido, verificado por `test_encuadre_de_resolver_no_se_penaliza`.

### `practicar`
- **Propósito**: generar una pregunta de opción múltiple para autopráctica repetible, CON respuesta y explicación (a diferencia de `resolver`, aquí sí es apropiado dar la respuesta — es autopráctica, no un trabajo calificado).
- **Salida**: formato de marcadores (`PREGUNTA:`, `OPCION_A-D:`, `RESPUESTA_CORRECTA:`, `EXPLICACION:`), parseado por `parsear_practica()`.
- **Estado de prueba en vivo**: ✅ probado en esta sesión — caso feliz (4 opciones bien formadas, `correctAnswer` válida) y caso límite (tema fuera de corpus: el LLM correctamente NO generó una pregunta inventada, declaró que el material no cubre el tema; `parsear_practica` devolvió `None` sobre ese texto, comportamiento de fallback correcto).
- **Bug real encontrado y corregido**: `verificar_citas()` marcaba las líneas `OPCION_A:`...`OPCION_D:` como "afirmación sin cita" — corregido excluyendo los marcadores de estructura del chequeo.

### `evaluar`
- **Propósito**: microevaluación que discrimina comprensión real (no dato trivial), con explicación que conecta a la operación AMI relevante.
- **Salida**: mismo formato que `practicar`, mismo parser.
- **Estado de prueba en vivo**: ✅ probado en esta sesión — caso feliz (parseo correcto) y caso límite (3 llamadas consecutivas sobre el mismo tema): las 3 preguntas generadas resultaron **naturalmente distintas** sin necesidad de instrucción adicional de variación.

### `repasar`
- **Propósito**: tarjeta de repaso espaciado — pregunta corta, respuesta breve, ambas citadas.
- **Salida**: formato de marcadores (`TARJETA_PREGUNTA:`, `TARJETA_RESPUESTA:`), parseado por `parsear_tarjeta()`.
- **Estado de prueba en vivo**: ✅ probado en esta sesión — caso feliz sin ningún problema de citas. Caso límite de evidencia escasa quedó bloqueado por cuota de API agotada durante la sesión de pruebas (no se completó; el aviso de suficiencia sí se verificó llegando correctamente en la capa de recuperación antes de necesitar el LLM).

## Lo que NO se pudo verificar en esta auditoría (requiere LLM en vivo, fuera de alcance offline)

Estos puntos del protocolo (Fase 8 completa) requieren llamadas reales al proveedor y no se ejecutaron en esta sesión de auditoría offline, por respetar el límite de "dry-run primero, autorización antes de corrida completa" del protocolo:

- Misma pregunta en los 8 modos, comparación de consistencia factual transversal.
- Resistencia a instrucciones que intentan cambiar el modo activo desde dentro del mensaje del usuario (relacionado con el hallazgo de `instruccion_maliciosa` en `reports/robustness_matrix.md`, pero a nivel de generación, no de recuperación).
- Persistencia de estado entre turnos — **hallazgo de arquitectura ya confirmado por auditoría de código previa**: el sistema es completamente **stateless a nivel de servidor y de LLM** (`servidor.py`/`agente.py`/`proveedor.py` no mantienen historial de conversación; cada llamada a `/api/preguntar` es independiente). Por diseño, no hay "aislamiento entre sesiones" que verificar porque no hay sesiones — pero tampoco hay "conversación larga" real: cada mensaje es un turno nuevo sin memoria de los anteriores, ni siquiera dentro del mismo modo. Esto es un hallazgo arquitectónico verificable sin LLM (por ausencia de código, no por comportamiento) y debería señalarse como limitación de producto, no solo de esta auditoría.
- Filtración de respuestas correctas en modo `practicar`/`evaluar` antes de que el estudiante responda — el frontend (`PracticeMode.tsx`/`AssessMode.tsx`) ya recibe `correctAnswer` en el mismo payload que la pregunta (confirmado por lectura de `httpStudyService.ts`), así que **la respuesta correcta SÍ viaja al cliente antes de que el estudiante conteste** — es inspeccionable vía DevTools del navegador. No es una filtración por LLM, es una decisión de arquitectura (comparación de respuesta correcta hecha client-side, no server-side) que vale la pena que quede señalada como hallazgo de seguridad/diseño, no verificado como "correcto" por defecto.

## Reproducir

```bash
python -m pytest tests/modes/ -v
```
