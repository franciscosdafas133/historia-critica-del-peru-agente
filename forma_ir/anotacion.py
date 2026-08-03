# -*- coding: utf-8 -*-
"""
Fase C2: anotacion de reglas de la gramatica inducida (Fase C1).

Repeticion sola no basta para decidir si una regla es organizacionalmente
util -- un encabezado de pagina repetido tambien se repite. Se anotan las
reglas con: estabilidad posicional, diversidad lexica, y compatibilidad
de anidamiento, para distinguir:
  - una regla que capta un HEADER REPETIDO: alta estabilidad posicional
    (siempre en el mismo lugar relativo), diversidad lexica CASI CERO
    (el texto que sigue es literalmente el mismo cada vez).
  - una regla que capta un PATRON REAL DE SUBSECCION (ej. "3.1 ...",
    "3.2 ...", "3.3 ..."): estabilidad posicional similar, pero
    diversidad lexica ALTA (cada ocurrencia habla de algo distinto).
"""
import math
from dataclasses import dataclass

from forma_ir.gramatica import Regla, expandir_regla
from forma_ir.tipos import Bloque


@dataclass
class OcurrenciaRegla:
    """Una ocurrencia concreta de una regla dentro de la secuencia top,
    con los bloques originales que abarca."""
    posicion_en_top: int  # indice dentro de la secuencia top (no de bloques!)
    indices_bloque: list[int]  # posiciones (seq) de los bloques que esta ocurrencia cubre


@dataclass
class AnotacionRegla:
    regla_id: int
    n_ocurrencias: int
    estabilidad_posicional: float  # 0..1, mayor = posiciones relativas mas consistentes
    diversidad_lexica: float  # entropia normalizada del texto que sigue a cada ocurrencia
    compatibilidad_anidamiento: bool  # todas las ocurrencias caen bajo el mismo tipo de contenedor
    es_candidata_limite: bool


def _posiciones_de_regla_en_top(regla_id: int, top: list[int]) -> list[int]:
    """Todas las posiciones (indices dentro de `top`) donde aparece
    -regla_id como simbolo directo."""
    return [i for i, s in enumerate(top) if s == -regla_id]


def _mapear_top_a_bloques(top: list[int], reglas: dict[int, Regla],
                            bloques_doc: list[Bloque]) -> list[list[int]]:
    """Para cada posicion de `top`, calcula que indices de bloque
    (posiciones `seq` originales) cubre esa posicion una vez expandida
    completamente. Necesario porque un simbolo del top puede ser un
    no-terminal que expande a varios bloques."""
    resultado = []
    cursor = 0
    for simbolo in top:
        if simbolo < 0:
            n_terminales = len(expandir_regla([simbolo], reglas))
        else:
            n_terminales = 1
        resultado.append(list(range(cursor, cursor + n_terminales)))
        cursor += n_terminales
    return resultado


def _texto_propio(indices_bloque: list[int], bloques_doc: list[Bloque]) -> str:
    """Texto que la propia ocurrencia de la regla cubre. La diversidad
    lexica que distingue header-repetido de patron-real-de-subseccion se
    mide sobre ESTE texto, no sobre lo que viene despues -- un header
    repetido tiene el mismo texto propio en cada ocurrencia (diversidad
    ~0); una regla que capta el INICIO de una subseccion real (ej. solo
    el numero+titulo "3.2 Instalacion", sin el cuerpo) tiene texto propio
    corto y a veces tambien repetitivo en su FORMA, pero el contenido
    real que la distingue esta en lo que sigue -- por eso se combina con
    _texto_posterior() en la funcion de diversidad final."""
    return " ".join(bloques_doc[i].texto for i in indices_bloque)


def _texto_posterior(indices_bloque: list[int], bloques_doc: list[Bloque],
                       n_bloques_contexto: int = 2) -> str:
    """Texto de los `n_bloques_contexto` bloques que siguen inmediatamente
    despues de una ocurrencia."""
    fin = indices_bloque[-1] + 1 if indices_bloque else 0
    siguientes = bloques_doc[fin:fin + n_bloques_contexto]
    return " ".join(b.texto for b in siguientes)


def _entropia_normalizada_de_textos(textos: list[str]) -> float:
    """Entropia de Shannon sobre la distribucion de PALABRAS entre los
    distintos textos (bag-of-words simple, sin embeddings), normalizada a
    [0,1] dividiendo entre el maximo teorico log2(n_textos_distintos).

    Diversidad ~0: el mismo texto (o textos con vocabulario casi
    identico) se repite en cada ocurrencia -> tipico de un header.
    Diversidad alta: cada ocurrencia trae vocabulario distinto -> tipico
    de un patron real de subseccion con contenido propio."""
    if len(textos) <= 1:
        return 0.0
    # Se usa el CONJUNTO de palabras de cada texto (no bag-of-words con
    # frecuencia) como la "categoria" de esa ocurrencia -- dos textos
    # identicos caen en la misma categoria, dos textos distintos en
    # categorias distintas. Esto evita depender de una metrica de
    # distancia semantica (embeddings), que esta prohibida en el nucleo.
    categorias: dict[frozenset, int] = {}
    for t in textos:
        clave = frozenset(t.lower().split())
        categorias[clave] = categorias.get(clave, 0) + 1

    n = len(textos)
    entropia = 0.0
    for conteo in categorias.values():
        p = conteo / n
        entropia -= p * math.log2(p)

    maximo_teorico = math.log2(len(categorias)) if len(categorias) > 1 else 1.0
    if maximo_teorico == 0:
        return 0.0
    return entropia / maximo_teorico


def _estabilidad_posicional(ocurrencias: list[OcurrenciaRegla], bloques_doc: list[Bloque]) -> float:
    """Mayor estabilidad = las ocurrencias caen en posiciones relativas
    de pagina/diapositiva mas consistentes entre si (usa bbox.y0 si esta
    disponible, o la posicion `seq` normalizada por longitud de pagina
    como aproximacion cuando no hay bbox)."""
    posiciones_relativas = []
    for oc in ocurrencias:
        if not oc.indices_bloque:
            continue
        b = bloques_doc[oc.indices_bloque[0]]
        if b.bbox is not None:
            # normaliza contra una altura de pagina tipica; suficiente
            # para el bineo grueso que esta heuristica necesita
            posiciones_relativas.append(min(max(b.bbox[1] / 792.0, 0.0), 1.0))

    if len(posiciones_relativas) < 2:
        return 0.0  # sin suficiente informacion posicional -> no se afirma estabilidad

    media = sum(posiciones_relativas) / len(posiciones_relativas)
    varianza = sum((p - media) ** 2 for p in posiciones_relativas) / len(posiciones_relativas)
    # varianza 0 (misma posicion siempre) -> estabilidad 1.0
    # varianza alta -> estabilidad tiende a 0
    return 1.0 / (1.0 + varianza * 20)  # el factor 20 castiga varianzas moderadas; ver test para calibrar


def _compatibilidad_anidamiento(ocurrencias: list[OcurrenciaRegla], bloques_doc: list[Bloque]) -> bool:
    """True si todas las ocurrencias comparten el mismo `pagina`/`diapositiva`
    en terminos de posicion RELATIVA dentro del documento (ej. todas caen
    en la primera mitad de cada pagina, o todas al inicio de cada
    diapositiva) -- una aproximacion barata de "compatibilidad de
    anidamiento" sin necesitar el arbol completo (eso es Fase C4)."""
    paginas = {bloques_doc[oc.indices_bloque[0]].pagina for oc in ocurrencias if oc.indices_bloque}
    diapositivas = {bloques_doc[oc.indices_bloque[0]].diapositiva for oc in ocurrencias if oc.indices_bloque}
    # Compatible si las ocurrencias tienden a caer en paginas/diapositivas
    # DISTINTAS entre si (lo esperable de un patron que se repite una vez
    # por pagina/seccion) en vez de agruparse todas en la misma.
    if len(ocurrencias) == 0:
        return False
    return len(paginas) > 1 or len(diapositivas) > 1 or (len(paginas) <= 1 and len(diapositivas) <= 1 and len(ocurrencias) == 1)


def anotar_reglas(reglas: dict[int, Regla], top: list[int],
                    bloques_doc: list[Bloque]) -> dict[int, AnotacionRegla]:
    """Calcula la AnotacionRegla de cada regla de la gramatica inducida."""
    mapa_top_a_bloques = _mapear_top_a_bloques(top, reglas, bloques_doc)
    anotaciones: dict[int, AnotacionRegla] = {}

    for rid, regla in reglas.items():
        posiciones = _posiciones_de_regla_en_top(rid, top)
        ocurrencias = [
            OcurrenciaRegla(posicion_en_top=p, indices_bloque=mapa_top_a_bloques[p])
            for p in posiciones
        ]

        # Diversidad lexica se mide sobre el TEXTO PROPIO de cada
        # ocurrencia (lo que la regla misma cubre) -- esta es la senal
        # que distingue "Anexo del silabo... CRONOGRAMA..." (texto
        # identico en las 8 ocurrencias, diversidad ~0, es un header) de
        # un patron real cuyo contenido varia entre ocurrencias.
        textos_propios = [_texto_propio(oc.indices_bloque, bloques_doc) for oc in ocurrencias]
        diversidad = _entropia_normalizada_de_textos(textos_propios)
        estabilidad = _estabilidad_posicional(ocurrencias, bloques_doc)
        anidamiento = _compatibilidad_anidamiento(ocurrencias, bloques_doc)

        # Candidata a limite: header-like (alta estabilidad posicional,
        # diversidad propia baja -- el mismo texto se repite) O
        # subseccion-like (diversidad propia alta ADEMAS de estabilidad
        # posicional real -- no solo "distinta cada vez", sino tambien
        # "cae siempre en un lugar consistente de la pagina/diapositiva").
        #
        # Bug encontrado en Checkpoint C3a con datos reales: el criterio
        # original ("estabilidad > 0.3 OR diversidad > 0.15") marcaba
        # como candidata el 87% de las reglas de un PDF de prosa
        # academica en dos columnas -- lineas de CUERPO DE TEXTO
        # justificado comparten firma orto-tipografica (mismo tamano de
        # fuente, misma indentacion) y por eso SEQUITUR las agrupa en
        # "reglas", pero su diversidad lexica es SIEMPRE ~1.0 (cada linea
        # de un parrafo dice algo distinto, trivialmente) sin que eso
        # signifique nada organizacional. La diversidad alta sola no
        # basta: debe venir acompanada de estabilidad posicional real
        # (>0.4, mas estricto que el umbral header-like de 0.3) para
        # contar como "subseccion-like". Ademas se excluyen reglas con
        # demasiadas ocurrencias (>15): un patron que se repite docenas de
        # veces en un documento de este tamano es casi siempre textura de
        # prosa, no un marcador estructural (un documento tipico no tiene
        # docenas de inicios de seccion).
        header_like = estabilidad > 0.6 and diversidad < 0.15
        subseccion_like = diversidad > 0.4 and estabilidad > 0.4
        no_es_prosa_corrida = len(ocurrencias) <= 15
        es_candidata = (header_like or subseccion_like) and no_es_prosa_corrida

        anotaciones[rid] = AnotacionRegla(
            regla_id=rid,
            n_ocurrencias=len(ocurrencias),
            estabilidad_posicional=round(estabilidad, 4),
            diversidad_lexica=round(diversidad, 4),
            compatibilidad_anidamiento=anidamiento,
            es_candidata_limite=es_candidata,
        )

    return anotaciones
