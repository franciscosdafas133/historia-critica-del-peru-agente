# -*- coding: utf-8 -*-
"""
Tests de conformidad para verificar_citas() y los parsers de marcadores
(agente.py). No son parte del algoritmo de recuperacion en si, pero son
la contraparte de "verificacion de citas / estructura de salida" que el
protocolo de auditoria pide cubrir, y viven en el mismo archivo que arma
el prompt sobre la evidencia recuperada.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from agente import verificar_citas, parsear_practica, parsear_tarjeta


def _paquetes(n):
    return [{}] * n


def test_detecta_citas_inexistentes():
    texto = "Esta afirmacion cita un fragmento que no existe [7]."
    v = verificar_citas(texto, _paquetes(3))
    assert 7 in v["citadas"]
    assert any("no existen" in p for p in v["problemas"])


def test_detecta_parrafo_sin_cita():
    texto = ("Esta es una afirmacion sustantiva bastante larga que "
             "supera los ochenta caracteres y no lleva ninguna cita al final del parrafo.")
    v = verificar_citas(texto, _paquetes(3))
    assert any("sin ninguna cita" in p for p in v["problemas"])


def test_parrafo_corto_no_se_penaliza():
    texto = "Muy corto."
    v = verificar_citas(texto, _paquetes(3))
    assert v["problemas"] == []


def test_parrafo_con_cita_no_se_penaliza():
    texto = ("Esta es una afirmacion sustantiva bastante larga que "
             "supera los ochenta caracteres y SI lleva su cita correspondiente [1].")
    v = verificar_citas(texto, _paquetes(3))
    assert v["problemas"] == []


def test_pregunta_de_cierre_no_se_penaliza():
    texto = ("Esta es una pregunta de cierre bastante larga que supera los "
             "ochenta caracteres pero termina en signo de interrogacion?")
    v = verificar_citas(texto, _paquetes(3))
    assert v["problemas"] == []


def test_encuadre_de_debate_no_se_penaliza():
    texto = ("Entiendo tu postura: sostienes que la epidemia fue el factor "
             "mas importante en el colapso demografico del siglo dieciseis.")
    v = verificar_citas(texto, _paquetes(3))
    assert v["problemas"] == []


def test_encuadre_de_resolver_no_se_penaliza():
    texto = ("Tu intento no contiene aun una propuesta de respuesta, por lo "
             "que no es posible evaluar tu analisis todavia en este momento.")
    v = verificar_citas(texto, _paquetes(3))
    assert v["problemas"] == []


def test_seccion_fuentes_no_se_penaliza():
    texto = "FUENTES\n[1] Contreras, C. (2020). La crisis demografica del siglo XVI."
    v = verificar_citas(texto, _paquetes(3))
    assert v["problemas"] == []


def test_lista_con_vinetas_no_se_penaliza():
    texto = "- Un punto de una lista bastante largo que supera los ochenta caracteres sin cita."
    v = verificar_citas(texto, _paquetes(3))
    assert v["problemas"] == []


def test_texto_vacio_no_lanza_excepcion():
    v = verificar_citas("", _paquetes(3))
    assert v["citadas"] == []
    assert v["problemas"] == []


def test_sin_usar_reporta_fragmentos_no_citados():
    texto = "Afirmacion corta con cita [1]."
    v = verificar_citas(texto, _paquetes(3))
    assert v["sin_usar"] == [2, 3]


# --- parsear_practica ---

def test_parsear_practica_formato_correcto():
    texto = (
        "PREGUNTA: ¿Cual es la capital?\n"
        "OPCION_A: Lima\n"
        "OPCION_B: Cusco\n"
        "OPCION_C: Arequipa\n"
        "OPCION_D: Trujillo\n"
        "RESPUESTA_CORRECTA: A\n"
        "EXPLICACION: Lima es la capital [1].\n"
        "FUENTES:\n[1] Fuente X"
    )
    r = parsear_practica(texto)
    assert r is not None
    assert r["prompt"] == "¿Cual es la capital?"
    assert r["options"] == ["Lima", "Cusco", "Arequipa", "Trujillo"]
    assert r["correctAnswer"] == "Lima"
    assert r["evidenceIds"] == [1]


def test_parsear_practica_formato_roto_devuelve_none():
    texto = "Lo siento, no puedo generar esa pregunta."
    assert parsear_practica(texto) is None


def test_parsear_practica_letra_invalida_devuelve_none():
    texto = (
        "PREGUNTA: ¿Cual es la capital?\n"
        "OPCION_A: Lima\nOPCION_B: Cusco\nOPCION_C: Arequipa\nOPCION_D: Trujillo\n"
        "RESPUESTA_CORRECTA: Z\n"
        "EXPLICACION: no aplica."
    )
    assert parsear_practica(texto) is None


# --- parsear_tarjeta ---

def test_parsear_tarjeta_formato_correcto():
    texto = "TARJETA_PREGUNTA: ¿Que es la mita?\nTARJETA_RESPUESTA: Trabajo forzado [2].\nFUENTES:\n[2] X"
    r = parsear_tarjeta(texto)
    assert r["question"] == "¿Que es la mita?"
    assert r["answer"] == "Trabajo forzado [2]."
    assert r["evidenceIds"] == [2]


def test_parsear_tarjeta_sin_marcadores_usa_fallback_de_lineas():
    texto = "¿Cuando fue la crisis?\nEntre 1520 y 1620."
    r = parsear_tarjeta(texto)
    assert r["question"] == "¿Cuando fue la crisis?"
    assert r["answer"] == "Entre 1520 y 1620."


def test_parsear_tarjeta_texto_vacio_devuelve_none():
    assert parsear_tarjeta("") is None
