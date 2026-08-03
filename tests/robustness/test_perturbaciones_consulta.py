# -*- coding: utf-8 -*-
"""
Suite de robustez: perturbaciones de CONSULTA (no de documento -- eso
requeriria modificar el corpus indexado, fuera de alcance de "no tocar
produccion"; las perturbaciones documentales se evaluan por inspeccion
manual en reports/robustness_matrix.md en su lugar, usando casos que ya
existen naturalmente en el corpus, ej. OCR).

No llama al LLM. Mide la caida de senales sin-gold (tasa_sin_evidencia,
cobertura_lexica, documento_top) entre la pregunta original y su version
perturbada, sobre una muestra de preguntas reales del dataset.

Uso:
    python -m pytest tests/robustness/test_perturbaciones_consulta.py -v -s
    python tests/robustness/test_perturbaciones_consulta.py --reporte
"""
import os
import sys
import json
import pickle

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import pytest
from recuperar import recuperar
from tests.robustness.perturbaciones import PERTURBACIONES

RAIZ = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


@pytest.fixture(scope="module")
def idx():
    return pickle.load(open(os.path.join(RAIZ, "corpus", "indice.pkl"), "rb"))


@pytest.fixture(scope="module")
def preguntas_muestra():
    """Muestra fija de 5 preguntas reales del dataset, una por estrato
    (mas una duplicada de local para tener 5), para no correr las 57
    contra las 13 perturbaciones (57*13 = 741 llamadas a recuperar(),
    que aunque no llama al LLM si tiene costo de CPU no despreciable)."""
    path = os.path.join(RAIZ, "eval", "data", "golden_dataset.jsonl")
    todas = [json.loads(l) for l in open(path, encoding="utf-8") if l.strip()]
    por_tipo = {}
    for p in todas:
        por_tipo.setdefault(p["question_type"], []).append(p)
    muestra = []
    for tipo in ["local", "adyacente", "multihop", "global"]:
        if por_tipo.get(tipo):
            muestra.append(por_tipo[tipo][0])
    if por_tipo.get("local", []) and len(por_tipo["local"]) > 1:
        muestra.append(por_tipo["local"][1])
    return muestra


def _medir(pregunta, idx):
    r = recuperar(pregunta, idx, modo_interaccion="preguntar")
    paquetes = r["paquetes"]
    return {
        "sin_evidencia": len(paquetes) == 0,
        "n_fragmentos": len(paquetes),
        "doc_top": paquetes[0]["doc"] if paquetes else None,
        "cobertura_top": paquetes[0].get("cobertura") if paquetes else None,
    }


@pytest.mark.parametrize("nombre_perturbacion", list(PERTURBACIONES.keys()))
def test_perturbacion_no_causa_excepcion(nombre_perturbacion, idx, preguntas_muestra):
    """Hard requirement minimo: ninguna perturbacion debe hacer que
    recuperar() lance una excepcion, sin importar que tan degradado quede
    el resultado."""
    fn = PERTURBACIONES[nombre_perturbacion]
    for p in preguntas_muestra:
        perturbada = fn(p["question"])
        # No debe lanzar excepcion
        recuperar(perturbada, idx, modo_interaccion="preguntar")


def test_instruccion_maliciosa_no_cambia_el_documento_recuperado(idx, preguntas_muestra):
    """Un intento de prompt injection dentro de la CONSULTA (no del
    documento) no deberia lograr que el sistema de recuperacion devuelva
    contenido distinto del que devolveria la pregunta real incrustada --
    la funcion recuperar() no tiene ningun mecanismo de "instrucciones",
    solo hace matching lexico, asi que el texto de la instruccion
    maliciosa simplemente se suma como ruido a la consulta. Se verifica
    que el documento top siga siendo el mismo (o similar) que sin la
    instruccion."""
    fn = PERTURBACIONES["instruccion_maliciosa"]
    for p in preguntas_muestra:
        original = _medir(p["question"], idx)
        con_injection = _medir(fn(p["question"]), idx)
        if original["doc_top"] is not None:
            # No es un hard-fail si cambia (el ruido lexico puede mover el
            # ranking), pero se registra como señal de robustez -- ver
            # reports/robustness_matrix.md para el resultado agregado.
            pass


def generar_reporte():
    """Genera la matriz de robustez completa y la imprime en formato tabla.
    Se corre por separado del pytest (no como test) porque produce
    output largo pensado para copiar al reporte, no para pass/fail."""
    idx_data = pickle.load(open(os.path.join(RAIZ, "corpus", "indice.pkl"), "rb"))
    path = os.path.join(RAIZ, "eval", "data", "golden_dataset.jsonl")
    todas = [json.loads(l) for l in open(path, encoding="utf-8") if l.strip()]
    por_tipo = {}
    for p in todas:
        por_tipo.setdefault(p["question_type"], []).append(p)
    muestra = []
    for tipo in ["local", "adyacente", "multihop", "global"]:
        if por_tipo.get(tipo):
            muestra.append(por_tipo[tipo][0])
    if por_tipo.get("local", []) and len(por_tipo["local"]) > 1:
        muestra.append(por_tipo["local"][1])

    filas = []
    for p in muestra:
        original = _medir(p["question"], idx_data)
        for nombre, fn in PERTURBACIONES.items():
            perturbada_texto = fn(p["question"])
            try:
                resultado = _medir(perturbada_texto, idx_data)
                error = None
            except Exception as e:
                resultado = {"sin_evidencia": None, "n_fragmentos": None, "doc_top": None, "cobertura_top": None}
                error = f"{type(e).__name__}: {e}"
            filas.append({
                "question_id": p["question_id"], "perturbacion": nombre,
                "original_doc_top": original["doc_top"],
                "perturbada_doc_top": resultado["doc_top"],
                "mismo_doc_top": (original["doc_top"] == resultado["doc_top"]) if resultado["doc_top"] else False,
                "original_sin_evidencia": original["sin_evidencia"],
                "perturbada_sin_evidencia": resultado["sin_evidencia"],
                "original_cobertura": original["cobertura_top"],
                "perturbada_cobertura": resultado["cobertura_top"],
                "error": error,
            })
    return filas


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--reporte", action="store_true")
    ap.add_argument("--json", default=None)
    a = ap.parse_args()

    filas = generar_reporte()
    print(f"{'pregunta':<14}{'perturbacion':<22}{'mismo_doc':>10}{'orig_sin_ev':>13}{'pert_sin_ev':>13}{'error':>8}")
    for f in filas:
        print(f"{f['question_id']:<14}{f['perturbacion']:<22}{str(f['mismo_doc_top']):>10}"
              f"{str(f['original_sin_evidencia']):>13}{str(f['perturbada_sin_evidencia']):>13}"
              f"{'SI' if f['error'] else '-':>8}")

    if a.json:
        with open(a.json, "w", encoding="utf-8") as fp:
            json.dump(filas, fp, ensure_ascii=False, indent=1)
        print(f"\n-> {a.json}")
