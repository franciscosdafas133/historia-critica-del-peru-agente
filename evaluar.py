# -*- coding: utf-8 -*-
"""
Banco de evaluacion - compara estrategias de construccion de contexto.

Corre las preguntas de preguntas_evaluacion.json contra cada estrategia y
mide tokens, latencia y composicion de la evidencia, por estrato.

Estrategias comparadas:
  completo    todo el corpus al prompt (rival real, sobre todo con caching)
  seccion     la semana correspondiente completa
  recuperacion  paquetes construidos por consulta (la propuesta)
  topk_fijo   RAG ingenuo: k bloques por similitud, sin expansion (piso)

Lo que NO mide todavia: recall de evidencia contra anotacion gold, porque
esa anotacion aun no existe. Sin ella se puede comparar costo y composicion,
pero no calidad de recuperacion. Anotar es el cuello de botella y es manual.

Uso:
    python evaluar.py                 # todas las preguntas
    python evaluar.py --estrato local
    python evaluar.py --csv salida.csv
"""
import sys, io, os, json, pickle, time, argparse, collections
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace", line_buffering=True)

import tiktoken
from recuperar import recuperar, analizar_pregunta, buscar
from agente import SISTEMA, prompt_recuperacion, prompt_completo

RAIZ = os.path.dirname(os.path.abspath(__file__))
ENC = tiktoken.get_encoding("cl100k_base")
ntok = lambda s: len(ENC.encode(s)) if s else 0


def estrategia_topk(q, idx, k=5):
    """RAG ingenuo: k bloques sueltos por score, sin expansion ni diversidad.
    Es el piso contra el que hay que demostrar que la expansion aporta algo."""
    plan = {"tipo": "explicativa", "filtros": {}, "presupuesto": 10**9, "k": k}
    cand = buscar(q, idx, plan)[:k]
    B, D = idx["bloques"], idx["docs"]
    paquetes = []
    for i, sc, crudo, cob in cand:
        d = D[B[i]["doc_id"]]
        u = "pagina" if "pagina" in B[i]["fuente"] else "diapositiva"
        paquetes.append({"doc": d["titulo"], "cita": d.get("cita") or d["titulo"],
                         "tokens": B[i]["tokens"], "texto": B[i]["texto"],
                         "paginas": f"{u} {B[i]['fuente'][u]}", "tipo": d["tipo"],
                         "autoridad": d["autoridad"], "archivo": d["archivo"],
                         "unidad": d.get("unidad"), "semana": d.get("semana"),
                         "score": round(sc, 3), "ocr": B[i]["fuente"].get("ocr", False)})
    return paquetes


def medir(q, idx, estrategia):
    t0 = time.time()
    docs_distintos = None
    if estrategia == "recuperacion":
        user, r = prompt_recuperacion(q, idx)
        if user is None: return None
        paquetes = r["paquetes"]
        extra = {"tipo_detectado": r["plan"]["tipo"], "avisos": len(r["avisos"]),
                 "presupuesto": r["plan"]["presupuesto"]}
        docs_distintos = len({p["doc"] for p in paquetes})
    elif estrategia == "topk_fijo":
        paquetes = estrategia_topk(q, idx)
        user = f"PREGUNTA:\n{q}\n\nEVIDENCIA:\n" + "\n\n".join(
            f"[{i}] {p['cita']} ({p['paginas']})\n{p['texto']}" for i, p in enumerate(paquetes, 1))
        extra = {"tipo_detectado": "-", "avisos": 0, "presupuesto": 0}
        docs_distintos = len({p["doc"] for p in paquetes})
    elif estrategia == "seccion":
        plan = analizar_pregunta(q, idx)
        sem = plan["filtros"].get("semana")
        if sem is None:
            r = recuperar(q, idx)
            sem = r["paquetes"][0]["semana"] if r["paquetes"] and r["paquetes"][0]["semana"] else 1
        user, n = prompt_completo(q, idx, {"semana": sem})
        paquetes = []; extra = {"tipo_detectado": f"S{sem}", "avisos": 0, "presupuesto": 0}
        docs_distintos = n
    else:
        user, n = prompt_completo(q, idx)
        paquetes = []; extra = {"tipo_detectado": "-", "avisos": 0, "presupuesto": 0}
        docs_distintos = n

    dt = time.time() - t0
    t_in = ntok(SISTEMA) + ntok(user)
    return {"estrategia": estrategia, "tokens_entrada": t_in,
            "n_fragmentos": len(paquetes) if paquetes else docs_distintos,
            "docs_distintos": docs_distintos, "latencia_s": round(dt, 3), **extra}


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--estrato", choices=["local", "adyacente", "multihop", "global"])
    ap.add_argument("--csv", help="guardar resultados")
    ap.add_argument("--estrategias", default="completo,seccion,recuperacion,topk_fijo")
    a = ap.parse_args()

    banco = json.load(open(os.path.join(RAIZ, "preguntas_evaluacion.json"), encoding="utf-8"))
    preguntas = banco["preguntas"]
    if a.estrato: preguntas = [p for p in preguntas if p["estrato"] == a.estrato]
    ests = a.estrategias.split(",")

    idx = pickle.load(open(os.path.join(RAIZ, "corpus", "indice.pkl"), "rb"))
    print(f"preguntas: {len(preguntas)}  estrategias: {ests}\n")

    filas = []
    for p in preguntas:
        print(f"{p['id']} [{p['estrato']:<10}] {p['pregunta'][:62]}")
        for e in ests:
            m = medir(p["pregunta"], idx, e)
            if m is None:
                print(f"     {e:<13} SIN EVIDENCIA"); continue
            m.update({"id": p["id"], "estrato": p["estrato"], "pregunta": p["pregunta"]})
            filas.append(m)
            print(f"     {e:<13} {m['tokens_entrada']:>8,} tok  "
                  f"{m['n_fragmentos']:>3} frag  {m['docs_distintos']:>2} docs  "
                  f"{m['latencia_s']:>6.2f}s  {m['tipo_detectado']}")
        print()

    # ---- resumen por estrato y estrategia ----
    print("=" * 92)
    print("RESUMEN: tokens de entrada promedio por estrato y estrategia")
    print("=" * 92)
    est_orden = ["local", "adyacente", "multihop", "global"]
    print(f"{'estrato':<12}" + "".join(f"{e:>17}" for e in ests))
    for s in est_orden:
        sub = [f for f in filas if f["estrato"] == s]
        if not sub: continue
        linea = f"{s:<12}"
        for e in ests:
            v = [f["tokens_entrada"] for f in sub if f["estrategia"] == e]
            linea += f"{(sum(v)//len(v) if v else 0):>17,}"
        print(linea)
    linea = f"{'TOTAL':<12}"
    for e in ests:
        v = [f["tokens_entrada"] for f in filas if f["estrategia"] == e]
        linea += f"{(sum(v)//len(v) if v else 0):>17,}"
    print(linea)

    print(f"\n{'estrategia':<15}{'tok/pregunta':>14}{'x vs recuperacion':>20}{'latencia med':>14}")
    base = [f["tokens_entrada"] for f in filas if f["estrategia"] == "recuperacion"]
    base = sum(base)/len(base) if base else 1
    for e in ests:
        v = [f["tokens_entrada"] for f in filas if f["estrategia"] == e]
        lat = [f["latencia_s"] for f in filas if f["estrategia"] == e]
        if not v: continue
        prom = sum(v)/len(v)
        print(f"{e:<15}{prom:>14,.0f}{prom/base:>19.1f}x{sum(lat)/len(lat):>13.2f}s")

    if a.csv:
        import csv
        with open(a.csv, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=list(filas[0].keys()))
            w.writeheader(); w.writerows(filas)
        print(f"\n-> {a.csv}")
