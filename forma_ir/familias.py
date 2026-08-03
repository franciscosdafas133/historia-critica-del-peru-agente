# -*- coding: utf-8 -*-
"""
Fase D: familias estructurales (paper, S5.3).

Cada UnidadRetenida se representa por features NO-SEMANTICAS (nunca
palabras, nunca un genero declarado como "contrato"/"manual"/"slide"):
longitud logaritmica, entropia lexica, type-token ratio, densidad
numerica, densidad de puntuacion, dispersion de longitud de oracion,
profundidad de indentacion, soporte de repeticion, posicion relativa.

El paper deja abierta la eleccion entre "a finite mixture or k-medoids
partition selected by MDL". Se usa KMeans + StandardScaler como
sustituto documentado de k-medoids (evita la dependencia
sklearn_extra, poco mantenida) y se selecciona k por una penalizacion
tipo BIC sobre la inercia del cluster -- mismo espiritu MDL de premiar
ajuste y penalizar complejidad, sin pretender ser un BIC exacto de un
modelo generativo declarado.

Las etiquetas resultantes (`familia_id`) son vecindarios empiricos
compactos, NO categorias de genero -- por diseno, no se les asigna
ningun nombre humano en esta fase.
"""
import math
import re
from collections import Counter
from dataclasses import dataclass

import numpy as np
from sklearn.cluster import KMeans
from sklearn.preprocessing import StandardScaler

from forma_ir.tipos import Bloque, UnidadRetenida

_RE_ORACION = re.compile(r"[.!?]+")


@dataclass
class FeaturesEstructurales:
    unidad_id: str
    log_longitud: float
    entropia_lexica: float
    type_token_ratio: float
    densidad_numerica: float
    densidad_puntuacion: float
    dispersion_longitud_oracion: float
    profundidad_indentacion: float
    soporte_repeticion: float
    posicion_relativa: float


def _entropia_shannon_palabras(texto: str) -> float:
    palabras = texto.lower().split()
    if not palabras:
        return 0.0
    conteo = Counter(palabras)
    n = len(palabras)
    entropia = 0.0
    for c in conteo.values():
        p = c / n
        entropia -= p * math.log2(p)
    return entropia


def _type_token_ratio(texto: str) -> float:
    palabras = texto.lower().split()
    if not palabras:
        return 0.0
    return len(set(palabras)) / len(palabras)


def _densidad_numerica(texto: str) -> float:
    if not texto:
        return 0.0
    return sum(1 for c in texto if c.isdigit()) / len(texto)


def _densidad_puntuacion(texto: str) -> float:
    if not texto:
        return 0.0
    return sum(1 for c in texto if not c.isalnum() and not c.isspace()) / len(texto)


def _dispersion_longitud_oracion(texto: str) -> float:
    """Desviacion estandar de la longitud (en palabras) de las oraciones
    de la unidad -- baja para unidades con oraciones uniformes (ej. filas
    de tabla de una sola linea repetidas), alta para prosa con oraciones
    de largo variable."""
    oraciones = [o.strip() for o in _RE_ORACION.split(texto) if o.strip()]
    if len(oraciones) < 2:
        return 0.0
    longitudes = [len(o.split()) for o in oraciones]
    media = sum(longitudes) / len(longitudes)
    varianza = sum((l - media) ** 2 for l in longitudes) / len(longitudes)
    return math.sqrt(varianza)


def _profundidad_indentacion(bloques_unidad: list[Bloque]) -> float:
    sangrias = [b.indentacion_pt for b in bloques_unidad if b.indentacion_pt is not None]
    if not sangrias:
        return 0.0
    return sum(sangrias) / len(sangrias)


def _soporte_repeticion(bloques_unidad: list[Bloque], firmas_unidad: list) -> float:
    """Fraccion de bloques de la unidad cuya firma orto-tipografica se
    repite al menos una vez DENTRO de la misma unidad -- alto para
    tablas/listas con patron interno repetido, bajo para prosa donde
    cada linea tiene una forma distinta."""
    if not firmas_unidad:
        return 0.0
    conteo = Counter(firmas_unidad)
    repetidas = sum(1 for f in firmas_unidad if conteo[f] > 1)
    return repetidas / len(firmas_unidad)


def calcular_features(unidad: UnidadRetenida, bloques_doc: list[Bloque],
                        firmas_doc: list, n_bloques_doc: int) -> FeaturesEstructurales:
    bloques_unidad = [bloques_doc[i] for i in unidad.indices_bloque]
    firmas_unidad = [firmas_doc[i] for i in unidad.indices_bloque]
    texto = unidad.texto

    n_palabras = len(texto.split())
    posicion_relativa = (unidad.indices_bloque[0] / n_bloques_doc) if n_bloques_doc > 0 else 0.0

    return FeaturesEstructurales(
        unidad_id=unidad.unidad_id,
        log_longitud=math.log2(1 + n_palabras),
        entropia_lexica=_entropia_shannon_palabras(texto),
        type_token_ratio=_type_token_ratio(texto),
        densidad_numerica=_densidad_numerica(texto),
        densidad_puntuacion=_densidad_puntuacion(texto),
        dispersion_longitud_oracion=_dispersion_longitud_oracion(texto),
        profundidad_indentacion=_profundidad_indentacion(bloques_unidad),
        soporte_repeticion=_soporte_repeticion(bloques_unidad, firmas_unidad),
        posicion_relativa=posicion_relativa,
    )


_CAMPOS_NUMERICOS = [
    "log_longitud", "entropia_lexica", "type_token_ratio", "densidad_numerica",
    "densidad_puntuacion", "dispersion_longitud_oracion", "profundidad_indentacion",
    "soporte_repeticion", "posicion_relativa",
]


def _matriz(features: list[FeaturesEstructurales]) -> np.ndarray:
    return np.array([[getattr(f, campo) for campo in _CAMPOS_NUMERICOS] for f in features])


def _bic_kmeans(matriz: np.ndarray, modelo: KMeans) -> float:
    """Penalizacion tipo BIC sobre un ajuste KMeans (variante Pelleg &
    Moore / X-means): -2*log-verosimilitud aproximada via Gaussianas
    isotropicas con VARIANZA PROPIA POR CLUSTER + penalizacion por
    numero de parametros libres (k centroides * d dimensiones + k
    proporciones de mezcla + k varianzas).

    Bug real encontrado en Checkpoint D: la primera version usaba una
    varianza UNICA compartida entre todos los clusters (inercia total /
    (n-k)). Con eso, la log-verosimilitud del modelo mejora casi
    automaticamente con cada aumento de k -- ampliar k SIEMPRE reduce la
    inercia total, y compartir una sola varianza global permite que esa
    reduccion se traduzca directo en ganancia, sin que la penalizacion
    lineal en k (n_parametros*log(n)) logre jamas compensarla. Verificado
    con datos reales: el BIC seguia bajando monotonicamente probando
    k=2..150 sobre las 2906 unidades del corpus completo, sin ningun
    minimo interior -- el criterio nunca podia elegir "suficientes
    clusters, no mas".

    La correccion (varianza LOCAL por cluster, siguiendo la formulacion
    de X-means) si penaliza correctamente: un cluster que ya es compacto
    (varianza local baja) no gana casi nada en verosimilitud al
    subdividirse mas, porque su propia varianza ya es pequena -- el
    termino de penalizacion por parametros adicionales (ahora incluye
    tambien las k varianzas estimadas) puede entonces superar la
    ganancia marginal y producir un minimo interior real."""
    n, d = matriz.shape
    k = modelo.n_clusters
    if n <= k:
        return float("inf")

    etiquetas = modelo.labels_
    log_verosimilitud = 0.0
    for c in range(k):
        miembros = matriz[etiquetas == c]
        n_c = len(miembros)
        if n_c == 0:
            continue
        centroide = modelo.cluster_centers_[c]
        suma_cuadrados = float(np.sum((miembros - centroide) ** 2))
        # varianza LOCAL de este cluster (no la inercia total del modelo)
        varianza_c = suma_cuadrados / max(n_c * d, 1)
        if varianza_c <= 1e-9:
            varianza_c = 1e-9
        log_verosimilitud += (
            -0.5 * n_c * d * math.log(2 * math.pi * varianza_c)
            - 0.5 * suma_cuadrados / varianza_c
            + n_c * math.log(n_c / n)  # peso de mezcla del cluster
        )

    n_parametros = k * d + k + k  # centroides + proporciones de mezcla + k varianzas locales
    return -2 * log_verosimilitud + n_parametros * math.log(n)


def elegir_k_y_clusterizar(features: list[FeaturesEstructurales], k_min: int = 2,
                             k_max: int | None = None, semilla: int = 42) -> tuple[list[int], int]:
    """Escala las features, prueba k en [k_min, k_max], elige el k que
    minimiza el BIC aproximado, devuelve (etiquetas_por_unidad, k_elegido).

    Si hay muy pocas unidades para clusterizar razonablemente (menos que
    2*k_min), todas caen en la familia 0 -- evitar clusters degenerados
    de un solo miembro en corpus chicos.

    Nota de calibracion (Checkpoint D): incluso con el BIC corregido
    (varianza local por cluster, ver `_bic_kmeans`), sobre las 2906
    unidades reales del corpus el BIC sigue mejorando muy lentamente
    hasta k~80-100 sin un minimo agudo -- plausible para un corpus
    genuinamente heterogeneo (tablas, prosa densa, slides, listas
    bibliograficas conviven), pero un k de esa magnitud produce
    "familias" de ~30 miembros cada una, demasiado granular para ser una
    agrupacion util (el paper describe "compact empirical neighborhoods",
    no cientos de micro-categorias). Se acota k_max a un techo practico
    explicito en vez de dejar que el BIC elija sin limite: el checkpoint
    humano (inspeccionar 20-30 unidades por familia) es el criterio real
    de aceptacion, no la optimalidad exacta del BIC."""
    n = len(features)
    if n < max(2 * k_min, 4):
        return [0] * n, 1

    matriz = _matriz(features)
    escalador = StandardScaler()
    matriz_escalada = escalador.fit_transform(matriz)

    if k_max is None:
        k_max = min(25, n // 3)
    k_max = max(k_max, k_min)

    mejor_bic = float("inf")
    mejor_etiquetas = None
    mejor_k = k_min
    for k in range(k_min, k_max + 1):
        if k >= n:
            break
        modelo = KMeans(n_clusters=k, random_state=semilla, n_init=10)
        etiquetas = modelo.fit_predict(matriz_escalada)
        bic = _bic_kmeans(matriz_escalada, modelo)
        if bic < mejor_bic:
            mejor_bic = bic
            mejor_etiquetas = etiquetas
            mejor_k = k

    if mejor_etiquetas is None:
        return [0] * n, 1
    return mejor_etiquetas.tolist(), mejor_k
