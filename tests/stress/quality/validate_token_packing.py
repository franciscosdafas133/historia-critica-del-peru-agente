# -*- coding: utf-8 -*-
"""Fase 4 (packing): curva reduccion de tokens vs evidencia conservada.
Barre epsilon = 0.00 .. 0.15 sobre las canarias y mide si el gold span
sobrevive al empaquetado. Local, sin LLM.
"""
import json, os, statistics, sys

RAIZ = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
sys.path.insert(0, RAIZ)
from forma_ir.comparar_con_produccion import preparar_indice, responder_consulta
from forma_ir.evidencia import tokenizar

BASE = os.path.join(RAIZ, "tests", "stress")
EPSILONS = [0.0, 0.02, 0.05, 0.10, 0.15]


def main():
    with open(os.path.join(BASE, "datasets", "gold_queries.jsonl"), encoding="utf-8") as f:
        gold = [json.loads(l) for l in f if l.strip()]
    muestra = [g for g in gold if g["answerable"] and g["gold_unit_ids"]][:60]
    print(f"Preparando indice... ({len(muestra)} consultas x {len(EPSILONS)} epsilons)")
    indice = preparar_indice()

    filas = []
    for eps in EPSILONS:
        tokens_antes_l, tokens_desp_l, retenidas, gold_ok, n_unid = [], [], [], [], []
        for g in muestra:
            r = responder_consulta(g["question"], indice, epsilon=eps)
            unidades = r["unidades_empaquetadas"]
            # tokens_antes = suma de tokens de las CANDIDATAS consideradas
            # (aproximado por las unidades del top de documentos antes del packing:
            # se reconstruye como suma de la evidencia disponible en los docs top)
            desp = r["tokens_totales"]
            antes = sum(len(tokenizar(u["texto"])) for u in unidades) or desp
            tokens_antes_l.append(antes)
            tokens_desp_l.append(desp)
            retenidas.append(r["fraccion_evidencia_retenida"])
            gold_ok.append(bool(set(u["unidad_id"] for u in unidades) & set(g["gold_unit_ids"])))
            n_unid.append(len(unidades))
        filas.append({
            "epsilon": eps,
            "tokens_mediana": statistics.median(tokens_desp_l),
            "unidades_media": round(statistics.mean(n_unid), 2),
            "fraccion_evidencia_retenida_media": round(statistics.mean(retenidas), 4),
            "gold_span_conservado_pct": round(100.0 * sum(gold_ok) / len(gold_ok), 2),
        })
        print(f"  eps={eps:.2f} tokens_med={filas[-1]['tokens_mediana']:.0f} "
              f"unid={filas[-1]['unidades_media']} retenida={filas[-1]['fraccion_evidencia_retenida_media']} "
              f"gold_conservado={filas[-1]['gold_span_conservado_pct']}%")

    base = filas[0]
    for f_ in filas:
        f_["delta_gold_pp_vs_eps0"] = round(f_["gold_span_conservado_pct"] - base["gold_span_conservado_pct"], 2)
        f_["reduccion_tokens_pct_vs_eps0"] = round(100.0 * (base["tokens_mediana"] - f_["tokens_mediana"]) / base["tokens_mediana"], 2) if base["tokens_mediana"] else 0.0

    with open(os.path.join(BASE, "results", "token_packing.json"), "w", encoding="utf-8") as f:
        json.dump({"n_consultas": len(muestra), "curva": filas}, f, ensure_ascii=False, indent=2)
    print("\n-> results/token_packing.json")


if __name__ == "__main__":
    main()
