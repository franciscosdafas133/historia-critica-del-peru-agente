# -*- coding: utf-8 -*-
"""
Checkpoint E: vector de evidencia lexica dispersa (paper, S5.4).

Casos calculables a mano sobre texto REAL corto del corpus: la unidad
`cronograma-hcp-2026-1-a#u2` (texto verificado abajo, extraido del
cronograma real) contiene la frase "Transiciones demograficas" DOS
veces -- una vez en el titulo numerado "2. Transiciones demograficas"
(posiciones de token 12-13) y otra vez en "2.1 Principales transiciones
demograficas" (posiciones 17-18). La consulta "transiciones
demograficas" matchea ambos terminos, cobertura c=1.0, y la ventana mas
corta que contiene ambos es de ancho 2 (la primera ocurrencia
adyacente, posiciones 12-13) -- x = 1.0 / (1 + log(1+2)) ~ 0.4765.
"""
import math

from forma_ir.evidencia import (
    _cobertura_idf,
    _compacidad,
    _es_bloque_ancla,
    _evidencia_ancla,
    _ventana_mas_corta,
    calcular_idf,
    calcular_vector_evidencia,
    tokenizar,
)
from forma_ir.firma import FirmaForma, calcular_estadisticas_doc, secuencia_de_firmas
from forma_ir.tipos import Bloque, UnidadRetenida

_TEXTO_UNIDAD_REAL = (
    "(del 23 al 29 de marzo) 24 y 25 de marzo 2. Transiciones demográficas "
    "2.1 Principales transiciones demográficas a lo largo de la historia del Perú -"
)


def _bloque(texto: str, seq: int, indentacion_pt: float | None = None,
             font_size: float | None = None) -> Bloque:
    return Bloque(
        bloque_id=f"test#{seq}", doc_id="test-doc", seq=seq, texto=texto,
        pagina=1, diapositiva=None, bbox=(indentacion_pt or 0.0, 0.0, 100.0, 10.0),
        font_size=font_size, bold=None, italic=None,
        indentacion_pt=indentacion_pt, espacio_vertical_antes=None, formato_fuente="pdf",
    )


# --- Tokenizacion ---

def test_tokenizar_texto_real_produce_secuencia_exacta():
    """Verificado a mano contra el texto real de cronograma-hcp-2026-1-a#u2:
    'transiciones' aparece en las posiciones 12 y 17; 'demograficas' en
    las posiciones 13 y 18."""
    tokens = tokenizar(_TEXTO_UNIDAD_REAL)
    assert tokens[12] == "transiciones"
    assert tokens[13] == "demográficas"
    assert tokens[17] == "transiciones"
    assert tokens[18] == "demográficas"
    assert len(tokens) == 27


# --- Cobertura IDF (formula 3) ---

def test_cobertura_ambos_terminos_matcheados_es_uno():
    idf = {"transiciones": 2.0, "demográficas": 1.5}
    tokens_query = tokenizar("transiciones demográficas")
    tokens_unidad = set(tokenizar(_TEXTO_UNIDAD_REAL))
    c = _cobertura_idf(tokens_query, tokens_unidad, idf)
    assert c == 1.0


def test_cobertura_parcial_pondera_por_idf():
    """Consulta con un termino que SI esta en la unidad (idf=3.0) y uno
    que NO (idf=1.0) -> cobertura = 3.0 / (3.0+1.0) = 0.75."""
    idf = {"transiciones": 3.0, "inexistente": 1.0}
    tokens_query = tokenizar("transiciones inexistente")
    tokens_unidad = set(tokenizar(_TEXTO_UNIDAD_REAL))
    c = _cobertura_idf(tokens_query, tokens_unidad, idf)
    assert c == 0.75


def test_cobertura_consulta_vacia_es_cero():
    assert _cobertura_idf([], {"a", "b"}, {}) == 0.0


# --- Ventana mas corta ---

def test_ventana_mas_corta_es_dos_para_terminos_adyacentes():
    tokens_query = tokenizar("transiciones demográficas")
    tokens_unidad = tokenizar(_TEXTO_UNIDAD_REAL)
    ventana = _ventana_mas_corta(tokens_query, tokens_unidad)
    assert ventana == 2  # la primera ocurrencia adyacente (posiciones 12-13)


def test_ventana_mas_corta_ningun_termino_presente_es_none():
    tokens_query = tokenizar("palabras que no existen aqui")
    tokens_unidad = tokenizar(_TEXTO_UNIDAD_REAL)
    assert _ventana_mas_corta(tokens_query, tokens_unidad) is None


def test_ventana_mas_corta_terminos_alejados_da_ventana_grande():
    tokens_query = ["a", "z"]
    tokens_unidad = ["a"] + ["x"] * 10 + ["z"]
    ventana = _ventana_mas_corta(tokens_query, tokens_unidad)
    assert ventana == 12  # de indice 0 a indice 11, ancho = 11-0+1


# --- Compacidad (formula 4) ---

def test_compacidad_caso_real_calculado_a_mano():
    """x = c / (1 + log(1+ventana)) con c=1.0, ventana=2:
    x = 1.0 / (1 + ln(3)) ~ 0.4765."""
    x = _compacidad(cobertura=1.0, ventana=2)
    esperado = 1.0 / (1 + math.log(3))
    assert abs(x - esperado) < 1e-9
    assert abs(x - 0.4765) < 1e-3


def test_compacidad_sin_ventana_es_cero():
    assert _compacidad(cobertura=1.0, ventana=None) == 0.0


# --- Ancla estructural ---

def test_bloque_con_numeracion_es_ancla():
    stats = calcular_estadisticas_doc([_bloque("2. Transiciones demográficas", 0)])
    firmas = secuencia_de_firmas([_bloque("2. Transiciones demográficas", 0)])
    assert _es_bloque_ancla(_bloque("2. Transiciones demográficas", 0), firmas[0]) is True


def test_bloque_de_prosa_normal_no_es_ancla():
    b = _bloque("esto es una oracion normal de cuerpo de texto sin numeracion", 0)
    firmas = secuencia_de_firmas([b])
    assert _es_bloque_ancla(b, firmas[0]) is False


def test_evidencia_ancla_uno_si_query_matchea_bloque_ancla():
    bloques = [_bloque("2. Transiciones demográficas", 0), _bloque("texto de cuerpo normal", 1)]
    firmas = secuencia_de_firmas(bloques)
    tokens_query = tokenizar("transiciones")
    assert _evidencia_ancla(tokens_query, bloques, firmas) == 1.0


def test_evidencia_ancla_cero_si_query_no_matchea_ningun_ancla():
    bloques = [_bloque("2. Algo completamente distinto", 0)]
    firmas = secuencia_de_firmas(bloques)
    tokens_query = tokenizar("transiciones demográficas")
    assert _evidencia_ancla(tokens_query, bloques, firmas) == 0.0


# --- IDF sobre corpus ---

def test_idf_termino_raro_tiene_idf_mayor_que_termino_comun():
    corpus = [
        tokenizar("el perro come pan"),
        tokenizar("el gato come pan"),
        tokenizar("el pez come pan"),
        tokenizar("gato exotico raro"),
    ]
    idf = calcular_idf(corpus)
    assert idf["raro"] > idf["come"]  # "come" en 3/4 docs, "raro" en 1/4


# --- Vector de evidencia end-to-end sobre la unidad real ---

def test_vector_evidencia_end_to_end_sobre_unidad_real():
    bloques_doc = [
        _bloque("Anexo del sílabo", 0),
        _bloque(_TEXTO_UNIDAD_REAL, 1),
        _bloque("Siglo XVI - Colonial", 2),
    ]
    firmas_doc = secuencia_de_firmas(bloques_doc)
    unidad = UnidadRetenida(
        unidad_id="test-doc#u1", doc_id="test-doc", indices_bloque=[1],
        texto=_TEXTO_UNIDAD_REAL, pagina_inicio=1, pagina_fin=1,
    )
    idf = calcular_idf([tokenizar(b.texto) for b in bloques_doc])
    vector = calcular_vector_evidencia(
        "transiciones demográficas", unidad, bloques_doc, firmas_doc, idf,
        longitud_promedio_unidad=15.0,
    )
    assert vector.c == 1.0
    assert abs(vector.x - 0.4765) < 1e-3
    assert vector.b > 0.0
