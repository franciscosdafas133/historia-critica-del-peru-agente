# -*- coding: utf-8 -*-
"""
Migra preguntas_evaluacion.json (57 preguntas, raiz del repo, formato legado)
al formato JSONL versionado usado por el harness de evaluacion nuevo.

NO modifica ni borra preguntas_evaluacion.json -- ese archivo sigue siendo
la fuente original. Este script solo lee y proyecta a un esquema nuevo.

Mapeo de campos legado -> nuevo (ver eval/data/ESQUEMA.md para el contrato
completo):
  id        -> question_id       (con prefijo "legado-" para dejar claro
                                   el origen y no colisionar con IDs nuevos)
  estrato   -> question_type      (local/adyacente/multihop/global se
                                   preservan tal cual: son las categorias
                                   reales que ya disenio el curso, no las
                                   fuerzo a las categorias del prompt del
                                   paper -- ver notas en ESQUEMA.md)
  pregunta  -> question
  evidencia_gold -> gold_evidence (vacio en el legado -> queda vacio;
                                   annotation_status se marca "pending")
  notas     -> notes

Campos que el legado NO tiene y se rellenan con valores explicitos de
"falta dato", nunca inventados:
  difficulty          -> null
  expected_document_ids -> []  (vacio, no inferido)
  acceptable_answers  -> []
  unanswerable        -> false (asuncion explicita: ninguna de las 57
                          preguntas del legado fue disenada como "sin
                          respuesta en el corpus" -- todas tienen una nota
                          de "respuesta esperada" o el documento fuente)
  required_mode       -> "preguntar" (asuncion explicita: el banco legado
                          se disenio para /api/preguntar, no para otros
                          modos -- ver docstring de preguntas_evaluacion.json)
  annotator           -> null
  split               -> "dev"  (todo el legado se asigna a development;
                          ningun dato de aqui debe usarse para ajustar
                          parametros y luego reportarse como "test")
"""
import json
import os

RAIZ = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
ENTRADA = os.path.join(RAIZ, "preguntas_evaluacion.json")
SALIDA = os.path.join(os.path.dirname(os.path.abspath(__file__)), "golden_dataset.jsonl")


def migrar():
    with open(ENTRADA, encoding="utf-8") as f:
        legado = json.load(f)

    filas = []
    for p in legado["preguntas"]:
        tiene_evidencia = bool(p.get("evidencia_gold"))
        filas.append({
            "question_id": f"legado-{p['id']}",
            "question": p["pregunta"],
            "question_type": p["estrato"],
            "difficulty": None,
            "expected_document_ids": [],
            "gold_evidence": p.get("evidencia_gold", []),
            "acceptable_answers": [],
            "unanswerable": False,
            "required_mode": "preguntar",
            "notes": p.get("notas", ""),
            "annotator": None,
            "split": "dev",
            "annotation_status": "annotated" if tiene_evidencia else "pending",
            "source": "preguntas_evaluacion.json",
        })

    with open(SALIDA, "w", encoding="utf-8") as f:
        for fila in filas:
            f.write(json.dumps(fila, ensure_ascii=False) + "\n")

    pendientes = sum(1 for f in filas if f["annotation_status"] == "pending")
    print(f"Migradas {len(filas)} preguntas -> {SALIDA}")
    print(f"  anotadas: {len(filas) - pendientes}")
    print(f"  pendientes de evidencia gold: {pendientes}")


if __name__ == "__main__":
    migrar()
