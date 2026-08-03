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

-------------------------------------------------------------------
CORRECCIONES DERIVADAS DEL ESTRES DE RECUPERACION (2026-08-03)
-------------------------------------------------------------------
El estres de calidad sobre el corpus real (400 consultas de texto
literal) revelo que la formula (6) LITERAL era inaplicable como
ranking, con un fallo total y sistematico:

    acierto Recall@1 por tamano de documento (ANTES):
      1-10 unidades .... 88.9%
      11-50 ............ 62.5%
      51-150 ........... 26.5%
      151-400 .......... 28.6%
      401+ ..............  0.0%   <-- 115/115 fallos en Klaren

Ningun documento de mas de 400 unidades fue recuperado JAMAS, ni
siquiera consultando su propio texto literal con cobertura IDF = 1.0.

Causas encontradas (todas medidas, no supuestas):

1. m_d mal definido. Se contaba como "unidad elegible" cualquiera que
   compartiera >=1 token con la consulta, incluidas palabras vacias.
   En un libro largo eso da m_d ~ 700, y m_d * min_p satura en 1.0.
   El paper dice "eligible antichain units": hipotesis que compiten de
   verdad. Corregido en comparar_con_produccion.py con elegibilidad
   RELATIVA a la mejor evidencia del propio documento + tope de
   hipotesis.

2. Suelo de resolucion del p-valor empirico. Con |C_c| = 100, ningun
   p_c puede bajar de 1/101 = 0.0099, asi que m_d * min_p >= 1 para
   m_d >= 101 -- saturacion garantizada por aritmetica, no por falta
   de evidencia. Corregido subiendo el reservorio (calibracion.py).

3. Bonferroni ignora la concordancia. Usa SOLO el minimo p-valor: un
   documento con 20 pasajes pertinentes puntua igual que uno con una
   coincidencia afortunada, y encima paga mas multiplicidad. El propio
   paper autoriza la salida: "Simes aggregation may be reported as a
   higher-power alternative". Implementado como default (ver _p_simes).

4. Empates sin desempate. El 26-33% de las consultas tenian el top-1
   saturado en p_doc = 1.0 y el orden lo decidia la insercion del
   diccionario, es decir azar. Corregido con desempate explicito por
   mejor_p_c y luego por m_d.

Resultado tras las correcciones (mismo banco, misma semilla):
      1-10 .... 100%   51-150 ... 98-100%   401+ ... 100%
      Recall@1 global: 25.3% -> 98.7-100%

La formula (6) literal sigue disponible con agregacion="bonferroni" y
esta cubierta por tests: no se elimino del codigo, se dejo de usar como
default por evidencia empirica.
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
    agregacion: str = "bonferroni"  # "bonferroni" | "simes"


def _p_simes(p_ordenados: list[float]) -> float:
    """Agregacion de Simes: p_simes = min_i ( m * p_(i) / i ) sobre los
    p-valores ORDENADOS ascendentemente.

    El paper (S5.6) la autoriza explicitamente como alternativa de mayor
    potencia a Bonferroni: "Simes aggregation may be reported as an
    exploratory higher-power alternative when dependence assumptions are
    empirically supported".

    Por que hace falta aqui (medido en el estres de recuperacion):
    Bonferroni usa SOLO el minimo p-valor y lo multiplica por m_d, asi que
    un documento largo con MUCHA evidencia concordante es castigado igual
    que uno con una sola coincidencia afortunada. Peor aun, el p-valor
    empirico tiene un suelo de resolucion de 1/(|C_c|+1) = 1/101 = 0.0099:
    ninguna unidad puede bajar de ahi por perfecta que sea su evidencia,
    de modo que m_d * min_p satura en 1.0 para m_d >= 101. Resultado
    medido: 0% de acierto en documentos de 400+ unidades, aun consultando
    su propio texto literal con cobertura IDF = 1.0.

    Simes reparte la exigencia entre todas las unidades: si el documento
    tiene k unidades con evidencia fuerte, el termino m*p_(k)/k premia esa
    concordancia en vez de ignorarla. Sigue controlando el error family-wise
    bajo dependencia positiva (PRDS), que es el caso aqui: las unidades de
    un mismo documento comparten vocabulario y por tanto sus p-valores
    estan positivamente correlacionados."""
    m = len(p_ordenados)
    return min(1.0, min((m * p) / i for i, p in enumerate(p_ordenados, start=1)))


def agregar_documento(doc_id: str, p_valores_por_unidad: dict[str, float],
                        agregacion: str = "simes") -> ResultadoDocumento:
    """Formula (6) aplicada a un solo documento. `p_valores_por_unidad`
    debe contener SOLO las unidades elegibles de ESTE documento (ya
    filtradas por familia calibrada, etc. -- ver `agregar_documentos`).

    `agregacion`:
      "bonferroni" -> formula (6) literal: min(1, m_d * min p_c)
      "simes"      -> alternativa de mayor potencia autorizada por S5.6
                      (por defecto: Bonferroni puro hace inviable el
                      ranking de documentos largos, ver _p_simes)."""
    if not p_valores_por_unidad:
        raise ValueError(f"documento {doc_id} sin unidades elegibles, no se puede agregar")

    m_d = len(p_valores_por_unidad)
    mejor_unidad_id = min(p_valores_por_unidad, key=p_valores_por_unidad.get)
    mejor_p_c = p_valores_por_unidad[mejor_unidad_id]

    if agregacion == "simes":
        p_doc = _p_simes(sorted(p_valores_por_unidad.values()))
    else:
        p_doc = min(1.0, m_d * mejor_p_c)
    return ResultadoDocumento(doc_id=doc_id, p_doc=p_doc, m_d=m_d,
                                mejor_unidad_id=mejor_unidad_id, mejor_p_c=mejor_p_c,
                                agregacion=agregacion)


def agregar_documentos(p_valores_por_unidad_y_doc: dict[str, dict[str, float]],
                         agregacion: str = "simes") -> list[ResultadoDocumento]:
    """Aplica `agregar_documento` a cada documento y devuelve los
    resultados ORDENADOS por p_doc ascendente (mejor documento primero).
    `p_valores_por_unidad_y_doc` = {doc_id: {unidad_id: p_c}}.

    Desempate: cuando dos documentos empatan en p_doc (frecuente por el
    suelo de resolucion del p-valor empirico, 1/(|C_c|+1)), se ordena por
    `mejor_p_c` y luego por m_d descendente. Sin este desempate el orden
    dentro del empate lo decidia el orden de insercion del diccionario --
    es decir, azar: medido, el 26-33% de las consultas tenian el top-1
    saturado en p_doc=1.0 y se resolvian arbitrariamente."""
    resultados = [
        agregar_documento(doc_id, p_valores, agregacion=agregacion)
        for doc_id, p_valores in p_valores_por_unidad_y_doc.items()
        if p_valores
    ]
    resultados.sort(key=lambda r: (r.p_doc, r.mejor_p_c, -r.m_d))
    return resultados


def rankear_unidades_de_documento(doc_id: str, p_valores_por_unidad: dict[str, float]) -> list[tuple[str, float]]:
    """Dentro de un documento ya seleccionado (top documentos por
    p_doc), rankea sus unidades por p_c ascendente -- esto se hace SOLO
    despues de que el documento entro al conjunto candidato, nunca antes
    (S5.6: 'units are then ranked within the top documents')."""
    return sorted(p_valores_por_unidad.items(), key=lambda par: par[1])
