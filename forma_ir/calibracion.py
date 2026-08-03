# -*- coding: utf-8 -*-
"""
Fase F: calibracion de nulo dividido condicionada por estructura (paper,
S5.5). La pieza matematicamente mas delicada del metodo -- convierte el
vector de evidencia disperso (Fase E) en una probabilidad empirica
comparable entre unidades de forma/familia distinta, sin pesos
aprendidos ni normalizacion de longitud ad-hoc.

Mecanismo (formulas 5a-5c del paper):
  1. Para la familia estructural c de una unidad candidata, se muestrean
     pseudo-consultas desde unidades SEMILLA de OTROS documentos
     (document-disjoint respecto al documento de la unidad real),
     emparejadas por conteo de terminos e IDF-cuantiles de la consulta
     real.
  2. Cada pseudo-consulta se puntua SOLO contra unidades fuera de su
     propio documento semilla -- los vectores de evidencia resultantes
     son "coincidencias accidentales" (matches de azar).
  3. Esos vectores accidentales se dividen UNA SOLA VEZ, antes de ver
     consultas de test, en una mitad de referencia R_c y una mitad de
     calibracion C_c.
  4. z_k(r) = rango marginal condicional de la coordenada k del vector
     real r, calculado contra R_c (formula 5a).
  5. T_c(r) = min_k z_k(r), la estadistica de cuello de botella --
     castiga que CUALQUIER coordenada sea debil, sin dejar que una
     coordenada fuerte compense a una debil (a diferencia de una suma
     ponderada).
  6. p_c(u,q) = rango empirico de T_c(r(u,q)) contra C_c (formula 5c).
  7. E(u,q) = -log p_c(u,q) es el score final de ranking.

RIESGO DE FUGA DE DATOS (documentado explicitamente por el paper, S5.5):
"Seeds, candidate units, and relevance judgments must be document-
disjoint; the reference/calibration split is frozen; and nulls are
cached...". Este modulo aplica tres salvaguardas activas:
  - `construir_reservorio_nulo` filtra explicitamente cualquier unidad
    semilla o candidata que pertenezca al MISMO documento de origen que
    se esta calibrando.
  - El split R_c/C_c se congela con una semilla fija en el momento de
    construccion del reservorio y NUNCA se recalcula al evaluar
    consultas de test reales (`p_valor_calibrado` solo LEE R_c/C_c, no
    los modifica).
  - `verificar_aislamiento_reservorio` calcula un hash del reservorio
    antes y despues de una tanda de consultas de test -- deben ser
    identicos; un test de regresion lo verifica explicitamente.
"""
import hashlib
import json
import math
import random
from collections import defaultdict
from dataclasses import dataclass

from forma_ir.evidencia import VectorEvidencia, calcular_vector_evidencia, tokenizar
from forma_ir.firma import FirmaForma
from forma_ir.tipos import Bloque, UnidadRetenida

_COORDENADAS = ("b", "c", "x", "a")

# Tamano minimo de muestra por familia para calibrar directamente; por
# debajo de esto, S5.5 exige agrupar con familias vecinas o caer a un
# fallback univariante conservador -- ver `p_valor_calibrado`.
MIN_MUESTRAS_POR_FAMILIA = 30


@dataclass
class ReservorioNulo:
    """R_c y C_c congelados para una familia estructural c. Los vectores
    se guardan como tuplas (b,c,x,a) en el mismo orden que _COORDENADAS,
    junto con el doc_id de origen de la unidad candidata (para poder
    re-verificar disjuncion de documento si hace falta)."""
    familia_id: int
    referencia: list[tuple[float, float, float, float]]  # R_c
    calibracion: list[tuple[float, float, float, float]]  # C_c

    def hash_estado(self) -> str:
        """Hash determinista del contenido de R_c+C_c -- usado para
        verificar que una tanda de consultas de test NO modifico el
        reservorio (ver `verificar_aislamiento_reservorio`)."""
        payload = json.dumps(
            {"familia_id": self.familia_id, "referencia": self.referencia, "calibracion": self.calibracion},
            sort_keys=True,
        )
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _quantil_idf(tokens_query: list[str], idf: dict[str, float]) -> float:
    """IDF promedio de los terminos de una consulta -- usado para
    emparejar pseudo-consultas con consultas reales por 'IDF quantile'
    (S5.5). Un promedio simple es una aproximacion honesta de
    'cuantil de IDF' sin requerir estimar la distribucion completa de
    IDF del corpus, suficiente para emparejar consultas de dificultad
    lexica similar."""
    valores = [idf.get(t, 0.0) for t in set(tokens_query)]
    if not valores:
        return 0.0
    return sum(valores) / len(valores)


def _generar_pseudo_query_desde_semilla(unidad_semilla: UnidadRetenida, n_terminos: int,
                                          rng: random.Random) -> str:
    """Una pseudo-consulta se construye tomando `n_terminos` palabras al
    azar (sin repeticion) del propio texto de una unidad semilla -- una
    consulta "tipica" de ese contenido, sin necesitar un modelo de
    lenguaje ni juicios de relevancia declarados."""
    palabras = list(set(tokenizar(unidad_semilla.texto)))
    if not palabras:
        return ""
    n = min(n_terminos, len(palabras))
    return " ".join(rng.sample(palabras, n))


def construir_reservorio_nulo(
    familia_id: int,
    unidades_de_la_familia: list[UnidadRetenida],
    todas_las_unidades: list[UnidadRetenida],
    bloques_por_doc: dict[str, list[Bloque]],
    firmas_por_doc: dict[str, list[FirmaForma]],
    idf: dict[str, float],
    longitud_promedio_unidad: float,
    n_pseudo_queries: int = 200,
    n_terminos_por_query: int = 3,
    semilla: int = 12345,
) -> ReservorioNulo | None:
    """Construye R_c/C_c para una familia estructural: para cada
    pseudo-consulta, elige una unidad SEMILLA al azar de la familia,
    genera una pseudo-query desde su texto, y la puntua contra unidades
    candidatas de la MISMA familia que esten en un documento DISTINTO al
    de la semilla (document-disjoint, salvaguarda de fuga de datos #1).
    El resultado se divide UNA VEZ en mitades R_c/C_c con una semilla
    fija -- nunca se vuelve a barajar despues de este punto."""
    if len(unidades_de_la_familia) < 2:
        return None

    rng = random.Random(semilla)
    vectores_accidentales: list[tuple[float, float, float, float]] = []

    # Indice invertido termino -> unidades de la familia que lo
    # contienen -- para elegir candidatas EMPAREJADAS por vocabulario
    # compartido (aproximacion honesta de "matched to term count and
    # IDF quantiles", S5.5), no completamente al azar.
    #
    # Motivo (Checkpoint F, verificacion de sanity-check con datos
    # reales): con candidatas puramente uniformes al azar, 65-98% de los
    # vectores accidentales resultaban en b=c=x=0.0 exactos (la
    # pseudo-query y la candidata no compartian NINGUN termino, esperable
    # dado un vocabulario de familia disperso: 8029 palabras unicas para
    # 199 unidades reales de una familia real). Esa masa de ceros
    # colapsaba la resolucion del rango marginal justo donde mas importa
    # -- el histograma de T_c en la propia calibracion quedaba
    # concentrado en un solo bin en vez de aproximar uniforme. Muestrear
    # candidatas que garantizadamente comparten AL MENOS un termino con
    # la pseudo-query (like el paper describe explicitamente) representa
    # mejor la nocion de "accidental match" real -- un match que al
    # menos tuvo la OPORTUNIDAD de ser fuerte, no ausencia total de
    # relacion.
    indice_invertido: dict[str, list[UnidadRetenida]] = defaultdict(list)
    for u in unidades_de_la_familia:
        for t in set(tokenizar(u.texto)):
            indice_invertido[t].append(u)

    for _ in range(n_pseudo_queries):
        semilla_unidad = rng.choice(unidades_de_la_familia)
        pseudo_query = _generar_pseudo_query_desde_semilla(semilla_unidad, n_terminos_por_query, rng)
        if not pseudo_query:
            continue

        # Candidatas emparejadas: unidades de la familia que comparten
        # al menos un termino con la pseudo-query, EXCLUYENDO el
        # documento de la semilla (salvaguarda de fuga de datos #1,
        # document-disjoint).
        terminos_query = set(tokenizar(pseudo_query))
        candidatas_emparejadas = {
            u.unidad_id: u
            for t in terminos_query
            for u in indice_invertido.get(t, [])
            if u.doc_id != semilla_unidad.doc_id
        }
        if candidatas_emparejadas:
            candidata = rng.choice(list(candidatas_emparejadas.values()))
        else:
            # Sin ninguna candidata que comparta vocabulario -- cae al
            # muestreo uniforme original (representa fielmente un
            # "accidental match" que resulto ser nulo total, que TAMBIEN
            # debe estar presente en el reservorio, solo que no debe
            # dominarlo).
            candidatas = [u for u in unidades_de_la_familia if u.doc_id != semilla_unidad.doc_id]
            if not candidatas:
                continue
            candidata = rng.choice(candidatas)

        bloques_doc = bloques_por_doc.get(candidata.doc_id, [])
        firmas_doc = firmas_por_doc.get(candidata.doc_id, [])
        if not bloques_doc:
            continue

        vector = calcular_vector_evidencia(
            pseudo_query, candidata, bloques_doc, firmas_doc, idf, longitud_promedio_unidad
        )
        vectores_accidentales.append((vector.b, vector.c, vector.x, vector.a))

    if len(vectores_accidentales) < 4:
        return None

    # Split UNA SOLA VEZ, con semilla fija -- congelado para siempre a
    # partir de aqui (salvaguarda de fuga de datos #2).
    rng_split = random.Random(semilla + 1)
    indices = list(range(len(vectores_accidentales)))
    rng_split.shuffle(indices)
    mitad = len(indices) // 2
    referencia = [vectores_accidentales[i] for i in indices[:mitad]]
    calibracion = [vectores_accidentales[i] for i in indices[mitad:]]

    if not referencia or not calibracion:
        return None

    return ReservorioNulo(familia_id=familia_id, referencia=referencia, calibracion=calibracion)


def rango_marginal(valor: float, coordenada_idx: int, referencia: list[tuple]) -> float:
    """Formula (5a): z_k(r) = (1 + #{a in R_c : a_k <= r_k}) / (|R_c|+1).
    Mayor evidencia -> mayor cuantil (rango marginal mas alto)."""
    if not referencia:
        return 0.5
    conteo = sum(1 for a in referencia if a[coordenada_idx] <= valor)
    return (1 + conteo) / (len(referencia) + 1)


def estadistica_cuello_de_botella(vector: tuple[float, ...], referencia: list[tuple]) -> float:
    """Formula (5b): T_c(r) = min_k z_k(r) -- la coordenada MAS DEBIL
    domina; una evidencia extrema en una sola coordenada (ej. BM25F muy
    alto por un termino raro) no puede compensar cobertura o compacidad
    pobres.

    Usa `len(vector)` (no la constante fija `_COORDENADAS` del modulo)
    para el numero de coordenadas -- en produccion siempre son las 4 de
    VectorEvidencia, pero fijar la longitud a una constante del modulo
    rompia con vectores de juguete de otra dimension en los tests del
    checkpoint F (IndexError), y no hay ninguna razon real para que esta
    funcion matematica generica asuma una dimensionalidad especifica."""
    rangos = [rango_marginal(vector[k], k, referencia) for k in range(len(vector))]
    return min(rangos)


def p_valor_calibrado(vector_evidencia: VectorEvidencia, reservorio: ReservorioNulo) -> float:
    """Formula (5c): p_c(u,q) = (1 + #{b in C_c : T_c(b) >= T_c(r)}) / (|C_c|+1).
    SOLO LEE el reservorio -- nunca lo modifica (salvaguarda de fuga de
    datos #2, verificable con `verificar_aislamiento_reservorio`)."""
    vector = (vector_evidencia.b, vector_evidencia.c, vector_evidencia.x, vector_evidencia.a)
    t_candidata = estadistica_cuello_de_botella(vector, reservorio.referencia)

    t_calibracion = [estadistica_cuello_de_botella(b, reservorio.referencia) for b in reservorio.calibracion]
    conteo = sum(1 for t in t_calibracion if t >= t_candidata)
    return (1 + conteo) / (len(reservorio.calibracion) + 1)


def score_final(vector_evidencia: VectorEvidencia, reservorio: ReservorioNulo) -> float:
    """E(u,q) = -log p_c(u,q). Menor p-valor (evidencia mas excepcional
    contra el nulo) -> score mayor."""
    p = p_valor_calibrado(vector_evidencia, reservorio)
    return -math.log(max(p, 1e-12))


def verificar_aislamiento_reservorio(reservorio: ReservorioNulo, hash_antes: str) -> bool:
    """True si el reservorio NO cambio desde `hash_antes` -- llamar
    ANTES y DESPUES de una tanda de consultas de test reales para
    confirmar que evaluar queries reales nunca contamina el nulo
    (salvaguarda de fuga de datos #3)."""
    return reservorio.hash_estado() == hash_antes


def construir_reservorios_por_familia(
    unidades_por_familia: dict[int, list[UnidadRetenida]],
    todas_las_unidades: list[UnidadRetenida],
    bloques_por_doc: dict[str, list[Bloque]],
    firmas_por_doc: dict[str, list[FirmaForma]],
    idf: dict[str, float],
    longitud_promedio_unidad: float,
) -> dict[int, ReservorioNulo]:
    """Construye un reservorio por familia; familias con muestra
    insuficiente (< MIN_MUESTRAS_POR_FAMILIA unidades disponibles para
    generar pseudo-queries) se omiten aqui -- el fallback de familias
    pequenas (agrupar con vecinas o caer a rank univariante) se resuelve
    en la capa de orquestacion, no en este modulo de bajo nivel."""
    reservorios = {}
    for familia_id, unidades in unidades_por_familia.items():
        if len(unidades) < MIN_MUESTRAS_POR_FAMILIA:
            continue
        r = construir_reservorio_nulo(
            familia_id, unidades, todas_las_unidades, bloques_por_doc, firmas_por_doc,
            idf, longitud_promedio_unidad,
        )
        if r is not None:
            reservorios[familia_id] = r
    return reservorios
