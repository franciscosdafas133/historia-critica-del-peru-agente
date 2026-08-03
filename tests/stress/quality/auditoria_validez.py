# -*- coding: utf-8 -*-
"""AUDITORIA DE VALIDEZ EXPERIMENTAL (rol: revisor adversarial).

No mide "que tan bien funciona": mide SI LAS MEDICIONES SIGNIFICAN ALGO.
Cada bloque responde a una objecion que un revisor de IR plantearia.

  V1. CIRCULARIDAD: las consultas literales copian texto de la unidad gold.
      ¿El 97.5% mide recuperacion o mide "encontrar la cadena que copie"?
      Control: consulta literal vs. consulta con los terminos gold ELIMINADOS.

  V2. BASELINE COMPETITIVO: sin comparacion, un numero absoluto no dice nada.
      BM25 puro sobre las mismas unidades. Si FORMA-IR no le gana, la
      maquinaria de calibracion no esta justificada.

  V3. ABLACIONES: ¿que componente aporta? Se apaga uno a la vez.

  V4. DIFICULTAD REAL: consultas donde el termino clave aparece en VARIOS
      documentos (no hay respuesta trivial por vocabulario raro).

  V5. SESGO DE CONCENTRACION: un documento tiene 35% del corpus. Se reporta
      macro-promedio por documento ademas del micro-promedio.
"""
import json, os, random, re, statistics, sys, time
from collections import Counter, defaultdict

RAIZ = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
sys.path.insert(0, RAIZ)
from forma_ir.comparar_con_produccion import preparar_indice, responder_consulta
from forma_ir.evidencia import tokenizar, tokenizar_consulta

BASE = os.path.join(RAIZ, "tests", "stress")
rng = random.Random(11)
N = int(os.environ.get("AUDIT_N", "200"))


def bm25_puro(query, indice, k1=1.5, b=0.75, top_k=5):
    """Baseline: BM25 clasico sobre unidades, sin calibracion, sin
    agregacion documental, sin familias. El mismo IDF y tokenizador."""
    idf = indice["idf"]
    pre = indice["precomputados"]
    Lavg = indice["longitud_promedio"]
    toks = tokenizar_consulta(query)
    inv = indice["indice_invertido"]
    cands = set()
    for t in set(toks):
        cands |= inv.get(t, set())
    scores = {}
    for uid in cands:
        p = pre.get(uid)
        if not p:
            continue
        tf = Counter(p["tokens_cuerpo"])
        L = len(p["tokens_cuerpo"])
        s = 0.0
        for t in set(toks):
            f = tf.get(t, 0)
            if not f:
                continue
            s += idf.get(t, 0.0) * (f * (k1 + 1)) / (f + k1 * (1 - b + b * L / max(Lavg, 1e-9)))
        if s > 0:
            scores[uid] = s
    # agregacion documental: mejor unidad por documento (max-score, estandar)
    porDoc = {}
    for uid, s in scores.items():
        d = uid.split("#")[0]
        if d not in porDoc or s > porDoc[d]:
            porDoc[d] = s
    return [d for d, _ in sorted(porDoc.items(), key=lambda kv: -kv[1])[:top_k]]


def rank_de(doc, docs):
    return docs.index(doc) + 1 if doc in docs else None


def main():
    print("Preparando indice...")
    idx = preparar_indice()
    U = idx["todas_las_unidades"]
    tam = Counter(u.doc_id for u in U)
    idf = idx["idf"]

    cand = [u for u in U if len(u.texto.split()) >= 40]
    rng.shuffle(cand)
    muestra = cand[:N]
    out = {}

    # ---------- V1. CIRCULARIDAD ----------
    print("\nV1. CIRCULARIDAD (literal vs. sin los terminos copiados)")
    lit_hits, abl_hits, n_abl = 0, 0, 0
    for u in muestra:
        pal = re.sub(r"\s+", " ", u.texto).split()
        q_lit = " ".join(pal[2:12])
        r = responder_consulta(q_lit, idx)
        lit_hits += (rank_de(u.doc_id, [d["doc_id"] for d in r["documentos"]]) == 1)

        # consulta "parafrastica dura": se toman los terminos de ALTO IDF del
        # resto de la unidad, excluyendo los que aparecen en q_lit. Simula a
        # un estudiante que pregunta por el TEMA sin copiar la frase.
        usados = set(tokenizar(q_lit))
        resto = [t for t in tokenizar(u.texto) if t not in usados and len(t) > 4]
        if len(set(resto)) < 4:
            continue
        n_abl += 1
        top = sorted(set(resto), key=lambda t: -idf.get(t, 0))[:6]
        r2 = responder_consulta(" ".join(top), idx)
        abl_hits += (rank_de(u.doc_id, [d["doc_id"] for d in r2["documentos"]]) == 1)
    out["V1_circularidad"] = {
        "recall1_literal_pct": round(100 * lit_hits / len(muestra), 1),
        "recall1_sin_terminos_copiados_pct": round(100 * abl_hits / n_abl, 1) if n_abl else None,
        "n": len(muestra), "n_ablacion": n_abl,
        "_lectura": "Si la 2a es MUCHO menor, el 97.5% mide sobre todo coincidencia de cadena.",
    }
    print("   " + json.dumps(out["V1_circularidad"], ensure_ascii=False))

    # ---------- V2. BASELINE COMPETITIVO ----------
    print("\nV2. BASELINE: FORMA-IR vs BM25 puro (mismas consultas)")
    f_hits = b_hits = f3 = b3 = 0
    empates = ganan_f = ganan_b = 0
    for u in muestra:
        pal = re.sub(r"\s+", " ", u.texto).split()
        q = " ".join(pal[2:12])
        rf = [d["doc_id"] for d in responder_consulta(q, idx)["documentos"]]
        rb = bm25_puro(q, idx)
        a = rank_de(u.doc_id, rf); c = rank_de(u.doc_id, rb)
        f_hits += (a == 1); b_hits += (c == 1)
        f3 += (a is not None and a <= 3); b3 += (c is not None and c <= 3)
        if (a == 1) and (c != 1): ganan_f += 1
        elif (c == 1) and (a != 1): ganan_b += 1
        else: empates += 1
    out["V2_baseline"] = {
        "forma_ir_recall1_pct": round(100 * f_hits / len(muestra), 1),
        "bm25_recall1_pct": round(100 * b_hits / len(muestra), 1),
        "forma_ir_recall3_pct": round(100 * f3 / len(muestra), 1),
        "bm25_recall3_pct": round(100 * b3 / len(muestra), 1),
        "solo_forma_ir_acierta": ganan_f, "solo_bm25_acierta": ganan_b, "empatan": empates,
        "_lectura": "Si BM25 iguala a FORMA-IR, la calibracion no esta justificada empiricamente.",
    }
    print("   " + json.dumps(out["V2_baseline"], ensure_ascii=False))

    # ---------- V4. DIFICULTAD REAL ----------
    print("\nV4. DIFICULTAD: consultas SIN terminos exclusivos del documento")
    df_doc = defaultdict(set)
    for u in U:
        for t in set(tokenizar(u.texto)):
            df_doc[t].add(u.doc_id)
    faciles = dificiles = 0
    f_ok = d_ok = 0
    for u in muestra:
        pal = re.sub(r"\s+", " ", u.texto).split()
        q = " ".join(pal[2:12])
        toks = [t for t in set(tokenizar_consulta(q)) if t in df_doc]
        if not toks:
            continue
        # exclusivo = termino que SOLO aparece en el documento correcto
        exclusivos = [t for t in toks if df_doc[t] == {u.doc_id}]
        ok = rank_de(u.doc_id, [d["doc_id"] for d in responder_consulta(q, idx)["documentos"]]) == 1
        if exclusivos:
            faciles += 1; f_ok += ok
        else:
            dificiles += 1; d_ok += ok
    out["V4_dificultad"] = {
        "con_termino_exclusivo": {"n": faciles, "recall1_pct": round(100 * f_ok / faciles, 1) if faciles else None},
        "sin_termino_exclusivo": {"n": dificiles, "recall1_pct": round(100 * d_ok / dificiles, 1) if dificiles else None},
        "_lectura": "Sin terminos exclusivos la tarea es realmente discriminativa.",
    }
    print("   " + json.dumps(out["V4_dificultad"], ensure_ascii=False))

    # ---------- V5. MACRO vs MICRO ----------
    print("\nV5. SESGO DE CONCENTRACION (macro-promedio por documento)")
    porDoc = defaultdict(list)
    for u in muestra:
        pal = re.sub(r"\s+", " ", u.texto).split()
        q = " ".join(pal[2:12])
        ok = rank_de(u.doc_id, [d["doc_id"] for d in responder_consulta(q, idx)["documentos"]]) == 1
        porDoc[u.doc_id].append(ok)
    micro = round(100 * sum(sum(v) for v in porDoc.values()) / sum(len(v) for v in porDoc.values()), 1)
    macro = round(statistics.mean([100 * sum(v) / len(v) for v in porDoc.values()]), 1)
    peores = sorted(((d, 100 * sum(v) / len(v), len(v), tam[d]) for d, v in porDoc.items()), key=lambda z: z[1])[:5]
    out["V5_concentracion"] = {
        "micro_promedio_pct": micro, "macro_promedio_pct": macro,
        "n_documentos_evaluados": len(porDoc),
        "peores_documentos": [{"doc": d[:45], "recall1_pct": round(p, 1), "n_consultas": n, "unidades": t} for d, p, n, t in peores],
        "_lectura": "El micro esta dominado por el doc con 35% del corpus; el macro trata igual a cada documento.",
    }
    print("   " + json.dumps(out["V5_concentracion"], ensure_ascii=False, indent=2)[:900])

    with open(os.path.join(BASE, "results", "auditoria_validez.json"), "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    print("\n-> results/auditoria_validez.json")


if __name__ == "__main__":
    main()
