# -*- coding: utf-8 -*-
"""Banco RAPIDO para iterar sobre el ranking (subconjunto del estres completo).

Mide lo esencial en ~1 min: acierto global, acierto por tamaño de documento,
saturacion de p_doc y estabilidad. Sirve para no esperar el estres completo
en cada iteracion; la validacion final SIEMPRE se hace con
stress_retrieval_core.py sobre 400 consultas.
"""
import json, os, random, re, statistics, sys, time
from collections import defaultdict

RAIZ = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
sys.path.insert(0, RAIZ)
from forma_ir.comparar_con_produccion import preparar_indice, responder_consulta

N = int(os.environ.get("BENCH_N", "150"))


def main(etiqueta="actual"):
    rng = random.Random(7)
    indice = preparar_indice()
    unidades = indice["todas_las_unidades"]
    tam = defaultdict(int)
    for u in unidades:
        tam[u.doc_id] += 1

    cand = [u for u in unidades if len(u.texto.split()) >= 30]
    rng.shuffle(cand)
    muestra = cand[:N]

    filas, lats = [], []
    for u in muestra:
        q = " ".join(re.sub(r"\s+", " ", u.texto).split()[2:12])
        t = time.time(); r = responder_consulta(q, indice); lats.append(time.time() - t)
        rk = next((i for i, d in enumerate(r["documentos"], 1) if d["doc_id"] == u.doc_id), None)
        filas.append({"doc": u.doc_id, "tam": tam[u.doc_id], "rank": rk,
                      "unidad_ok": u.unidad_id in [x["unidad_id"] for x in r["unidades_empaquetadas"]],
                      "p_top1": r["documentos"][0]["p_doc"] if r["documentos"] else None})

    def pct(c, base):
        return round(100.0 * sum(1 for f in base if c(f)) / len(base), 1) if base else None

    res = {"etiqueta": etiqueta, "n": len(filas),
           "recall_1": pct(lambda f: f["rank"] == 1, filas),
           "recall_3": pct(lambda f: f["rank"] and f["rank"] <= 3, filas),
           "recall_5": pct(lambda f: f["rank"] and f["rank"] <= 5, filas),
           "unidad_exacta": pct(lambda f: f["unidad_ok"], filas),
           "ausente_top5": pct(lambda f: f["rank"] is None, filas),
           "saturado_1.0": pct(lambda f: f["p_top1"] is not None and f["p_top1"] >= 0.999, filas),
           "lat_p50_ms": round(statistics.median(lats) * 1000, 1),
           "por_tamano": {}}
    for lo, hi, nom in [(1, 10, "1-10"), (11, 50, "11-50"), (51, 150, "51-150"), (151, 400, "151-400"), (401, 10**9, "401+")]:
        sub = [f for f in filas if lo <= f["tam"] <= hi]
        if sub:
            res["por_tamano"][nom] = {"n": len(sub), "r1": pct(lambda f: f["rank"] == 1, sub),
                                       "r3": pct(lambda f: f["rank"] and f["rank"] <= 3, sub)}
    print(json.dumps(res, ensure_ascii=False, indent=2))
    hist = os.path.join(RAIZ, "tests", "stress", "results", "bench_historial.jsonl")
    with open(hist, "a", encoding="utf-8") as f:
        f.write(json.dumps(res, ensure_ascii=False) + "\n")
    return res


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "actual")
