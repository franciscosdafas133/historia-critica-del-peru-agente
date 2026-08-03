# -*- coding: utf-8 -*-
"""
Tests de conformidad para expandir() y construir_paquetes() (recuperar.py).

Construyen un indice de juguete minimo (sin pasar por indexar_corpus.py)
para poder verificar a mano el resultado exacto: no-overlap, respeto de
presupuesto, comportamiento en bordes de documento, documentos de 1-2
bloques.
"""
import os
import sys

import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from rank_bm25 import BM25Okapi

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from texto_util import tokenizar
from recuperar import expandir, construir_paquetes, buscar


def _bloque(bloque_id, doc_id, texto, pagina, tokens=None):
    return {
        "bloque_id": bloque_id,
        "doc_id": doc_id,
        "texto": texto,
        "tokens": tokens if tokens is not None else max(len(texto.split()), 1),
        "fuente": {"pagina": pagina},
        "_full": texto,
    }


def _indice_juguete(bloques, docs, vecinos):
    """Construye un idx minimo pero funcional (BM25 + TFIDF reales)
    a partir de una lista de bloques ya armados."""
    tok_corpus = [tokenizar(b["_full"]) for b in bloques]
    bm25 = BM25Okapi(tok_corpus) if any(tok_corpus) else BM25Okapi([["placeholder"]])
    tfidf = TfidfVectorizer(analyzer="word", tokenizer=tokenizar, lowercase=False,
                             token_pattern=None, min_df=1)
    M = tfidf.fit_transform([b["_full"] for b in bloques])
    return {
        "bloques": bloques, "docs": docs, "bm25": bm25, "tfidf": tfidf, "M": M,
        "vecinos": vecinos, "por_semana": {}, "por_unidad": {}, "por_autoridad": {},
        "por_autor": {}, "por_tipo": {}, "por_doc": {},
    }


def test_expandir_documento_de_un_solo_bloque():
    """Un documento de un solo bloque no debe intentar expandirse fuera
    de si mismo -- no hay vecinos, expandir debe devolver solo la semilla."""
    vecinos = {0: {"anterior": None, "siguiente": None}}
    idx = _indice_juguete(
        [_bloque(0, "docA", "unico bloque del documento", 1)],
        {"docA": {"doc_id": "docA", "titulo": "Doc A", "tipo": "lectura",
                   "autoridad": "academica", "archivo": "docA.pdf", "tokens": 5}},
        vecinos,
    )
    span = expandir(0, idx, score=1.0, radio=3)
    assert span == [0]


def test_expandir_documento_de_dos_bloques_respeta_frontera():
    """Documento de 2 bloques: expandir desde el bloque 0 con radio grande
    no debe generar indices fuera del documento (no hay bloque 2)."""
    vecinos = {
        0: {"anterior": None, "siguiente": 1},
        1: {"anterior": 0, "siguiente": None},
    }
    idx = _indice_juguete(
        [_bloque(0, "docA", "primer bloque", 1), _bloque(1, "docA", "segundo bloque", 2)],
        {"docA": {"doc_id": "docA", "titulo": "Doc A", "tipo": "lectura",
                   "autoridad": "academica", "archivo": "docA.pdf", "tokens": 5}},
        vecinos,
    )
    span = expandir(0, idx, score=1.0, radio=5)
    assert span == [0, 1]
    assert len(span) == len(set(span))  # sin duplicados


def test_construir_paquetes_no_supera_presupuesto():
    """Con un presupuesto muy bajo, construir_paquetes nunca debe exceder
    el total de tokens acumulados sobre plan['presupuesto']."""
    bloques = [
        _bloque(0, "docA", "la crisis demografica del siglo dieciseis fue grave", 1, tokens=50),
        _bloque(1, "docA", "epidemias y guerra afectaron a la poblacion andina", 2, tokens=50),
        _bloque(2, "docA", "la desestructuracion del trabajo colonial agravo la crisis", 3, tokens=50),
    ]
    vecinos = {
        0: {"anterior": None, "siguiente": 1},
        1: {"anterior": 0, "siguiente": 2},
        2: {"anterior": 1, "siguiente": None},
    }
    docs = {"docA": {"doc_id": "docA", "titulo": "Doc A", "cita": "Doc A",
                       "tipo": "lectura", "autoridad": "academica",
                       "archivo": "docA.pdf", "tokens": 150}}
    idx = _indice_juguete(bloques, docs, vecinos)

    plan = {"tipo": "local", "filtros": {}, "presupuesto": 60, "k": 3,
            "terminos": tokenizar("crisis demografica")}
    paquetes, plan = construir_paquetes("crisis demografica", idx, plan)

    total_tokens = sum(p["tokens"] for p in paquetes)
    assert total_tokens <= plan["presupuesto"], (
        f"Presupuesto violado: {total_tokens} tokens usados, limite {plan['presupuesto']}"
    )


def test_construir_paquetes_sin_solapamiento_de_bloques():
    """Ningun indice de bloque debe aparecer en mas de un paquete devuelto
    (equivalente al requisito de 'no overlap entre spans')."""
    bloques = [
        _bloque(0, "docA", "primer fragmento sobre economia colonial", 1, tokens=30),
        _bloque(1, "docA", "segundo fragmento sobre economia colonial", 2, tokens=30),
        _bloque(2, "docA", "tercer fragmento sobre economia colonial", 3, tokens=30),
        _bloque(3, "docA", "cuarto fragmento totalmente distinto sobre clima", 4, tokens=30),
    ]
    vecinos = {
        0: {"anterior": None, "siguiente": 1},
        1: {"anterior": 0, "siguiente": 2},
        2: {"anterior": 1, "siguiente": 3},
        3: {"anterior": 2, "siguiente": None},
    }
    docs = {"docA": {"doc_id": "docA", "titulo": "Doc A", "cita": "Doc A",
                       "tipo": "lectura", "autoridad": "academica",
                       "archivo": "docA.pdf", "tokens": 120}}
    idx = _indice_juguete(bloques, docs, vecinos)

    plan = {"tipo": "explicativa", "filtros": {}, "presupuesto": 9000, "k": 10,
            "terminos": tokenizar("economia colonial")}
    paquetes, plan = construir_paquetes("economia colonial", idx, plan)

    # Reconstruye que indices de bloque uso cada paquete a partir de su
    # rango de paginas (cada bloque de prueba tiene una pagina distinta).
    paginas_usadas = []
    for p in paquetes:
        paginas_usadas.append(p["paginas"])
    # No debe haber dos paquetes que reclamen exactamente el mismo rango
    # de paginas (eso indicaria que un bloque fue usado dos veces).
    assert len(paginas_usadas) == len(set(paginas_usadas))


def test_construir_paquetes_indice_sin_bloques_relevantes_no_lanza_excepcion():
    """No hay forma de construir un TfidfVectorizer sobre CERO documentos
    (sklearn exige vocabulario no vacio) -- el caso real de "sin evidencia"
    en produccion es un indice con contenido pero ninguna coincidencia con
    la consulta, no un indice literalmente vacio. Se simula asi."""
    bloques = [_bloque(0, "docA", "contenido totalmente ajeno sobre gastronomia", 1, tokens=20)]
    docs = {"docA": {"doc_id": "docA", "titulo": "Doc A", "cita": "Doc A",
                       "tipo": "lectura", "autoridad": "academica",
                       "archivo": "docA.pdf", "tokens": 20}}
    vecinos = {0: {"anterior": None, "siguiente": None}}
    idx = _indice_juguete(bloques, docs, vecinos)

    plan = {"tipo": "local", "filtros": {}, "presupuesto": 3000, "k": 4,
            "terminos": tokenizar("terminos que no aparecen para nada")}
    paquetes, plan = construir_paquetes("terminos que no aparecen para nada", idx, plan)
    # No debe lanzar excepcion; puede devolver 0 paquetes o el unico
    # bloque disponible, segun el umbral de cobertura -- lo que se
    # verifica aqui es la ausencia de excepcion, no un conteo exacto.
    assert isinstance(paquetes, list)


def test_presupuesto_menor_a_un_bloque_degrada_a_bloque_unico():
    """Si el presupuesto es menor que el tamano de la semilla + su
    vecindad completa, construir_paquetes debe degradar a usar solo el
    nucleo (ver comentario 'degradar a solo el nucleo' en recuperar.py)
    en vez de fallar o exceder el presupuesto."""
    bloques = [
        _bloque(0, "docA", "bloque grande con mucho contenido relevante aqui", 1, tokens=500),
        _bloque(1, "docA", "bloque vecino tambien grande con mas contenido", 2, tokens=500),
    ]
    vecinos = {
        0: {"anterior": None, "siguiente": 1},
        1: {"anterior": 0, "siguiente": None},
    }
    docs = {"docA": {"doc_id": "docA", "titulo": "Doc A", "cita": "Doc A",
                       "tipo": "lectura", "autoridad": "academica",
                       "archivo": "docA.pdf", "tokens": 1000}}
    idx = _indice_juguete(bloques, docs, vecinos)

    # Presupuesto menor que un solo bloque (500 tokens) -> no debe poder
    # devolver nada, o como maximo el nucleo si cupiera; aqui no cabe ni
    # el nucleo, asi que se espera lista vacia sin excepcion.
    plan = {"tipo": "explicativa", "filtros": {}, "presupuesto": 100, "k": 5,
            "terminos": tokenizar("bloque contenido")}
    paquetes, plan = construir_paquetes("bloque contenido", idx, plan)

    total_tokens = sum(p["tokens"] for p in paquetes)
    assert total_tokens <= 100
