# -*- coding: utf-8 -*-
"""Fase 4: calidad de recuperacion SIN generacion, contra el mismo codigo
FORMA-IR que corre en produccion (los campos internos -- p_unit, p_doc,
unidad_id, cobertura -- no se exponen por la API publica, y la regla de
la auditoria es no inventar endpoints).

Calcula ranking documental, evidencia, procedencia, calibracion y packing.
Salida: results/retrieval_quality.json
"""
import json, math, os, statistics, sys, time

RAIZ = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
sys.path.insert(0, RAIZ)
from forma_ir.comparar_con_produccion import preparar_indice, responder_consulta

BASE = os.path.join(RAIZ, "tests", "stress")
RESULTS = os.path.join(BASE, "results")


def cargar(nombre):
    with open(os.path.join(BASE, "datasets", nombre), encoding="utf-8") as f:
        return [json.loads(l) for l in f if l.strip()]


def dcg(rels):
    return sum(r / math.log2(i + 2) for i, r in enumerate(rels))


def main(limite=None):
    gold = cargar("gold_queries.jsonl")
    if limite:
        gold = gold[:limite]
    print(f"Preparando indice FORMA-IR...")
    t0 = time.time()
    indice = preparar_indice()
    t_indice = time.time() - t0
    print(f"  indice listo en {t_indice:.1f}s")

    unidades_validas = {u.unidad_id for u in indice["todas_las_unidades"]}
    docs_validos = set(indice["bloques_por_doc"].keys())
    unidad_por_id = {u.unidad_id: u for u in indice["todas_las_unidades"]}

    filas = []
    problemas_procedencia = []
    problemas_calibracion = []

    for g in gold:
        t0 = time.time()
        r = responder_consulta(g["question"], indice)
        lat = time.time() - t0
        doc_ids = [d["doc_id"] for d in r["documentos"]]
        unidades = r["unidades_empaquetadas"]
        unit_ids = [u["unidad_id"] for u in unidades]

        # --- procedencia (HARD_GATE) ---
        for u in unidades:
            if u["doc_id"] not in docs_validos:
                problemas_procedencia.append({"query_id": g["query_id"], "tipo": "doc_inexistente", "valor": u["doc_id"]})
            if u["unidad_id"] not in unidades_validas:
                problemas_procedencia.append({"query_id": g["query_id"], "tipo": "unidad_inexistente", "valor": u["unidad_id"]})
            if not u.get("texto"):
                problemas_procedencia.append({"query_id": g["query_id"], "tipo": "texto_vacio", "valor": u["unidad_id"]})
            else:
                # texto verificable contra la fuente real
                real = unidad_por_id.get(u["unidad_id"])
                if real is not None and u["texto"] != real.texto:
                    problemas_procedencia.append({"query_id": g["query_id"], "tipo": "texto_no_coincide_fuente", "valor": u["unidad_id"]})
            pag = u.get("pagina_inicio")
            if pag is not None and (not isinstance(pag, int) or pag < 0):
                problemas_procedencia.append({"query_id": g["query_id"], "tipo": "pagina_invalida", "valor": str(pag)})

        # --- calibracion (HARD_GATE) ---
        for d in r["documentos"]:
            p = d["p_doc"]
            if p is None or isinstance(p, bool) or math.isnan(p) or math.isinf(p) or not (0.0 <= p <= 1.0):
                problemas_calibracion.append({"query_id": g["query_id"], "tipo": "p_doc_fuera_rango_o_nan", "valor": str(p)})
            if not isinstance(d["m_d"], int) or d["m_d"] < 1:
                problemas_calibracion.append({"query_id": g["query_id"], "tipo": "m_d_invalido", "valor": str(d["m_d"])})

        gold_docs = set(g["gold_document_ids"])
        gold_units = set(g["gold_unit_ids"])
        rank_doc = next((i + 1 for i, d in enumerate(doc_ids) if d in gold_docs), None)

        fila = {
            "query_id": g["query_id"], "category": g["category"], "difficulty": g["difficulty"],
            "answerable": g["answerable"], "latencia_s": round(lat, 4),
            "n_docs": len(doc_ids), "n_unidades": len(unidades),
            "doc_top1": doc_ids[0] if doc_ids else None,
            "rank_gold_doc": rank_doc,
            "doc_recall_1": bool(rank_doc == 1),
            "doc_recall_3": bool(rank_doc is not None and rank_doc <= 3),
            "doc_recall_5": bool(rank_doc is not None and rank_doc <= 5),
            "rr": (1.0 / rank_doc) if rank_doc else 0.0,
            "ndcg_5": (dcg([1.0 if d in gold_docs else 0.0 for d in doc_ids[:5]]) / dcg([1.0])) if gold_docs else None,
            "evidence_recall_1": bool(unit_ids[:1] and set(unit_ids[:1]) & gold_units),
            "evidence_recall_3": bool(set(unit_ids[:3]) & gold_units),
            "evidence_recall_5": bool(set(unit_ids[:5]) & gold_units),
            "evidence_precision": (len(set(unit_ids) & gold_units) / len(unit_ids)) if unit_ids else 0.0,
            "gold_span_contenido": bool(gold_units & set(unit_ids)),
            "tokens_totales": r["tokens_totales"],
            "fraccion_evidencia_retenida": r["fraccion_evidencia_retenida"],
            "abstuvo": len(unidades) == 0,
            "p_doc_top1": r["documentos"][0]["p_doc"] if r["documentos"] else None,
        }
        filas.append(fila)

    respondibles = [f for f in filas if f["answerable"] and f["query_id"] not in {}]
    con_gold = [f for f in respondibles if f["rank_gold_doc"] is not None or True]
    con_gold = [f for f in respondibles if any(g["query_id"] == f["query_id"] and g["gold_document_ids"] for g in gold)]
    no_respondibles = [f for f in filas if not f["answerable"]]

    def pct(xs):
        return round(100.0 * sum(1 for x in xs if x) / len(xs), 2) if xs else None

    resumen = {
        "n_consultas": len(filas),
        "indice_build_s": round(t_indice, 2),
        "ranking_documental": {
            "top1_accuracy_pct": pct([f["doc_recall_1"] for f in con_gold]),
            "recall_at_1_pct": pct([f["doc_recall_1"] for f in con_gold]),
            "recall_at_3_pct": pct([f["doc_recall_3"] for f in con_gold]),
            "recall_at_5_pct": pct([f["doc_recall_5"] for f in con_gold]),
            "mrr": round(statistics.mean([f["rr"] for f in con_gold]), 4) if con_gold else None,
            "ndcg_at_5": round(statistics.mean([f["ndcg_5"] for f in con_gold if f["ndcg_5"] is not None]), 4) if con_gold else None,
            "mean_rank_primer_relevante": round(statistics.mean([f["rank_gold_doc"] for f in con_gold if f["rank_gold_doc"]]), 2) if any(f["rank_gold_doc"] for f in con_gold) else None,
        },
        "evidencia": {
            "evidence_recall_at_1_pct": pct([f["evidence_recall_1"] for f in con_gold]),
            "evidence_recall_at_3_pct": pct([f["evidence_recall_3"] for f in con_gold]),
            "evidence_recall_at_5_pct": pct([f["evidence_recall_5"] for f in con_gold]),
            "evidence_precision_media": round(statistics.mean([f["evidence_precision"] for f in con_gold]), 4) if con_gold else None,
            "gold_span_contenido_pct": pct([f["gold_span_contenido"] for f in con_gold]),
            "tokens_recuperados_mediana": statistics.median([f["tokens_totales"] for f in filas]) if filas else None,
            "unidades_por_consulta_media": round(statistics.mean([f["n_unidades"] for f in filas]), 2) if filas else None,
        },
        "abstencion": {
            "no_respondibles": len(no_respondibles),
            "rechazo_pct": pct([f["abstuvo"] for f in no_respondibles]),
            "_nota": "rechazo = 0 unidades devueltas. FORMA-IR delega la abstencion textual al agente via avisos; ver reporte.",
        },
        "procedencia": {
            "problemas": len(problemas_procedencia),
            "validez_pct": round(100.0 * (1 - len(problemas_procedencia) / max(sum(f["n_unidades"] for f in filas), 1)), 2),
            "detalle": problemas_procedencia[:20],
        },
        "calibracion": {"problemas": len(problemas_calibracion), "detalle": problemas_calibracion[:20]},
        "latencia_local_s": {
            "p50": round(statistics.median([f["latencia_s"] for f in filas]), 4),
            "p95": round(sorted(f["latencia_s"] for f in filas)[int(0.95 * len(filas))], 4) if len(filas) > 1 else None,
        },
        "por_categoria": {},
    }
    cats = sorted({f["category"] for f in filas})
    for c in cats:
        sub = [f for f in filas if f["category"] == c]
        sub_gold = [f for f in sub if f["answerable"]]
        resumen["por_categoria"][c] = {
            "n": len(sub),
            "doc_recall_3_pct": pct([f["doc_recall_3"] for f in sub_gold]) if sub_gold else None,
            "evidence_recall_5_pct": pct([f["evidence_recall_5"] for f in sub_gold]) if sub_gold else None,
            "abstuvo_pct": pct([f["abstuvo"] for f in sub]),
            "latencia_p50_s": round(statistics.median([f["latencia_s"] for f in sub]), 4),
        }

    os.makedirs(RESULTS, exist_ok=True)
    with open(os.path.join(RESULTS, "retrieval_quality.json"), "w", encoding="utf-8") as f:
        json.dump({"resumen": resumen, "filas": filas}, f, ensure_ascii=False, indent=2)
    print(json.dumps(resumen, ensure_ascii=False, indent=2)[:3000])


if __name__ == "__main__":
    main(int(sys.argv[1]) if len(sys.argv) > 1 else None)
