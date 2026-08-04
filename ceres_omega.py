# -*- coding: utf-8 -*-
"""
CERES-Omega - motor de recuperacion abierta y verificable

Implementacion del manuscrito CERES-Omega (Delgado Santana, v3.0, 2026) sobre
el corpus del curso Historia Critica del Peru.

    carpeta_documentos/CERES_OMEGA_motor_recuperacion_mayor_90 (1).pdf

Reemplaza a FORMA-IR, borrado en c724b66 tras medir que perdia contra BM25
puro en ranking documental (96.5% vs 98.5% Recall@1 sobre 200 consultas
pareadas). Ese resultado es la razon por la que este motor conserva BM25 como
generador de candidatos y no intenta sustituirlo: el paper tambien lo degrada
a "solo generador de candidatos" (seccion 2) en vez de descartarlo.


QUE SE IMPLEMENTA FIEL Y QUE SE SUSTITUYE
-----------------------------------------
El paper (seccion 7) reconoce que el prototipo actual "usa BM25 y TF-IDF/coseno,
persiste el indice en pickle, no cuenta con embeddings semanticos dedicados,
base vectorial ni suite de pruebas" y que por eso "no puede ejecutar CERES-Omega
completo". Este modulo implementa la ARQUITECTURA completa y sustituye los
componentes ENTRENADOS por equivalentes deterministas con el mismo contrato.
Ninguna sustitucion es silenciosa:

  Etapa del paper          Aqui                             Fidelidad
  ---------------------------------------------------------------------------
  4.1 Ingesta multigranular  bloques del indice + oraciones   parcial: los
                             como atomos citables             atomos se derivan
                                                              en consulta, no
                                                              hay provenance.db
  4.2 Compilador de req.     DAG por analisis lexico de la    fiel en contrato,
                             pregunta (entidades, foco,       heuristico en la
                             restricciones temporales)        extraccion
  4.3 Frontera alta cobert.  BM25F + TF-IDF/coseno + titulo   fiel: RRF sobre
                             + entidad + estructura, con RRF  rankings, sin
                                                              mezclar escalas
  4.4 Multi-puente           haz de estados con B puentes,    fiel
                             consultas condicionadas
  4.5 Compatibilidad conj.   ParaSet -> scorer lexico de      SUSTITUIDO: sin
                             conjunto (cobertura, redundancia checkpoints no hay
                             diversidad, autoridad)           cross-encoder
  4.6 Recuperacion residual  consulta que resta lo cubierto   fiel
  4.7 Lector atomico         seleccion de oraciones por       SUSTITUIDO: el
                             cobertura de requisito           paper pide DeBERTa
                                                              supervisado
  4.8 Verificador            suficiencia por requisito,       fiel en estructura
                             ANSWER/PARTIAL/INSUFFICIENT      (sin calibracion)
  5   Politica monotonica    la frontera F nunca se destruye  fiel
                             al optimizar la prueba E

Consecuencia honesta: este motor NO puede reclamar el >90% del titulo del
paper. Ese numero se deriva de R@5 publicado por BridgeRAG con un LLM de 70B y
un embedding de 7B (seccion 10, amenazas a la validez). Lo que si se implementa
es el contrato que hace la afirmacion FALSABLE: completitud estricta por
requisito, procedencia por atomo y abstencion explicita. Medirlo requiere el
banco de evaluacion anotado que se borro junto con FORMA-IR.


CONTRATO DE SALIDA
------------------
recuperar() devuelve el mismo dict que consumian agente.py y servidor.py
(paquetes / plan / avisos), mas el bloque "ceres" con el contrato del
Apendice A del paper: decision, requirements, evidence, unmet_requirements,
coverage. Lo primero mantiene la web viva; lo segundo es lo que permite
auditar el motor.


QUE SE MIDIO Y QUE NO
---------------------
Medido (04-08-2026, corpus de 1.310 bloques / 39 documentos):

  - Gate de alcance: 33/34 preguntas etiquetadas a mano (22 del temario real,
    12 ajenas). 0 falsos negativos, 1 falso positivo ("cual es la capital de
    Francia", que devuelve PARTIAL, no ANSWER). Umbral 0.50 elegido por
    barrido; la curva completa esta en fuera_de_alcance().
  - Latencia: 0,03-0,3 s por consulta en caliente; 3,4 s la primera (carga
    del indice). Antes de cachear tokens por bloque llegaba a 12,7 s.
  - Multi-puente: los 5 puentes producen expansiones distintas (verificado
    sobre la pregunta de colapso demografico), no cinco copias del mismo
    ranking.
  - Camino completo servidor -> LLM -> verificacion de citas: responde 200
    con citas validas.

NO medido, y por tanto no afirmado:

  - Completitud estricta >=90% (META A del paper). Requiere el banco anotado
    document-disjoint de la seccion 8.3, que se borro con FORMA-IR.
  - Completitud atomica exacta (META B). Requiere el lector supervisado.
  - Comparacion contra BM25 puro como baseline. Sin banco, no hay forma de
    saber si este motor mejora o empeora el ranking anterior.

Reconstruir ese banco es el siguiente paso obligatorio: sin el, "funciona
bien" es una impresion, no un resultado.
"""
import math
import re
from collections import defaultdict

import numpy as np

from texto_util import STOP, normtxt, tokenizar

# ---------------------------------------------------------------------------
# Seccion 12 del paper: configuracion recomendada de primera implementacion.
# Los valores del paper estan pensados para 2Wiki (6.119 pasajes). Este corpus
# tiene 1.310 bloques, ~5x menos, y las cantidades de frontera se reducen en
# proporcion para no arrastrar el corpus entero a cada consulta.
# ---------------------------------------------------------------------------
FRONTERA_LEXICA = 40      # paper: top 40 lexical
FRONTERA_DENSA = 40       # paper: top 40 dense (aqui TF-IDF/coseno)
FRONTERA_ESTRUCTURA = 20  # paper: top 20 estructura
PUENTES = 5               # paper: B = 5
POOL_POR_ESTADO = 20      # paper: 20 candidatos por estado
BEAM = 12                 # paper: 8-16 con diversidad por cadena
RONDAS_MAX = 3            # paper: 3 rondas antes de abstenerse

# Presupuesto de evidencia en tokens. No viene del paper: viene de la economia
# del proyecto -- el corpus entero son 738k tokens y mandarlo completo a la API
# en cada consulta es exactamente el coste que este motor existe para evitar.
PRESUPUESTO = {
    "puntual": 3500,     # una fecha, un dato: poca evidencia bien elegida
    "conceptual": 9000,  # un proceso historico: varias fuentes
    "amplia": 14000,     # resumir una semana o unidad
}

# Cupo por documento. Klaren (146k tokens) y Aldana-Pereyra (99k) son el 33%
# del corpus; sin cupo, cualquier busqueda por similitud devuelve fragmentos
# suyos solo por tamano. El README lo documenta como hecho de diseno.
CUPO_POR_DOC = 3

# Umbrales de la senal semantica en el gate de alcance, medidos sobre el
# banco de 77 preguntas con pruebas/calibrar_semantico.py (indice de Cohere
# embed-v4.0, 1024 dim). Distribucion observada:
#
#     preguntas del curso   mediana 0.525   min 0.298   max 0.725
#     preguntas ajenas      mediana 0.291   min 0.169   max 0.495
#
# Las dos nubes se solapan entre 0.30 y 0.50, asi que ningun umbral unico
# separa bien. De ahi los dos cortes: fuera de la zona de solape decide la
# semantica sola; dentro de ella decide la senal lexica, que es justo donde
# esta es fiable (preguntas administrativas, autores, filtros de semana).
#
#   >= ALTA  el corpus trata el tema sin duda -> aceptar
#   <  BAJA  no lo trata -> rechazar
#   en medio -> lo decide el puntaje lexico
#
# ALTA = 0.51: por encima no se cuela ninguna ajena del banco.
# BAJA = 0.30: por debajo no cae ninguna del curso (la mas baja es 0.298,
#              "¿Que se ve en la semana 13?", que ademas entra por la ruta
#              estructural y no llega hasta aqui).
UMBRAL_SIM_ALTA = 0.51
UMBRAL_SIM_BAJA = 0.30

# Minimo lexico exigido DENTRO de la zona gris semantica (0.30-0.51), donde
# ninguna de las dos senales decide sola. Curva medida sobre las 27 preguntas
# del banco que caen en esa franja (13 del curso, 14 ajenas):
#
#     umbral   pierde del curso   cuela ajenas
#       1.0          1/13             6/14
#       1.1          3/13             4/14
#       1.4          4/13             1/14
#       1.6          7/13             0/14
#
# No hay corte limpio: "¿Quien fue Tupac Amaru II?" (ajena) puntua 1.39 y
# "¿Que dice Klaren sobre el APRA?" (del curso) puntua 1.93 -- las nubes se
# solapan de verdad.
#
# Medido de extremo a extremo sobre el banco completo:
#
#     umbral   responde del curso   rechaza ajenas   global
#       1.0         49/49 (100%)      23/28 (82%)     93,5%
#       1.2         47/49  (96%)      26/28 (93%)     94,8%
#       1.4         47/49  (96%)      28/28 (100%)    97,4%   <- elegido
#
# 1.2 es estrictamente peor que 1.4: pierde las mismas dos preguntas del
# curso y ademas deja pasar dos ajenas.
#
# Con 1.4 el coste son dos preguntas reales -- "¿Por que varian tanto las
# cifras de poblacion prehispanica?" y "¿Como se relacionan independencia,
# sociedad y fiscalidad?" -- a cambio de cerrar por completo la puerta a la
# historia peruana que el curso no cubre. Se acepta porque ese era el fallo
# que hacia al agente inventar: devolvia diez fragmentos sobre ferrocarriles
# para una pregunta sobre Sendero Luminoso.
UMBRAL_ZONA_GRIS = 1.4


# ===========================================================================
# 4.2  COMPILADOR DE REQUISITOS
# ===========================================================================

# Marcas lexicas del tipo de consulta. El paper compila la pregunta a un DAG
# de proposiciones verificables; sin un parser semantico entrenado, el tipo se
# infiere de la forma de la pregunta y determina cuantos requisitos se abren.
_CAUSAL = ("por que", "porque", "causa", "causas", "origen", "origino", "debido",
           "explica", "explicar", "razon", "razones", "consecuencia", "consecuencias",
           "influyo", "provoco", "genero", "llevo a", "resulto")
_COMPARA = ("compara", "comparar", "diferencia", "diferencias", "frente a", "versus",
            "contraste", "contrastar", "distingue", "mientras que", "en cambio",
            "desacuerdo", "discrepan", "ambos", "las dos", "los dos")
_AMPLIA = ("resume", "resumir", "resumen", "panorama", "vision general", "que cubre",
           "que se ve", "temas de", "sintesis", "repasar", "todo lo que")
_PUNTUAL = ("cuando", "que dia", "que fecha", "cuanto", "cuantos", "cuantas",
            "quien", "quienes", "donde", "cual es la fecha", "a que hora")

# Consultas administrativas: el silabo y el cronograma mandan sobre estas, no
# las lecturas academicas (NUCLEO 2, operacion AUTORIDAD en agente.py).
_ADMIN = ("examen", "parcial", "final", "nota", "notas", "calificacion", "entrega",
          "plazo", "cronograma", "silabo", "syllabus", "evaluacion", "rubrica",
          "peso", "asistencia", "horario", "clase", "sesion", "semana", "fecha",
          "creditos", "credito", "profesor", "docente", "seccion", "curso",
          "requisito", "requisitos", "bibliografia", "trabajo", "practica",
          "control", "lectura obligatoria", "sumilla", "competencias")

_SEMANA_RE = re.compile(r"\bsemanas?\s+(\d{1,2})\b")
_UNIDAD_RE = re.compile(r"\bunidad\s+(\d{1,2})\b")

# Vocabulario que delata una explicacion causal DENTRO de la evidencia. Un
# requisito causal no se demuestra porque el bloque repita las palabras de la
# pregunta, sino porque enuncia un mecanismo. Sin esta distincion r1 y r2
# miden lo mismo y un solo bloque cierra la busqueda en la primera ronda.
_MARCAS_CAUSALES = ["causa", "causas", "causo", "provoco", "genero", "origino",
                    "debido", "consecuencia", "consecuencias", "resulto",
                    "produjo", "explica", "razon", "factor", "factores",
                    "efecto", "efectos", "impacto", "llevo", "condujo",
                    "derivo", "influyo", "determino", "por tanto", "asi",
                    "mientras", "permitio", "favorecio", "agravo"]

# Terminos de la pregunta que no aportan a la recuperacion pero sobreviven a
# tokenizar() porque miden mas de 2 caracteres.
_VACIOS = {"que", "cual", "cuales", "como", "donde", "cuando", "quien", "quienes",
           "cuanto", "cuantos", "cuanta", "cuantas", "porque", "para",
           "dice", "dicen", "sobre", "acerca", "segun", "curso", "material",
           "materiales", "lectura", "lecturas", "texto", "textos", "autor",
           "autores", "explica", "explicar", "resume", "resumir", "significa",
           "significo", "hay", "tiene", "puede", "debe", "seria", "fueron"}


def _entidades(pregunta):
    """Terminos de contenido de la pregunta, en orden de aparicion.

    Sustituye al extractor de entidades del paper (4.4). Un NER entrenado
    distinguiria persona/lugar/obra; aqui solo se filtra el vocabulario
    funcional, que es lo que necesita la expansion por entidad.
    """
    vistos, out = set(), []
    for t in tokenizar(pregunta):
        if t in _VACIOS or t in vistos:
            continue
        vistos.add(t)
        out.append(t)
    return out


def _capitalizadas(pregunta):
    """Nombres propios probables: capitalizadas que no son vocabulario comun.

    Senal barata de entidad nombrada (Contreras, Klaren, Lima, Tupac Amaru)
    que el tokenizador pierde al pasar todo a minusculas.

    No basta con descartar la primera palabra: "Por que colapso..." empieza
    con mayuscula y "Por" no es una entidad. Se filtra por vocabulario
    (stopwords + terminos funcionales), que es lo que distingue "Por" de
    "Contreras" independientemente de la posicion.
    """
    palabras = re.findall(r"\b[A-ZÁÉÍÓÚÑ][a-záéíóúñ]{2,}\b", pregunta)
    out, vistos = [], set()
    for w in palabras:
        n = normtxt(w)
        if n in STOP or n in _VACIOS or n in vistos:
            continue
        vistos.add(n)
        out.append(n)
    return out


def compilar_requisitos(pregunta, idx):
    """4.2 - Convierte la consulta en un DAG de requisitos verificables.

    Cada requisito es una proposicion que la evidencia debe demostrar. El DAG
    real del paper tiene dependencias entre nodos (r2 necesita la variable que
    resuelve r1); aqui las dependencias se expresan como orden: los requisitos
    de puente se resuelven antes que los de detalle.

    Devuelve (requisitos, plan). El plan conserva la forma que ya esperaban
    agente.py y servidor.py.
    """
    low = normtxt(pregunta)

    # Texto normalizado para comparar por FRASE, con la puntuacion convertida
    # en espacios y un espacio guarda a cada lado. Asi "cuando" se detecta
    # igual en "Cuando es el examen" que en "¿Cuando es el examen?": las
    # preguntas reales del frontend llegan con "¿", y con startswith() se
    # clasificaban como conceptual, devolviendo 15 fragmentos de contexto
    # para una pregunta que se responde con la fila del cronograma.
    plano = " " + re.sub(r"[^a-z0-9]+", " ", low).strip() + " "

    def _tiene(frases):
        return any(f" {f} " in plano for f in frases)

    ents = _entidades(pregunta)
    propios = _capitalizadas(pregunta)

    # --- tipo de consulta ---
    if _tiene(_AMPLIA):
        tipo = "amplia"
    elif _tiene(_CAUSAL):
        tipo = "conceptual"
    elif _tiene(_COMPARA):
        tipo = "conceptual"
    elif _tiene(_PUNTUAL):
        tipo = "puntual"
    else:
        tipo = "conceptual"

    # --- filtros estructurales explicitos ---
    filtros = {}
    m = _SEMANA_RE.search(low)
    if m:
        s = int(m.group(1))
        if s in idx["por_semana"]:
            filtros["semana"] = s
    m = _UNIDAD_RE.search(low)
    if m:
        u = int(m.group(1))
        if u in idx["por_unidad"]:
            filtros["unidad"] = u

    es_admin = _tiene(_ADMIN)

    # --- construccion del DAG ---
    reqs = []

    # Cuando la pregunta se ancla a una semana o unidad ("que se ve en la
    # semana 13"), los terminos utiles no estan en la pregunta sino en el
    # TEMA de esa semana, que el indice ya conoce. Sin esto el requisito se
    # queda con ["semana"] y ningun bloque puede satisfacerlo.
    terminos_estructura = []
    if "semana" in filtros:
        for i in idx["por_semana"].get(filtros["semana"], [])[:1]:
            doc = idx["docs"].get(idx["bloques"][i]["doc_id"], {})
            terminos_estructura = [t for t in tokenizar(doc.get("semana_tema") or "")
                                   if t not in _VACIOS][:6]
    if "unidad" in filtros and not terminos_estructura:
        for i in idx["por_unidad"].get(filtros["unidad"], [])[:1]:
            doc = idx["docs"].get(idx["bloques"][i]["doc_id"], {})
            terminos_estructura = [t for t in tokenizar(doc.get("unidad_nombre") or "")
                                   if t not in _VACIOS][:6]

    # r1: nucleo tematico. Siempre existe: es la proposicion que la pregunta
    # pide demostrar directamente.
    terms_r1 = [t for t in (ents[:8] or tokenizar(pregunta)[:8])
                if t not in ("semana", "unidad")]
    terms_r1 = terms_r1 + [t for t in terminos_estructura if t not in terms_r1]

    reqs.append({
        "id": "r1",
        "proposition": f"evidencia directa sobre: {pregunta.strip()}",
        "mandatory": True,
        "terms": terms_r1[:8] or tokenizar(pregunta)[:8],
        "entities": propios,
        "kind": "nucleo",
        "accepted_evidence_types": ["rector", "evaluacion"] if es_admin else
                                   ["lectura", "clase", "rector", "evaluacion", "guion"],
        "acceptance_test": "al menos un atomo cubre los terminos centrales de la pregunta",
        "status": "MISSING",
        "support_ids": [],
        "dependencies": [],
    })

    # r2: mecanismo causal. Solo en preguntas de "por que": el paper (4.4)
    # abre un requisito por salto, y una pregunta causal tiene dos -- el hecho
    # y su explicacion.
    #
    # Sus terminos NO son los de r1. Si lo fueran, r1 y r2 medirian lo mismo y
    # un solo bloque cerraria ambos, que es como el motor se detenia en la
    # primera ronda dando un unico paquete. Un requisito causal se satisface
    # con vocabulario causal presente EN LA EVIDENCIA, no en la pregunta.
    if _tiene(_CAUSAL):
        reqs.append({
            "id": "r2",
            "proposition": "explicacion causal o mecanismo que conecta los terminos de la pregunta",
            "mandatory": True,
            "terms": ents[:6],
            "marker_terms": _MARCAS_CAUSALES,
            "entities": propios,
            "kind": "causal",
            "accepted_evidence_types": ["lectura", "clase"],
            "acceptance_test": "un atomo enuncia causa, consecuencia o condicion",
            "status": "MISSING",
            "support_ids": [],
            "dependencies": ["r1"],
        })

    # r3: segunda postura. En preguntas comparativas y en las causales, el
    # NUCLEO 2 del agente (operacion DESACUERDO) exige exponer ambas posturas.
    # Es un requisito de cobertura, no de existencia: no se abstiene si falta.
    if _tiene(_COMPARA) or tipo == "conceptual":
        reqs.append({
            "id": "r3",
            "proposition": "una segunda fuente independiente que confirme o tensione r1",
            "mandatory": False,
            "terms": ents[:6],
            "entities": propios,
            "kind": "contraste",
            "accepted_evidence_types": ["lectura", "clase"],
            "acceptance_test": "un atomo de un documento distinto al de r1 cubre el mismo tema",
            "status": "MISSING",
            "support_ids": [],
            "dependencies": ["r1"],
        })

    plan = {
        "tipo": tipo,
        "presupuesto": PRESUPUESTO[tipo],
        "filtros": filtros,
        "tokens_usados": 0,
        "admin": es_admin,
        "entidades": propios,
    }
    return reqs, plan


# ===========================================================================
# 4.3  FRONTERA DE ALTA COBERTURA
# ===========================================================================

def _rrf(rankings, k=60):
    """Reciprocal Rank Fusion (4.3).

    El paper es explicito: "evitando mezclar directamente escalas
    incompatibles". BM25 devuelve scores no acotados y el coseno TF-IDF vive
    en [0,1]; sumarlos daria el peso a BM25 por escala, no por calidad. RRF
    fusiona por POSICION, que es comparable entre rankings.
    """
    acc = defaultdict(float)
    for ranking in rankings:
        for pos, i in enumerate(ranking):
            acc[i] += 1.0 / (k + pos + 1)
    return acc


def _ranking_bm25(idx, terms, n):
    if not terms:
        return []
    s = idx["bm25"].get_scores(terms)
    return [int(i) for i in np.argsort(-s)[:n] if s[i] > 0]


def _ranking_denso(idx, texto, n):
    """La senal DENSA del paper (4.3).

    Usa embeddings cuando estan disponibles (corpus/embeddings.npz + clave de
    API) y cae a TF-IDF/coseno cuando no. La diferencia importa: TF-IDF sigue
    contando palabras, asi que no reconoce que "viruela" y "sarampion"
    responden a una pregunta sobre "epidemias". Los embeddings si.

    El fallback no es decorativo: si Render se queda sin cuota de embeddings
    a mitad de una clase, el motor sigue respondiendo con las senales
    lexicas en vez de caerse.
    """
    import semantico
    # Se embebe SIEMPRE la pregunta original del estudiante, nunca los
    # terminos residuales de un requisito. Motivo medido: el haz llama a esta
    # funcion una vez por requisito y por ronda, con un texto distinto cada
    # vez, asi que el cache no servia de nada y cada consulta acababa
    # haciendo 5-10 llamadas de embedding. El p95 subio de 187 ms a 7,8 s.
    #
    # Ademas de barato, es mas correcto: la similitud semantica de "colapso
    # demografico causa provoco" (terminos residuales sueltos) es ruido; la
    # de la pregunta completa es la senal que se quiere.
    sims = semantico.similitudes(idx.get("_ceres_consulta") or texto, idx)
    if sims is not None:
        # Umbral deliberadamente bajo: la frontera busca COBERTURA, no
        # precision (4.3) -- lo que sobre lo poda el scorer de conjuntos
        # despues, y lo que se pierda aqui ya no se puede recuperar. Con
        # Cohere las similitudes viven en un rango mas bajo que con Gemini
        # (la mediana de una pregunta valida es 0.525), asi que 0.20 deja
        # entrar el material relacionado sin arrastrar el corpus entero.
        return [int(i) for i in np.argsort(-sims)[:n] if sims[i] > 0.20]

    v = idx["tfidf"].transform([texto])
    sims = (idx["M"] @ v.T).toarray().ravel()
    return [int(i) for i in np.argsort(-sims)[:n] if sims[i] > 0]


def _ranking_titulo(idx, terms):
    """BM25F sobre el campo titulo/contexto: los bloques llevan _ctx con
    titulo del documento, tema de la semana y nombre de unidad."""
    if not terms:
        return []
    cache = idx.get("_ceres_ctx")
    if cache is None:
        cache = [set(tokenizar(b.get("_ctx", ""))) for b in idx["bloques"]]
        idx["_ceres_ctx"] = cache
    ts = set(terms)
    marcados = []
    for i, ctx in enumerate(cache):
        golpes = len(ts & ctx)
        if golpes:
            marcados.append((golpes, i))
    marcados.sort(key=lambda x: -x[0])
    return [i for _, i in marcados]


def _ranking_entidad(idx, propios):
    """Expansion por entidad (4.4). Busca los nombres propios de la pregunta
    en el texto del bloque y en la autoria del documento.

    Dos precauciones aprendidas midiendo sobre este corpus:

    1. Coincidencia por TOKEN, no por substring. Con substring, "contreras"
       casaba con el cronograma (que lo lista como lectura programada) igual
       que con el capitulo de Contreras. El cronograma ganaba por tener el
       nombre repetido en una tabla de sesiones.
    2. La autoria pesa mas que la mencion. Si el estudiante pregunta "que
       dice Contreras", el documento ESCRITO por Contreras es la fuente, no
       el que lo cita de pasada.
    """
    if not propios:
        return []
    props = set(propios)
    toks_bloques = _tokens_bloques(idx)

    # Tokens de autoria por documento, cacheados: el diccionario de docs no
    # cambia durante la vida del proceso.
    autor_cache = idx.get("_ceres_autores")
    if autor_cache is None:
        autor_cache = {}
        for doc_id, d in idx["docs"].items():
            autores = normtxt(" ".join(d.get("autores") or []))
            autor_cache[doc_id] = set(re.findall(r"[a-z0-9]+", autores))
        idx["_ceres_autores"] = autor_cache

    marcados = []
    for i, b in enumerate(idx["bloques"]):
        golpes = len(props & toks_bloques[i])
        es_autor = len(props & autor_cache.get(b["doc_id"], set()))

        if golpes or es_autor:
            # La autoria domina: pesa mas que cualquier cantidad de menciones.
            marcados.append((es_autor * 10 + golpes, i))
    marcados.sort(key=lambda x: -x[0])
    return [i for _, i in marcados]


def _ranking_estructura(idx, filtros, admin):
    """Senal estructural: semana/unidad pedidas explicitamente, o documentos
    normativos cuando la consulta es administrativa."""
    out = []
    if "semana" in filtros:
        out += idx["por_semana"].get(filtros["semana"], [])
    if "unidad" in filtros:
        out += idx["por_unidad"].get(filtros["unidad"], [])
    if admin:
        out += idx["por_tipo"].get("rector", [])
        out += idx["por_tipo"].get("evaluacion", [])
    vistos, uniq = set(), []
    for i in out:
        if i not in vistos:
            vistos.add(i)
            uniq.append(i)
    return uniq


def frontera(pregunta, req, idx, plan):
    """4.3 - F(r) = UnionTopN{BM25F, Dense, Title, Entity, Structure}

    "La frontera debe evaluarse con Recall de evidencia y no con precision.
    La precision se recupera despues; una evidencia perdida en esta etapa no
    puede ser inventada por el generador."

    Devuelve dict {indice_bloque: score_rrf}. No se filtra ni se poda: eso lo
    hace el scorer de conjuntos, despues, sin destruir F (politica monotonica,
    seccion 5).
    """
    terms = req["terms"]
    texto_q = pregunta if req["kind"] == "nucleo" else " ".join(terms)

    rankings = [
        _ranking_bm25(idx, terms, FRONTERA_LEXICA),
        _ranking_denso(idx, texto_q, FRONTERA_DENSA),
        _ranking_titulo(idx, terms)[:FRONTERA_ESTRUCTURA],
        _ranking_entidad(idx, req["entities"])[:FRONTERA_ESTRUCTURA],
        _ranking_estructura(idx, plan["filtros"], plan["admin"])[:FRONTERA_ESTRUCTURA],
    ]
    fused = _rrf([r for r in rankings if r])

    # Filtro estructural duro: si el estudiante pidio la semana 2, un bloque
    # de la semana 9 no es evidencia aunque puntue alto. Se aplica aqui y no
    # antes para que el filtro no vacie la frontera cuando no hay nada en esa
    # semana -- en ese caso se conserva F completa y se avisa.
    if plan["filtros"]:
        permitidos = set(_ranking_estructura(idx, plan["filtros"], False))
        if permitidos:
            filtrado = {i: s for i, s in fused.items() if i in permitidos}
            if filtrado:
                return filtrado
    return dict(fused)


# ===========================================================================
# 4.5  COMPATIBILIDAD DEL CONJUNTO  (ParaSet sustituido)
# ===========================================================================

def _idf(idx, termino):
    """IDF del termino sobre el corpus, cacheado en el indice en memoria.

    Necesario para que la cobertura mida TEMA y no coincidencia accidental.
    Sin esto, "cual es la receta de la pizza margarita?" obtenia cobertura
    0.667 -- "receta" aparece una vez y "margarita" es un nombre propio en
    textos de historia peruana -- y el motor respondia ANSWER a una pregunta
    que el corpus no cubre. Un termino que sale en 7 de 1310 bloques pesa
    mucho; uno que sale en 400, casi nada.
    """
    cache = idx.setdefault("_ceres_idf", {})
    if termino in cache:
        return cache[termino]
    n = sum(1 for toks in _tokens_bloques(idx) if termino in toks)
    N = len(idx["bloques"])
    cache[termino] = math.log((N + 1) / (n + 1)) + 1.0
    return cache[termino]


def _tokens_bloques(idx):
    """Tokens por bloque, calculados una vez por proceso.

    El indice se carga una sola vez en el servidor (cargar_indice), asi que
    este cache vive lo que vive el worker. Recalcularlo por consulta costaba
    segundos: es la causa principal de las latencias de 12s medidas.
    """
    cache = idx.get("_ceres_toks")
    if cache is None:
        cache = [set(tokenizar(b["texto"])) for b in idx["bloques"]]
        idx["_ceres_toks"] = cache
    return cache


def _cobertura_req(req, bloques_texto, idx=None, estado=None):
    """C_r(E): en que medida la evidencia demuestra el requisito.

    Cada TIPO de requisito tiene su propia prueba de aceptacion, y esa es la
    razon de ser del DAG: si todos midieran presencia de los terminos de la
    pregunta, un solo bloque los cerraria todos y el haz se detendria en la
    primera ronda sin explorar.

      nucleo    -> los terminos de la pregunta aparecen en la evidencia
      causal    -> ademas hay vocabulario de mecanismo (causa, provoco, ...)
      contraste -> hay >=2 documentos distintos cubriendo el tema
    """
    terms = set(req["terms"])
    if not terms:
        return 0.0

    # Union de tokens del conjunto. Cuando el llamador pasa los indices del
    # estado se usa el cache por bloque: re-tokenizar el texto completo de
    # cada candidato en cada expansion del haz era el coste dominante (hasta
    # 12s por consulta antes de este cambio).
    if idx is not None and estado:
        toks = _tokens_bloques(idx)
        presentes = set()
        for i in estado:
            presentes |= toks[i]
    else:
        presentes = set(tokenizar(" ".join(bloques_texto)))

    # Cobertura ponderada por IDF: encontrar "aprismo" demuestra mucho mas que
    # encontrar "poblacion". Sin ponderar, dos terminos comunes bastaban para
    # superar el umbral y responder preguntas ajenas al corpus.
    if idx is not None:
        peso_total = sum(_idf(idx, t) for t in terms)
        peso_hit = sum(_idf(idx, t) for t in terms & presentes)
        base = peso_hit / peso_total if peso_total else 0.0
    else:
        base = len(terms & presentes) / len(terms)

    if req["kind"] == "causal":
        marcas = set(req.get("marker_terms", []))
        golpes = len(marcas & presentes)
        # Se exige tema Y mecanismo: el minimo de ambos, para que un bloque
        # lleno de conectores pero ajeno al tema no cierre el requisito.
        mecanismo = min(1.0, golpes / 3.0)
        return min(base, mecanismo)

    if req["kind"] == "contraste":
        if idx is None or not estado:
            return 0.0
        docs = {idx["bloques"][i]["doc_id"] for i in estado}
        # Cubierto solo si el tema aparece y llega de dos documentos distintos.
        return base if len(docs) >= 2 else 0.0

    return base


def _redundancia(idx, estado):
    """Solapamiento lexico medio entre pares del conjunto.

    El paper penaliza redundancia en J(E). Dos bloques casi identicos ocupan
    presupuesto sin anadir cobertura -- caso real en este corpus, donde una
    diapositiva suele parafrasear la lectura de esa semana.
    """
    if len(estado) < 2:
        return 0.0
    toks = _tokens_bloques(idx)
    sets = [toks[i] for i in estado]
    pares, acc = 0, 0.0
    for a in range(len(sets)):
        for b in range(a + 1, len(sets)):
            u = len(sets[a] | sets[b])
            if u:
                acc += len(sets[a] & sets[b]) / u
            pares += 1
    return acc / pares if pares else 0.0


_PESO_AUTORIDAD = {"oficial": 1.15, "academica": 1.0, "docente": 0.92}


def paraset(idx, reqs, estado, frontera_scores):
    """4.5 - Scorer rapido de conjuntos.

    SUSTITUYE al ParaSet entrenado del paper. Este es lexico y deterministico:
    puntua el CONJUNTO, no la suma de sus piezas, que es la propiedad que el
    paper exige ("Retrieving a Set, Not Independent Passages"). Lo que no puede
    hacer sin entrenamiento es detectar incompatibilidad semantica ni
    wrong-bridge; para eso hacen falta los negativos estructurados de 4.5.

    Ordena segun J(E) de la seccion 5, lexicograficamente:
      1. factibilidad (todos los requisitos obligatorios con algo de cobertura)
      2. maximizar el requisito PEOR cubierto  <- impide que una rama excelente
         oculte una rama vacia
      3. cobertura ponderada
      4. precision: menos redundancia, mas diversidad documental
    """
    if not estado:
        return (0, 0.0, 0.0, 0.0)

    textos = [idx["bloques"][i]["texto"] for i in estado]
    cobs = []
    for r in reqs:
        c = _cobertura_req(r, textos, idx, estado)
        if r["mandatory"]:
            cobs.append(c)
    peor = min(cobs) if cobs else 0.0
    media = sum(_cobertura_req(r, textos, idx, estado) for r in reqs) / len(reqs)

    factible = 1 if all(c > 0 for c in cobs) else 0

    docs = {idx["bloques"][i]["doc_id"] for i in estado}
    diversidad = len(docs) / len(estado)
    autoridad = sum(_PESO_AUTORIDAD.get(idx["bloques"][i]["autoridad"], 1.0)
                    for i in estado) / len(estado)
    base = sum(frontera_scores.get(i, 0.0) for i in estado) / len(estado)

    precision = (0.45 * diversidad
                 + 0.30 * autoridad
                 + 0.25 * min(base * 60, 1.0)
                 - 0.40 * _redundancia(idx, estado))

    return (factible, round(peor, 4), round(media, 4), round(precision, 4))


def set_ce(idx, reqs, estado, frontera_scores, plan):
    """4.5 - Reranker final sobre los finalistas.

    SUSTITUYE al cross-encoder SetCE. Anade a ParaSet dos senales que solo
    tienen sentido al final, cuando el conjunto ya es pequeno:
      - contigüidad: bloques vecinos del mismo documento leen mejor que
        fragmentos sueltos (usa idx["vecinos"], relacion objetiva del indice)
      - ajuste al presupuesto: un conjunto que se pasa de tokens sera podado,
        y podar es perder evidencia
    """
    factible, peor, media, precision = paraset(idx, reqs, estado, frontera_scores)

    contiguos = 0
    conj = set(estado)
    for i in estado:
        v = idx["vecinos"].get(i, {})
        if v.get("siguiente") in conj or v.get("anterior") in conj:
            contiguos += 1
    bono_cont = 0.12 * (contiguos / len(estado)) if estado else 0.0

    tokens = sum(int(idx["bloques"][i]["tokens"]) for i in estado)
    exceso = max(0.0, (tokens - plan["presupuesto"]) / max(plan["presupuesto"], 1))
    castigo = 0.35 * min(exceso, 1.0)

    return (factible, peor, media, round(precision + bono_cont - castigo, 4))


# ===========================================================================
# 4.6  RECUPERACION RESIDUAL
# ===========================================================================

def consulta_residual(pregunta, req, estado, idx):
    """4.6 - "La nueva consulta resta semanticamente lo ya cubierto y busca
    solo la informacion residual."

    Devuelve los terminos del requisito que la evidencia actual NO cubre. Sin
    esto, cada ronda vuelve a recuperar el mismo bloque prominente -- el
    "lost-in-retrieval" de la referencia [4].
    """
    if not estado:
        return req["terms"]
    cubierto = set()
    for i in estado:
        cubierto |= set(tokenizar(idx["bloques"][i]["texto"]))

    # Un requisito causal sin cubrir no se arregla repitiendo el tema (ya
    # esta cubierto por r1): lo que falta es el mecanismo. La consulta
    # residual busca tema + vocabulario causal, que es la "pieza faltante"
    # de 4.6 en vez de la pregunta original.
    if req["kind"] == "causal":
        marcas = [m for m in req.get("marker_terms", []) if m not in cubierto]
        return req["terms"][:3] + marcas[:6]

    faltantes = [t for t in req["terms"] if t not in cubierto]
    return faltantes or req["terms"]


# ===========================================================================
# 4.4  BUSQUEDA MULTI-PUENTE  +  6. ALGORITMO PRINCIPAL
# ===========================================================================

def _puentes(frontera_scores, estado, b=PUENTES):
    """Selecciona los B mejores puentes no usados todavia.

    "BridgeRAG usa un puente principal. CERES-Omega conserva los B mejores
    puentes para reducir el riesgo de bloqueo temprano."
    """
    cands = sorted((s, i) for i, s in frontera_scores.items() if i not in estado)
    return [i for _, i in cands[::-1][:b]]


def _condicionar(idx, Fr, puente, estado, req):
    """s_bridge(q, r, b, c): utilidad de c para cerrar r dado el puente b.

    Implementa la version estructural del scoring condicionado de 4.4. El
    paper extrae entidades del puente y las inyecta en la consulta del
    siguiente salto; sin NER entrenado, se usan tres relaciones objetivas que
    el indice ya conoce:

      - vecindad: c es el bloque anterior o siguiente del puente (el
        argumento continua ahi, es la senal mas fuerte)
      - mismo documento: c pertenece a la cadena del puente
      - solape lexico con el puente: c comparte vocabulario especifico con
        lo que el puente ya demostro, sin ser una copia

    Devuelve los indices ordenados por utilidad descendente.
    """
    toks = _tokens_bloques(idx)
    b_pu = idx["bloques"][puente]
    doc_pu = b_pu["doc_id"]
    vec = idx["vecinos"].get(puente, {})
    contiguos = {vec.get("anterior"), vec.get("siguiente")} - {None}
    tok_pu = toks[puente]
    terms_req = set(req["terms"])

    puntuados = []
    for c, s in Fr.items():
        if c == puente:
            continue
        bono = 0.0
        if c in contiguos:
            bono += 0.5
        if idx["bloques"][c]["doc_id"] == doc_pu:
            bono += 0.2

        # Solape con el puente: util hasta cierto punto. Un bloque casi
        # identico al puente no aporta evidencia nueva, solo la repite.
        tc = toks[c]
        if tok_pu and tc:
            jac = len(tok_pu & tc) / len(tok_pu | tc)
            bono += 0.3 * jac if jac < 0.6 else -0.3

        # Aporte propio al requisito: lo que el puente NO cubre todavia.
        nuevos = len((terms_req & tc) - tok_pu)
        bono += 0.15 * nuevos

        puntuados.append((s + bono, c))

    puntuados.sort(key=lambda x: -x[0])
    return [c for _s, c in puntuados]


def _verificar(idx, reqs, estado):
    """4.8 - Marca cada requisito como SUPPORTED o MISSING y devuelve los
    obligatorios que siguen abiertos."""
    textos = [idx["bloques"][i]["texto"] for i in estado]
    faltan = []
    for r in reqs:
        c = _cobertura_req(r, textos, idx, estado)
        # Umbral por tipo de requisito. El paper insiste en no fijar 0.5 por
        # defecto (seccion 12) y en calibrar en validacion; sin banco de
        # evaluacion, estos valores son explicitos y revisables, no calibrados.
        umbral = 0.55 if r["kind"] == "nucleo" else 0.40
        r["status"] = "SUPPORTED" if c >= umbral else "MISSING"
        r["coverage"] = round(c, 3)
        if r["status"] == "MISSING" and r["mandatory"]:
            faltan.append(r)
    return faltan


def fuera_de_alcance(pregunta, reqs, idx, plan=None):
    """Decide si el corpus simplemente no trata el tema de la pregunta.

    El paper (4.8) reserva ABSENT para "busquedas exhaustivas bajo un alcance
    explicito" y devuelve INSUFFICIENT cuando se agota la busqueda. Pero sin
    esta comprobacion previa, una pregunta ajena al curso ("la receta de la
    pizza margarita") igual encontraba bloques: "receta" y "margarita"
    aparecen sueltos en textos de historia peruana, y la cobertura por
    terminos daba 0.667 -> ANSWER. El motor afirmaba tener evidencia de algo
    que el corpus no contiene.

    La senal correcta no es cuantos terminos de la pregunta existen en el
    corpus, sino si algun bloque DESARROLLA el tema: densidad de repeticion
    de esos terminos y cuantos bloques buenos hay (ver el detalle mas abajo,
    donde se combinan las dos senales).

    Rutas exentas, que no pasan por el puntaje porque las responde el indice
    estructural y no BM25: consultas con filtro de semana/unidad, consultas
    por un autor del corpus y consultas administrativas con vocabulario del
    silabo.
    """
    # Ancla estructural ("semana 13", "unidad 2"): la responde el indice
    # estructural, no BM25, asi que el gate no aplica.
    if plan and plan.get("filtros"):
        return False, None

    # Peticiones de extraer el producto evaluado. El motor no puede "negarse"
    # -- su trabajo es traer evidencia, y el cronograma es evidencia legitima
    # para una consulta sobre el examen -- pero SI puede no entregar el
    # maximo de contexto a quien pide las respuestas. Quien debe negarse a
    # resolver la tarea es el prompt (seccion TRABAJOS Y EVALUACIONES del
    # NUCLEO en agente.py); esto solo evita alimentar el intento.
    low_p = normtxt(pregunta)
    plano_p = " " + re.sub(r"[^a-z0-9]+", " ", low_p).strip() + " "
    if any(f" {f} " in plano_p for f in (
            "respuestas del examen", "respuestas de la evaluacion",
            "resuelve por mi", "resuelveme", "hazme el trabajo",
            "escribeme el ensayo", "dame las respuestas",
            "haz mi tarea", "resuelve el ejercicio por mi")):
        return True, ("Esta consulta pide el producto de una evaluacion. El agente "
                      "puede ensenar el tema y senalar que lecturas cubren cada "
                      "parte, pero no entrega el trabajo resuelto.")

    terms = reqs[0]["terms"]
    if not terms:
        return True, "La consulta no contiene terminos que buscar."

    # Pregunta por un autor del curso ("que dice Klaren sobre el APRA"): el
    # documento existe y es la fuente. Se comprueba contra la autoria real
    # del indice, no contra una lista fija. Sin esto el gate se abstenia de
    # preguntas sobre lecturas centrales cuando el apellido no puntuaba alto
    # en BM25 -- el nombre del autor casi nunca aparece dentro de su propio
    # texto.
    autor_cache = idx.get("_ceres_autores")
    if autor_cache is None:
        autor_cache = {}
        for doc_id, d in idx["docs"].items():
            a = normtxt(" ".join(d.get("autores") or []))
            autor_cache[doc_id] = set(re.findall(r"[a-z0-9]+", a))
        idx["_ceres_autores"] = autor_cache
    todos_autores = set()
    for s in autor_cache.values():
        todos_autores |= s
    if todos_autores & set(reqs[0].get("entities") or []):
        return False, None

    # Consulta administrativa: SOLO si ademas menciona algo que el silabo o
    # el cronograma pueden responder. "curso" a secas no basta -- con eso,
    # "como hago una pizza para la clase del curso?" pasaba el gate.
    if plan and plan.get("admin"):
        fuertes = ("examen", "parcial", "nota", "notas", "calificacion",
                   "entrega", "plazo", "cronograma", "silabo", "evaluacion",
                   "rubrica", "creditos", "credito", "profesor", "docente",
                   "horario", "asistencia", "sumilla", "bibliografia",
                   "requisito", "requisitos", "seccion", "evalua", "evaluar",
                   "lecturas", "lectura", "unidad", "semana", "temas", "tema")

        # Se busca en el TEXTO de la pregunta, no en los terminos del
        # requisito: palabras como "semana" o "unidad" se filtran de los
        # terminos por ser vocabulario estructural, y con ello "¿en que
        # semana se ve la independencia?" perdia su unica marca
        # administrativa y caia al puntaje general.
        marca_admin = any(f" {f} " in plano_p for f in fuertes)

        # Pero mencionar "examen" no convierte en administrativa a cualquier
        # consulta: "cual es la mejor manera de estudiar para un examen?" es
        # una peticion de tecnica de estudio, no del calendario del curso.
        # Se exige que la pregunta pida un DATO del curso, no un consejo.
        pide_consejo = any(f" {f} " in plano_p for f in (
            "mejor manera", "como estudiar", "consejos", "recomiendas",
            "recomiendame", "tips", "como memorizar", "como aprender"))

        if marca_admin and not pide_consejo:
            return False, None

    # 1. Terminos que el corpus no conoce en absoluto.
    toks = _tokens_bloques(idx)
    desconocidos = []
    for t in terms:
        if not any(t in s for s in toks):
            desconocidos.append(t)
    if len(desconocidos) >= max(2, len(terms) - 1):
        return True, (f"El material del curso no menciona: "
                      f"{', '.join(desconocidos[:4])}.")

    # 2. Concentracion: los terminos DISTINTIVOS de la pregunta deben
    #    aparecer juntos en algun bloque.
    #
    #    La magnitud de BM25 no sirve para decidir esto. Medido sobre este
    #    corpus, "quien gano el mundial de futbol 2022?" obtiene 11.98 y
    #    "por que colapso la poblacion andina en el siglo XVI?" obtiene
    #    12.14: indistinguibles. La razon es que "mundial" aparece en 77
    #    bloques (guerra mundial, sistema mundial) y "2022" en 28 (anios de
    #    publicacion), asi que el score sube por coincidencias accidentales
    #    de terminos frecuentes.
    #
    #    Lo que si distingue es la CO-OCURRENCIA de los terminos raros: en
    #    una pregunta que el corpus cubre, sus terminos especificos caen
    #    juntos en el mismo bloque. En una ajena, cada uno aparece por su
    #    lado en documentos sin relacion.
    toks_b = _tokens_bloques(idx)

    # 2. ¿El corpus TRATA el tema, o solo contiene sus palabras?
    #
    #    La version anterior de este gate medía la fraccion IDF de terminos
    #    que algun bloque concentraba. No funcionaba, y el banco de 77
    #    preguntas lo dejo claro: rechazaba 0 de 8 preguntas de historia
    #    peruana ajenas al temario.
    #
    #        "reforma agraria 1969"       frac = 1.000   (FUERA del corpus)
    #        "colapso poblacion andina"   frac = 1.000   (del curso)
    #
    #    Ningun umbral separa 1.000 de 1.000. El problema es de fondo: una
    #    pregunta de historia peruana ajena usa el MISMO vocabulario que una
    #    del temario, asi que la presencia de terminos no distingue nada.
    #
    #    Lo que si distingue son dos senales sobre la evidencia real:
    #
    #    DENSIDAD - cuantas veces por mil tokens repite un bloque los terminos
    #    de la pregunta. Un texto que TRATA un tema lo repite; uno que solo lo
    #    menciona de pasada, no. Medido sobre el banco:
    #        dentro  mediana 153,8 por mil
    #        fuera   mediana  12,6 por mil, maximo 59,5
    #
    #    BM25_TOP10 - la media de los diez mejores scores. Si el corpus trata
    #    el tema hay VARIOS bloques buenos; si es coincidencia, hay uno.
    #        dentro  mediana 10,7
    #        fuera   mediana  5,1
    #
    #    Se combinan en un puntaje en vez de exigir ambas por separado: una
    #    pregunta legitima puede ser fuerte en una y mediana en la otra
    #    ("¿Que dice Klaren sobre el APRA?" tiene densidad 200 pero top10
    #    5,3, porque el corpus tiene poco sobre el APRA). Exigir las dos
    #    mataba preguntas reales; exigir una sola dejaba pasar las ajenas.
    pesos = {t: _idf(idx, t) for t in terms}
    total = sum(pesos.values())
    if total <= 0:
        return True, "La consulta no contiene terminos que buscar."

    scores = idx["bm25"].get_scores(terms)
    bm25_top10 = float(np.mean(np.sort(scores)[-10:])) if len(scores) else 0.0

    densidad = 0.0
    for i, s in enumerate(toks_b):
        juntos = [t for t in terms if t in s]
        if len(juntos) < 2:
            continue
        texto = tokenizar(idx["bloques"][i]["texto"])
        if texto:
            ocurrencias = sum(texto.count(t) for t in juntos)
            densidad = max(densidad, ocurrencias / len(texto) * 1000)

    # Pesos y umbral elegidos por barrido sobre el banco de 77 preguntas
    # (pruebas/banco_preguntas.py). Curva medida, w = peso de la densidad:
    #
    #     w     umbral   falsos negativos   falsos positivos   global
    #    0.3     0.8            1                  6           68/77
    #    0.5     1.0            4                  3           68/77
    #    0.7     1.0            1                  5           69/77  <- elegido
    #    1.0     1.8           11                  0           64/77
    #    1.5     1.2            1                  6           68/77
    #
    # Se prefiere el falso positivo al falso negativo: negarse a responder
    # una pregunta real del curso deja al estudiante sin nada, mientras que
    # devolver evidencia debil todavia pasa por el NUCLEO del agente, que
    # obliga al modelo a declarar cuando la evidencia no alcanza.
    #
    # NOTA: 77 preguntas etiquetadas por una sola persona no son el banco
    # anotado que exige el paper (8.3: anotacion previa, splits por documento,
    # varios conjuntos minimos validos). El umbral es defendible con datos,
    # no calibrado.
    PESO_DENSIDAD = 0.7
    UMBRAL = 1.0

    puntaje = PESO_DENSIDAD * (densidad / 100.0) + (bm25_top10 / 10.0)

    # Senal semantica: ¿hay algo en el corpus que HABLE de esto, aunque no
    # repita las palabras? Es lo que las senales lexicas no pueden ver.
    #
    # Se usa como arbitro en los dos sentidos, porque los dos fallos existen:
    #   - rescata preguntas del curso cuyo vocabulario no coincide con el de
    #     las lecturas ("epidemias" vs "viruela/sarampion")
    #   - rechaza preguntas ajenas que comparten palabras con el corpus
    #     ("gobierno de Velasco Alvarado")
    #
    # Si la capa semantica no esta disponible (sin indice, sin clave, sin
    # cuota) devuelve None y el gate decide solo con lo lexico, como antes.
    import semantico
    sim = semantico.similitud_maxima(pregunta, idx)

    if sim is None:
        # Sin capa semantica (sin indice, sin clave, sin cuota): decide solo
        # lo lexico, como antes de existir esta senal.
        if puntaje < UMBRAL:
            return True, ("El material autorizado del curso no cubre esta "
                          "consulta: sus terminos aparecen sueltos, en "
                          "documentos que no desarrollan el tema.")
        return False, None

    if sim >= UMBRAL_SIM_ALTA:
        return False, None                # el corpus trata el tema, sin duda

    if sim < UMBRAL_SIM_BAJA:
        return True, ("El material autorizado del curso no trata este tema. "
                      "El agente solo responde con las lecturas, diapositivas "
                      "y documentos del curso.")

    # --- zona de solape (0.30-0.51): aqui viven los casos dificiles ---
    #
    # Un primer intento delegaba esta franja entera a la senal lexica, y no
    # sirvio de nada: las cinco preguntas que se colaban ("Velasco Alvarado"
    # 0.45, "Tupac Amaru II" 0.47, "guerra del Pacifico" 0.50) caen justo
    # aqui, y la senal lexica es precisamente la que ya fallaba con ellas.
    #
    # Lo que si las separa es exigir las DOS cosas a la vez. Una pregunta
    # legitima que cae en esta franja lo hace por vocabulario poco frecuente
    # ("¿Fue la independencia un proyecto nacional unificado?", sim 0.396)
    # pero tiene respaldo lexico fuerte: el corpus desarrolla el tema. Una
    # ajena tiene similitud media porque comparte dominio -- historia
    # peruana -- pero ningun bloque la desarrolla.
    #
    # Se pide un minimo lexico mas alto que el general: en esta franja la
    # duda ya esta instalada, y el coste de equivocarse es afirmar con
    # evidencia que no sostiene la respuesta.
    if puntaje < UMBRAL_ZONA_GRIS:
        return True, ("El material autorizado del curso menciona algo de esto, "
                      "pero no lo desarrolla: no hay evidencia suficiente para "
                      "responder sin inventar.")

    return False, None


def buscar(pregunta, reqs, idx, plan):
    """6 - CERES_OMEGA(question q, corpus C)

    Haz de estados con diversidad por cadena. Cada estado es un conjunto de
    bloques; se expande anadiendo candidatos que cierren el requisito abierto,
    condicionados por un puente.
    """
    # Frontera por requisito (4.3). Se conserva intacta toda la corrida:
    # politica monotonica de la seccion 5.
    F = {r["id"]: frontera(pregunta, r, idx, plan) for r in reqs}
    F_union = defaultdict(float)
    for m in F.values():
        for i, s in m.items():
            F_union[i] += s

    if not F_union:
        return [], F, F_union, []

    # Estados iniciales: un puente cada uno, cadenas distintas.
    inicial = _puentes(F_union, set(), PUENTES)
    beam = [[i] for i in inicial] or [[]]
    completos = []

    for _ronda in range(RONDAS_MAX):
        expandidos = []
        for estado in beam:
            faltan = _verificar(idx, reqs, estado)
            if not faltan:
                completos.append(list(estado))
                continue

            for req in faltan:
                # Consulta residual: solo la pieza que falta (4.6)
                residual = consulta_residual(pregunta, req, estado, idx)
                req_res = dict(req, terms=residual)
                Fr = frontera(pregunta, req_res, idx, plan)

                for puente in _puentes(F_union, set(estado), PUENTES):
                    # 4.4 - "Las consultas del siguiente salto combinan la
                    # pregunta, el requisito pendiente, entidades extraidas
                    # del puente y las variables ya resueltas."
                    #
                    # El puente reordena los candidatos: se puntua cada uno
                    # por su utilidad para cerrar r DADO lo que el puente ya
                    # demuestra (s_bridge del paper). Sin esto, los B puentes
                    # generaban expansiones identicas y el multi-puente era
                    # decorativo: el haz exploraba una sola cadena.
                    cands = _condicionar(idx, Fr, puente, estado, req)
                    for c in cands[:POOL_POR_ESTADO]:
                        if c in estado:
                            continue
                        expandidos.append(estado + [c])

        if not expandidos:
            break

        # Deduplicar conjuntos equivalentes antes de puntuar
        vistos, unicos = set(), []
        for e in expandidos:
            k = tuple(sorted(e))
            if k not in vistos:
                vistos.add(k)
                unicos.append(e)

        unicos.sort(key=lambda e: paraset(idx, reqs, e, F_union), reverse=True)

        # Diversidad por cadena: el haz no puede llenarse de variantes del
        # mismo documento (4.4, "estados con cadenas diferentes").
        beam, firmas = [], set()
        for e in unicos:
            firma = tuple(sorted({idx["bloques"][i]["doc_id"] for i in e}))
            if firma in firmas and len(beam) >= BEAM // 2:
                continue
            firmas.add(firma)
            beam.append(e)
            if len(beam) >= BEAM:
                break

        if completos:
            break

    finalistas = completos + beam
    if not finalistas:
        return [], F, F_union, []

    mejor = max(finalistas, key=lambda e: set_ce(idx, reqs, e, F_union, plan))

    # Politica monotonica (seccion 5), lado positivo: una vez asegurada la
    # prueba E*, el presupuesto sobrante se rellena DESDE LA FRONTERA F, que
    # nunca se destruyo. Sin esto el motor entregaba 625 tokens de un
    # presupuesto de 9000: suficiente para cerrar los requisitos, pobre para
    # que el estudiante lea el contexto y para que el modelo distinga postura
    # de dato. La ampliacion no puede cambiar la decision ya tomada -- solo
    # anade contexto por debajo del tope de tokens.
    prueba = list(mejor)
    ampliado = _rellenar(idx, mejor, F_union, plan, reqs)
    return ampliado, F, F_union, prueba


def _rellenar(idx, estado, F_union, plan, reqs):
    """Amplia E* con los mejores bloques de F que quepan en el presupuesto.

    Respeta el cupo por documento (Klaren y Aldana-Pereyra son el 33% del
    corpus: sin cupo, rellenar equivale a mandar esos dos libros) y prefiere
    documentos que todavia no aportan, que es lo que da al modelo material
    para contrastar posturas en vez de repetir una sola.
    """
    if not estado:
        return estado

    # Una consulta puntual ("cuando es el examen parcial") se responde con el
    # bloque que la contiene. Rellenar hasta el presupuesto le anadia
    # capitulos de Klaren y Contreras que no tienen nada que ver con una
    # fecha de examen: ruido caro que el modelo debe descartar. Solo se
    # rellena cuando la tarea pide contexto o contraste.
    if plan["tipo"] == "puntual":
        return estado

    actual = list(estado)
    tokens = sum(int(idx["bloques"][i]["tokens"]) for i in actual)
    por_doc = defaultdict(int)
    for i in actual:
        por_doc[idx["bloques"][i]["doc_id"]] += 1

    # Reserva: no se llena hasta el borde, el empaquetado aun debe caber.
    tope = int(plan["presupuesto"] * 0.92)

    # Tope de fragmentos, no solo de tokens. El panel de evidencia del
    # frontend lista TODOS los paquetes, y una respuesta que cita 5 de 17
    # deja al estudiante 12 tarjetas que nadie referencia: ruido visual que
    # sugiere que el agente uso material que en realidad ignoro. El limite
    # es por tarea, no global -- un resumen de semana si justifica mas
    # fragmentos que una pregunta puntual.
    max_frag = {"puntual": 4, "conceptual": 10, "amplia": 14}[plan["tipo"]]
    cupo = _cupo_para(plan)
    candidatos = sorted(F_union.items(), key=lambda kv: -kv[1])

    # Dos pasadas: primero un bloque por documento nuevo, para que la
    # evidencia represente varias fuentes antes de profundizar en una sola.
    # Es la version operativa de la operacion DESACUERDO del agente: si el
    # relleno se hiciera por score puro, el documento mejor posicionado se
    # llevaria todo el presupuesto sobrante.
    for solo_nuevos in (True, False):
        for i, _s in candidatos:
            if len(actual) >= max_frag:
                return actual
            if i in actual:
                continue
            b = idx["bloques"][i]
            doc_id = b["doc_id"]
            if solo_nuevos and por_doc[doc_id] > 0:
                continue
            if por_doc[doc_id] >= cupo:
                continue
            t = int(b["tokens"])
            if tokens + t > tope:
                continue
            actual.append(i)
            por_doc[doc_id] += 1
            tokens += t

    return actual


# ===========================================================================
# 4.7  LECTOR ATOMICO
# ===========================================================================

_ORACION_RE = re.compile(r"(?<=[.!?])\s+(?=[A-ZÁÉÍÓÚÑ¿¡])")


def atomos(idx, bloque_i, reqs):
    """4.7 - Selecciona las oraciones que sostienen cada requisito.

    SUSTITUYE al lector supervisado (DeBERTa-v3 con perdida conjunta de
    soporte, span y cobertura). Este puntua oraciones por solapamiento con los
    terminos del requisito -- exactamente la "heuristica lexical" que el paper
    relega a "fallback diagnostico". Se marca como tal en la salida.

    El paper exige que cada atomo resuelva al contenido original: aqui cada
    uno lleva su bloque_id, su documento, su pagina y el offset dentro del
    bloque, de modo que se puede reconstruir la cita.
    """
    b = idx["bloques"][bloque_i]
    texto = b["texto"]
    oraciones = [o.strip() for o in _ORACION_RE.split(texto) if len(o.strip()) > 40]
    if not oraciones:
        return []

    terms = set()
    for r in reqs:
        terms |= set(r["terms"])

    puntuadas = []
    for pos, o in enumerate(oraciones):
        toks = set(tokenizar(o))
        if not toks:
            continue
        golpes = len(terms & toks)
        if golpes:
            puntuadas.append({
                "sentence": o,
                "score": round(golpes / max(len(terms), 1), 3),
                "offset": texto.find(o),
                "position": pos,
            })
    puntuadas.sort(key=lambda a: -a["score"])
    return puntuadas[:3]


# ===========================================================================
# EMPAQUETADO  ->  contrato que ya consumian agente.py y servidor.py
# ===========================================================================

def _cupo_para(plan):
    """Cuantos bloques como maximo puede aportar un mismo documento.

    Un resumen de semana SI debe poder apoyarse varias veces en la lectura de
    esa semana; una pregunta conceptual no, porque entonces Klaren o
    Aldana-Pereyra -- juntos el 33% del corpus -- copan la evidencia por
    tamano y el estudiante deja de ver el desacuerdo entre autores, que es el
    contenido del curso (README, y NUCLEO 2 operacion DESACUERDO).
    """
    if plan["tipo"] == "amplia" or plan.get("filtros"):
        return CUPO_POR_DOC + 2
    return CUPO_POR_DOC


def _cita_de(idx, doc_id):
    d = idx["docs"][doc_id]
    return d.get("cita") or d.get("titulo") or doc_id


def _ubicacion(b):
    f = b["fuente"]
    if isinstance(f, str):  # defensivo: indices viejos guardaban el dict como str
        return "s/ubicacion"
    if f.get("pagina") is not None:
        return f"p. {f['pagina']}"
    if f.get("diapositiva") is not None:
        return f"diap. {f['diapositiva']}"
    return "s/ubicacion"


def _empaquetar(idx, estado, reqs, plan, F_union):
    """Convierte el conjunto E* en los "paquetes" que espera el resto del
    sistema, aplicando cupo por documento y presupuesto de tokens.

    Politica monotonica (seccion 5): esta poda opera sobre E*, nunca sobre F.
    Si el presupuesto deja fuera evidencia obligatoria, se avisa en vez de
    silenciarlo.
    """
    # Ordenar por aporte al peor requisito, no por score individual.
    orden = sorted(estado, key=lambda i: -F_union.get(i, 0.0))

    # El cupo se aplica AQUI, que es la unica puerta por la que pasa todo lo
    # que llega al prompt. _rellenar propone; _empaquetar dispone. Tenerlo en
    # los dos sitios con contadores separados dejaba pasar 4 bloques del
    # mismo documento pese al limite de 3.
    cupo = _cupo_para(plan)

    por_doc = defaultdict(int)
    paquetes, tokens, descartados_cupo = [], 0, 0

    for i in orden:
        b = idx["bloques"][i]
        doc_id = b["doc_id"]
        if por_doc[doc_id] >= cupo:
            descartados_cupo += 1
            continue
        t = int(b["tokens"])
        if tokens + t > plan["presupuesto"] and paquetes:
            continue
        por_doc[doc_id] += 1
        tokens += t

        d = idx["docs"][doc_id]
        f = b["fuente"] if isinstance(b["fuente"], dict) else {}
        paquetes.append({
            "doc": d.get("titulo") or doc_id,
            "doc_id": doc_id,
            "bloque_id": b["bloque_id"],
            "cita": _cita_de(idx, doc_id),
            "paginas": _ubicacion(b),
            "archivo": f.get("archivo", d.get("archivo", "")),
            "tipo": b["tipo"],
            "autoridad": b["autoridad"],
            "unidad": b["unidad"] if b["unidad"] not in ("None", None) else None,
            "semana": b["semana"] if b["semana"] not in ("None", None) else None,
            "tokens": t,
            "score": round(F_union.get(i, 0.0), 5),
            "cobertura": round(_cobertura_req(reqs[0], [b["texto"]]), 3),
            "ocr": bool(f.get("ocr")),
            "texto": b["texto"],
            "atomos": atomos(idx, i, reqs),
        })

    plan["tokens_usados"] = tokens
    return paquetes, descartados_cupo


def _contrato_ceres(pregunta, reqs, paquetes, decision):
    """Apendice A del paper: contrato minimo de salida."""
    evidencia = []
    for n, p in enumerate(paquetes, 1):
        evidencia.append({
            "id": f"ev_{n}",
            "document_id": p["doc_id"],
            "block_id": p["bloque_id"],
            "locator": {"page": p["paginas"], "file": p["archivo"]},
            "atoms": [a["sentence"] for a in p["atomos"]],
            "atom_selector": "lexical_fallback",  # 4.7: no es el lector supervisado
            "raw_text": p["texto"][:400],
        })
    return {
        "decision": decision,
        "question": pregunta,
        "requirements": [{
            "id": r["id"],
            "proposition": r["proposition"],
            "status": r["status"],
            "mandatory": r["mandatory"],
            "coverage": r.get("coverage", 0.0),
            "acceptance_test": r["acceptance_test"],
            "support_ids": [e["id"] for e in evidencia],
        } for r in reqs],
        "evidence": evidencia,
        "unmet_requirements": [r["id"] for r in reqs if r["status"] == "MISSING"],
        "contradictions": [],  # requiere el verificador semantico de 4.8
        "coverage": round(
            sum(1 for r in reqs if r["status"] == "SUPPORTED") / len(reqs), 3
        ) if reqs else 0.0,
    }


# ===========================================================================
# API PUBLICA  -  misma firma que el motor anterior
# ===========================================================================

def analizar_pregunta(pregunta, idx):
    """Compatibilidad: servidor.py /api/comparar lo usa para conocer el plan
    sin ejecutar la recuperacion completa."""
    _reqs, plan = compilar_requisitos(pregunta, idx)
    return plan


def recuperar(pregunta, idx, modo_interaccion="preguntar"):
    """Punto de entrada. Devuelve {paquetes, plan, avisos, ceres}.

    modo_interaccion ajusta el presupuesto: los modos que generan una tarjeta
    o una pregunta de opcion multiple (repasar/practicar/evaluar) necesitan
    menos evidencia que una explicacion causal, y mandarles 14k tokens es
    gasto sin retorno.
    """
    # La pregunta original queda disponible para toda la consulta: es lo
    # unico que se embebe, una sola vez, y de ahi salen tanto la senal densa
    # de la frontera como la del gate. Sin esto el haz embebia terminos
    # residuales en cada ronda y la latencia se multiplicaba por 40.
    idx["_ceres_consulta"] = pregunta

    reqs, plan = compilar_requisitos(pregunta, idx)

    if modo_interaccion in ("repasar",):
        plan["presupuesto"] = min(plan["presupuesto"], PRESUPUESTO["puntual"])
    elif modo_interaccion in ("practicar", "evaluar"):
        plan["presupuesto"] = min(plan["presupuesto"], PRESUPUESTO["conceptual"])
    elif modo_interaccion in ("debate", "explicacion"):
        plan["presupuesto"] = max(plan["presupuesto"], PRESUPUESTO["conceptual"])
    elif modo_interaccion == "resumen":
        plan["presupuesto"] = PRESUPUESTO["amplia"]

    # 4.8 - abstencion temprana. Se decide ANTES de buscar: si el corpus no
    # trata el tema, recuperar los bloques "menos malos" solo produce una
    # respuesta con evidencia irrelevante pero citada, que es peor que decir
    # que no se sabe.
    fuera, motivo = fuera_de_alcance(pregunta, reqs, idx, plan)
    if fuera:
        plan["tokens_usados"] = 0
        for r in reqs:
            r["status"] = "MISSING"
            r["coverage"] = 0.0
        return {
            "paquetes": [],
            "plan": plan,
            "avisos": [motivo],
            "ceres": _contrato_ceres(pregunta, reqs, [], "INSUFFICIENT"),
        }

    estado, _F, F_union, prueba = buscar(pregunta, reqs, idx, plan)

    avisos = []
    if not estado:
        plan["tokens_usados"] = 0
        for r in reqs:
            r["status"] = "MISSING"
            r["coverage"] = 0.0
        return {
            "paquetes": [],
            "plan": plan,
            "avisos": ["Ninguna fuente autorizada del curso cubre esta consulta."],
            "ceres": _contrato_ceres(pregunta, reqs, [], "INSUFFICIENT"),
        }

    # La suficiencia se juzga sobre la PRUEBA (E*), no sobre el conjunto ya
    # ampliado con contexto: si el relleno pudiera marcar un requisito como
    # cubierto, el motor declararia ANSWER gracias a bloques que solo estan
    # ahi para dar contexto. Seccion 5: la prueba y la frontera son objetos
    # distintos y no se confunden.
    faltan = _verificar(idx, reqs, prueba or estado)
    paquetes, descartados = _empaquetar(idx, estado, reqs, plan, F_union)

    # 4.8 - decision: ANSWER / PARTIAL / INSUFFICIENT
    obligatorios_ok = all(r["status"] == "SUPPORTED" for r in reqs if r["mandatory"])
    opcionales_ok = all(r["status"] == "SUPPORTED" for r in reqs)
    if obligatorios_ok and opcionales_ok:
        decision = "ANSWER"
    elif obligatorios_ok:
        decision = "PARTIAL"
    elif paquetes:
        decision = "PARTIAL"
    else:
        decision = "INSUFFICIENT"

    # Avisos: se pasan al prompt como NOTAS INTERNAS (ver agente.py,
    # prompt_recuperacion). Es donde el motor le dice al modelo que la
    # evidencia es incompleta, en vez de dejar que el modelo lo suponga.
    for r in faltan:
        avisos.append(
            f"Requisito sin respaldo suficiente ({r['id']}: {r['kind']}). "
            f"La evidencia puede no cubrir toda la pregunta -- dilo explicitamente."
        )
    if decision == "PARTIAL" and not faltan:
        avisos.append("Falta una segunda fuente independiente: no presentes esto como consenso.")
    if descartados:
        avisos.append(
            f"{descartados} fragmento(s) del mismo documento quedaron fuera por el cupo "
            f"de {CUPO_POR_DOC} por documento."
        )
    if any(p["ocr"] for p in paquetes):
        avisos.append("Hay fragmentos de OCR: cifras, nombres y fechas pueden estar mal transcritos.")
    if plan["filtros"] and not any(
        p["semana"] == plan["filtros"].get("semana") for p in paquetes
    ) and "semana" in plan["filtros"]:
        avisos.append(
            f"No hay material indexado para la semana {plan['filtros']['semana']}; "
            f"la evidencia viene de otras semanas."
        )

    return {
        "paquetes": paquetes,
        "plan": plan,
        "avisos": avisos,
        "ceres": _contrato_ceres(pregunta, reqs, paquetes, decision),
    }
