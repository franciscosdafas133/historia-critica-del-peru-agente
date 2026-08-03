# -*- coding: utf-8 -*-
"""
Checkpoint B: firma orto-tipografica + deteccion de nuisance.

Incluye los casos literales del paper ("3.2 Installation", "IV --
Liability", "Q:") mas casos reales extraidos de
Cronograma_HCP_2026_1_A.pdf (documento real de 8 paginas con header
repetido en cada pagina, ya confirmado en el checkpoint A).
"""
import os

from forma_ir.tipos import Bloque
from forma_ir.firma import (
    firmar_bloque, calcular_estadisticas_doc, detectar_nuisance,
    _jaccard_palabras, _clase_capitalizacion, _bin_fuente_relativo,
)
from forma_ir.ingesta import extraer_pdf

RAIZ = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
FIXTURE_CRONOGRAMA = os.path.join(RAIZ, "tests", "forma_ir", "fixtures", "cronograma_fixture.pdf")


def _bloque_minimo(texto: str, indentacion_pt=None, font_size=None) -> Bloque:
    return Bloque(
        bloque_id="test#0", doc_id="test", seq=0, texto=texto,
        pagina=1, diapositiva=None, bbox=None,
        font_size=font_size, bold=None, italic=None,
        indentacion_pt=indentacion_pt, espacio_vertical_antes=None,
        formato_fuente="pdf",
    )


# --- Casos literales del paper ---

def test_mask_digito_ejemplo_del_paper():
    stats = calcular_estadisticas_doc([])
    f = firmar_bloque(_bloque_minimo("3.2 Installation"), stats)
    assert f.mask_digito is True


def test_mask_numeral_romano_ejemplo_del_paper():
    stats = calcular_estadisticas_doc([])
    f = firmar_bloque(_bloque_minimo("IV — Liability"), stats)
    assert f.mask_numeral_romano is True


def test_mask_prefijo_alfa_no_confunde_con_capitalizacion_de_titulo():
    stats = calcular_estadisticas_doc([])
    f = firmar_bloque(_bloque_minimo("Q: algo"), stats)
    # "Q:" no calza con el patron "letra.)espacio" (requiere punto o
    # parentesis tras la letra) -- se verifica el perfil de delimitadores
    # en su lugar, que si debe capturar el caracter ':'
    assert ":" in f.perfil_delimitadores


def test_dos_firmas_de_formas_distintas_no_son_iguales():
    """Las tres formas del paper deben producir firmas DISTINTAS entre si
    -- si colapsaran a la misma firma, SEQUITUR (Fase C) no podria
    distinguirlas como patrones organizacionales diferentes."""
    stats = calcular_estadisticas_doc([])
    f1 = firmar_bloque(_bloque_minimo("3.2 Installation"), stats)
    f2 = firmar_bloque(_bloque_minimo("IV — Liability"), stats)
    f3 = firmar_bloque(_bloque_minimo("Q: algo"), stats)
    assert len({f1, f2, f3}) == 3


# --- Clase de capitalizacion ---

def test_clase_capitalizacion_todo_mayus():
    assert _clase_capitalizacion("CRONOGRAMA DE ACTIVIDADES") == "TODO_MAYUS"


def test_clase_capitalizacion_titulo():
    assert _clase_capitalizacion("Historia Critica del Peru") == "Titulo"


def test_clase_capitalizacion_normal():
    assert _clase_capitalizacion("esto es una oracion normal") == "normal"


def test_clase_capitalizacion_vacio():
    assert _clase_capitalizacion("   ") == "vacio"


# --- Tamano de fuente relativo (no absoluto) ---

def test_tamano_fuente_relativo_a_mediana_no_absoluto():
    """El mismo tamano absoluto (20pt) debe clasificarse distinto segun
    la mediana del documento -- 20pt es 'grande' en un documento cuyo
    cuerpo es 10pt, pero 'normal' en uno cuyo cuerpo ya es 20pt."""
    grande_en_doc_chico = _bin_fuente_relativo(20.0, mediana=10.0)
    normal_en_doc_grande = _bin_fuente_relativo(20.0, mediana=19.0)
    assert grande_en_doc_chico is not None and grande_en_doc_chico > 0
    assert normal_en_doc_grande == 0


# --- Jaccard de palabras (fix del bug encontrado en desarrollo) ---

def test_jaccard_palabras_discrimina_frases_sin_vocabulario_compartido():
    """Regresion del bug real encontrado: Jaccard de CARACTERES daba 0.80
    entre 'regional. El caso del caucho.' y 'Cordillera de los Andes. Las'
    (texto real del cronograma) pese a no compartir ninguna palabra --
    Jaccard de PALABRAS debe dar un valor bajo en ese mismo caso."""
    a = "regional. El caso del caucho."
    b = "Cordillera de los Andes. Las"
    assert _jaccard_palabras(a, b) < 0.3


def test_jaccard_palabras_alto_para_texto_casi_identico():
    a = "Anexo del silabo - CRONOGRAMA DE ACTIVIDADES"
    b = "Anexo del silabo - CRONOGRAMA DE ACTIVIDADES"
    assert _jaccard_palabras(a, b) == 1.0


# --- Deteccion de nuisance sobre documento real ---

def test_nuisance_detecta_header_repetido_del_cronograma_real():
    bloques = extraer_pdf(FIXTURE_CRONOGRAMA, "cronograma-test")
    nuisance_ids = detectar_nuisance(bloques)

    header = next(b for b in bloques if "CRONOGRAMA DE ACTIVIDADES" in b.texto.upper())
    assert header.bloque_id in nuisance_ids


def test_nuisance_no_borra_ningun_bloque():
    bloques = extraer_pdf(FIXTURE_CRONOGRAMA, "cronograma-test")
    n_antes = len(bloques)
    detectar_nuisance(bloques)
    assert len(bloques) == n_antes  # nunca se muta/borra la lista de entrada


def test_nuisance_marca_menos_del_50_por_ciento_en_documento_real():
    """Regresion del bug de Jaccard de caracteres: con ese bug, 291/732
    (40%) de los bloques del cronograma real quedaban marcados, incluyendo
    contenido real de la tabla. Tras el fix a Jaccard de palabras, deberia
    marcar una fraccion mucho menor, dominada por headers genuinos."""
    bloques = extraer_pdf(FIXTURE_CRONOGRAMA, "cronograma-test")
    nuisance_ids = detectar_nuisance(bloques)
    assert len(nuisance_ids) / len(bloques) < 0.35


def test_nuisance_no_marca_contenido_real_de_tabla_como_ruido():
    """Caso especifico de falso positivo ya encontrado y corregido: un
    fragmento de referencia bibliografica real no debe quedar marcado
    solo por casualidad de caracteres compartidos con otro bloque."""
    bloques = extraer_pdf(FIXTURE_CRONOGRAMA, "cronograma-test")
    nuisance_ids = detectar_nuisance(bloques)
    caucho = [b for b in bloques if "caso del caucho" in b.texto]
    if caucho:  # solo si el fixture real contiene ese texto
        assert caucho[0].bloque_id not in nuisance_ids
