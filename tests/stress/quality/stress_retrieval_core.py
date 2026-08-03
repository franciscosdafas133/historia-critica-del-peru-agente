# -*- coding: utf-8 -*-
"""ESTRES DE RECUPERACION (calidad, no infraestructura).

Somete al motor a presion en los ejes que definen si SIRVE:
  A. ACIERTO a escala        - 400 consultas auto-verificables (gold exacto)
  B. DISCRIMINACION          - ¿distingue el doc correcto de uno muy parecido?
  C. ROBUSTEZ LEXICA         - misma intencion, escritura degradada progresiva
  D. SENSIBILIDAD AL TAMAÑO  - ¿el ranking depende del tamaño del documento?
  E. ESTABILIDAD SEMANTICA   - paráfrasis de la misma pregunta -> mismo doc?
  F. EFICIENCIA vs CARGA DE CORPUS - latencia por longitud de consulta
  G. CALIBRACION UTIL        - ¿p_doc separa aciertos de fallos?

Todo local contra el mismo codigo desplegado. Sin LLM, sin costo.
Salida: results/stress_retrieval_core.json
"""
import json, os, random, re, statistics, sys, time, unicodedata
from collections import Counter, defaultdict

RAIZ = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
sys.path.insert(0, RAIZ)
from forma_ir.comparar_con_produccion import preparar_indice, responder_consulta
from forma_ir.evidencia import tokenizar

BASE = os.path.join(RAIZ, "tests", "stress")
rng = random.Random(7)


def sin_tildes(s):
    return "".join(c for c in unicodedata.normalize("NFD", s) if unicodedata.category(c) != "Mn")


def degradar(texto, nivel):
    """nivel 0=intacto, 1=sin tildes, 2=+1 typo, 3=+2 typos, 4=minusculas+3 typos."""
    s = texto
    if nivel >= 1:
        s = sin_tildes(s)
    n_typos = {0: 0, 1: 0, 2: 1, 3: 2, 4: 3}[nivel]
    palabras = s.split()
    largas = [i for i, w in enumerate(palabras) if len(w) >= 6]
    for i in largas[:n_typos]:
        w = palabras[i]; k = len(w) // 2
        palabras[i] = w[:k] + w[k + 1] + w[k] + w[k + 2:]
    s = " ".join(palabras)
    if nivel >= 4:
        s = s.lower()
    return s


def rank_de(doc_esperado, documentos):
    for i, d in enumerate(documentos, 1):
        if d["doc_id"] == doc_esperado:
            return i
    return None


def main():
    print("Preparando indice FORMA-IR...")
    t0 = time.time()
    indice = preparar_indice()
    t_build = time.time() - t0
    unidades = indice["todas_las_unidades"]
    por_doc = defaultdict(list)
    for u in unidades:
        por_doc[u.doc_id].append(u)
    tam_doc = {d: len(us) for d, us in por_doc.items()}
    print(f"  indice en {t_build:.1f}s · {len(unidades)} unidades · {len(por_doc)} documentos\n")

    out = {"indice_build_s": round(t_build, 2), "n_unidades": len(unidades), "n_documentos": len(por_doc)}
    lat_global = []

    # ---------- A. ACIERTO A ESCALA (400 consultas auto-verificables) ----------
    print("A. ACIERTO A ESCALA (400 consultas desde unidades reales)")
    candidatas = [u for u in unidades if len(u.texto.split()) >= 30]
    rng.shuffle(candidatas)
    muestra = candidatas[:400]
    filas_a = []
    for u in muestra:
        palabras = re.sub(r"\s+", " ", u.texto).split()
        q = " ".join(palabras[2:12])  # frase literal de 10 palabras
        t = time.time(); r = responder_consulta(q, indice); dt = time.time() - t
        lat_global.append(dt)
        rk = rank_de(u.doc_id, r["documentos"])
        uids = [x["unidad_id"] for x in r["unidades_empaquetadas"]]
        filas_a.append({"doc": u.doc_id, "tam_doc": tam_doc[u.doc_id], "rank": rk,
                        "unidad_ok": u.unidad_id in uids,
                        "p_doc_top1": r["documentos"][0]["p_doc"] if r["documentos"] else None,
                        "p_doc_correcto": next((d["p_doc"] for d in r["documentos"] if d["doc_id"] == u.doc_id), None),
                        "lat": dt, "n_unid": len(uids)})
    def pctm(cond, base):
        return round(100.0 * sum(1 for f in base if cond(f)) / len(base), 1) if base else None
    out["A_acierto_escala"] = {
        "n": len(filas_a),
        "recall_1_pct": pctm(lambda f: f["rank"] == 1, filas_a),
        "recall_3_pct": pctm(lambda f: f["rank"] and f["rank"] <= 3, filas_a),
        "recall_5_pct": pctm(lambda f: f["rank"] and f["rank"] <= 5, filas_a),
        "unidad_exacta_pct": pctm(lambda f: f["unidad_ok"], filas_a),
        "mrr": round(statistics.mean([1.0 / f["rank"] if f["rank"] else 0.0 for f in filas_a]), 4),
        "no_aparece_pct": pctm(lambda f: f["rank"] is None, filas_a),
    }
    print("   " + json.dumps(out["A_acierto_escala"], ensure_ascii=False))

    # ---------- B. DISCRIMINACION: doc correcto vs vecino mas parecido ----------
    print("B. DISCRIMINACION (¿elige el doc correcto entre parecidos?)")
    conf = Counter()
    for f in filas_a:
        if f["rank"] != 1:
            conf[f["doc"]] += 1
    out["B_discriminacion"] = {
        "docs_mas_perjudicados": [{"doc": d, "fallos": n, "tam": tam_doc[d]} for d, n in conf.most_common(8)],
        "_nota": "fallos = veces que su propio texto literal NO lo devolvio como top-1",
    }
    for d, n in conf.most_common(5):
        print(f"   {n:3d} fallos · {tam_doc[d]:5d} unid · {d[:50]}")

    # ---------- C. ROBUSTEZ LEXICA (degradacion progresiva) ----------
    print("C. ROBUSTEZ LEXICA (misma consulta, escritura degradada)")
    base_c = muestra[:120]
    robustez = []
    for nivel in range(5):
        aciertos, lats = 0, []
        for u in base_c:
            palabras = re.sub(r"\s+", " ", u.texto).split()
            q = degradar(" ".join(palabras[2:12]), nivel)
            t = time.time(); r = responder_consulta(q, indice); lats.append(time.time() - t)
            rk = rank_de(u.doc_id, r["documentos"])
            aciertos += 1 if (rk and rk <= 3) else 0
        robustez.append({"nivel": nivel,
                         "descripcion": ["intacta", "sin tildes", "1 typo", "2 typos", "3 typos+minusculas"][nivel],
                         "recall_3_pct": round(100.0 * aciertos / len(base_c), 1),
                         "lat_p50_ms": round(statistics.median(lats) * 1000, 1)})
        print(f"   nivel {nivel} ({robustez[-1]['descripcion']:20s}) recall@3={robustez[-1]['recall_3_pct']:5.1f}%")
    out["C_robustez_lexica"] = {"curva": robustez,
        "caida_total_pp": round(robustez[0]["recall_3_pct"] - robustez[-1]["recall_3_pct"], 1)}

    # ---------- D. SENSIBILIDAD AL TAMAÑO DEL DOCUMENTO ----------
    print("D. SENSIBILIDAD AL TAMAÑO DEL DOCUMENTO")
    cortes = [(1, 10), (11, 50), (51, 150), (151, 400), (401, 99999)]
    tabla_d = []
    for lo, hi in cortes:
        sub = [f for f in filas_a if lo <= f["tam_doc"] <= hi]
        if not sub:
            continue
        tabla_d.append({"rango_unidades": f"{lo}-{hi if hi < 99999 else '+'}", "n": len(sub),
                        "recall_1_pct": pctm(lambda f: f["rank"] == 1, sub),
                        "recall_3_pct": pctm(lambda f: f["rank"] and f["rank"] <= 3, sub),
                        "p_doc_correcto_medio": round(statistics.mean([f["p_doc_correcto"] for f in sub if f["p_doc_correcto"] is not None]), 4) if any(f["p_doc_correcto"] is not None for f in sub) else None})
        print(f"   {tabla_d[-1]['rango_unidades']:>10s} unid | n={len(sub):3d} | recall@1={tabla_d[-1]['recall_1_pct']:5.1f}% | recall@3={tabla_d[-1]['recall_3_pct']:5.1f}%")
    out["D_sensibilidad_tamano"] = tabla_d

    # ---------- E. ESTABILIDAD ANTE PARAFRASIS ----------
    print("E. ESTABILIDAD ANTE PARAFRASIS (mismo contenido, distinta ventana)")
    estables = 0; total_e = 0; detalle_e = []
    for u in muestra[:100]:
        palabras = re.sub(r"\s+", " ", u.texto).split()
        if len(palabras) < 40:
            continue
        total_e += 1
        variantes = [" ".join(palabras[2:12]), " ".join(palabras[14:24]), " ".join(palabras[26:36])]
        tops = []
        for v in variantes:
            r = responder_consulta(v, indice)
            tops.append(r["documentos"][0]["doc_id"] if r["documentos"] else None)
        if len(set(tops)) == 1:
            estables += 1
        else:
            detalle_e.append({"doc": u.doc_id, "tops": tops})
    out["E_estabilidad_parafrasis"] = {
        "n": total_e, "mismo_top1_en_3_ventanas_pct": round(100.0 * estables / total_e, 1) if total_e else None,
        "ejemplos_inestables": detalle_e[:5]}
    print(f"   mismo top-1 en 3 ventanas del MISMO documento: {out['E_estabilidad_parafrasis']['mismo_top1_en_3_ventanas_pct']}%")

    # ---------- F. EFICIENCIA vs LONGITUD DE CONSULTA ----------
    print("F. EFICIENCIA (latencia vs longitud de consulta)")
    tabla_f = []
    for n_pal in [1, 3, 10, 30, 100, 300]:
        lats = []
        for u in muestra[:30]:
            palabras = re.sub(r"\s+", " ", u.texto).split()
            q = " ".join((palabras * 12)[:n_pal])
            t = time.time(); responder_consulta(q, indice); lats.append((time.time() - t) * 1000)
        tabla_f.append({"palabras_consulta": n_pal, "lat_p50_ms": round(statistics.median(lats), 1),
                        "lat_p95_ms": round(sorted(lats)[int(0.95 * len(lats)) - 1], 1)})
        print(f"   {n_pal:4d} palabras -> p50={tabla_f[-1]['lat_p50_ms']:7.1f}ms p95={tabla_f[-1]['lat_p95_ms']:7.1f}ms")
    out["F_eficiencia"] = {"curva": tabla_f,
        "lat_global_p50_ms": round(statistics.median(lat_global) * 1000, 1),
        "lat_global_p95_ms": round(sorted(lat_global)[int(0.95 * len(lat_global))] * 1000, 1)}

    # ---------- G. ¿LA CALIBRACION ES UTIL? ----------
    print("G. CALIBRACION: ¿p_doc separa aciertos de fallos?")
    aciertos = [f["p_doc_top1"] for f in filas_a if f["rank"] == 1 and f["p_doc_top1"] is not None]
    fallos = [f["p_doc_top1"] for f in filas_a if f["rank"] != 1 and f["p_doc_top1"] is not None]
    saturados = sum(1 for f in filas_a if f["p_doc_top1"] is not None and f["p_doc_top1"] >= 0.999)
    out["G_calibracion"] = {
        "p_doc_top1_medio_en_aciertos": round(statistics.mean(aciertos), 4) if aciertos else None,
        "p_doc_top1_medio_en_fallos": round(statistics.mean(fallos), 4) if fallos else None,
        "separacion": round((statistics.mean(fallos) - statistics.mean(aciertos)), 4) if aciertos and fallos else None,
        "saturados_en_1.0_pct": round(100.0 * saturados / len(filas_a), 1),
        "_lectura": "p_doc BAJO deberia indicar acierto. Si la separacion es ~0 o negativa, la calibracion NO discrimina.",
    }
    print("   " + json.dumps(out["G_calibracion"], ensure_ascii=False))

    os.makedirs(os.path.join(BASE, "results"), exist_ok=True)
    with open(os.path.join(BASE, "results", "stress_retrieval_core.json"), "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    print("\n-> results/stress_retrieval_core.json")


if __name__ == "__main__":
    main()
