# -*- coding: utf-8 -*-
"""
Anotacion de bloques de oro: el banco que exige la seccion 8.3 del paper.

    python pruebas/anotar_oro.py --candidatos          # genera el borrador
    python pruebas/anotar_oro.py --medir               # mide contra lo anotado

POR QUE HACE FALTA
------------------
Todo lo medido hasta ahora (gate, latencia, invariantes) dice si el motor
RESPONDE cuando debe. Ninguna de esas metricas dice si la evidencia que trae
es la CORRECTA. Un motor puede acertar el 100% de las decisiones y recuperar
fragmentos irrelevantes.

Eso ya paso una vez en este proyecto: FORMA-IR parecia bueno y perdia contra
BM25 puro (96,5% vs 98,5% Recall@1). El banco que lo detecto se borro en
c724b66. Esto lo reconstruye.

COMO SE USA
-----------
1. `--candidatos` escribe pruebas/oro.json con los bloques que el motor actual
   recupera para cada pregunta, marcados como "pendiente".

2. UNA PERSONA revisa ese archivo y marca cada bloque como:
     "si"    el bloque contiene evidencia necesaria para responder
     "no"    el bloque es irrelevante o solo comparte palabras
     "extra" el bloque ayuda pero no es imprescindible

   Puede anadir bloques que el motor NO recupero (campo "faltantes"): son los
   que revelan fallos de recall, y son los mas valiosos del banco.

3. `--medir` calcula, contra esa anotacion:
     Recall de bloques de oro   ¿trae todo lo necesario?  (META A del paper)
     Precision                  ¿cuanto de lo que trae sirve?
     Completitud estricta       ¿trae TODOS los de oro?   <- metrica principal

SESGO CONOCIDO Y DECLARADO
--------------------------
Anotar sobre lo que el motor recupera arrastra un sesgo: los bloques buenos
que nunca recupera no aparecen como candidatos, asi que el recall medido sale
optimista. El campo "faltantes" existe para corregirlo, pero solo funciona si
quien anota busca activamente en el corpus, no solo revisa la lista.

El paper (8.3) exige ademas splits por documento y anotacion ANTES de ejecutar
el sistema. Esto no cumple ninguna de las dos: es un banco de trabajo honesto
sobre sus limites, no el banco definitivo.
"""
import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

RUTA = os.path.join(os.path.dirname(os.path.abspath(__file__)), "oro.json")

# Subconjunto del banco: preguntas del temario donde la evidencia correcta es
# identificable sin ambiguedad. No se anotan las administrativas (su respuesta
# esta en un unico bloque del cronograma y no discriminan un motor de otro).
PREGUNTAS_ORO = [
    "¿Por qué colapsó la población andina en el siglo XVI?",
    "¿Qué dice Contreras sobre el centralismo?",
    "¿Por qué las haciendas azucareras originaron el aprismo?",
    "¿Qué significó la división norte patriota y sur realista?",
    "¿Por qué Lima concentró el poder frente al resto del país?",
    "¿Qué dice Klarén sobre el APRA?",
    "¿Qué fue la transición demográfica en el Perú?",
    "¿Cómo afectaron las epidemias coloniales a la población indígena?",
    "¿Qué papel tuvo la geografía en la economía peruana?",
    "¿Qué dice Aldana sobre las regiones vivas y activas?",
    "¿Qué relación hay entre glaciares y el fenómeno del Niño?",
    "¿Qué plantea O'Phelan sobre la independencia?",
    "¿Qué son las ciudades intermedias?",
    "¿Qué fue la disputa de jurisdicciones según Sobrevilla?",
    "¿Por qué varían tanto las cifras de población prehispánica?",
    "¿Qué es el concepto de nación según Contreras?",
    "¿Cómo influyó el cambio climático en los desastres naturales?",
    "¿Qué es la nación radical según Renique?",
    "¿Qué fue el pluralismo médico en el Perú colonial?",
    "¿Cómo se formaron las haciendas azucareras del norte?",
]


def cargar_idx():
    import pickle
    raiz = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    with open(os.path.join(raiz, "corpus", "indice.pkl"), "rb") as f:
        return pickle.load(f)


def generar_candidatos():
    from ceres_omega import recuperar
    idx = cargar_idx()

    previo = {}
    if os.path.exists(RUTA):
        with open(RUTA, encoding="utf-8") as f:
            for e in json.load(f)["preguntas"]:
                previo[e["pregunta"]] = {b["bloque_id"]: b["oro"]
                                         for b in e["bloques"]}
        print(f"anotacion previa encontrada: se conservan las etiquetas ya puestas")

    salida = []
    for q in PREGUNTAS_ORO:
        r = recuperar(q, idx)
        bloques = []
        for p in r["paquetes"]:
            bid = p["bloque_id"]
            bloques.append({
                "bloque_id": bid,
                "documento": p["doc"],
                "ubicacion": p["paginas"],
                "extracto": p["texto"][:260].replace("\n", " ").strip(),
                "oro": previo.get(q, {}).get(bid, "pendiente"),
            })
        salida.append({
            "pregunta": q,
            "bloques": bloques,
            "faltantes": [],
            "nota": "",
        })

    doc = {
        "_instrucciones": {
            "oro": "marca cada bloque: 'si' (evidencia necesaria), "
                   "'no' (irrelevante), 'extra' (ayuda pero no imprescindible)",
            "faltantes": "bloque_id de bloques del corpus que DEBERIAN estar "
                         "y el motor no trajo. Son los mas valiosos: revelan "
                         "fallos de recall que esta lista no puede mostrar.",
            "sesgo": "esta lista solo contiene lo que el motor YA recupera. "
                     "Anotar solo aqui da un recall optimista.",
        },
        "preguntas": salida,
    }
    with open(RUTA, "w", encoding="utf-8") as f:
        json.dump(doc, f, ensure_ascii=False, indent=1)

    pend = sum(1 for e in salida for b in e["bloques"] if b["oro"] == "pendiente")
    print(f"escrito {RUTA}")
    print(f"  {len(salida)} preguntas, "
          f"{sum(len(e['bloques']) for e in salida)} bloques candidatos")
    print(f"  {pend} pendientes de anotar")
    print("\nAbre el archivo y marca cada bloque. Luego: --medir")


def medir():
    from ceres_omega import recuperar
    if not os.path.exists(RUTA):
        print(f"No existe {RUTA}. Corre primero: --candidatos")
        return 1
    with open(RUTA, encoding="utf-8") as f:
        doc = json.load(f)

    anotadas = []
    for e in doc["preguntas"]:
        oro = {b["bloque_id"] for b in e["bloques"] if b["oro"] == "si"}
        oro |= set(e.get("faltantes") or [])
        pendientes = sum(1 for b in e["bloques"] if b["oro"] == "pendiente")
        if oro and not pendientes:
            anotadas.append((e["pregunta"], oro))

    if not anotadas:
        pend = sum(1 for e in doc["preguntas"]
                   for b in e["bloques"] if b["oro"] == "pendiente")
        print(f"Todavia no hay preguntas anotadas por completo ({pend} bloques "
              f"pendientes).")
        print("Marca al menos una pregunta entera y vuelve a correr --medir.")
        return 1

    idx = cargar_idx()
    print("=" * 78)
    print(f"METRICAS CONTRA BLOQUES DE ORO  ({len(anotadas)} preguntas anotadas)")
    print("=" * 78)
    print(f"\n{'recall':>8s}{'prec':>8s}{'completo':>10s}  pregunta")

    recalls, precs, completos = [], [], 0
    for q, oro in anotadas:
        r = recuperar(q, idx)
        traidos = {p["bloque_id"] for p in r["paquetes"]}
        aciertos = oro & traidos
        rec = len(aciertos) / len(oro)
        pre = len(aciertos) / len(traidos) if traidos else 0.0
        comp = oro <= traidos
        recalls.append(rec)
        precs.append(pre)
        completos += int(comp)
        print(f"{rec:8.2f}{pre:8.2f}{'SI' if comp else 'no':>10s}  {q[:46]}")

    n = len(anotadas)
    print(f"\n  Recall de bloques de oro    {sum(recalls)/n:.3f}"
          "    (META A del paper: >= 0.90)")
    print(f"  Precision                   {sum(precs)/n:.3f}"
          "    (cuanto de lo traido sirve)")
    print(f"  Completitud estricta        {completos/n:.3f}"
          f"    ({completos}/{n} traen TODA la evidencia)")
    print("\n  La completitud estricta es la metrica principal del paper: la")
    print("  proporcion de consultas cuyo conjunto recuperado contiene toda")
    print("  la evidencia necesaria.")
    print("\n  SESGO: si solo se anoto sobre lo que el motor ya recuperaba,")
    print("  el recall sale optimista. El campo 'faltantes' lo corrige.")
    return 0


def main():
    ap = argparse.ArgumentParser(description="Banco de bloques de oro")
    ap.add_argument("--candidatos", action="store_true",
                    help="generar/actualizar el borrador de anotacion")
    ap.add_argument("--medir", action="store_true",
                    help="medir el motor contra lo ya anotado")
    a = ap.parse_args()
    if a.candidatos:
        generar_candidatos()
        return 0
    if a.medir:
        return medir()
    ap.print_help()
    return 0


if __name__ == "__main__":
    sys.exit(main())
