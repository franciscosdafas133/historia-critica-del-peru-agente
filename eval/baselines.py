# -*- coding: utf-8 -*-
"""
Baselines de comparacion para el metodo real de recuperar.py. Codigo nuevo
de evaluacion, no toca produccion. Cada baseline recibe (q, idx, presupuesto)
y devuelve una lista de "paquetes" con la misma forma que recuperar()
(campos: doc, cita, paginas, tipo, autoridad, archivo, tokens, texto, score),
para que las metricas de eval/metricas.py operen igual sobre todos.
"""
import os
import sys

import numpy as np
from sklearn.metrics.pairwise import cosine_similarity

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from recuperar import buscar
from texto_util import tokenizar


def _empaquetar(idx, i, score, cobertura=None):
    B, D = idx["bloques"], idx["docs"]
    d = D[B[i]["doc_id"]]
    u = "pagina" if "pagina" in B[i]["fuente"] else "diapositiva"
    return {
        "doc": d["titulo"], "cita": d.get("cita") or d["titulo"],
        "tokens": B[i]["tokens"], "texto": B[i]["texto"],
        "paginas": f"{u} {B[i]['fuente'][u]}", "tipo": d["tipo"],
        "autoridad": d["autoridad"], "archivo": d["archivo"],
        "unidad": d.get("unidad"), "semana": d.get("semana"),
        "score": round(float(score), 3), "cobertura": cobertura,
        "ocr": B[i]["fuente"].get("ocr", False), "bloque_id": B[i]["bloque_id"],
    }


def fixed_window(q, idx, presupuesto, ventana_tokens=128):
    """Ventana fija: toma los bloques mejor rankeados por el mismo score
    hibrido BM25+TFIDF que usa el sistema real, pero SIN expansion de
    vecindad ni filtrado estructural -- cada bloque entra tal cual hasta
    llenar el presupuesto, cortando bloques individuales a `ventana_tokens`
    si son mas grandes (aproximado por proporcion de caracteres, no hay
    tokenizador exacto de subcadena aqui)."""
    plan = {"tipo": "explicativa", "filtros": {}, "presupuesto": 10**9, "k": 10**6}
    cand = buscar(q, idx, plan, pool=200)
    paquetes, tokens_usados = [], 0
    for i, sc, crudo, cob in cand:
        if tokens_usados >= presupuesto:
            break
        p = _empaquetar(idx, i, sc, cob)
        if p["tokens"] > ventana_tokens:
            frac = ventana_tokens / p["tokens"]
            corte = max(1, int(len(p["texto"]) * frac))
            p["texto"] = p["texto"][:corte]
            p["tokens"] = ventana_tokens
        if tokens_usados + p["tokens"] > presupuesto:
            continue
        paquetes.append(p)
        tokens_usados += p["tokens"]
    return paquetes


def parrafo(q, idx, presupuesto):
    """Un 'parrafo' aqui es directamente el bloque tal cual esta indexado
    (el indexador ya segmenta por unidad logica, no por oracion suelta) --
    equivalente a fixed_window sin recorte de tamano, dejando el bloque
    completo o descartandolo si no cabe."""
    plan = {"tipo": "explicativa", "filtros": {}, "presupuesto": 10**9, "k": 10**6}
    cand = buscar(q, idx, plan, pool=200)
    paquetes, tokens_usados = [], 0
    for i, sc, crudo, cob in cand:
        p = _empaquetar(idx, i, sc, cob)
        if tokens_usados + p["tokens"] > presupuesto:
            continue
        paquetes.append(p)
        tokens_usados += p["tokens"]
    return paquetes


def sentence_top(q, idx, presupuesto):
    """Aproximacion de 'sentence-top' del paper: en vez de rankear
    oraciones sueltas (el indice no esta segmentado a ese nivel), se
    rankean bloques por similitud coseno TF-IDF PURA (sin BM25, sin
    z-score combinado), tomando tantos como quepan en el presupuesto sin
    ningun mecanismo de diversidad ni expansion. Es deliberadamente el
    baseline mas simple posible: 'similaridad y ya'."""
    qv = idx["tfidf"].transform([q])
    s_tf = cosine_similarity(qv, idx["M"]).ravel()
    orden = np.argsort(-s_tf)
    paquetes, tokens_usados = [], 0
    for i in orden:
        i = int(i)
        if tokens_usados >= presupuesto:
            break
        p = _empaquetar(idx, i, s_tf[i])
        if tokens_usados + p["tokens"] > presupuesto:
            continue
        paquetes.append(p)
        tokens_usados += p["tokens"]
    return paquetes


BASELINES = {
    "fixed_128": lambda q, idx, presupuesto: fixed_window(q, idx, presupuesto, ventana_tokens=128),
    "fixed_256": lambda q, idx, presupuesto: fixed_window(q, idx, presupuesto, ventana_tokens=256),
    "parrafo": parrafo,
    "sentence_top": sentence_top,
}
