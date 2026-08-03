# -*- coding: utf-8 -*-
"""
Tests de conformidad para analizar_pregunta() (recuperar.py).

Estos tests verifican el metodo REALMENTE implementado (clasificacion por
reglas lexicas + presupuesto fijo por tipo), no el algoritmo BASIL del
paper -- ver reports/paper_conformance.md para el detalle de por que BASIL
no existe en este repositorio y que se evalua en su lugar.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from recuperar import analizar_pregunta


class IdxFalso(dict):
    """idx minimo: analizar_pregunta solo lee idx["por_autor"]."""
    def __init__(self):
        super().__init__()
        self["por_autor"] = {}


def test_clasifica_local_por_palabra_clave():
    idx = IdxFalso()
    plan = analizar_pregunta("¿Cuándo es el examen parcial?", idx)
    assert plan["tipo"] == "local"


def test_clasifica_explicativa_por_defecto():
    idx = IdxFalso()
    # Sin pistas de local ni global, cae a explicativa (default declarado
    # en el codigo: analizar_pregunta arranca tipo="explicativa").
    plan = analizar_pregunta("Historia del Peru en el siglo XX", idx)
    assert plan["tipo"] == "explicativa"


def test_clasifica_explicativa_por_porque():
    idx = IdxFalso()
    plan = analizar_pregunta("¿Por qué colapsó la población andina?", idx)
    assert plan["tipo"] == "explicativa"


def test_clasifica_global_por_pista_de_corpus_completo():
    idx = IdxFalso()
    plan = analizar_pregunta("¿Cómo se relacionan las dos unidades del curso?", idx)
    assert plan["tipo"] == "global"


def test_presupuesto_fijo_por_tipo():
    idx = IdxFalso()
    assert analizar_pregunta("¿Cuándo es el examen?", idx)["presupuesto"] == 3000
    assert analizar_pregunta("Explica la crisis demografica", idx)["presupuesto"] == 9000
    assert analizar_pregunta("relacion entre las unidades del curso", idx)["presupuesto"] == 30000


def test_k_semillas_fijo_por_tipo():
    idx = IdxFalso()
    assert analizar_pregunta("¿Cuándo es el examen?", idx)["k"] == 4
    assert analizar_pregunta("Explica la crisis demografica", idx)["k"] == 10
    assert analizar_pregunta("relacion entre las unidades del curso", idx)["k"] == 24


def test_detecta_filtro_de_semana():
    idx = IdxFalso()
    plan = analizar_pregunta("¿Qué se ve en la semana 13?", idx)
    assert plan["filtros"].get("semana") == 13


def test_detecta_filtro_de_unidad():
    idx = IdxFalso()
    plan = analizar_pregunta("temas de la unidad 2", idx)
    assert plan["filtros"].get("unidad") == 2


def test_detecta_filtro_de_autoridad_oficial():
    idx = IdxFalso()
    plan = analizar_pregunta("¿cuándo es el examen y cuánto vale?", idx)
    assert plan["filtros"].get("autoridad") == "oficial"


def test_detecta_autor_si_esta_en_indice():
    idx = IdxFalso()
    idx["por_autor"] = {"contreras": [1, 2, 3]}
    plan = analizar_pregunta("¿Qué dice Contreras sobre el centralismo?", idx)
    assert plan["filtros"].get("autor") == "contreras"


def test_no_detecta_filtros_en_pregunta_generica():
    idx = IdxFalso()
    plan = analizar_pregunta("¿Qué es la transición demográfica?", idx)
    assert plan["filtros"] == {}


def test_consulta_vacia_no_lanza_excepcion():
    idx = IdxFalso()
    plan = analizar_pregunta("", idx)
    # Con string vacio, "tipo" cae al default ("explicativa") porque
    # ninguna lista de pistas hace match sobre una cadena vacia.
    assert plan["tipo"] == "explicativa"
    assert plan["terminos"] == []


def test_unicode_y_tildes_no_rompen_clasificacion():
    idx = IdxFalso()
    # Con tilde y sin tilde deben clasificar igual (normtxt quita tildes).
    con_tilde = analizar_pregunta("¿Cuál es la definición de nación?", idx)
    sin_tilde = analizar_pregunta("Cual es la definicion de nacion?", idx)
    assert con_tilde["tipo"] == sin_tilde["tipo"]
