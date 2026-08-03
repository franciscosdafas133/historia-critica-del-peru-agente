# -*- coding: utf-8 -*-
"""Fase 9: aislamiento entre usuarios + consistencia de cache.

Inserta marcadores NO sensibles por usuario y verifica que ninguna
respuesta contenga el marcador de otra sesion. Ademas: 100 peticiones de
la MISMA consulta (determinismo) y N consultas distintas simultaneas
(sin respuestas cruzadas). Sin LLM.
"""
import json, os, sys, threading, time
from collections import defaultdict
import requests

RAIZ = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
BASE = os.path.join(RAIZ, "tests", "stress")
BASE_URL = os.environ.get("BASE_URL", "https://historia-critica-del-peru-agente.onrender.com")
URL = BASE_URL + os.environ.get("RETRIEVE_PATH", "/api/preguntar")
TIMEOUT = 100


def cargar(nombre):
    with open(os.path.join(BASE, "datasets", nombre), encoding="utf-8") as f:
        return [json.loads(l) for l in f if l.strip()]


def pedir(pregunta, rid, user_id, cookies=None):
    try:
        r = requests.post(URL, json={"pregunta": pregunta, "modo": "preguntar"},
                          headers={"X-Request-Id": rid, "X-User-Id": user_id},
                          cookies=cookies or {}, timeout=TIMEOUT)
        d = r.json() if r.status_code == 200 else {}
        return {"rid": rid, "user_id": user_id, "status": r.status_code,
                "blob": json.dumps(d, ensure_ascii=False),
                "docs": [p.get("archivo") for p in d.get("paquetes", [])],
                "unidades": [p.get("nucleo") for p in d.get("paquetes", [])],
                "eco": d.get("pregunta")}
    except Exception as e:
        return {"rid": rid, "user_id": user_id, "status": None, "error": f"{type(e).__name__}",
                "blob": "", "docs": [], "unidades": [], "eco": None}


def main():
    out = {"url": URL, "pruebas": {}}

    # --- 1. Marcadores por usuario en paralelo ---
    print("1. Aislamiento con marcadores por usuario (10 usuarios simultaneos)")
    marcadores = {f"user{i}": f"ZQMARKER{i}X" for i in range(10)}
    resultados = []
    def w(uid, marca):
        resultados.append(pedir(f"transicion demografica {marca}", f"iso-{uid}-{int(time.time()*1000)}", uid,
                                cookies={"sesion": f"cookie-{uid}"}))
    hilos = [threading.Thread(target=w, args=(u, m)) for u, m in marcadores.items()]
    for h in hilos: h.start()
    for h in hilos: h.join(timeout=TIMEOUT + 5)

    fugas = []
    for r in resultados:
        propio = marcadores[r["user_id"]]
        for otro_u, otra_m in marcadores.items():
            if otro_u != r["user_id"] and otra_m in r["blob"]:
                fugas.append({"receptor": r["user_id"], "marcador_de": otro_u})
        if r["eco"] and propio not in r["eco"]:
            fugas.append({"receptor": r["user_id"], "problema": "eco_no_corresponde", "eco": r["eco"][:80]})
    out["pruebas"]["marcadores"] = {"n": len(resultados), "fugas": fugas, "ok": not fugas}
    print(f"   respuestas={len(resultados)} fugas={len(fugas)}")

    # --- 2. Determinismo: 100x la misma consulta ---
    print("2. Determinismo: 100 peticiones de la misma consulta (10 hilos)")
    adv = [a for a in cargar("adversarial_queries.jsonl") if a.get("repeticiones")]
    q = adv[0]["query"] if adv else "que es la transicion demografica"
    n_rep = int(os.environ.get("N_REPETICIONES", "100"))
    firmas, errores = [], []
    lock = threading.Lock()
    def w2(i):
        r = pedir(q, f"det-{i}-{int(time.time()*1000)}", f"det{i%10}")
        with lock:
            if r["status"] == 200:
                firmas.append(tuple(r["docs"]))
            else:
                errores.append(r)
    hilos = []
    for i in range(n_rep):
        t = threading.Thread(target=w2, args=(i,)); hilos.append(t)
    for i in range(0, len(hilos), 10):
        lote = hilos[i:i+10]
        for h in lote: h.start()
        for h in lote: h.join(timeout=TIMEOUT + 5)
    distintas = set(firmas)
    out["pruebas"]["determinismo"] = {
        "n": n_rep, "ok_respuestas": len(firmas), "errores": len(errores),
        "firmas_distintas": len(distintas), "determinista": len(distintas) <= 1,
        "muestras": [list(f) for f in list(distintas)[:3]]}
    print(f"   ok={len(firmas)} errores={len(errores)} firmas_distintas={len(distintas)}")

    # --- 3. Consultas distintas simultaneas (respuestas cruzadas) ---
    print("3. Consultas distintas simultaneas (sin cruce de respuestas)")
    gold = [g for g in cargar("gold_queries.jsonl") if g["answerable"]][:20]
    res3 = []
    def w3(g, i):
        res3.append((g["question"], pedir(g["question"], f"cross-{i}-{int(time.time()*1000)}", f"cross{i}")))
    hilos = [threading.Thread(target=w3, args=(g, i)) for i, g in enumerate(gold)]
    for h in hilos: h.start()
    for h in hilos: h.join(timeout=TIMEOUT + 5)
    cruces = [{"enviada": q[:60], "eco": r["eco"][:60] if r["eco"] else None}
              for q, r in res3 if r["status"] == 200 and r["eco"] != q]
    out["pruebas"]["cruce_respuestas"] = {"n": len(res3), "cruces": cruces, "ok": not cruces}
    print(f"   n={len(res3)} cruces={len(cruces)}")

    # --- 4. request_id duplicados ---
    print("4. Request IDs repetidos")
    rid_fijo = "duplicado-fijo-001"
    res4 = []
    def w4(i):
        res4.append(pedir("examen parcial", rid_fijo, f"dup{i}"))
    hilos = [threading.Thread(target=w4, args=(i,)) for i in range(5)]
    for h in hilos: h.start()
    for h in hilos: h.join(timeout=TIMEOUT + 5)
    ok4 = all(r["status"] == 200 for r in res4)
    out["pruebas"]["request_id_duplicado"] = {"n": len(res4), "todas_200": ok4,
        "docs_iguales": len({tuple(r["docs"]) for r in res4 if r["status"] == 200}) <= 1, "ok": ok4}
    print(f"   n={len(res4)} todas_200={ok4}")

    out["hard_gate_fugas"] = len(fugas) + len(cruces)
    os.makedirs(os.path.join(BASE, "results"), exist_ok=True)
    with open(os.path.join(BASE, "results", "user_isolation.json"), "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    print(f"\nFUGAS TOTALES (HARD_GATE) = {out['hard_gate_fugas']}")


if __name__ == "__main__":
    main()
