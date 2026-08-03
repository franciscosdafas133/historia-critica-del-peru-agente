# -*- coding: utf-8 -*-
"""
Fase G: documento y multiplicidad (paper, S5.6).

Rankear unidades directamente favorece documentos que generan muchas
unidades (mas oportunidades de que alguna tenga p-valor bajo por puro
azar). FORMA-IR agrega primero a nivel documento con una correccion
tipo Bonferroni, penalizando la fragmentacion en vez de premiarla:

    p_doc(d,q) = min(1, m_d * min[u in d] p_c(u,q))    (6)

donde m_d es el numero de unidades elegibles del documento d en el
antichain de recuperacion. Esta forma es valida bajo dependencia
arbitraria entre las unidades de un mismo documento (no requiere
independencia, a diferencia de una correccion menos conservadora).

Los documentos se rankean por p_doc (menor es mejor); las unidades se
rankean DENTRO de los documentos top solamente, no globalmente.
"""
from dataclasses import dataclass

from forma_ir.evidencia import VectorEvidencia
from forma_ir.tipos import UnidadRetenida


@dataclass
class ResultadoDocumento:
    doc_id: str
    p_doc: float
    m_d: int  # numero de unidades elegibles del documento
    mejor_unidad_id: str  # la unidad con menor p_c(u,q) dentro del documento
    mejor_p_c: float


def agregar_documento(doc_id: str, p_valores_por_unidad: dict[str, float]) -> ResultadoDocumento:
    """Formula (6) aplicada a un solo documento. `p_valores_por_unidad`
    debe contener SOLO las unidades elegibles de ESTE documento (ya
    filtradas por familia calibrada, etc. -- ver `agregar_documentos`)."""
    if not p_valores_por_unidad:
        raise ValueError(f"documento {doc_id} sin unidades elegibles, no se puede agregar")

    m_d = len(p_valores_por_unidad)
    mejor_unidad_id = min(p_valores_por_unidad, key=p_valores_por_unidad.get)
    mejor_p_c = p_valores_por_unidad[mejor_unidad_id]

    p_doc = min(1.0, m_d * mejor_p_c)
    return ResultadoDocumento(doc_id=doc_id, p_doc=p_doc, m_d=m_d,
                                mejor_unidad_id=mejor_unidad_id, mejor_p_c=mejor_p_c)


def agregar_documentos(p_valores_por_unidad_y_doc: dict[str, dict[str, float]]) -> list[ResultadoDocumento]:
    """Aplica `agregar_documento` a cada documento y devuelve los
    resultados ORDENADOS por p_doc ascendente (mejor documento primero).
    `p_valores_por_unidad_y_doc` = {doc_id: {unidad_id: p_c}}."""
    resultados = [
        agregar_documento(doc_id, p_valores)
        for doc_id, p_valores in p_valores_por_unidad_y_doc.items()
        if p_valores
    ]
    resultados.sort(key=lambda r: r.p_doc)
    return resultados


def rankear_unidades_de_documento(doc_id: str, p_valores_por_unidad: dict[str, float]) -> list[tuple[str, float]]:
    """Dentro de un documento ya seleccionado (top documentos por
    p_doc), rankea sus unidades por p_c ascendente -- esto se hace SOLO
    despues de que el documento entro al conjunto candidato, nunca antes
    (S5.6: 'units are then ranked within the top documents')."""
    return sorted(p_valores_por_unidad.items(), key=lambda par: par[1])
