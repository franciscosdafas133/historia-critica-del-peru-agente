# -*- coding: utf-8 -*-
"""
Checkpoint G: documento y multiplicidad (paper, S5.6).

Caso central calculado a mano: un documento A con 1 sola unidad
elegible (p_c=0.02) contra un documento B con 20 unidades elegibles
cuyo MEJOR p_c es 0.01 -- un p-valor absoluto mas bajo que el de A.
Sin correccion de multiplicidad, B ganaria (0.01 < 0.02). Con la
correccion Bonferroni de la formula (6):
  p_doc(A) = min(1, 1 * 0.02) = 0.02
  p_doc(B) = min(1, 20 * 0.01) = 0.2
A debe ganar (0.02 < 0.2) pese a NO tener el p-valor absoluto mas bajo
-- exactamente el comportamiento que el paper busca: penalizar
fragmentacion en vez de premiarla.
"""
import pytest

from forma_ir.documento import agregar_documento, agregar_documentos, rankear_unidades_de_documento


def test_checkpoint_g_documento_con_menos_unidades_gana_pese_a_p_absoluto_mayor():
    p_valores = {
        "doc-a": {"doc-a#u0": 0.02},
        "doc-b": {f"doc-b#u{i}": 0.5 for i in range(19)} | {"doc-b#u19": 0.01},
    }
    resultados = agregar_documentos(p_valores)

    assert resultados[0].doc_id == "doc-a"
    assert resultados[0].p_doc == pytest.approx(0.02)
    assert resultados[1].doc_id == "doc-b"
    assert resultados[1].p_doc == pytest.approx(0.2)
    # confirma explicitamente que B tenia el mejor p_c absoluto, pero PIERDE
    assert resultados[1].mejor_p_c < resultados[0].mejor_p_c
    assert resultados[0].p_doc < resultados[1].p_doc


def test_agregar_documento_un_solo_documento_calculo_directo():
    r = agregar_documento("doc-x", {"doc-x#u0": 0.1, "doc-x#u1": 0.3})
    assert r.m_d == 2
    assert r.mejor_unidad_id == "doc-x#u0"
    assert r.mejor_p_c == pytest.approx(0.1)
    assert r.p_doc == pytest.approx(min(1.0, 2 * 0.1))


def test_p_doc_nunca_supera_uno():
    """m_d * mejor_p_c puede exceder 1 con muchas unidades y p moderado
    -- p_doc debe truncarse a 1.0 (es una probabilidad)."""
    r = agregar_documento("doc-y", {f"doc-y#u{i}": 0.5 for i in range(10)})
    assert r.p_doc == 1.0


def test_agregar_documento_sin_unidades_lanza_excepcion():
    with pytest.raises(ValueError):
        agregar_documento("doc-vacio", {})


def test_agregar_documentos_ordena_por_p_doc_ascendente():
    p_valores = {
        "doc-1": {"doc-1#u0": 0.5},
        "doc-2": {"doc-2#u0": 0.01},
        "doc-3": {"doc-3#u0": 0.2},
    }
    resultados = agregar_documentos(p_valores)
    assert [r.doc_id for r in resultados] == ["doc-2", "doc-3", "doc-1"]


def test_rankear_unidades_dentro_de_documento_ordena_por_p_c():
    p_valores = {"u0": 0.5, "u1": 0.02, "u2": 0.3}
    ranking = rankear_unidades_de_documento("doc-x", p_valores)
    assert [uid for uid, _p in ranking] == ["u1", "u2", "u0"]
