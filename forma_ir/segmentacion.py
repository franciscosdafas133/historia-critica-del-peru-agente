# -*- coding: utf-8 -*-
"""
Fase C3a: candidatos de limite SIN el objetivo MDL completo (eso es C4).

Union heuristica de: inicios de ocurrencia de reglas marcadas como
candidatas a limite (Fase C2), progresiones de numeracion, transiciones
de indentacion, cambios grandes de espaciado, y puntos de cambio lexico
(PELT sobre una senal de distancia de Jaccard entre ventanas de bloques
consecutivos).

CHECKPOINT MAS IMPORTANTE DEL PLAN: si los candidatos aqui no coinciden
razonablemente con lo que un lector humano ve como inicio de seccion al
abrir el documento original, no tiene sentido construir C4/D/E/F/G/H
sobre una segmentacion mala.
"""
import numpy as np
import ruptures as rpt

from forma_ir.anotacion import AnotacionRegla, _mapear_top_a_bloques, _posiciones_de_regla_en_top
from forma_ir.firma import FirmaForma
from forma_ir.gramatica import Regla
from forma_ir.tipos import Bloque


def _jaccard_palabras(a: str, b: str) -> float:
    sa, sb = set(a.lower().split()), set(b.lower().split())
    if not sa and not sb:
        return 1.0
    if not sa or not sb:
        return 0.0
    return len(sa & sb) / len(sa | sb)


def senal_cambio_lexico(bloques_doc: list[Bloque], radio_ventana: int = 3) -> np.ndarray:
    """Para cada posicion i, distancia de Jaccard entre la ventana de
    `radio_ventana` bloques ANTES de i y la ventana de `radio_ventana`
    bloques DESPUES de i. Un pico en esta senal indica un cambio brusco
    de vocabulario -- candidato a limite de seccion tematica."""
    n = len(bloques_doc)
    senal = np.zeros(n)
    for i in range(n):
        izq = " ".join(b.texto for b in bloques_doc[max(0, i - radio_ventana):i])
        der = " ".join(b.texto for b in bloques_doc[i:min(n, i + radio_ventana)])
        senal[i] = 1.0 - _jaccard_palabras(izq, der)
    return senal


def puntos_de_cambio_lexico(bloques_doc: list[Bloque], factor_penalidad: float = 2.0) -> list[int]:
    """PELT (Pruned Exact Linear Time) sobre la senal de cambio lexico,
    via la libreria `ruptures` -- algoritmo estandar y ya probado, en vez
    de reimplementarlo a mano (decision documentada en el plan: instalar
    ruptures evita reimplementar programacion dinamica propensa a
    errores de indice, algo que ya paso en Fase C1 con SEQUITUR).

    La penalidad NO puede ser un valor fijo: la senal de Jaccard tiene
    escala y varianza muy distintas segun el documento (ej. en prosa
    academica densa la media de la senal es ~0.93 con std~0.06 -- una
    penalidad fija de 3.0, calibrada mentalmente para una senal en [0,1]
    "tipica", apagaba el detector casi por completo, 0 puntos en los 3
    documentos del checkpoint C3a). Se usa la penalidad tipo BIC estandar
    para PELT con modelo l2: pen = factor * sigma^2 * log(n) -- escala
    con el ruido y el largo de la senal en vez de con un numero magico."""
    n = len(bloques_doc)
    if n < 4:
        return []
    senal = senal_cambio_lexico(bloques_doc)
    varianza = float(np.var(senal))
    if varianza <= 1e-9:
        return []  # senal constante -> ningun cambio lexico real que detectar
    import math
    penalidad = factor_penalidad * varianza * math.log(n)
    algo = rpt.Pelt(model="l2", min_size=2).fit(senal.reshape(-1, 1))
    puntos = algo.predict(pen=penalidad)
    # ruptures devuelve los puntos de corte incluyendo el final de la
    # senal (len(senal)) como ultimo elemento -- se descarta, no es un
    # limite real dentro del documento.
    return [p for p in puntos if p < len(bloques_doc)]


def _progresion_numeracion(bloques_doc: list[Bloque]) -> set[int]:
    """Indices de bloque donde empieza una progresion de numeracion
    creciente (1., 2., 3.,... o I, II, III,...) -- deteccion simple por
    regex + verificacion de que el numero extraido efectivamente crece
    respecto a la ultima ocurrencia numerica vista."""
    import re
    candidatos = set()
    ultimo_num = None
    for i, b in enumerate(bloques_doc):
        m = re.match(r"^\s*(\d+)[.\)]", b.texto)
        if m:
            n = int(m.group(1))
            if ultimo_num is None or n == ultimo_num + 1:
                candidatos.add(i)
            ultimo_num = n
    return candidatos


def _transiciones_indentacion(bloques_doc: list[Bloque], percentil: float = 90.0,
                                firmas_doc: list[FirmaForma] | None = None) -> set[int]:
    """Candidato si el salto de indentacion respecto al bloque anterior
    esta entre los mas grandes observados en el documento (percentil
    relativo, no un umbral absoluto en puntos).

    Un umbral fijo (probado primero: 5pt) resulta inutil como senal
    discriminativa: en PPTX, sucesivos shapes casi nunca comparten
    exactamente el mismo x0 aunque visualmente esten "alineados" (ruido
    de posicionamiento del autor de las diapositivas), asi que un umbral
    absoluto bajo marcaba 91% de los bloques de un deck real como
    candidato -- no discrimina nada. El percentil relativo al propio
    documento evita ese problema: solo los saltos genuinamente atipicos
    para ESE documento cuentan.

    En un PDF de dos columnas persistia otro problema incluso con
    percentil relativo: el salto de indentacion entre "fin de columna
    izquierda" e "inicio de columna derecha" es geometricamente grande y
    consistente, y el layout multi-columna produce MUCHOS de esos saltos
    -- son ruido de layout, no estructura. Se descartan los indices cuya
    firma orto-tipografica es una firma dominante del documento (cuerpo
    de texto corrido, ver `_firmas_dominantes`)."""
    dominantes = _firmas_dominantes(firmas_doc) if firmas_doc is not None else set()
    saltos = []
    for i in range(1, len(bloques_doc)):
        a, b = bloques_doc[i - 1].indentacion_pt, bloques_doc[i].indentacion_pt
        if a is not None and b is not None:
            saltos.append((i, abs(a - b)))
    if len(saltos) < 5:
        return set()
    valores = [s for _, s in saltos]
    umbral = float(np.percentile(valores, percentil))
    if umbral <= 0:
        return set()
    return {i for i, s in saltos
            if s >= umbral and not (firmas_doc is not None and firmas_doc[i] in dominantes)}


def _cambios_grandes_espaciado(bloques_doc: list[Bloque],
                                 firmas_doc: list[FirmaForma] | None = None) -> set[int]:
    """Candidato si el espacio vertical antes de un bloque supera el
    percentil 90 de los espacios observados en el documento -- excluyendo
    firmas dominantes (cuerpo de texto corrido), mismo razonamiento que
    en `_transiciones_indentacion`."""
    dominantes = _firmas_dominantes(firmas_doc) if firmas_doc is not None else set()
    espacios = [b.espacio_vertical_antes for b in bloques_doc if b.espacio_vertical_antes is not None]
    if len(espacios) < 5:
        return set()
    umbral = float(np.percentile(espacios, 90))
    return {i for i, b in enumerate(bloques_doc)
            if b.espacio_vertical_antes is not None and b.espacio_vertical_antes >= umbral and umbral > 0
            and not (firmas_doc is not None and firmas_doc[i] in dominantes)}


def _firmas_dominantes(firmas_doc: list[FirmaForma], fraccion_umbral: float = 0.05) -> set[FirmaForma]:
    """Firmas que por si solas cubren mas de `fraccion_umbral` del
    documento -- tipicamente el cuerpo de texto corrido. Un limite de
    seccion es por definicion algo RARO dentro de un documento; una
    firma que aparece en >5% de todos los bloques no puede serlo, sea
    cual sea su diversidad lexica o estabilidad posicional.

    Encontrado en Checkpoint C3a: en un PDF academico de dos columnas,
    4 firmas de "linea de cuerpo de texto en columna" cubrian 511/2046
    bloques (25%) por compartir tamano de fuente e interlineado -- sin
    este filtro, SEQUITUR + el criterio de C2 seguian marcando cientos
    de lineas de prosa corrida como candidatas."""
    from collections import Counter
    conteo = Counter(firmas_doc)
    n = len(firmas_doc)
    if n == 0:
        return set()
    return {f for f, c in conteo.items() if c / n >= fraccion_umbral}


def _inicios_de_reglas_candidatas(reglas: dict[int, Regla], top: list[int],
                                    anotaciones: dict[int, AnotacionRegla],
                                    bloques_doc: list[Bloque],
                                    firmas_doc: list[FirmaForma] | None = None) -> set[int]:
    mapa_top_a_bloques = _mapear_top_a_bloques(top, reglas, bloques_doc)
    dominantes = _firmas_dominantes(firmas_doc) if firmas_doc is not None else set()
    candidatos = set()
    for rid, anot in anotaciones.items():
        if not anot.es_candidata_limite:
            continue
        for pos in _posiciones_de_regla_en_top(rid, top):
            indices = mapa_top_a_bloques[pos]
            if not indices:
                continue
            primero = indices[0]
            if firmas_doc is not None and firmas_doc[primero] in dominantes:
                continue
            candidatos.add(primero)
    return candidatos


def candidatos_limite(bloques_doc: list[Bloque], reglas: dict[int, Regla], top: list[int],
                        anotaciones: dict[int, AnotacionRegla],
                        firmas_doc: list[FirmaForma] | None = None,
                        factor_penalidad_pelt: float = 2.0) -> dict[int, set[str]]:
    """Union heuristica de todas las fuentes de candidatos. Devuelve un
    dict {indice_bloque: {fuentes}} para poder inspeccionar POR QUE cada
    posicion fue marcada (auditable, util para el checkpoint humano).

    `firmas_doc` (opcional pero fuertemente recomendado) permite filtrar
    firmas dominantes -- ver `_firmas_dominantes`. Sin ella, el filtro se
    omite (compatibilidad hacia atras para quien ya tenga solo
    reglas/top/anotaciones a mano)."""
    fuentes: dict[int, set[str]] = {}

    def agregar(indices, nombre):
        for i in indices:
            fuentes.setdefault(i, set()).add(nombre)

    agregar(_inicios_de_reglas_candidatas(reglas, top, anotaciones, bloques_doc, firmas_doc), "regla_gramatica")
    agregar(_progresion_numeracion(bloques_doc), "numeracion")
    agregar(_transiciones_indentacion(bloques_doc, firmas_doc=firmas_doc), "indentacion")
    agregar(_cambios_grandes_espaciado(bloques_doc, firmas_doc=firmas_doc), "espaciado")
    agregar(puntos_de_cambio_lexico(bloques_doc, factor_penalidad=factor_penalidad_pelt), "cambio_lexico")

    return fuentes
