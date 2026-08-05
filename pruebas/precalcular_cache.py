# -*- coding: utf-8 -*-
"""
Pre-embebe las preguntas del banco y las guarda en cache.

    python pruebas/precalcular_cache.py

POR QUE
-------
Sin esto, evaluar el motor consume cuota de embeddings, y cuando la cuota se
agota la capa semantica devuelve None sin avisar: el gate cae a la senal
lexica y el resultado cambia. Medido: la MISMA configuracion dio 97,4% con
cuota y 90,9% sin ella.

Un numero que depende de la cuota del dia no se puede publicar ni comparar
entre corridas. Con el cache poblado, la evaluacion es deterministica y no
gasta cuota.

Es reanudable: si se corta, vuelve a correrlo y sigue con las que faltan.
"""
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pruebas.banco_preguntas import DENTRO, FUERA, ADVERSARIALES, INVARIANTES  # noqa: E402


def main():
    import pickle
    import semantico

    raiz = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    with open(os.path.join(raiz, "corpus", "indice.pkl"), "rb") as f:
        idx = pickle.load(f)

    if not semantico.disponible():
        print("La capa semantica no esta disponible (falta indice o clave).")
        return 1

    consultas = list(DENTRO) + list(FUERA)
    consultas += [q for q, _r, _resp in ADVERSARIALES if q.strip()]
    consultas += [q for q, _p, _d in INVARIANTES]
    consultas = list(dict.fromkeys(consultas))          # unicas, en orden

    ya = sum(1 for q in consultas if q in semantico._CACHE)
    print(f"{len(consultas)} consultas del banco; {ya} ya en cache")

    nuevas = fallos = 0
    for i, q in enumerate(consultas, 1):
        if q in semantico._CACHE:
            continue
        v = semantico.similitud_maxima(q, idx)
        if v is None:
            fallos += 1
            print(f"  [{i}/{len(consultas)}] FALLO  {q[:52]}")
            if fallos >= 5:
                print("\n5 fallos seguidos: la cuota esta agotada.")
                print("Guardando lo conseguido; vuelve a correr mas tarde.")
                break
        else:
            nuevas += 1
            fallos = 0
            print(f"  [{i}/{len(consultas)}] {v:.3f}  {q[:52]}")
        time.sleep(1.6)                                 # respeta 40/min

    guardado = semantico.guardar_cache()
    total = sum(1 for q in consultas if q in semantico._CACHE)
    print(f"\n{nuevas} nuevas embebidas · {total}/{len(consultas)} en cache")
    print(f"cache {'guardado' if guardado else 'sin cambios'}: {semantico.RUTA_CACHE}")
    if total < len(consultas):
        print(f"\nFaltan {len(consultas)-total}. Vuelve a correr este script")
        print("cuando se renueve la cuota para completarlo.")
        return 1
    print("\nBanco completo en cache: la evaluacion ya es reproducible")
    print("y no consume cuota.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
