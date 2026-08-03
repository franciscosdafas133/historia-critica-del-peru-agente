# Archivo histórico

Código y resultados de etapas anteriores del proyecto. **Nada de esto está
en uso**: la página en producción corre FORMA-IR (`forma_ir/` +
`forma_ir_recuperar.py`). Se conserva porque sirve como línea base y como
evidencia para el paper, no por nostalgia.

## Contenido

| Carpeta / archivo | Qué es | Por qué se conserva |
|---|---|---|
| `recuperar.py` | Método léxico original (BM25 + TF-IDF + expansión por metadatos curriculares). Fue el motor de producción hasta el commit `621ecbd`. | **Línea base de comparación.** Es el "antes" contra el que se mide cualquier método nuevo. |
| `evaluar.py` | Script de evaluación del método original. | Depende de `recuperar.py`. |
| `eval/` | Arnés de evaluación: dataset de 57 preguntas, métricas con bootstrap, baselines. | El dataset (`eval/data/golden_dataset.jsonl`) es reutilizable; sigue con 0/57 preguntas anotadas con gold. |
| `reports/` | Auditoría de conformidad con el paper BASIL y reportes derivados. | Historia del proyecto; BASIL fue descartado. |
| `tests_load/`, `tests_paper_conformance/`, `tests_robustness/` | Tests del método original. | Importan `recuperar.py`; se mueven juntos para no dejar el repo con imports rotos. |

## Qué sigue vivo (NO archivar)

- `forma_ir/` y `forma_ir_recuperar.py` — motor en producción.
- `forma_ir_corpus/` — corpus procesado que ese motor consume.
- `tests/forma_ir/` — 118 tests del motor activo.
- `tests/stress/` — suite de estrés y auditoría de validez. **Reutilizable
  tal cual para evaluar JIGSAW-R**: el banco de consultas, el baseline BM25
  pareado, las pruebas de circularidad y los reportes no dependen de
  FORMA-IR en particular.

## Mediciones que conviene recordar

De la auditoría del 2026-08-03 sobre el corpus real (36 documentos, 2 906 unidades):

- FORMA-IR: Recall@1 97.5 %, Recall@3 99.5 % (400 consultas de texto literal).
- **BM25 puro: Recall@1 98.5 %** en las mismas consultas pareadas (empatan en 192 de 200).
  → Ningún método nuevo debería reclamar superioridad de ranking sin superar esta cifra.
- Separabilidad respondible/no-respondible: AUC 0.893.
- Procedencia válida: 100 % en 206 consultas.
- Macro-promedio por documento 87.2 % frente a micro 96.5 % (el corpus está
  concentrado: un documento aporta el 35 % de las unidades).

Detalle completo en `tests/stress/results/` y `tests/stress/reports/`.
