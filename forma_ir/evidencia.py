# -*- coding: utf-8 -*-
"""
Fase E: vector de evidencia lexica dispersa (paper, S5.4).

r(u,q) = [ b(u,q), c(u,q), x(u,q), a(u,q) ]    (2)

  b: BM25F-style sobre el cuerpo de la unidad + su "ruta ancestral"
     (aqui: el texto del header/regla estructural mas cercano hacia
     atras en el documento, proxy honesto de "ancestro" mientras no
     exista un arbol jerarquico completo -- C4 produce una particion
     PLANA, no un arbol multi-nivel; ver limitacion documentada en el
     modulo).
  c: cobertura de terminos de la consulta ponderada por IDF (formula 3).
  x: compacidad -- cobertura entre 1+log(1+ventana_mas_corta) (formula 4).
  a: evidencia de ancla estructural -- 1.0 si algun termino de la
     consulta aparece dentro de una firma "ancla" (bloque con
     mask_digito/mask_numeral_romano/TODO_MAYUS, es decir con forma de
     encabezado/numeracion) de la propia unidad, 0.0 si no.

Ningun coordinate usa terminos de expansion, embeddings, ni pesos
aprendidos -- exactamente lo que el paper exige para el "core
experiment" (S5.4: "Expansion terms, embeddings, learned weights, and
LLM judgments are excluded from the core experiment").
"""
import math
import re
from collections import Counter
from dataclasses import dataclass

from forma_ir.firma import FirmaForma
from forma_ir.tipos import Bloque, UnidadRetenida

_RE_TOKEN = re.compile(r"\w+", re.UNICODE)


def tokenizar(texto: str) -> list[str]:
    """Tokenizacion lexica simple: minusculas, solo caracteres de
    palabra (incluye acentos/eñe via \\w con re.UNICODE). Sin stemming
    ni stopwords -- el paper no pide ninguno de los dos para el vector
    de evidencia disperso, y agregar cualquiera introduciria una
    decision linguistica no declarada en la formula."""
    return _RE_TOKEN.findall(texto.lower())


# Palabras funcionales de PREGUNTA. No son stopwords del corpus (el corpus
# se sigue indexando entero, sin stemming ni stopwords, tal como pide el
# paper): son marcadores de acto de habla interrogativo que aparecen en la
# CONSULTA del usuario y no en la prosa academica indexada.
#
# Motivo (medido sobre el corpus real): el IDF las considera raras
# precisamente porque el corpus casi no contiene preguntas, asi que
# "cómo" (IDF 5.89) y "qué" (5.77) pesaban MAS que "haciendas" (4.78) o
# "apra" (5.03). Una pregunta de estudiante quedaba dominada por su
# andamiaje interrogativo en vez de por su contenido, y el ranking se iba
# a documentos irrelevantes. Filtrarlas SOLO en la consulta es
# normalizacion lexica, no semantica: no introduce modelos ni embeddings.
_FUNCIONALES_CONSULTA = {
    "que", "qué", "cual", "cuál", "cuales", "cuáles", "quien", "quién",
    "quienes", "quiénes", "como", "cómo", "cuando", "cuándo", "donde",
    "dónde", "cuanto", "cuánto", "cuanta", "cuánta", "cuantos", "cuántos",
    "cuantas", "cuántas", "por", "para", "porque", "por qué", "es", "son",
    "era", "eran", "fue", "fueron", "ser", "sido", "estar", "esta", "está",
    "estan", "están", "hay", "tiene", "tienen", "tener", "tuvo", "tuvieron",
    "hace", "hacen", "hacer", "dice", "dicen", "decir", "dijo",
    "el", "la", "los", "las", "un", "una", "unos", "unas", "lo", "al", "del",
    "de", "en", "y", "o", "a", "con", "sin", "sobre", "entre", "se", "su",
    "sus", "me", "mi", "te", "tu", "nos", "yo", "explicame", "explícame",
    "dime", "cuentame", "cuéntame", "quiero", "saber", "puedes", "podrias",
    "podrías", "favor", "ayuda", "ayudame", "ayúdame",
}


def tokenizar_consulta(texto: str, minimo_tokens: int = 2) -> list[str]:
    """Tokeniza una CONSULTA de usuario descartando palabras funcionales
    interrogativas (ver `_FUNCIONALES_CONSULTA`).

    Si el filtro dejara menos de `minimo_tokens` terminos (ej. la consulta
    "¿qué es?"), devuelve la tokenizacion completa sin filtrar: es
    preferible una consulta ruidosa a una consulta vacia."""
    todos = tokenizar(texto)
    filtrados = [t for t in todos if t not in _FUNCIONALES_CONSULTA]
    return filtrados if len(filtrados) >= minimo_tokens else todos


@dataclass
class VectorEvidencia:
    unidad_id: str
    b: float  # BM25F sobre cuerpo + ruta ancestral
    c: float  # cobertura ponderada por IDF
    x: float  # compacidad
    a: float  # evidencia de ancla estructural


def calcular_idf(corpus_tokens: list[list[str]]) -> dict[str, float]:
    """IDF clasico BM25: log((N - df + 0.5) / (df + 0.5) + 1) sobre el
    corpus de UNIDADES (no de documentos) -- consistente con que la
    unidad, no el documento, es el objeto de indexacion en FORMA-IR."""
    n_docs = len(corpus_tokens)
    df: Counter = Counter()
    for tokens in corpus_tokens:
        for t in set(tokens):
            df[t] += 1
    idf = {}
    for t, freq in df.items():
        idf[t] = math.log((n_docs - freq + 0.5) / (freq + 0.5) + 1)
    return idf


def _bm25f(tokens_query: list[str], tokens_cuerpo: list[str], tokens_ancestro: list[str],
            idf: dict[str, float], longitud_promedio: float,
            k1: float = 1.5, b_cuerpo: float = 0.75, b_ancestro: float = 0.75,
            peso_ancestro: float = 0.3) -> float:
    """BM25F de dos campos (cuerpo, ruta ancestral) con normalizacion de
    longitud independiente por campo -- version BM25F estandar (Robertson
    et al.), pesos de campo fijos y declarados (no aprendidos, consistente
    con R5 del paper: 'no LLM or embedding... training-free core')."""
    if not tokens_query:
        return 0.0
    freq_cuerpo = Counter(tokens_cuerpo)
    freq_ancestro = Counter(tokens_ancestro)
    len_cuerpo = len(tokens_cuerpo)
    len_ancestro = len(tokens_ancestro)

    score = 0.0
    for t in set(tokens_query):
        idf_t = idf.get(t, 0.0)
        if idf_t <= 0:
            continue
        tf_combinado = (
            freq_cuerpo.get(t, 0) / (1 - b_cuerpo + b_cuerpo * (len_cuerpo / max(longitud_promedio, 1e-9)))
            + peso_ancestro * freq_ancestro.get(t, 0) / (1 - b_ancestro + b_ancestro * (len_ancestro / max(longitud_promedio, 1e-9)))
        )
        score += idf_t * (tf_combinado * (k1 + 1)) / (tf_combinado + k1)
    return score


def _cobertura_idf(tokens_query: list[str], tokens_unidad: set[str], idf: dict[str, float]) -> float:
    """Formula (3): c(u,q) = sum(IDF(t) for t in q&u) / sum(IDF(t) for t in q)."""
    terminos_query_unicos = set(tokens_query)
    if not terminos_query_unicos:
        return 0.0
    idf_total = sum(idf.get(t, 0.0) for t in terminos_query_unicos)
    if idf_total <= 0:
        return 0.0
    idf_matcheado = sum(idf.get(t, 0.0) for t in terminos_query_unicos if t in tokens_unidad)
    return idf_matcheado / idf_total


def _ventana_mas_corta(tokens_query: list[str], tokens_unidad: list[str]) -> int | None:
    """Ventana (en tokens) mas corta del texto de la unidad que contiene
    al menos un match de CADA termino distinto de la consulta que
    aparece en la unidad (ventana desordenada, ver S5.4: 'shortest
    ordered or unordered window'; se implementa la version desordenada,
    mas simple y suficiente para el core experiment declarado).
    None si ningun termino de la consulta aparece en la unidad."""
    terminos_relevantes = set(tokens_query) & set(tokens_unidad)
    if not terminos_relevantes:
        return None

    # Ventana deslizante de dos punteros sobre las posiciones donde
    # aparece CUALQUIER termino relevante -- estandar para "smallest
    # window containing all of a set K of distinct keys" en O(n).
    posiciones = [(i, tok) for i, tok in enumerate(tokens_unidad) if tok in terminos_relevantes]
    if not posiciones:
        return None

    conteo_ventana: Counter = Counter()
    izquierda = 0
    mejor = None
    for derecha, (idx_d, tok_d) in enumerate(posiciones):
        conteo_ventana[tok_d] += 1
        while len(conteo_ventana) == len(terminos_relevantes):
            idx_i, tok_i = posiciones[izquierda]
            ancho = idx_d - idx_i + 1
            if mejor is None or ancho < mejor:
                mejor = ancho
            conteo_ventana[tok_i] -= 1
            if conteo_ventana[tok_i] == 0:
                del conteo_ventana[tok_i]
            izquierda += 1
    return mejor


def _compacidad(cobertura: float, ventana: int | None) -> float:
    """Formula (4): x(u,q) = c(u,q) / (1 + log(1 + shortestWindow(u,q)))."""
    if ventana is None:
        return 0.0
    return cobertura / (1 + math.log(1 + ventana))


def _es_bloque_ancla(b: Bloque, firma: FirmaForma) -> bool:
    """Un bloque cuenta como "ancla estructural" si su firma tiene forma
    de encabezado/numeracion observable -- mask_digito, mask_numeral_romano,
    o capitalizacion TODO_MAYUS/Titulo. Ninguna de estas senales usa
    identidad de palabras, solo forma (consistente con S5.1)."""
    return (firma.mask_digito or firma.mask_numeral_romano or firma.mask_prefijo_alfa
            or firma.clase_capitalizacion in ("TODO_MAYUS", "Titulo"))


def _evidencia_ancla(tokens_query: list[str], bloques_unidad: list[Bloque],
                       firmas_unidad: list[FirmaForma]) -> float:
    """a(u,q): 1.0 si algun termino de la consulta aparece dentro de un
    bloque-ancla de la unidad (un encabezado/numeracion dentro de la
    propia unidad coincide lexicamente con la consulta), 0.0 si no."""
    terminos_query = set(tokens_query)
    if not terminos_query:
        return 0.0
    for b, f in zip(bloques_unidad, firmas_unidad):
        if _es_bloque_ancla(b, f):
            if terminos_query & set(tokenizar(b.texto)):
                return 1.0
    return 0.0


def _texto_ancestro(unidad: UnidadRetenida, bloques_doc: list[Bloque],
                      firmas_doc: list[FirmaForma]) -> str:
    """Proxy de 'ruta ancestral' mientras C4 produzca una particion PLANA
    (no un arbol jerarquico multi-nivel): el texto del bloque-ancla mas
    cercano ANTES del inicio de la unidad, en todo el documento -- el
    header/numeracion bajo el cual la unidad conceptualmente cae.

    Limitacion declarada: esto es una aproximacion de un nivel, no la
    ruta ancestral completa que produciria un arbol de segmentacion
    recursivo real (fuera de alcance de esta iteracion de C4, ver
    docstring de forma_ir/mdl.py)."""
    inicio = unidad.indices_bloque[0] if unidad.indices_bloque else 0
    for i in range(inicio - 1, -1, -1):
        if _es_bloque_ancla(bloques_doc[i], firmas_doc[i]):
            return bloques_doc[i].texto
    return ""


def precomputar_unidad(unidad: UnidadRetenida, bloques_doc: list[Bloque],
                         firmas_doc: list[FirmaForma]) -> dict:
    """Precalcula, UNA sola vez por unidad (en tiempo de indexacion),
    todo lo que calcular_vector_evidencia necesita y que NO depende de
    la consulta: tokens del cuerpo, tokens de la ruta ancestral, y los
    conjuntos de tokens de los bloques-ancla de la unidad.

    Optimizacion critica encontrada en produccion: sin esto, cada
    consulta re-tokenizaba el texto de las ~2,900 unidades del corpus y
    re-escaneaba el documento entero hacia atras buscando el ancestro de
    cada unidad (_texto_ancestro es O(bloques_del_documento) por unidad
    -- en el documento mas grande, ~6,million de operaciones por consulta
    solo en ancestros). Todo eso es invariante entre consultas."""
    tokens_cuerpo = tokenizar(unidad.texto)
    tokens_ancestro = tokenizar(_texto_ancestro(unidad, bloques_doc, firmas_doc))
    anclas_tokens = []
    for i in unidad.indices_bloque:
        if _es_bloque_ancla(bloques_doc[i], firmas_doc[i]):
            anclas_tokens.append(set(tokenizar(bloques_doc[i].texto)))
    return {
        "tokens_cuerpo": tokens_cuerpo,
        "set_cuerpo": set(tokens_cuerpo),
        "tokens_ancestro": tokens_ancestro,
        "anclas_tokens": anclas_tokens,
    }


def calcular_vector_evidencia(query: str, unidad: UnidadRetenida, bloques_doc: list[Bloque],
                                firmas_doc: list[FirmaForma], idf: dict[str, float],
                                longitud_promedio_unidad: float,
                                precomputado: dict | None = None) -> VectorEvidencia:
    """`precomputado` (opcional): salida de precomputar_unidad() para esta
    unidad -- evita re-tokenizar y re-escanear ancestros en cada consulta
    (ver docstring de precomputar_unidad). Sin el, el calculo es identico
    pero mas lento (compatibilidad con los llamadores/tests existentes)."""
    # Consulta filtrada de palabras funcionales interrogativas
    # (ver tokenizar_consulta). El CORPUS se sigue tokenizando entero.
    tokens_query = tokenizar_consulta(query)

    if precomputado is not None:
        tokens_cuerpo = precomputado["tokens_cuerpo"]
        set_cuerpo = precomputado["set_cuerpo"]
        tokens_ancestro = precomputado["tokens_ancestro"]
        anclas_tokens = precomputado["anclas_tokens"]
    else:
        tokens_cuerpo = tokenizar(unidad.texto)
        set_cuerpo = set(tokens_cuerpo)
        tokens_ancestro = tokenizar(_texto_ancestro(unidad, bloques_doc, firmas_doc))
        anclas_tokens = [
            set(tokenizar(bloques_doc[i].texto))
            for i in unidad.indices_bloque
            if _es_bloque_ancla(bloques_doc[i], firmas_doc[i])
        ]

    b = _bm25f(tokens_query, tokens_cuerpo, tokens_ancestro, idf, longitud_promedio_unidad)
    c = _cobertura_idf(tokens_query, set_cuerpo, idf)
    ventana = _ventana_mas_corta(tokens_query, tokens_cuerpo)
    x = _compacidad(c, ventana)

    terminos_query = set(tokens_query)
    a = 1.0 if terminos_query and any(terminos_query & at for at in anclas_tokens) else 0.0

    return VectorEvidencia(unidad_id=unidad.unidad_id, b=b, c=c, x=x, a=a)
