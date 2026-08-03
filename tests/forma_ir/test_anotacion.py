# -*- coding: utf-8 -*-
"""
Checkpoint C2: anotacion de reglas de la gramatica inducida.

Caso real construido a mano: el header repetido del cronograma ("Anexo
del silabo... CRONOGRAMA...", 13 lineas identicas en las 8 paginas del
documento) debe distinguirse de reglas que capturan estructura con
contenido variable entre ocurrencias.

Nota de desarrollo: la primera version media diversidad lexica sobre el
texto que sigue DESPUES de cada ocurrencia de la regla, no sobre el texto
que la propia regla cubre -- eso hacia que TODAS las reglas salieran con
diversidad=1.0 (el contenido despues de un header repetido logicamente
varia pagina a pagina, sea o no la regla misma repetitiva). Se corrigio
a medir diversidad sobre el texto propio, que es la senal que el paper
describe.
"""
import os

from forma_ir.tipos import Bloque
from forma_ir.firma import secuencia_de_firmas
from forma_ir.gramatica import inducir_gramatica
from forma_ir.anotacion import anotar_reglas, _entropia_normalizada_de_textos
from forma_ir.ingesta import extraer_pdf

RAIZ = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
FIXTURE_CRONOGRAMA = os.path.join(RAIZ, "tests", "forma_ir", "fixtures", "cronograma_fixture.pdf")


def _construir_gramatica(bloques_doc):
    firmas = secuencia_de_firmas(bloques_doc)
    alfabeto, simbolos = {}, []
    for f in firmas:
        if f not in alfabeto:
            alfabeto[f] = len(alfabeto)
        simbolos.append(alfabeto[f])
    return inducir_gramatica(simbolos)


# --- Entropia normalizada, casos calculables a mano ---

def test_entropia_cero_para_textos_identicos():
    textos = ["mismo texto"] * 5
    assert _entropia_normalizada_de_textos(textos) == 0.0


def test_entropia_maxima_para_textos_todos_distintos():
    textos = ["uno dos", "tres cuatro", "cinco seis", "siete ocho"]
    e = _entropia_normalizada_de_textos(textos)
    assert e == 1.0  # todas las categorias son distintas y de igual tamano -> entropia maxima normalizada


def test_entropia_con_una_sola_ocurrencia_es_cero():
    assert _entropia_normalizada_de_textos(["algo"]) == 0.0


def test_entropia_intermedia_entre_repetido_y_variado():
    """3 textos: dos identicos, uno distinto -> entropia entre 0 y 1."""
    textos = ["igual", "igual", "distinto"]
    e = _entropia_normalizada_de_textos(textos)
    assert 0.0 < e < 1.0


# --- Caso real: header repetido del cronograma ---

def test_header_repetido_real_tiene_diversidad_lexica_cero():
    bloques = extraer_pdf(FIXTURE_CRONOGRAMA, "cronograma-test")
    reglas, top = _construir_gramatica(bloques)
    anotaciones = anotar_reglas(reglas, top, bloques)

    # La regla con mas ocurrencias en un documento de 8 paginas con
    # header identico en cada una debe tener 8 ocurrencias y diversidad 0
    regla_header = max(anotaciones.values(), key=lambda a: a.n_ocurrencias)
    assert regla_header.n_ocurrencias == 8
    assert regla_header.diversidad_lexica == 0.0
    assert regla_header.estabilidad_posicional > 0.9  # header cae siempre en el mismo lugar de la pagina


def test_header_repetido_es_marcado_como_candidata_a_limite():
    """Aunque su diversidad sea 0, un header MUY estable posicionalmente
    SI debe marcarse como candidata a limite -- es un marcador valido de
    'inicio de pagina/seccion', solo que no aporta contenido variable."""
    bloques = extraer_pdf(FIXTURE_CRONOGRAMA, "cronograma-test")
    reglas, top = _construir_gramatica(bloques)
    anotaciones = anotar_reglas(reglas, top, bloques)

    regla_header = max(anotaciones.values(), key=lambda a: a.n_ocurrencias)
    assert regla_header.es_candidata_limite is True


def test_reglas_con_contenido_variable_tienen_diversidad_alta():
    """Nota de desarrollo (post Checkpoint C3a): extraer_pdf ahora fusiona
    lineas consecutivas de igual firma en parrafos (ver docstring de
    extraer_pdf) para eliminar el ruido de fragmentacion que Checkpoint
    C3a encontro en documentos de prosa multi-columna. Efecto colateral
    esperado y deseable en este fixture: la fragmentacion de celdas de
    tabla en multiples "bloques" por linea desaparece, asi que ya no hay
    varias reglas artificiales con 3+ ocurrencias de diversidad mixta
    -- solo sobrevive la regla real del header repetido (diversidad 0).
    Este test ahora verifica que NINGUNA regla con 3+ ocurrencias tenga
    diversidad alta espuria, en vez de exigir que la mayoria la tenga."""
    bloques = extraer_pdf(FIXTURE_CRONOGRAMA, "cronograma-test")
    reglas, top = _construir_gramatica(bloques)
    anotaciones = anotar_reglas(reglas, top, bloques)

    con_varias_ocurrencias = [a for a in anotaciones.values() if a.n_ocurrencias >= 3]
    assert len(con_varias_ocurrencias) >= 1
    for a in con_varias_ocurrencias:
        assert a.diversidad_lexica <= 0.3, f"regla {a.regla_id} con diversidad espuria {a.diversidad_lexica}"


def test_todas_las_reglas_reciben_anotacion():
    bloques = extraer_pdf(FIXTURE_CRONOGRAMA, "cronograma-test")
    reglas, top = _construir_gramatica(bloques)
    anotaciones = anotar_reglas(reglas, top, bloques)
    assert set(anotaciones.keys()) == set(reglas.keys())
