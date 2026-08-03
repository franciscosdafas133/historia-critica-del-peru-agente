# -*- coding: utf-8 -*-
"""
Checkpoint A: tests del extractor con pistas fisicas (forma_ir/ingesta.py).

Los valores exactos de font_size/bold/bbox de este test se verificaron a
mano (Read directo del PDF con PyMuPDF en modo interactivo antes de
escribir el extractor) contra tests/forma_ir/fixtures/cronograma_fixture.pdf,
una copia real de Cronograma_HCP_2026_1_A.pdf (1 pagina, tabla con
encabezados en negrita Arial 11/10pt).
"""
import os

from forma_ir.ingesta import extraer_pdf, _es_negrita, _es_italica

RAIZ = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
FIXTURE_CRONOGRAMA = os.path.join(RAIZ, "tests", "forma_ir", "fixtures", "cronograma_fixture.pdf")


def test_bit_negrita_confirmado_empiricamente():
    # Arial,Bold con flags=16 -> negrita (verificado contra el PDF real)
    assert _es_negrita(16, "Arial,Bold") is True
    # Calibri con flags=0 -> no negrita
    assert _es_negrita(0, "Calibri") is False


def test_bit_italica_confirmado_empiricamente():
    # TimesLTStd-Italic con flags=6 (4 serifed + 2 italic) -> italica
    assert _es_italica(6, "TimesLTStd-Italic") is True
    # TimesLTStd-Roman con flags=4 (solo serifed) -> NO italica
    assert _es_italica(4, "TimesLTStd-Roman") is False
    # TimesLTStd-BoldItalic con flags=22 (16 bold + 4 serifed + 2 italic)
    assert _es_italica(22, "TimesLTStd-BoldItalic") is True
    assert _es_negrita(22, "TimesLTStd-BoldItalic") is True


def test_extraer_pdf_cronograma_produce_bloques_no_vacios():
    bloques = extraer_pdf(FIXTURE_CRONOGRAMA, "cronograma-test")
    assert len(bloques) > 0
    assert all(b.doc_id == "cronograma-test" for b in bloques)
    assert all(b.formato_fuente == "pdf" for b in bloques)
    # El fixture tiene 8 paginas reales (confirmado con fitz.open() directo,
    # no asumido); todas las paginas presentes deben caer en ese rango.
    assert all(1 <= b.pagina <= 8 for b in bloques)


def test_extraer_pdf_encabezado_de_tabla_es_negrita():
    """Verificado a mano: el primer bloque de texto real ('Anexo del
    silabo...') y los encabezados de columna de la tabla ('Semana',
    'Clases y', 'fechas', etc.) estan en Arial,Bold."""
    bloques = extraer_pdf(FIXTURE_CRONOGRAMA, "cronograma-test")
    encabezado = next(b for b in bloques if "CRONOGRAMA" in b.texto.upper())
    assert encabezado.bold is True
    assert encabezado.font_size == 11.04

    col_semana = next(b for b in bloques if b.texto.strip() == "Semana")
    assert col_semana.bold is True
    assert col_semana.font_size == 9.96


def test_extraer_pdf_secuencia_es_ordenada_y_unica():
    bloques = extraer_pdf(FIXTURE_CRONOGRAMA, "cronograma-test")
    secuencias = [b.seq for b in bloques]
    assert secuencias == sorted(secuencias)
    assert len(set(secuencias)) == len(secuencias)  # sin duplicados
    assert secuencias[0] == 0


def test_extraer_pdf_bbox_tiene_cuatro_componentes_numericos():
    bloques = extraer_pdf(FIXTURE_CRONOGRAMA, "cronograma-test")
    for b in bloques[:20]:
        assert b.bbox is not None
        assert len(b.bbox) == 4
        x0, y0, x1, y1 = b.bbox
        assert x1 >= x0
        assert y1 >= y0


def test_extraer_pdf_documento_inexistente_lanza_excepcion_clara():
    import pytest
    with pytest.raises(Exception):
        extraer_pdf(os.path.join(RAIZ, "no_existe_este_archivo.pdf"), "no-existe")


# --- Fusion de lineas en parrafos (Checkpoint C3a, ver forma_ir/segmentacion.py) ---
#
# Bug real encontrado: con "un bloque = una linea fisica", un PDF de
# prosa academica en dos columnas (Contreras 2020) fragmentaba cada
# parrafo en decenas de bloques de firma casi identica, que SEQUITUR
# agrupaba en reglas de gramatica falsamente marcadas como "candidatas a
# limite" (27% de lineas del documento). Se corrigio fusionando lineas
# consecutivas del mismo `block` de PyMuPDF que comparten firma
# tipografica e interlineado normal. Fixture: copia real de
# Contreras_2020_Crisisdemografica_sigloXVI.pdf.

FIXTURE_CONTRERAS = os.path.join(RAIZ, "tests", "forma_ir", "fixtures", "contreras_fixture.pdf")


def test_extraer_pdf_fusiona_lineas_de_un_mismo_parrafo():
    """El primer parrafo real del abstract en español ('El asentamiento
    espanol...') ocupa varias lineas fisicas en el PDF (confirmado
    inspeccionando el layout con fitz directamente) pero debe llegar
    como UN SOLO bloque tras la fusion, no fragmentado linea por linea."""
    bloques = extraer_pdf(FIXTURE_CONTRERAS, "contreras-test")
    parrafo = next(b for b in bloques if b.texto.startswith("El asentamiento español"))
    # el parrafo fusionado debe contener texto que en el PDF original
    # esta varias lineas despues del inicio -- prueba de que se fusiono
    # mas de una linea fisica en este bloque.
    assert "crisis demográfica" in parrafo.texto.lower()
    assert len(parrafo.texto) > 200  # una sola linea fisica no llega a este largo


def test_extraer_pdf_no_fusiona_a_traves_de_cambio_de_firma():
    """El titulo en negrita 14pt no debe fusionarse con el parrafo de
    cuerpo (8pt, no negrita) que le sigue, aunque esten verticalmente
    cerca -- distinta firma tipografica es la señal de que son
    unidades visuales distintas."""
    bloques = extraer_pdf(FIXTURE_CONTRERAS, "contreras-test")
    titulo = next(b for b in bloques if "CRISIS DEMOGRÁFICA DEL SIGLO XVI" in b.texto)
    assert titulo.font_size == 14.0
    assert titulo.bold is True
    assert "asentamiento español" not in titulo.texto.lower()


def test_extraer_pdf_fusion_no_cruza_columnas_por_x0_distinto():
    """Regresion: dos lineas con el mismo tamano/negrita pero x0 muy
    distinto (ej. fin de columna izquierda / inicio de columna derecha
    en la misma altura de pagina) no deben fusionarse solo por
    compartir firma tipografica -- el chequeo de indentacion compatible
    (delta <= 3pt) debe impedirlo."""
    from forma_ir.ingesta import _mismo_parrafo
    linea_col_izq = {
        "bbox": (50.0, 300.0, 250.0, 310.0),
        "spans": [{"size": 8.0, "flags": 0, "font": "Calibri", "text": "fin de columna izquierda"}],
    }
    linea_col_der = {
        "bbox": (310.0, 300.0, 500.0, 310.0),
        "spans": [{"size": 8.0, "flags": 0, "font": "Calibri", "text": "inicio de columna derecha"}],
    }
    assert _mismo_parrafo(linea_col_izq, linea_col_der) is False
