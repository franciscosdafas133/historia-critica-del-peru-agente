# -*- coding: utf-8 -*-
"""
Fase B: firma orto-tipografica por bloque + deteccion de nuisance
(encabezados/pies repetidos).

La firma NUNCA usa identidad de palabras (excepto una stoplist de
puntuacion puramente estructural) -- solo forma observable: sangria,
capitalizacion, numeracion, tamano de fuente relativo. Esto es lo que
permite que "3.2 Installation", "IV -- Liability" y "Q:" revelen formas
repetibles sin mapearse a una categoria predeclarada de encabezado,
articulo o hablante (ver paper, seccion 5.1).
"""
import re
import statistics
from dataclasses import dataclass

from forma_ir.tipos import Bloque, mayusculas_ratio, termina_en_puntuacion

_RE_DIGITO = re.compile(r"^\s*\d+[.\)]")
_RE_ROMANO = re.compile(r"^\s*[IVXLCDM]+[.\)\s—-]", re.IGNORECASE)
_RE_ALFA_PREFIJO = re.compile(r"^\s*[A-Za-z][.\)]\s")
_RE_DELIMITADOR = re.compile(r"[:;—\-•*]")


@dataclass(frozen=True)
class FirmaForma:
    """Frozen + hasheable: SEQUITUR (Fase C) opera sobre secuencias de
    simbolos discretos, necesita poder usar la firma como clave de dict/set."""

    sangria_bin: int
    salto_vertical_bin: int
    longitud_linea_bin: int
    mask_digito: bool
    mask_numeral_romano: bool
    mask_prefijo_alfa: bool
    clase_capitalizacion: str  # "TODO_MAYUS" | "Titulo" | "normal" | "vacio"
    sufijo_puntuacion: str | None
    perfil_delimitadores: str
    ratio_numerico_bin: int  # cuantizado en bins de 0.1, para ser hasheable/estable
    ratio_simbolo_bin: int
    rango_fuente_bin: int | None  # relativo a la MEDIANA del documento, no absoluto


@dataclass
class EstadisticasDoc:
    mediana_font_size: float | None
    n_bloques: int


def _bin_sangria(indentacion_pt: float | None) -> int:
    if indentacion_pt is None:
        return -1  # bin especial "sin dato"
    return round(indentacion_pt / 6)  # cuantizado cada ~6pt


def _bin_espacio(espacio: float | None) -> int:
    if espacio is None:
        return -1
    return round(espacio / 4)  # cuantizado cada ~4pt


def _bin_longitud(texto: str) -> int:
    n = len(texto)
    if n < 20:
        return 0
    if n < 60:
        return 1
    if n < 120:
        return 2
    return 3


# Conectores tipicos del castellano que un "Titulo" (Title Case) deja en
# minuscula por convencion gramatical -- "Historia Critica del Peru" es un
# titulo valido pese a que "del" no empieza en mayuscula. Sin esta lista,
# cualquier titulo real con preposicion/articulo se clasificaria como
# "normal", perdiendo la senal (confirmado por el test de regresion).
_CONECTORES_TITULO = {"de", "del", "la", "las", "el", "los", "y", "en", "a", "un", "una"}


def _clase_capitalizacion(texto: str) -> str:
    t = texto.strip()
    if not t:
        return "vacio"
    letras = [c for c in t if c.isalpha()]
    if not letras:
        return "normal"
    ratio = mayusculas_ratio(t)
    if ratio > 0.9:
        return "TODO_MAYUS"
    # "Titulo": cada palabra de contenido (de mas de 2 letras, que no sea
    # un conector) empieza en mayuscula.
    palabras = [p for p in t.split() if len(p) > 2 and p[0].isalpha()
                and p.lower() not in _CONECTORES_TITULO]
    if palabras and all(p[0].isupper() for p in palabras):
        return "Titulo"
    return "normal"


def _perfil_delimitadores(texto: str) -> str:
    encontrados = sorted(set(_RE_DELIMITADOR.findall(texto)))
    return "".join(encontrados)


def _ratio_numerico(texto: str) -> float:
    if not texto:
        return 0.0
    return sum(1 for c in texto if c.isdigit()) / len(texto)


def _ratio_simbolo(texto: str) -> float:
    if not texto:
        return 0.0
    return sum(1 for c in texto if not c.isalnum() and not c.isspace()) / len(texto)


def _bin_fuente_relativo(font_size: float | None, mediana: float | None) -> int | None:
    """Bin relativo a la mediana del documento -- un tamano de 20pt es
    'grande' en un documento cuyo cuerpo es 10pt, pero 'normal' en una
    diapositiva cuyo cuerpo ya es 20pt. Comparar tamanos ABSOLUTOS entre
    documentos de distinto formato (PDF de lectura vs PPTX de clase) no
    tendria sentido -- por eso se normaliza contra la mediana propia."""
    if font_size is None or mediana is None or mediana <= 0:
        return None
    ratio = font_size / mediana
    if ratio < 0.85:
        return -1  # mas chico que el cuerpo tipico
    if ratio <= 1.15:
        return 0  # tamano de cuerpo normal
    if ratio <= 1.6:
        return 1  # subtitulo
    return 2  # titulo grande


def calcular_estadisticas_doc(bloques_doc: list[Bloque]) -> EstadisticasDoc:
    tamanos = [b.font_size for b in bloques_doc if b.font_size is not None]
    mediana = statistics.median(tamanos) if tamanos else None
    return EstadisticasDoc(mediana_font_size=mediana, n_bloques=len(bloques_doc))


def firmar_bloque(b: Bloque, stats: EstadisticasDoc) -> FirmaForma:
    texto = b.texto
    return FirmaForma(
        sangria_bin=_bin_sangria(b.indentacion_pt),
        salto_vertical_bin=_bin_espacio(b.espacio_vertical_antes),
        longitud_linea_bin=_bin_longitud(texto),
        mask_digito=bool(_RE_DIGITO.match(texto)),
        mask_numeral_romano=bool(_RE_ROMANO.match(texto)),
        mask_prefijo_alfa=bool(_RE_ALFA_PREFIJO.match(texto)),
        clase_capitalizacion=_clase_capitalizacion(texto),
        sufijo_puntuacion=termina_en_puntuacion(texto),
        perfil_delimitadores=_perfil_delimitadores(texto),
        ratio_numerico_bin=round(_ratio_numerico(texto) * 10),
        ratio_simbolo_bin=round(_ratio_simbolo(texto) * 10),
        rango_fuente_bin=_bin_fuente_relativo(b.font_size, stats.mediana_font_size),
    )


def secuencia_de_firmas(bloques_doc: list[Bloque]) -> list[FirmaForma]:
    stats = calcular_estadisticas_doc(bloques_doc)
    return [firmar_bloque(b, stats) for b in bloques_doc]


# ---------------------------------------------------------------------------
# Deteccion de nuisance: encabezados/pies repetidos por recurrencia
# posicional + similitud de texto. Se MARCA, nunca se borra -- el bloque
# se preserva integro en el registro fuente (ver paper, seccion 5.1).
# ---------------------------------------------------------------------------

def _jaccard_palabras(a: str, b: str) -> float:
    """Jaccard sobre PALABRAS, no caracteres. Un Jaccard de caracteres es
    casi inutil para discriminar textos cortos en un idioma dado: dos
    frases castellanas cualesquiera comparten casi todo el alfabeto
    (vocales, consonantes comunes, espacio, punto), asi que su Jaccard de
    caracteres sale artificialmente alto sin importar el contenido --
    confirmado empiricamente: 'regional. El caso del caucho.' vs
    'Cordillera de los Andes. Las' dio 0.80 de jaccard de caracteres pese
    a no compartir ni una palabra. Jaccard de palabras no tiene ese
    problema porque el vocabulario real de dos frases distintas casi
    nunca se solapa por accidente."""
    sa = set(a.lower().split())
    sb = set(b.lower().split())
    if not sa and not sb:
        return 1.0
    if not sa or not sb:
        return 0.0
    return len(sa & sb) / len(sa | sb)


def _bin_posicion_pagina(b: Bloque, alto_pagina: float = 792.0) -> int | None:
    """Bin grueso de posicion vertical relativa (arriba/medio/abajo de
    pagina) usando bbox.y0 -- alto_pagina default es carta US en puntos
    (792pt), suficiente para el bineo grueso que necesita esta heuristica;
    no se pretende exactitud por tamano real de cada PDF."""
    if b.bbox is None:
        return None
    y0 = b.bbox[1]
    frac = min(max(y0 / alto_pagina, 0.0), 1.0)
    if frac < 0.15:
        return 0  # arriba (header)
    if frac > 0.85:
        return 2  # abajo (footer)
    return 1  # medio


def detectar_nuisance(bloques_doc: list[Bloque], umbral_jaccard: float = 0.8,
                       min_ocurrencias: int = 3) -> set[str]:
    """Devuelve el conjunto de bloque_id marcados como candidatos molestos:
    texto casi identico (Jaccard de caracteres >= umbral) que recurre en
    la MISMA posicion relativa de pagina (bin arriba/medio/abajo) al
    menos `min_ocurrencias` veces en el documento."""
    from collections import defaultdict

    grupos: dict[int, list[Bloque]] = defaultdict(list)
    for b in bloques_doc:
        pos = _bin_posicion_pagina(b)
        if pos is None:
            continue
        grupos[pos].append(b)

    nuisance: set[str] = set()
    for _pos, candidatos in grupos.items():
        usados = set()
        for i, b1 in enumerate(candidatos):
            if b1.bloque_id in usados:
                continue
            similares = [b1]
            for b2 in candidatos[i + 1:]:
                if b2.bloque_id in usados:
                    continue
                if _jaccard_palabras(b1.texto, b2.texto) >= umbral_jaccard:
                    similares.append(b2)
            if len(similares) >= min_ocurrencias:
                for s in similares:
                    nuisance.add(s.bloque_id)
                    usados.add(s.bloque_id)
    return nuisance
