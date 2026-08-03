# -*- coding: utf-8 -*-
"""¿EXISTE UN REGIMEN DONDE FORMA-IR SUPERE A BM25?

V2 mostro que en consultas literales BM25 iguala o supera a FORMA-IR. Eso
NO refuta el metodo: refuta que ESA tarea sea la adecuada para evaluarlo.
El paper afirma resolver un problema especifico -- comparabilidad entre
unidades HETEROGENEAS (S1: "heterogeneous units compete under one score
even though length, lexical density, repetition, and discourse form alter
the score's null distribution").

Si esa afirmacion es cierta, la ventaja debe aparecer donde BM25 falla por
heterogeneidad, no en recuperacion de cadena literal. Se prueban regimenes:

  R1. HETEROGENEIDAD DE LONGITUD: la unidad correcta es CORTA (diapositiva,
      fila de tabla) y compite con unidades largas del mismo corpus.
  R2. CONSULTAS CORTAS (2-3 terminos): poca evidencia, donde la
      normalizacion por longitud de BM25 es mas fragil.
  R3. CONSULTAS PARAFRASTICAS: vocabulario distinto al de la unidad.
  R4. DOCUMENTO CORRECTO PEQUEÑO vs DOCUMENTO GRANDE DISTRACTOR: el caso
      que motiva la correccion de multiplicidad del paper (S5.6).
  R5. PRECISION DE ABSTENCION: consultas sin respuesta en el corpus.
      BM25 SIEMPRE devuelve algo; p-valores calibrados permiten decir "no".

Se reporta cada regimen por separado, con conteo de victorias pareadas.
"""
import json, os, random, re, statistics, sys
from collections import Counter, defaultdict

RAIZ = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
sys.path.insert(0, RAIZ)
from forma_ir.comparar_con_produccion import preparar_indice, responder_consulta
from forma_ir.evidencia import tokenizar, tokenizar_consulta

BASE = os.path.join(RAIZ, "tests", "stress")
rng = random.Random(23)
N = int(os.environ.get("REG_N", "120"))


def bm25_puro(query, indice, k1=1.5, b=0.75, top_k=5):
    idf, pre = indice["idf"], indice["precomputados"]
    Lavg = indice["longitud_promedio"]
    toks = tokenizar_consulta(query)
    inv = indice["indice_invertido"]
    cands = set()
    for t in set(toks):
        cands |= inv.get(t, set())
    porDoc = {}
    for uid in cands:
        p = pre.get(uid)
        if not p:
            continue
        tf = Counter(p["tokens_cuerpo"]); L = len(p["tokens_cuerpo"]); s = 0.0
        for t in set(toks):
            f = tf.get(t, 0)
            if f:
                s += idf.get(t, 0.0) * (f * (k1 + 1)) / (f + k1 * (1 - b + b * L / max(Lavg, 1e-9)))
        if s > 0:
            d = uid.split("#")[0]
            if d not in porDoc or s > porDoc[d]:
                porDoc[d] = s
    return [d for d, _ in sorted(porDoc.items(), key=lambda kv: -kv[1])[:top_k]]


def r1(doc, docs):
    return docs and docs[0] == doc


def duelo(consultas, idx, etiqueta):
    """consultas: lista de (query, doc_esperado). Devuelve metricas pareadas."""
    f = b = solo_f = solo_b = 0
    for q, doc in consultas:
        df = [d["doc_id"] for d in responder_consulta(q, idx)["documentos"]]
        db = bm25_puro(q, idx)
        of, ob = r1(doc, df), r1(doc, db)
        f += of; b += ob
        solo_f += (of and not ob); solo_b += (ob and not of)
    n = len(consultas)
    res = {"regimen": etiqueta, "n": n,
           "forma_ir_recall1_pct": round(100 * f / n, 1) if n else None,
           "bm25_recall1_pct": round(100 * b / n, 1) if n else None,
           "solo_forma_ir": solo_f, "solo_bm25": solo_b,
           "delta_pp": round(100 * (f - b) / n, 1) if n else None}
    print(f"   {etiqueta:34s} FORMA-IR {res['forma_ir_recall1_pct']:5.1f}%  BM25 {res['bm25_recall1_pct']:5.1f}%"
          f"  delta {res['delta_pp']:+5.1f}pp  (solo-F {solo_f} / solo-B {solo_b})")
    return res


def main():
    print("Preparando indice...")
    idx = preparar_indice()
    U = idx["todas_las_unidades"]
    tam = Counter(u.doc_id for u in U)
    idf = idx["idf"]
    out = {"regimenes": []}

    def frase(u, ini=2, n=10):
        return " ".join(re.sub(r"\s+", " ", u.texto).split()[ini:ini + n])

    # R1: unidad correcta CORTA (heterogeneidad de longitud)
    cortas = [u for u in U if 8 <= len(u.texto.split()) <= 25]
    rng.shuffle(cortas)
    cons = [(frase(u, 0, 8), u.doc_id) for u in cortas[:N]]
    out["regimenes"].append(duelo(cons, idx, "R1 unidad correcta CORTA"))

    # R2: consultas de 2-3 terminos de alto IDF
    largas = [u for u in U if len(u.texto.split()) >= 60]
    rng.shuffle(largas)
    cons = []
    for u in largas[:N]:
        ts = sorted(set(t for t in tokenizar(u.texto) if len(t) > 5), key=lambda t: -idf.get(t, 0))[:3]
        if len(ts) == 3:
            cons.append((" ".join(ts), u.doc_id))
    out["regimenes"].append(duelo(cons, idx, "R2 consulta CORTA (3 terminos)"))

    # R3: parafrastica (terminos del resto de la unidad, sin la frase)
    cons = []
    for u in largas[:N]:
        pal = re.sub(r"\s+", " ", u.texto).split()
        usados = set(tokenizar(" ".join(pal[2:12])))
        resto = [t for t in tokenizar(u.texto) if t not in usados and len(t) > 4]
        if len(set(resto)) >= 5:
            ts = sorted(set(resto), key=lambda t: -idf.get(t, 0))[:6]
            cons.append((" ".join(ts), u.doc_id))
    out["regimenes"].append(duelo(cons, idx, "R3 PARAFRASTICA (otro vocabulario)"))

    # R4: documento correcto PEQUEÑO (<=30 unidades) -- multiplicidad S5.6
    peques = [u for u in U if tam[u.doc_id] <= 30 and len(u.texto.split()) >= 30]
    rng.shuffle(peques)
    cons = [(frase(u), u.doc_id) for u in peques[:N]]
    out["regimenes"].append(duelo(cons, idx, "R4 doc correcto PEQUENO (<=30 u)"))

    # R4b: documento correcto GRANDE (>=200 unidades)
    grandes = [u for u in U if tam[u.doc_id] >= 200 and len(u.texto.split()) >= 30]
    rng.shuffle(grandes)
    cons = [(frase(u), u.doc_id) for u in grandes[:N]]
    out["regimenes"].append(duelo(cons, idx, "R4b doc correcto GRANDE (>=200 u)"))

    # R5: ABSTENCION -- consultas sin respuesta en el corpus
    print("\n   R5 ABSTENCION (consultas fuera del corpus)")
    fuera = ["formula quimica acido sulfurico", "kubernetes cluster docker", "mundial futbol 2022",
             "red neuronal convolucional backpropagation", "receta de ceviche paso a paso",
             "teoria de cuerdas dimensiones extra", "python pandas dataframe merge",
             "sintomas de la diabetes tipo 2", "reglas del ajedrez enroque", "temperatura de fusion del acero"]
    f_abst = b_abst = 0
    detalle = []
    for q in fuera:
        r = responder_consulta(q, idx)
        # FORMA-IR: se abstiene si NINGUN documento supera el umbral de
        # significancia (p_doc alto = evidencia no significativa)
        p0 = r["documentos"][0]["p_doc"] if r["documentos"] else 1.0
        f_ab = p0 > 0.05
        # BM25 no tiene noción de "no significativo": siempre devuelve algo
        b_ab = len(bm25_puro(q, idx)) == 0
        f_abst += f_ab; b_abst += b_ab
        detalle.append({"q": q, "p_doc": round(p0, 4), "forma_ir_abstiene": bool(f_ab), "bm25_abstiene": bool(b_ab)})
        print(f"      p_doc={p0:.4f} {'ABSTIENE' if f_ab else 'responde ':9s} | {q[:44]}")
    out["R5_abstencion"] = {"n": len(fuera),
                            "forma_ir_abstiene_pct": round(100 * f_abst / len(fuera), 1),
                            "bm25_abstiene_pct": round(100 * b_abst / len(fuera), 1),
                            "detalle": detalle,
                            "_lectura": "BM25 no puede abstenerse: no tiene escala calibrada. Aqui FORMA-IR aporta algo que el baseline NO puede dar."}
    print(f"   FORMA-IR se abstiene en {out['R5_abstencion']['forma_ir_abstiene_pct']}% | BM25 en {out['R5_abstencion']['bm25_abstiene_pct']}%")

    with open(os.path.join(BASE, "results", "regimenes.json"), "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    print("\n-> results/regimenes.json")


if __name__ == "__main__":
    main()
