# -*- coding: utf-8 -*-
"""
Calibra los umbrales semanticos del gate contra el banco de 77 preguntas.

    python pruebas/calibrar_semantico.py

Mide la similitud semantica maxima de cada pregunta con el corpus y reporta
la curva completa de umbrales: cuantas preguntas del curso se perderian y
cuantas ajenas se colarian en cada punto.

No elige por su cuenta: imprime la curva para que la decision quede a la
vista y sea revisable, como pide la seccion 12 del paper ("umbral calibrado
en validacion; nunca fijar 0,5 por defecto").

CUIDADO: hace una llamada de embedding por pregunta (77 en total).
"""
import os
import statistics
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pruebas.banco_preguntas import DENTRO, FUERA, FAMILIAS_FUERA  # noqa: E402


def main():
    import pickle
    import semantico

    raiz = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    with open(os.path.join(raiz, "corpus", "indice.pkl"), "rb") as f:
        idx = pickle.load(f)

    if not semantico.disponible():
        print("La capa semantica no esta disponible.")
        print("Falta corpus/embeddings.npz (corre indexar_embeddings.py) o la")
        print("clave GEMINI_API_KEY en .env.")
        return 1

    print("=" * 78)
    print("CALIBRACION DE LA SENAL SEMANTICA")
    print("=" * 78)
    print(f"  {len(DENTRO)} preguntas del curso + {len(FUERA)} ajenas")
    print(f"  {len(DENTRO) + len(FUERA)} llamadas de embedding\n")

    d_sims, f_sims = [], []
    for q in DENTRO:
        s = semantico.similitud_maxima(q, idx)
        if s is not None:
            d_sims.append((s, q))
        time.sleep(0.35)
    for q in FUERA:
        s = semantico.similitud_maxima(q, idx)
        if s is not None:
            f_sims.append((s, q))
        time.sleep(0.35)

    if not d_sims or not f_sims:
        print("No se obtuvieron similitudes (¿cuota agotada?).")
        return 1

    d = [s for s, _ in d_sims]
    f = [s for s, _ in f_sims]
    print(f"  DENTRO  mediana {statistics.median(d):.3f}  "
          f"min {min(d):.3f}  max {max(d):.3f}")
    print(f"  FUERA   mediana {statistics.median(f):.3f}  "
          f"min {min(f):.3f}  max {max(f):.3f}")

    print(f"\n  {'umbral':>8s}{'pierde del curso':>19s}{'deja pasar ajenas':>20s}")
    for u in [x / 100 for x in range(45, 86, 2)]:
        perdidas = sum(1 for s in d if s < u)
        pasan = sum(1 for s in f if s >= u)
        marca = ""
        if perdidas == 0:
            marca = "  <- no pierde ninguna del curso"
        print(f"  {u:8.2f}{perdidas:>12d}/{len(d):<6d}{pasan:>12d}/{len(f):<6d}{marca}")

    print("\n  Las mas bajas del curso (definen el umbral inferior seguro):")
    for s, q in sorted(d_sims)[:6]:
        print(f"     {s:.3f}  {q[:58]}")

    print("\n  Las mas altas de las ajenas (las que cuesta rechazar):")
    for s, q in sorted(f_sims, reverse=True)[:8]:
        fam = next((n for n, qs in FAMILIAS_FUERA.items() if q in qs), "?")
        print(f"     {s:.3f}  [{fam[:22]:24s}] {q[:44]}")

    seguro = min(d)
    cuelan = sum(1 for s in f if s >= seguro)
    print(f"\n  Umbral que no pierde ninguna del curso: {seguro:.3f}")
    print(f"  A ese umbral se colarian {cuelan} de {len(f)} ajenas.")
    print("\n  Sugerencia para ceres_omega.py:")
    print(f"     UMBRAL_SIM_BAJA = {max(0.0, seguro - 0.02):.2f}"
          "   (por debajo: rechazar sin mirar lo lexico)")
    p75 = sorted(f)[int(len(f) * 0.75)]
    print(f"     UMBRAL_SIM_ALTA = {max(p75, statistics.median(d)):.2f}"
          "   (por encima: aceptar sin mirar lo lexico)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
