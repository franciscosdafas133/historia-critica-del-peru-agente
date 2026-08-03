# -*- coding: utf-8 -*-
"""
Checkpoint I: conexion del pipeline completo A-H al dataset de
evaluacion (paper, seccion de metodo end-to-end).

No depende del corpus completo persistido (forma_ir_corpus/) -- usa un
corpus sintetico pequeno de 2 documentos para verificar que
`responder_consulta` ejecuta el pipeline E->F->G->H de punta a punta sin
excepcion y produce salida auditable (S5.8: texto extractivo, doc_id,
pagina, score calibrado, correccion de documento, conteo de tokens).

El corpus real de 57 preguntas se corre por separado via
`python -m forma_ir.comparar_con_produccion` (mas lento, no apto para
un test unitario rapido) -- ver forma_ir_corpus/evaluacion_57_preguntas.json
para el resultado real persistido tras esa corrida."""
from collections import defaultdict

from forma_ir.calibracion import construir_reservorios_por_familia
from forma_ir.comparar_con_produccion import responder_consulta
from forma_ir.evidencia import calcular_idf, tokenizar
from forma_ir.firma import secuencia_de_firmas
from forma_ir.tipos import Bloque, UnidadRetenida


def _bloque(texto: str, seq: int, doc_id: str) -> Bloque:
    return Bloque(
        bloque_id=f"{doc_id}#{seq}", doc_id=doc_id, seq=seq, texto=texto,
        pagina=1, diapositiva=None, bbox=(0.0, 0.0, 100.0, 10.0),
        font_size=10.0, bold=None, italic=None,
        indentacion_pt=0.0, espacio_vertical_antes=None, formato_fuente="pdf",
    )


def _construir_indice_sintetico():
    """2 documentos con vocabulario deliberadamente compartido (para que
    la calibracion de Fase F tenga con que construir reservorios) y
    contenido distinguible por consulta."""
    palabras_compartidas = ["historia", "peru", "crisis", "poblacion", "siglo", "colonial"]
    bloques_a = [
        _bloque(f"{palabras_compartidas[i % len(palabras_compartidas)]} parrafo numero {i} sobre el tema", i, "doc-a")
        for i in range(20)
    ]
    bloques_b = [
        _bloque(f"{palabras_compartidas[(i+3) % len(palabras_compartidas)]} contenido distinto {i} de este documento", i, "doc-b")
        for i in range(20)
    ]
    bloques_por_doc = {"doc-a": bloques_a, "doc-b": bloques_b}
    firmas_por_doc = {doc_id: secuencia_de_firmas(bloques) for doc_id, bloques in bloques_por_doc.items()}

    unidades_a = [
        UnidadRetenida(unidad_id=f"doc-a#u{i}", doc_id="doc-a", indices_bloque=[i],
                        texto=bloques_a[i].texto, pagina_inicio=1, pagina_fin=1, familia_id=0)
        for i in range(20)
    ]
    unidades_b = [
        UnidadRetenida(unidad_id=f"doc-b#u{i}", doc_id="doc-b", indices_bloque=[i],
                        texto=bloques_b[i].texto, pagina_inicio=1, pagina_fin=1, familia_id=0)
        for i in range(20)
    ]
    todas_las_unidades = unidades_a + unidades_b
    unidades_por_familia = {0: todas_las_unidades}
    unidades_por_doc = {"doc-a": unidades_a, "doc-b": unidades_b}

    idf = calcular_idf([tokenizar(b.texto) for bloques in bloques_por_doc.values() for b in bloques])
    longitud_promedio = sum(len(u.texto.split()) for u in todas_las_unidades) / len(todas_las_unidades)

    reservorios = construir_reservorios_por_familia(
        unidades_por_familia, todas_las_unidades, bloques_por_doc, firmas_por_doc, idf, longitud_promedio
    )

    return {
        "bloques_por_doc": bloques_por_doc,
        "firmas_por_doc": firmas_por_doc,
        "unidades_por_doc": unidades_por_doc,
        "todas_las_unidades": todas_las_unidades,
        "idf": idf,
        "longitud_promedio": longitud_promedio,
        "reservorios": reservorios,
    }


def test_responder_consulta_produce_salida_auditable():
    indice = _construir_indice_sintetico()
    resultado = responder_consulta("historia peru colonial", indice, top_k_documentos=2)

    assert "documentos" in resultado
    assert "unidades_empaquetadas" in resultado
    assert "tokens_totales" in resultado
    assert "latencia_s" in resultado
    for doc in resultado["documentos"]:
        assert "doc_id" in doc and "p_doc" in doc and "m_d" in doc
    for u in resultado["unidades_empaquetadas"]:
        assert "unidad_id" in u and "doc_id" in u and "texto" in u


def test_responder_consulta_sin_ninguna_evidencia_no_lanza_excepcion():
    indice = _construir_indice_sintetico()
    resultado = responder_consulta("palabras que nunca aparecen en absoluto aqui", indice)
    assert resultado["cobertura"] is False
    assert resultado["unidades_empaquetadas"] == []


def test_responder_consulta_respeta_presupuesto_de_tokens_razonablemente():
    """No es una garantia dura (el greedy puede excederse en la ultima
    unidad seleccionada, ver S5.7), pero con un presupuesto muy chico y
    epsilon relajado, el resultado no debe traer todo el corpus."""
    indice = _construir_indice_sintetico()
    resultado = responder_consulta("historia peru colonial", indice, epsilon=0.9)
    total_tokens_corpus = sum(len(u.texto.split()) for u in indice["todas_las_unidades"])
    assert resultado["tokens_totales"] < total_tokens_corpus
