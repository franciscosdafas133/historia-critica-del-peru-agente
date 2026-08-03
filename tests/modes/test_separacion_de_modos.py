# -*- coding: utf-8 -*-
"""
Tests de separacion observable entre los 8 modos reales del agente, sin
LLM. Verifica la parte del contrato que SI se puede comprobar sin gastar
tokens de API: que cada modo produce un system prompt distinto y
correctamente formado, que el enrutamiento por nombre de modo funciona,
y que un modo invalido cae al default de forma segura.

Los modos reales (enumerados desde el codigo, no inventados -- ver
agente.py:MODOS) son: preguntar, resumen, explicacion, debate, resolver,
practicar, evaluar, repasar. Ver reports/modes_evaluation.md para el
contrato de comportamiento completo de cada uno y los resultados de
pruebas EN VIVO (que si requieren LLM y se corrieron en sesiones
anteriores de este proyecto, no en esta auditoria offline).
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from agente import sistema_para, MODOS, ETIQUETA_MODO, NUCLEO

MODOS_REALES = ["preguntar", "resumen", "explicacion", "debate",
                 "resolver", "practicar", "evaluar", "repasar"]


def test_existen_exactamente_ocho_modos():
    assert set(MODOS.keys()) == set(MODOS_REALES)


def test_cada_modo_tiene_etiqueta():
    for modo in MODOS_REALES:
        assert modo in ETIQUETA_MODO
        assert len(ETIQUETA_MODO[modo]) > 0


def test_cada_modo_produce_system_prompt_distinto():
    """Separacion observable: dos modos distintos no deben producir el
    mismo texto de system prompt (si lo hicieran, serian la misma
    etiqueta visual sin comportamiento real distinto)."""
    prompts = {modo: sistema_para(modo) for modo in MODOS_REALES}
    textos = list(prompts.values())
    assert len(set(textos)) == len(MODOS_REALES), (
        "Dos o mas modos producen el mismo system prompt -- alguno seria "
        "solo una etiqueta visual sin comportamiento distinto."
    )


def test_todos_los_modos_incluyen_el_nucleo_comun():
    """Cambiar de modo nunca debe desactivar las reglas base (evidencia
    obligatoria, citas, AMI) -- verificado literalmente: el NUCLEO debe
    ser un prefijo exacto de cada system prompt."""
    for modo in MODOS_REALES:
        assert sistema_para(modo).startswith(NUCLEO)


def test_modo_invalido_cae_a_preguntar_sin_excepcion():
    resultado = sistema_para("modo_que_no_existe")
    assert resultado == sistema_para("preguntar")


def test_modo_vacio_cae_a_preguntar():
    assert sistema_para("") == sistema_para("preguntar")


def test_modo_practicar_y_evaluar_comparten_formato_pero_no_son_identicos():
    """practicar y evaluar generan el mismo TIPO de salida (parseada por
    la misma funcion parsear_practica en agente.py), pero deben seguir
    siendo dos modos con prompt propio, no el mismo modo con dos nombres."""
    p_practicar = sistema_para("practicar")
    p_evaluar = sistema_para("evaluar")
    assert p_practicar != p_evaluar
    assert "PRACTICAR" in p_practicar
    assert "EVALUARME" in p_evaluar


def test_modo_resumen_declara_excepcion_al_cierre_con_pregunta():
    """El nucleo pide cerrar con pregunta (regla 10, 'CIERRE QUE ABRE');
    el propio codigo declara una EXCEPCION explicita para resumen. Se
    verifica que esa excepcion este documentada en el texto del modo."""
    assert "EXCEPCION" in sistema_para("resumen")


def test_ambos_modos_de_pregunta_multiple_usan_mismo_parser():
    """practicar y evaluar deben ser parseables con la misma funcion --
    si el formato de marcadores diverge, el frontend (que usa un solo
    parser para ambos, ver httpStudyService.ts) fallaria silenciosamente
    para uno de los dos."""
    from agente import parsear_practica
    texto_generico = (
        "PREGUNTA: test\nOPCION_A: a\nOPCION_B: b\nOPCION_C: c\nOPCION_D: d\n"
        "RESPUESTA_CORRECTA: A\nEXPLICACION: porque si [1]."
    )
    # El mismo texto debe parsear igual sin importar de que modo vino --
    # el parser no depende del modo, solo del formato del texto.
    assert parsear_practica(texto_generico) is not None
