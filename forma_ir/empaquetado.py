# -*- coding: utf-8 -*-
"""
Fase H: empaquetado de contexto restringido por evidencia (paper, S5.7).

La economia de tokens es explicitamente secundaria. Dado el conjunto de
unidades candidatas significativas C_alpha(q) (tras el descubrimiento de
documento de la Fase G), se define una utilidad de cobertura submodular
sobre los "atomos de evidencia" z de la consulta (aqui: sus terminos
lexicos distintos):

    F(A) = Sum[z in Z_q] IDF(z) * max[u in A] a_uz    (7)

donde a_uz es 1.0 si el termino z aparece en la unidad u, 0.0 si no
(evidencia binaria de cobertura por unidad -- consistente con el vector
de evidencia disperso de la Fase E, sin introducir una nueva senal).
F es monotona submodular porque a_uz >= 0 (maximo de indicadores no-
negativos).

La seleccion final MINIMIZA el costo en tokens sujeto a preservar una
fraccion (1-epsilon) de la evidencia alcanzable:

    min[A subset C_alpha] Sum[u in A] tokens(u)
    sujeto a F(A) >= (1-epsilon) * F(C_alpha)    (8)

Un algoritmo greedy de cobertura submodular selecciona en cada paso la
unidad con mayor GANANCIA MARGINAL POR TOKEN (no mayor ganancia
absoluta) -- la distincion es la que el checkpoint H de este plan exige
verificar explicitamente con un caso de juguete.
"""
import math
import re
from dataclasses import dataclass

from forma_ir.tipos import UnidadRetenida

_RE_TOKEN = re.compile(r"\w+", re.UNICODE)


def contar_tokens(texto: str) -> int:
    """Conteo de tokens barato y determinista (palabras, no subwords de
    un tokenizador de LLM especifico) -- suficiente como proxy de costo
    relativo entre unidades; el metodo no depende de que provider LLM
    consuma el resultado despues."""
    return len(_RE_TOKEN.findall(texto))


@dataclass
class ResultadoEmpaquetado:
    unidades_seleccionadas: list[str]  # unidad_id, en orden de seleccion
    tokens_totales: int
    cobertura_f: float
    cobertura_maxima_f: float
    fraccion_evidencia_retenida: float


def _atomos_de_query(tokens_query: list[str], idf: dict[str, float]) -> dict[str, float]:
    """Z_q: terminos distintos de la consulta, con su peso IDF(z)."""
    return {t: idf.get(t, 0.0) for t in set(tokens_query)}


def _cobertura_de_unidad(tokens_unidad: set[str], atomos: dict[str, float]) -> set[str]:
    """Que atomos de la consulta cubre esta unidad (a_uz=1 para esos z)."""
    return {z for z in atomos if z in tokens_unidad}


def calcular_F(atomos_cubiertos_por_alguna_unidad: set[str], atomos: dict[str, float]) -> float:
    """Formula (7): F(A) = sum IDF(z) para cada z cubierto por AL MENOS
    una unidad de A (el max[u in A] a_uz colapsa a "cubierto o no" dado
    que a_uz es binario)."""
    return sum(atomos[z] for z in atomos_cubiertos_por_alguna_unidad)


def empaquetar_por_cobertura_submodular(
    unidades_candidatas: list[UnidadRetenida],
    query: str,
    idf: dict[str, float],
    tokenizar_fn,
    epsilon: float = 0.05,
    presupuesto_max_tokens: int | None = None,
) -> ResultadoEmpaquetado:
    """Greedy de cobertura submodular: en cada paso, elige la unidad NO
    seleccionada con mayor GANANCIA MARGINAL DE F POR TOKEN, hasta
    alcanzar F(A) >= (1-epsilon)*F(C_alpha) o agotar las candidatas.

    `presupuesto_max_tokens` (opcional): tope DURO de tokens totales --
    se detiene ANTES de agregar una unidad que lo excederia, incluso si
    la cobertura objetivo aun no se alcanzo. Sin esto, el objetivo de
    cobertura (formula 8 del paper) es la unica condicion de parada, lo
    que en integracion con un consumidor real (un LLM con limite de
    contexto/costo) puede crecer sin control -- encontrado al conectar
    el metodo a produccion (agente.py espera un presupuesto de tokens
    respetado, ver forma_ir_recuperar.py). El paper mismo trata el
    presupuesto como una restriccion explicita del problema (ecuacion
    8: 'min tokens sujeto a F(A) >= (1-epsilon)F(C_alpha)'), asi que
    esto no es una desviacion del diseno, es completar la mitad de la
    restriccion que faltaba implementar.

    Nunca corta una unidad -- se selecciona entera o no se selecciona
    (restriccion de "provenance constraints that forbid slicing an
    atomic induced unit", S5.7)."""
    tokens_query = tokenizar_fn(query)
    atomos = _atomos_de_query(tokens_query, idf)

    cobertura_por_unidad: dict[str, set[str]] = {}
    tokens_por_unidad: dict[str, int] = {}
    unidad_por_id: dict[str, UnidadRetenida] = {}
    for u in unidades_candidatas:
        tokens_u = set(tokenizar_fn(u.texto))
        cobertura_por_unidad[u.unidad_id] = _cobertura_de_unidad(tokens_u, atomos)
        tokens_por_unidad[u.unidad_id] = max(contar_tokens(u.texto), 1)
        unidad_por_id[u.unidad_id] = u

    cobertura_total_alcanzable = set().union(*cobertura_por_unidad.values()) if cobertura_por_unidad else set()
    f_maxima = calcular_F(cobertura_total_alcanzable, atomos)
    objetivo = (1 - epsilon) * f_maxima

    if f_maxima == 0.0:
        return ResultadoEmpaquetado([], 0, 0.0, 0.0, 0.0)

    seleccionadas: list[str] = []
    cubierto_acumulado: set[str] = set()
    restantes = set(cobertura_por_unidad.keys())
    tokens_acumulados = 0
    f_actual = 0.0

    while restantes and f_actual < objetivo:
        mejor_id = None
        mejor_ganancia_por_token = -1.0
        for uid in restantes:
            if presupuesto_max_tokens is not None and tokens_acumulados + tokens_por_unidad[uid] > presupuesto_max_tokens:
                continue  # excederia el presupuesto duro -- no es candidata valida en este paso
            nuevo_cubierto = cobertura_por_unidad[uid] - cubierto_acumulado
            ganancia = calcular_F(nuevo_cubierto, atomos)
            costo = tokens_por_unidad[uid]
            ganancia_por_token = ganancia / costo
            if ganancia_por_token > mejor_ganancia_por_token:
                mejor_ganancia_por_token = ganancia_por_token
                mejor_id = uid

        if mejor_id is None or mejor_ganancia_por_token <= 0.0:
            break  # ninguna unidad restante aporta cobertura nueva (o todas exceden el presupuesto)

        seleccionadas.append(mejor_id)
        cubierto_acumulado |= cobertura_por_unidad[mejor_id]
        tokens_acumulados += tokens_por_unidad[mejor_id]
        f_actual = calcular_F(cubierto_acumulado, atomos)
        restantes.discard(mejor_id)

    return ResultadoEmpaquetado(
        unidades_seleccionadas=seleccionadas,
        tokens_totales=tokens_acumulados,
        cobertura_f=f_actual,
        cobertura_maxima_f=f_maxima,
        fraccion_evidencia_retenida=(f_actual / f_maxima) if f_maxima > 0 else 0.0,
    )
