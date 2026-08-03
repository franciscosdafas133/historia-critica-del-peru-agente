# -*- coding: utf-8 -*-
"""
Utilidad para anotadores: calcula normalized_text + text_hash de un
fragmento de evidencia, usando el mismo normalizador que el indice real
(texto_util.normtxt), para que el hash coincida con lo que produciria el
sistema si ese mismo texto estuviera en un bloque indexado.

Uso:
    python eval/data/calcular_hash.py "texto de la evidencia aqui"
"""
import sys, os, hashlib

RAIZ = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, RAIZ)

from texto_util import normtxt


def main():
    if len(sys.argv) < 2:
        print('Uso: python calcular_hash.py "texto de la evidencia"')
        sys.exit(1)
    texto = " ".join(sys.argv[1:])
    normalizado = normtxt(texto)
    h = hashlib.sha256(normalizado.encode("utf-8")).hexdigest()
    print("normalized_text:", normalizado)
    print("text_hash: sha256:" + h)


if __name__ == "__main__":
    main()
