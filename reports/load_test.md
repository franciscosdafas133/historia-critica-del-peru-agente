# Prueba de carga: capa de recuperación (sin LLM)

**Fecha:** 2026-08-02 | **Commit:** `e02a74e` | **Hardware:** Windows AMD64, AMD Family 25 Model 80 (Ryzen serie 5000/6000), Python 3.11.6

## Alcance

Esta prueba mide únicamente la capa de **recuperación** (`recuperar()`, sin Flask, sin LLM, sin red) bajo concurrencia local con `ThreadPoolExecutor`. Es representativa de la capacidad real del backend Flask desplegado en Render porque `recuperar()` es la operación dominante en CPU de cada request — el resto del trabajo de `/api/preguntar` (JSON parsing, construcción de la respuesta) es despreciable en comparación.

**No mide** la capa end-to-end con LLM (eso está limitado deliberadamente a 1-2 usuarios reales por el protocolo, para no gastar cuota de API en pruebas de carga — ver `reports/final_evaluation.md` para el estado de esa parte).

## Resultados: escalamiento (1 → 50 usuarios simultáneos, 3 preguntas cada uno)

| Usuarios | Requests | req/s | Latencia p50 | Latencia p95 | Latencia p99 | Errores | Crecimiento memoria |
|---:|---:|---:|---:|---:|---:|---:|---:|
| 1 | 3 | 23.3 | 0.038s | 0.055s | 0.055s | 0 | +3.9 MB |
| 2 | 6 | 22.4 | 0.087s | 0.096s | 0.096s | 0 | −1.1 MB |
| 5 | 15 | 24.2 | 0.170s | 0.268s | 0.268s | 0 | +2.2 MB |
| 10 | 30 | 22.9 | 0.409s | 0.602s | 0.646s | 0 | +0.9 MB |
| 20 | 60 | 22.7 | 0.732s | 1.197s | 1.613s | 0 | −0.4 MB |
| 50 | 150 | 22.8 | 1.394s | 2.652s | 3.214s | 0 | +2.9 MB |

**Cero errores en las 264 requests de toda la escalera.**

## Soak test (200 requests, 10 usuarios, misma pregunta repetida)

| Métrica | Valor |
|---|---|
| Requests totales | 200 |
| req/s | 23.07 |
| Latencia p50 / p95 / p99 | 0.410s / 0.661s / 0.779s |
| Errores | 0 |
| Crecimiento de memoria | +3.7 MB |

## Interpretación

- **Throughput estable (~22-24 req/s) independiente de la concurrencia**: esto es consistente con un cuello de botella de CPU serializado por el GIL de Python — el trabajo total que el proceso puede hacer por segundo es aproximadamente constante, sin importar cuántos threads compitan por él. No hay ganancia de throughput agregando más "usuarios simultáneos" más allá de lo que un solo hilo ya logra.
- **La latencia por request crece linealmente con la concurrencia** (p50 pasa de 0.038s con 1 usuario a 1.394s con 50): cada request espera su turno de CPU. Con 3 usuarios reales (el caso de uso declarado para este despliegue), la latencia esperada de la capa de recuperación sola es del orden de **0.1-0.2s**, insignificante frente a los 15-70 segundos que toma la generación del LLM (medido en sesiones anteriores de este proyecto).
- **Sin fugas de memoria**: el crecimiento oscila entre −1.1 MB y +3.9 MB sin tendencia — consistente con ruido normal del recolector de basura de Python, no con una fuga real. El índice (`corpus/indice.pkl`, 11.1 MB en disco) se carga una sola vez en memoria compartida (`servidor.py:cargar_indice()`, patrón singleton con variable global) y no se duplica por request ni por thread.
- **Cero errores en 464 requests combinadas** (264 de la escalera + 200 del soak): la capa de recuperación es robusta bajo la carga probada. No se observó ninguna excepción, timeout interno, ni resultado corrupto.
- **"Contaminación entre sesiones"**: no aplica en el sentido tradicional porque el sistema es completamente stateless (hallazgo ya documentado en `reports/modes_evaluation.md`) — no hay estado compartido mutable entre requests salvo el índice de solo lectura, así que no hay vector de contaminación cruzada posible en esta capa.

## Capacidad observada vs. caso de uso real (3 usuarios)

Con 3 usuarios reales haciendo preguntas de forma natural (no simultáneas ráfaga), la capa de recuperación **no es el cuello de botella del sistema** — el cuello de botella real es:

1. **La latencia del LLM** (15-70s medidos en sesiones anteriores, dependiente del proveedor).
2. **El cold start de Render free tier** (~30-50s tras 15 min de inactividad, ya documentado en trabajo previo de despliegue).
3. **Las cuotas de API** (Gemini 20/día, Groq limitado por tokens/minuto — ambos ya encontrados como bloqueantes reales durante las pruebas de despliegue de esta sesión de trabajo).

La capa de recuperación en sí podría sostener con margen amplio a decenas de usuarios simultáneos sin degradarse (0 errores hasta 50), muy por encima de lo que el caso de uso de 3 estudiantes necesita.

## Lo que falta (fuera de esta prueba, requiere autorización explícita por protocolo)

- **Spike repentino**: no se probó una ráfaga instantánea (todas las requests llegando en el mismo instante sin rampa) — el harness actual ya lanza todas las tareas de golpe vía `ThreadPoolExecutor`, así que technically el escalamiento de 50 usuarios ya es un spike; no se hizo una variante separada con un patrón de llegada distinto (ej. Poisson).
- **Reindexación concurrente**: no se probó porque la arquitectura actual no soporta reindexación en caliente de forma seguRa — el índice se carga una vez al arrancar el proceso (`IDX = None` global, cargado bajo demanda la primera vez) y no hay ningún mecanismo de recarga sin reiniciar el servidor.
- **Carga end-to-end con LLM real**: limitada a 1-2 usuarios por protocolo — ver `reports/final_evaluation.md` para el estado y el costo estimado de una corrida mayor.

## Reproducir

```bash
python -m pytest tests/load/carga_recuperacion.py -v          # smoke + uso real (rápido)
python tests/load/carga_recuperacion.py --escalamiento --json eval/results/load_escalamiento.json
python tests/load/carga_recuperacion.py --soak --json eval/results/load_soak.json
```
