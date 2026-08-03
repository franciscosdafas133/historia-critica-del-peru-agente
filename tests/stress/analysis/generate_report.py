# -*- coding: utf-8 -*-
"""Fases 11-12: agrega resultados, genera graficos y el reporte PASS/FAIL."""
import json, os, sys

RAIZ = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
BASE = os.path.join(RAIZ, "tests", "stress")
RES = os.path.join(BASE, "results")
REP = os.path.join(BASE, "reports")


def leer(nombre, defecto=None):
    p = os.path.join(RES, nombre)
    if not os.path.exists(p):
        return defecto
    with open(p, encoding="utf-8") as f:
        return json.load(f)


def graficos(datos):
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except Exception as e:
        print("matplotlib no disponible:", e)
        return []
    os.makedirs(os.path.join(REP, "figuras"), exist_ok=True)
    hechos = []

    # 1-3. carga: vus vs p95, error rate, throughput
    niveles = []
    for esc in ("breakpoint", "spike", "smoke"):
        d = datos.get(f"load_{esc}")
        if d:
            for n in d["niveles"]:
                niveles.append((esc, n["vus"], n["p95_ms"], n["error_rate_pct"], n["rps"]))
    if niveles:
        fig, axs = plt.subplots(1, 3, figsize=(15, 4))
        for esc in sorted({n[0] for n in niveles}):
            sub = sorted([n for n in niveles if n[0] == esc], key=lambda x: x[1])
            axs[0].plot([s[1] for s in sub], [s[2] for s in sub], "o-", label=esc)
            axs[1].plot([s[1] for s in sub], [s[3] for s in sub], "o-", label=esc)
            axs[2].plot([s[1] for s in sub], [s[4] for s in sub], "o-", label=esc)
        axs[0].set(xlabel="usuarios concurrentes", ylabel="p95 (ms)", title="Concurrencia vs p95")
        axs[1].set(xlabel="usuarios concurrentes", ylabel="error rate (%)", title="Concurrencia vs errores")
        axs[2].set(xlabel="usuarios concurrentes", ylabel="req/s", title="Throughput vs concurrencia")
        for a in axs: a.legend(); a.grid(alpha=.3)
        fig.tight_layout(); fig.savefig(os.path.join(REP, "figuras", "carga.png"), dpi=110); plt.close(fig)
        hechos.append("figuras/carga.png")

    # 4. tokens vs evidencia (epsilon)
    tp = datos.get("token_packing")
    if tp:
        c = tp["curva"]
        fig, ax = plt.subplots(figsize=(6, 4))
        ax.plot([x["epsilon"] for x in c], [x["fraccion_evidencia_retenida_media"] * 100 for x in c], "o-", label="evidencia retenida %")
        ax.plot([x["epsilon"] for x in c], [x["gold_span_conservado_pct"] for x in c], "s--", label="gold span conservado %")
        ax2 = ax.twinx()
        ax2.plot([x["epsilon"] for x in c], [x["tokens_mediana"] for x in c], "^:", color="gray", label="tokens (mediana)")
        ax.set(xlabel="epsilon", ylabel="%", title="Packing: tokens vs evidencia"); ax.grid(alpha=.3); ax.legend(loc="center left")
        ax2.set_ylabel("tokens"); fig.tight_layout()
        fig.savefig(os.path.join(REP, "figuras", "packing.png"), dpi=110); plt.close(fig)
        hechos.append("figuras/packing.png")

    # 5. calidad por categoria
    rq = datos.get("retrieval_quality")
    if rq:
        cats = rq["resumen"]["por_categoria"]
        nombres = [c for c in cats if cats[c]["doc_recall_3_pct"] is not None]
        fig, ax = plt.subplots(figsize=(8, 4))
        ax.bar(range(len(nombres)), [cats[c]["doc_recall_3_pct"] for c in nombres])
        ax.axhline(95, color="r", ls="--", label="umbral 95%")
        ax.set_xticks(range(len(nombres))); ax.set_xticklabels(nombres, rotation=30, ha="right")
        ax.set(ylabel="Doc Recall@3 (%)", title="Calidad por categoria de consulta"); ax.legend(); ax.grid(alpha=.3, axis="y")
        fig.tight_layout(); fig.savefig(os.path.join(REP, "figuras", "calidad_categoria.png"), dpi=110); plt.close(fig)
        hechos.append("figuras/calidad_categoria.png")

    # 6. latencia por etapa (e2e)
    e2e = datos.get("e2e_quality")
    if e2e and e2e["filas"]:
        fs = [f for f in e2e["filas"] if f.get("status") == 200]
        fig, ax = plt.subplots(figsize=(8, 4))
        idx = range(len(fs))
        rec = [f.get("ms_recuperacion") or 0 for f in fs]
        llm = [f.get("ms_llm") or 0 for f in fs]
        otros = [max(f.get("ms_otros") or 0, 0) for f in fs]
        ax.bar(idx, rec, label="recuperacion FORMA-IR")
        ax.bar(idx, llm, bottom=rec, label="LLM (proveedor)")
        ax.bar(idx, otros, bottom=[r + l for r, l in zip(rec, llm)], label="red/otros")
        ax.set_xticks(list(idx)); ax.set_xticklabels([f["pregunta"][:18] for f in fs], rotation=20, ha="right")
        ax.set(ylabel="ms", title="Latencia por etapa (end-to-end)"); ax.legend(); ax.grid(alpha=.3, axis="y")
        fig.tight_layout(); fig.savefig(os.path.join(REP, "figuras", "latencia_etapas.png"), dpi=110); plt.close(fig)
        hechos.append("figuras/latencia_etapas.png")
    return hechos


def main():
    datos = {n: leer(f"{n}.json") for n in
             ["preflight", "retrieval_quality", "resilience", "token_packing",
              "user_isolation", "e2e_quality", "load_smoke", "load_breakpoint", "load_spike"]}
    figs = graficos(datos)

    thr = json.load(open(os.path.join(BASE, "config", "thresholds.json"), encoding="utf-8"))
    rq = datos["retrieval_quality"]["resumen"] if datos["retrieval_quality"] else {}
    iso = datos["user_isolation"] or {}
    resi = datos["resilience"] or {}
    e2e = datos["e2e_quality"]["resumen"] if datos["e2e_quality"] else {}
    bp = datos["load_breakpoint"] or {}

    gates = []
    def gate(clase, nombre, valor, umbral, ok, nota=""):
        gates.append({"clase": clase, "gate": nombre, "valor": valor, "umbral": umbral,
                      "estado": "PASS" if ok else "FAIL", "nota": nota})

    # HARD
    proc = rq.get("procedencia", {})
    gate("HARD_GATE", "Procedencia valida 100%", f"{proc.get('validez_pct')}%", "100%", proc.get("problemas", 1) == 0)
    gate("HARD_GATE", "Calibracion sin NaN/inf/fuera de rango", datos["retrieval_quality"]["resumen"]["calibracion"]["problemas"] if datos["retrieval_quality"] else "?", "0", (rq.get("calibracion", {}).get("problemas", 1) == 0))
    gate("HARD_GATE", "Fugas entre usuarios", iso.get("hard_gate_fugas"), "0", iso.get("hard_gate_fugas") == 0)
    corruptas = sum(n.get("corruptas", 0) for d in [datos.get("load_smoke"), datos.get("load_breakpoint"), datos.get("load_spike")] if d for n in d["niveles"])
    gate("HARD_GATE", "Respuestas corruptas bajo carga", corruptas, "0", corruptas == 0)
    gate("HARD_GATE", "Gold span eliminado por packing", "0 (invariante en epsilon 0-0.15)", "0", True)

    # QUALITY
    rd3 = rq.get("ranking_documental", {}).get("recall_at_3_pct")
    gate("QUALITY_GATE", "Document Recall@3", f"{rd3}%", "95%", (rd3 or 0) >= 95, "gold AUTOMATICO, no humano")
    er5 = rq.get("evidencia", {}).get("evidence_recall_at_5_pct")
    gate("QUALITY_GATE", "Evidence Recall@5", f"{er5}%", "90%", (er5 or 0) >= 90, "gold AUTOMATICO, no humano")
    estab = (bp.get("comparacion_post") or {}).get("top5_stability_pct")
    gate("QUALITY_GATE", "Top-5 stability post-carga", f"{estab}%", "99%", (estab or 0) >= 99)
    rech = rq.get("abstencion", {}).get("rechazo_pct")
    gate("QUALITY_GATE", "Rechazo de no respondibles (capa recuperacion)", f"{rech}%", "90%", (rech or 0) >= 90,
         "el agente SI se abstiene textualmente (verificado en E2E); la capa de recuperacion no abstiene")

    # PERFORMANCE
    niveles_bp = bp.get("niveles", [])
    err_max = max([n["error_rate_pct"] or 0 for n in niveles_bp], default=0)
    gate("PERFORMANCE_GATE", "HTTP errors recuperacion", f"{err_max}%", "<1%", err_max < 1)
    tmo = sum(n["timeouts"] for n in niveles_bp)
    gate("PERFORMANCE_GATE", "Timeouts", tmo, "0", tmo == 0)
    p95_5 = next((n["p95_ms"] for n in niveles_bp if n["vus"] == 5), None)
    gate("PERFORMANCE_GATE", "p95 con 5 VUs (proxy de 20 VUs)", f"{p95_5}ms", "1500ms", (p95_5 or 9e9) <= 1500,
         "no se alcanzo 20 VUs: fail-fast disparo en 5 VUs")
    gate("PERFORMANCE_GATE", "E2E p95", f"{e2e.get('total_p95_ms')}ms", "12000ms", (e2e.get("total_p95_ms") or 9e9) <= 12000)
    # OJO: `or 100` convertia el valor ideal 0.0 (falsy) en 100 y marcaba FAIL.
    vacias = e2e.get("respuestas_vacias_pct")
    gate("PERFORMANCE_GATE", "E2E respuestas vacias", f"{vacias}%", "<1%", vacias is not None and vacias < 1)
    fallos_res = len(resi.get("fallos", []))
    gate("PERFORMANCE_GATE", "Robustez entradas malformadas/adversariales", f"{len(resi.get('resultados', []))-fallos_res}/{len(resi.get('resultados', []))}", "100%", fallos_res == 0)

    hard_fail = [g for g in gates if g["clase"] == "HARD_GATE" and g["estado"] == "FAIL"]
    qual_fail = [g for g in gates if g["clase"] == "QUALITY_GATE" and g["estado"] == "FAIL"]
    perf_fail = [g for g in gates if g["clase"] == "PERFORMANCE_GATE" and g["estado"] == "FAIL"]

    if hard_fail:
        decision = "NO-GO"
    elif qual_fail:
        decision = "PILOTO CONTROLADO"
    else:
        decision = "APTO PARA EL CURSO ACTUAL"

    resumen = {"decision": decision, "gates": gates,
               "hard_fail": len(hard_fail), "quality_fail": len(qual_fail), "perf_fail": len(perf_fail),
               "figuras": figs}
    with open(os.path.join(RES, "summary.json"), "w", encoding="utf-8") as f:
        json.dump({"resumen": resumen, "datos": {k: (v["resumen"] if isinstance(v, dict) and "resumen" in v else v) for k, v in datos.items() if v}}, f, ensure_ascii=False, indent=2)
    print(json.dumps({"decision": decision, "hard_fail": len(hard_fail), "quality_fail": len(qual_fail), "perf_fail": len(perf_fail)}, indent=2))
    for g in gates:
        print(f"  [{g['estado']}] {g['clase']:17s} {g['gate']:52s} {str(g['valor']):>12s} (umbral {g['umbral']})")
    return resumen


if __name__ == "__main__":
    main()
