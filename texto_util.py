# -*- coding: utf-8 -*-
"""Utilidades de texto compartidas por el indexador y el recuperador.

Vive en su propio modulo a proposito: el vectorizador TF-IDF guarda una
referencia al tokenizador dentro del indice serializado, y si esa funcion
estuviera definida en un script ejecutable, el indice solo podria abrirse
desde ese mismo script.
"""
import re, unicodedata

STOP = set("""a al algo algunas algunos ante antes como con contra cual cuando de del desde donde dos el la
los las un una unos unas y o u e en entre era erais eran es esa ese eso esta este esto estos estas fue fueron
ha han hasta hay la le les lo mas más me mi mucho muy no nos o os otra otro para pero poco por porque que
quien se sea ser si sin sobre solo son su sus también tanto te tiene tienen todo todos tras un una uno y ya
cual cuales the of and to in is it that this for on as with be by an are from at or was were which not but
have has""".split())


def normtxt(s):
    """Minusculas sin tildes, para que 'demografía' y 'demografia' coincidan."""
    s = unicodedata.normalize("NFKD", s.lower())
    return "".join(c for c in s if not unicodedata.combining(c))


def tokenizar(s):
    """Tokens alfanumericos de mas de 2 caracteres, sin stopwords."""
    return [t for t in re.findall(r"[a-z0-9]+", normtxt(s)) if len(t) > 2 and t not in STOP]
