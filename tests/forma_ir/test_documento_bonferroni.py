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
    """Formula (6) LITERAL del paper (Bonferroni). Se pide explicitamente
    porque el default de produccion pasó a Simes -- ver la nota en
    `test_simes_es_el_default_y_no_castiga_la_concordancia`."""
    p_valores = {
        "doc-a": {"doc-a#u0": 0.02},
        "doc-b": {f"doc-b#u{i}": 0.5 for i in range(19)} | {"doc-b#u19": 0.01},
    }
    resultados = agregar_documentos(p_valores, agregacion="bonferroni")

    assert resultados[0].doc_id == "doc-a"
    assert resultados[0].p_doc == pytest.approx(0.02)
    assert resultados[1].doc_id == "doc-b"
    assert resultados[1].p_doc == pytest.approx(0.2)
    # confirma explicitamente que B tenia el mejor p_c absoluto, pero PIERDE
    assert resultados[1].mejor_p_c < resultados[0].mejor_p_c
    assert resultados[0].p_doc < resultados[1].p_doc


def test_agregar_documento_un_solo_documento_calculo_directo():
    r = agregar_documento("doc-x", {"doc-x#u0": 0.1, "doc-x#u1": 0.3}, agregacion="bonferroni")
    assert r.m_d == 2
    assert r.mejor_unidad_id == "doc-x#u0"
    assert r.mejor_p_c == pytest.approx(0.1)
    assert r.p_doc == pytest.approx(min(1.0, 2 * 0.1))


def test_p_doc_nunca_supera_uno():
    """m_d * mejor_p_c puede exceder 1 con muchas unidades y p moderado
    -- p_doc debe truncarse a 1.0 (es una probabilidad)."""
    r = agregar_documento("doc-y", {f"doc-y#u{i}": 0.5 for i in range(10)}, agregacion="bonferroni")
    assert r.p_doc == 1.0


# --- Simes (S5.6: "higher-power alternative") ---

def test_simes_calculo_a_mano():
    """p_simes = min_i (m * p_(i) / i). Con p = [0.01, 0.02, 0.30] y m=3:
      i=1: 3*0.01/1 = 0.03
      i=2: 3*0.02/2 = 0.03
      i=3: 3*0.30/3 = 0.30
    -> min = 0.03"""
    r = agregar_documento("doc-s", {"u0": 0.01, "u1": 0.02, "u2": 0.30}, agregacion="simes")
    assert r.p_doc == pytest.approx(0.03)
    assert r.agregacion == "simes"


def test_simes_premia_concordancia_donde_bonferroni_la_ignora():
    """Un documento con VARIAS unidades de evidencia fuerte deberia ganar
    a uno con una sola coincidencia del mismo p-valor minimo. Bonferroni
    usa solo el minimo (y ademas lo multiplica por m_d), asi que castiga
    al documento concordante; Simes lo premia.

    Este es el caso que hundia a los documentos largos del corpus real:
    Klaren (1029 unidades) con cobertura IDF=1.0 en su propio texto
    literal quedaba fuera del top-5 en el 100% de los intentos.

    Nota sobre la matematica (verificada a mano al escribir este test):
    con p-valores IDENTICOS Simes empata con el minimo (5 unidades a 0.02
    dan exactamente 0.02, porque el termino m*p/i se minimiza en i=m). La
    ventaja de Simes aparece cuando el documento tiene evidencia
    ESCALONADA -- varias unidades buenas de distinta fuerza, que es el
    caso real de un libro largo con multiples pasajes pertinentes."""
    # documento con evidencia escalonada (varias unidades buenas)
    concordante = {"u0": 0.02, "u1": 0.03, "u2": 0.04, "u3": 0.05, "u4": 0.06}
    aislado = {"u0": 0.02, "u1": 0.9, "u2": 0.9, "u3": 0.9, "u4": 0.9}

    simes_conc = agregar_documento("conc", concordante, agregacion="simes").p_doc
    simes_aisl = agregar_documento("aisl", aislado, agregacion="simes").p_doc
    assert simes_conc < simes_aisl, "Simes debe premiar la evidencia concordante"

    # Bonferroni los considera IGUALES: solo mira el minimo (0.02) y el
    # mismo m_d=5 -> no distingue concordancia de coincidencia aislada.
    bonf_conc = agregar_documento("conc", concordante, agregacion="bonferroni").p_doc
    bonf_aisl = agregar_documento("aisl", aislado, agregacion="bonferroni").p_doc
    assert bonf_conc == bonf_aisl, "Bonferroni ignora la concordancia (motivo del cambio)"


def test_simes_es_el_default():
    r = agregar_documento("doc-d", {"u0": 0.01, "u1": 0.02})
    assert r.agregacion == "simes"


def test_simes_nunca_supera_uno_ni_baja_de_cero():
    for ps in ({"u0": 1.0, "u1": 1.0}, {"u0": 0.999}, {f"u{i}": 0.9 for i in range(50)}):
        r = agregar_documento("d", ps, agregacion="simes")
        assert 0.0 <= r.p_doc <= 1.0


def test_desempate_por_mejor_p_c_cuando_p_doc_empata():
    """Con p_doc identico, debe ganar el de mejor evidencia unitaria --
    nunca el orden de insercion del diccionario (que era azar puro y
    resolvia arbitrariamente el 26-33% de las consultas medidas)."""
    p_valores = {
        "doc-debil": {"u0": 1.0},
        "doc-fuerte": {"u0": 0.5, "u1": 1.0},
    }
    resultados = agregar_documentos(p_valores, agregacion="bonferroni")
    assert all(r.p_doc == pytest.approx(1.0) for r in resultados)
    assert resultados[0].doc_id == "doc-fuerte"


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
