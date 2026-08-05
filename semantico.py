# -*- coding: utf-8 -*-
"""
Capa semantica: la senal DENSA de la frontera de CERES-Omega (seccion 4.3).

Aisla el uso de embeddings del resto del motor. Si el indice no existe o la
API no responde, todo sigue funcionando con las senales lexicas: el motor
NUNCA depende de que esta capa este disponible.

    from semantico import disponible, similitudes, similitud_maxima

POR QUE HACE FALTA
------------------
Las senales lexicas (BM25, TF-IDF) cuentan palabras, y eso fallaba en los dos
sentidos sobre este corpus:

  falso negativo: "¿Como afectaron las epidemias coloniales?" recuperaba poco,
      porque las lecturas dicen "viruela", "sarampion", "patogenos" -- nunca
      la palabra "epidemias".
  falso positivo: "¿Que fue el gobierno de Velasco Alvarado?" recuperaba diez
      fragmentos, porque "gobierno" y "velasco" existen sueltos en el corpus
      aunque el curso no trate ese tema.

Ningun umbral sobre conteo de palabras separa esos dos casos. El significado
si: medido con la API, "viruela y sarampion diezmaron la poblacion" queda a
0.757 de "colapso demografico del siglo XVI" y a 0.442 de "receta de pizza".

DONDE VIVE CADA COSA
--------------------
Los vectores de los 1310 bloques se calculan una vez con
indexar_embeddings.py y viajan en el repo (corpus/embeddings.npz, ~4 MB).
En produccion solo se carga ese array; la consulta se embebe por API, una
llamada por pregunta. Asi el backend cabe en los 512 MB del plan gratuito de
Render, que no aguantaria PyTorch.
"""
import os
import threading

import numpy as np

RAIZ = os.path.dirname(os.path.abspath(__file__))
RUTA = os.path.join(RAIZ, "corpus", "embeddings.npz")
# Clave de entorno por proveedor. El indice guarda con cual se construyo, y
# la consulta DEBE embeberse con el mismo: los vectores de Cohere y los de
# Gemini viven en espacios distintos, asi que mezclarlos da similitudes que
# parecen validas y no significan nada.
#
# La dimension tambien es por proveedor: embed-v4.0 solo admite
# 256/512/1024/1536 y rechaza otras con un 422.
CLAVES = {"cohere": "COHERE_API_KEY", "gemini": "GEMINI_API_KEY"}
MODELOS = {"cohere": "embed-v4.0", "gemini": "gemini-embedding-001"}
DIMS = {"cohere": 1024, "gemini": 768}

_M = None            # matriz (n_bloques x DIM), normalizada por fila
_ORDEN = None        # bloque_id -> fila
_CLIENTE = None
_PROV = None         # proveedor con el que se construyo el indice

# Contadores de salud de la capa. Sin esto, una caida del proveedor degrada
# el motor en silencio: sigue respondiendo, pero peor, y la medicion deja de
# ser reproducible sin que nada lo indique.
#
# Caso real: una corrida del banco dio 97,4% y otra 90,9% con el MISMO
# codigo. La diferencia era que en la segunda el trial de Cohere ya no tenia
# cuota mensual, todas las llamadas devolvian 429 y el gate decidia solo con
# la senal lexica. Un resultado que depende de la cuota del dia no se puede
# publicar.
_LLAMADAS = 0
_FALLOS = 0
_ULTIMO_ERROR = None
_ESTADO = None       # None = sin intentar, True/False = resultado del intento
_LOCK = threading.Lock()
_CACHE = {}          # consulta -> vector, para no re-embeber lo mismo
_CACHE_MAX = 4096
# Cache en disco. Dos motivos, uno de producto y otro de metodo:
#
#  - producto: las preguntas de un curso se repiten mucho entre estudiantes
#    ("¿cuando es el examen?"), y cada repeticion costaba una llamada.
#  - metodo: sin el, la evaluacion del motor depende de si hay cuota ese dia.
#    Con el, una vez embebido el banco, las mediciones son reproducibles y no
#    consumen cuota -- que es condicion para publicar un numero.
RUTA_CACHE = os.path.join(RAIZ, "corpus", "consultas_cache.npz")
_CACHE_SUCIO = False


def _cargar():
    """Carga el indice y el cliente una sola vez por proceso."""
    global _M, _ORDEN, _CLIENTE, _ESTADO, _PROV
    if _ESTADO is not None:
        return _ESTADO
    with _LOCK:
        if _ESTADO is not None:
            return _ESTADO
        try:
            if not os.path.exists(RUTA):
                _ESTADO = False
                return False
            z = np.load(RUTA, allow_pickle=True)
            _M = z["M"].astype("float32")
            _ORDEN = {str(b): i for i, b in enumerate(z["ids"])}
            _PROV = str(z["proveedor"]) if "proveedor" in z else "gemini"

            try:
                from dotenv import load_dotenv
                load_dotenv(os.path.join(RAIZ, ".env"))
            except ImportError:
                pass

            clave = os.environ.get(CLAVES[_PROV])
            if not clave:
                # Hay vectores pero no con que embeber la consulta: la capa
                # queda inutil, pero el motor sigue con las senales lexicas.
                # Se anuncia para que la degradacion sea visible y no
                # silenciosa -- el motor responde igual, solo que peor.
                print(f"AVISO: el indice semantico es de '{_PROV}' pero falta "
                      f"{CLAVES[_PROV]}; el motor usara solo senales lexicas.")
                _ESTADO = False
                return False

            # Cache de consultas ya embebidas. Solo se acepta si es del mismo
            # proveedor: los vectores de Cohere y Gemini no son comparables.
            if os.path.exists(RUTA_CACHE):
                try:
                    zc = np.load(RUTA_CACHE, allow_pickle=True)
                    if str(zc["proveedor"]) == _PROV:
                        for t, v in zip(zc["textos"], zc["vectores"]):
                            _CACHE[str(t)] = v.astype("float32")
                except Exception:                       # noqa: BLE001
                    pass                                # cache corrupto: se ignora

            if _PROV == "cohere":
                import cohere
                # timeout corto y sin reintentos del SDK: esta llamada esta
                # en el camino critico de cada consulta del estudiante. Si el
                # proveedor tarda, es mejor perder la senal semantica en esa
                # consulta que hacerle esperar diez segundos -- el motor sigue
                # con las senales lexicas. Sin esto el p99 llegaba a 11,7 s
                # por los reintentos internos del SDK ante el limite de cuota.
                _CLIENTE = cohere.ClientV2(api_key=clave, timeout=6,
                                           max_retries=0)
            else:
                from google import genai
                _CLIENTE = genai.Client(api_key=clave)
            _ESTADO = True
        except Exception:                               # noqa: BLE001
            # Cualquier fallo (indice corrupto, SDK ausente, red) degrada a
            # solo-lexico en vez de tumbar la consulta.
            _ESTADO = False
    return _ESTADO


def disponible():
    """True si la busqueda semantica puede usarse en esta consulta."""
    return _cargar()


def salud():
    """Estadisticas de uso de la capa en este proceso.

    Toda medicion del motor DEBE reportar esto: un resultado obtenido con la
    capa caida no es comparable con uno obtenido con la capa viva, y sin este
    dato la diferencia es invisible.
    """
    return {
        "cargada": _ESTADO is True,
        "proveedor": _PROV,
        "llamadas": _LLAMADAS,
        "fallos": _FALLOS,
        "tasa_fallo": (_FALLOS / _LLAMADAS) if _LLAMADAS else 0.0,
        "ultimo_error": _ULTIMO_ERROR,
    }


def guardar_cache():
    """Persiste las consultas embebidas en esta sesion.

    Se llama explicitamente (no en cada consulta) para no escribir en disco
    dentro del camino critico de una peticion web.
    """
    global _CACHE_SUCIO
    if not _CACHE_SUCIO or not _CACHE or _PROV is None:
        return False
    try:
        textos = list(_CACHE.keys())
        vectores = np.stack([_CACHE[t] for t in textos])
        np.savez_compressed(RUTA_CACHE, textos=np.array(textos, dtype=object),
                            vectores=vectores, proveedor=_PROV)
        _CACHE_SUCIO = False
        return True
    except Exception:                                   # noqa: BLE001
        return False


def reiniciar_contadores():
    """Pone a cero los contadores de salud (util entre bloques de medicion)."""
    global _LLAMADAS, _FALLOS, _ULTIMO_ERROR
    _LLAMADAS = _FALLOS = 0
    _ULTIMO_ERROR = None


def _embeber_consulta(texto):
    """Vector normalizado de la consulta, o None si la API falla.

    Se cachea: en una sesion el estudiante repite y reformula preguntas
    parecidas, y cada llamada cuesta cuota.
    """
    global _LLAMADAS, _FALLOS, _ULTIMO_ERROR
    if texto in _CACHE:
        return _CACHE[texto]
    _LLAMADAS += 1
    try:
        if _PROV == "cohere":
            r = _CLIENTE.embed(texts=[texto], model=MODELOS["cohere"],
                               input_type="search_query",
                               embedding_types=["float"],
                               output_dimension=DIMS["cohere"])
            v = np.asarray(r.embeddings.float_[0], dtype="float32")
        else:
            from google.genai import types
            cfg = types.EmbedContentConfig(task_type="RETRIEVAL_QUERY",
                                           output_dimensionality=DIMS["gemini"])
            r = _CLIENTE.models.embed_content(model=MODELOS["gemini"],
                                              contents=[texto], config=cfg)
            v = np.asarray(r.embeddings[0].values, dtype="float32")
        n = np.linalg.norm(v)
        if n == 0:
            return None
        v = v / n
        global _CACHE_SUCIO
        if len(_CACHE) >= _CACHE_MAX:
            _CACHE.clear()
        _CACHE[texto] = v
        _CACHE_SUCIO = True
        return v
    except Exception as e:                              # noqa: BLE001
        # Cuota agotada, red caida, etc. El motor continua sin esta senal:
        # devolver None hace que ceres_omega decida solo con lo lexico, que
        # es peor pero funciona. Preferible a dejar al estudiante sin
        # respuesta porque el proveedor tuvo un mal minuto.
        #
        # No se reintenta a proposito: un reintento con espera convierte un
        # fallo de cuota en una consulta de 10 s.
        _FALLOS += 1
        _ULTIMO_ERROR = f"{type(e).__name__}: {str(e)[:120]}"
        if _FALLOS == 1 or _FALLOS % 25 == 0:
            print(f"AVISO semantico: {_FALLOS}/{_LLAMADAS} llamadas fallidas. "
                  f"Ultimo: {_ULTIMO_ERROR}")
        return None


def similitudes(consulta, idx):
    """Similitud coseno de la consulta contra todos los bloques.

    Devuelve un array alineado con idx["bloques"], o None si no hay capa
    semantica disponible. Los bloques que no esten en el indice de vectores
    reciben 0.
    """
    if not _cargar():
        return None
    v = _embeber_consulta(consulta)
    if v is None:
        return None

    sims_por_id = _M @ v
    out = np.zeros(len(idx["bloques"]), dtype="float32")
    for i, b in enumerate(idx["bloques"]):
        fila = _ORDEN.get(b["bloque_id"])
        if fila is not None:
            out[i] = sims_por_id[fila]
    return out


def similitud_maxima(consulta, idx):
    """La mejor similitud de la consulta con cualquier bloque del corpus.

    Es la senal que usa el gate: responde "¿hay algo en este corpus que
    hable de esto?" sin depender de que se repitan las palabras exactas.
    """
    s = similitudes(consulta, idx)
    if s is None or not len(s):
        return None
    return float(np.max(s))
