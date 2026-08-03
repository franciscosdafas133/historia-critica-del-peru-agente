# -*- coding: utf-8 -*-
"""Fases 7 y 8: carga incremental con fail-fast + calidad bajo carga (canarias)
+ aislamiento entre usuarios. Sin LLM. k6 no esta disponible en este entorno,
asi que se implementa con hilos + requests (misma responsabilidad).

Uso: python tests/stress/load/run_load.py [escenario]
  escenarios: smoke | normal | pico | spike | breakpoint | soak
"""
import json, os, statistics, sys, threading, time
from collections import defaultdict
import requests

RAIZ = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
BASE = os.path.join(RAIZ, "tests", "stress")
BASE_URL = os.environ.get("BASE_URL", "https://historia-critica-del-peru-agente.onrender.com")
URL = BASE_URL + os.environ.get("RETRIEVE_PATH", "/api/preguntar")
CFG = json.load(open(os.path.join(BASE, "config", "workload.json"), encoding="utf-8"))
THR = json.load(open(os.path.join(BASE, "config", "thresholds.json"), encoding="utf-8"))
LIM = CFG["limites_globales"]
MAX_REQUESTS = int(os.environ.get("MAX_REQUESTS", LIM["MAX_REQUESTS"]))
TIMEOUT = 100

_lock = threading.Lock()
_total_requests = 0


def cargar(nombre):
    with open(os.path.join(BASE, "datasets", nombre), encoding="utf-8") as f:
        return [json.loads(l) for l in f if l.strip()]


def presupuesto_disponible():
    with _lock:
        return _total_requests < MAX_REQUESTS


def consumir():
    global _total_requests
    with _lock:
        _total_requests += 1
        return _total_requests


def una_peticion(pregunta, request_id, user_id=None):
    """Devuelve metricas de UNA peticion, con instrumentacion (Fase 6)."""
    consumir()
    headers = {"Content-Type": "application/json", "X-Request-Id": request_id}
    if user_id:
        headers["X-User-Id"] = user_id
    body = {"pregunta": pregunta, "modo": "preguntar"}
    t0 = time.time()
    try:
        r = requests.post(URL, json=body, headers=headers, timeout=TIMEOUT)
        ms = (time.time() - t0) * 1000
        try:
            d = r.json()
        except Exception:
            d = {}
        paquetes = d.get("paquetes", []) if isinstance(d, dict) else []
        return {"request_id": request_id, "user_id": user_id, "status": r.status_code, "ms": round(ms, 1),
                "ms_recuperacion": d.get("ms_recuperacion"),
                "n_paquetes": len(paquetes),
                "docs": [p.get("archivo") for p in paquetes],
                "unidades": [p.get("nucleo") for p in paquetes],
                "hash_textos": [hash(p.get("extracto", "")) for p in paquetes],
                "tokens_evidencia": d.get("tokens_evidencia"),
                "avisos": len(d.get("avisos", []) or []),
                "bytes_resp": len(r.content), "error": None,
                "corrupta": bool(paquetes) and any(not p.get("archivo") or p.get("extracto") is None for p in paquetes),
                "pregunta_eco": d.get("pregunta")}
    except Exception as e:
        return {"request_id": request_id, "user_id": user_id, "status": None,
                "ms": round((time.time() - t0) * 1000, 1), "error": f"{type(e).__name__}",
                "n_paquetes": 0, "docs": [], "unidades": [], "hash_textos": [],
                "corrupta": False, "timeout": isinstance(e, requests.Timeout)}


def correr_nivel(vus, duracion_s, preguntas, etiqueta):
    """Genera carga con `vus` hilos durante `duracion_s`. Fail-fast interno."""
    resultados, parar = [], threading.Event()
    def worker(i):
        k = i
        while not parar.is_set() and presupuesto_disponible():
            q = preguntas[k % len(preguntas)]
            rid = f"{etiqueta}-vu{i}-{k}-{int(time.time()*1000)}"
            resultados.append(una_peticion(q, rid, user_id=f"vu{i}"))
            k += vus
    hilos = [threading.Thread(target=worker, args=(i,), daemon=True) for i in range(vus)]
    t0 = time.time()
    for h in hilos:
        h.start()
    while time.time() - t0 < duracion_s:
        time.sleep(1)
        with _lock:
            snap = list(resultados)
        if len(snap) >= 10:
            errores = [r for r in snap if r["status"] is None or r["status"] >= 500]
            tasa = 100.0 * len(errores) / len(snap)
            if tasa > THR["fail_fast"]["error_rate_pct_ventana"] and len(snap) >= 20:
                print(f"    FAIL-FAST: error rate {tasa:.1f}% > {THR['fail_fast']['error_rate_pct_ventana']}%")
                break
        if not presupuesto_disponible():
            print(f"    LIMITE MAX_REQUESTS alcanzado")
            break
    parar.set()
    for h in hilos:
        h.join(timeout=TIMEOUT + 5)
    return resultados


def resumir(rs, vus, etiqueta, dur):
    ok = [r for r in rs if r["status"] == 200]
    lat = sorted(r["ms"] for r in ok)
    errores = [r for r in rs if r["status"] is None or r["status"] >= 500]
    timeouts = [r for r in rs if r.get("timeout")]
    def pct(p):
        return round(lat[min(int(p * len(lat)), len(lat) - 1)], 1) if lat else None
    return {"etiqueta": etiqueta, "vus": vus, "duracion_s": dur, "requests": len(rs),
            "rps": round(len(rs) / dur, 2) if dur else None,
            "ok": len(ok), "error_rate_pct": round(100.0 * len(errores) / len(rs), 2) if rs else None,
            "timeouts": len(timeouts), "corruptas": sum(1 for r in rs if r.get("corrupta")),
            "p50_ms": pct(0.50), "p90_ms": pct(0.90), "p95_ms": pct(0.95), "p99_ms": pct(0.99),
            "max_ms": lat[-1] if lat else None,
            "ms_recuperacion_p95": round(sorted([r["ms_recuperacion"] for r in ok if r.get("ms_recuperacion")])[
                min(int(0.95 * len([r for r in ok if r.get("ms_recuperacion")])), max(0, len([r for r in ok if r.get("ms_recuperacion")]) - 1))], 1) if any(r.get("ms_recuperacion") for r in ok) else None}


def snapshot_canarias(canarias, etiqueta):
    """Fase 8: ejecuta canarias 1 vez c/u y guarda firma de resultado."""
    salida = []
    for c in canarias:
        r = una_peticion(c["question"], f"canary-{etiqueta}-{c['query_id']}")
        salida.append({"query_id": c["query_id"], "etiqueta": etiqueta,
                       "status": r["status"], "ms": r["ms"], "docs": r["docs"],
                       "unidades": r["unidades"], "hash_textos": r["hash_textos"],
                       "n_paquetes": r["n_paquetes"], "corrupta": r.get("corrupta")})
    return salida


def comparar_canarias(base, otro):
    """Top-5 stability + perdida de evidencia."""
    idx = {c["query_id"]: c for c in base}
    estables, cambios = 0, []
    for c in otro:
        b = idx.get(c["query_id"])
        if not b:
            continue
        if b["docs"] == c["docs"]:
            estables += 1
        else:
            cambios.append({"query_id": c["query_id"], "baseline": b["docs"], "bajo_carga": c["docs"]})
    n = len([c for c in otro if c["query_id"] in idx])
    return {"n": n, "top5_stability_pct": round(100.0 * estables / n, 2) if n else None, "cambios": cambios[:10]}


def main():
    escenario = sys.argv[1] if len(sys.argv) > 1 else "breakpoint"
    gold = cargar("gold_queries.jsonl")
    canarias = cargar("canary_queries.jsonl")
    preguntas = [g["question"] for g in gold if g["answerable"]][:60]
    out = {"escenario": escenario, "url": URL, "inicio": time.strftime("%Y-%m-%d %H:%M:%S"), "niveles": []}

    print(f"[{escenario}] baseline de canarias (sin carga)...")
    base_canarias = snapshot_canarias(canarias, "baseline")
    out["canarias_baseline"] = base_canarias
    lat_base = statistics.median([c["ms"] for c in base_canarias if c["status"] == 200])
    out["baseline_p50_ms"] = round(lat_base, 1)
    print(f"  baseline p50 = {lat_base:.0f}ms")

    if escenario == "smoke":
        niveles = [(1, CFG["smoke"]["duracion_s"])]
    elif escenario == "normal":
        niveles = [tuple(e) for e in CFG["carga_normal"]["etapas"]]
    elif escenario == "pico":
        niveles = [(CFG["pico_clase"]["ramp_a_vus"], CFG["pico_clase"]["duracion_s"])]
    elif escenario == "spike":
        niveles = [(CFG["spike"]["base_vus"], 30), (CFG["spike"]["pico_vus"], CFG["spike"]["pico_s"]), (CFG["spike"]["base_vus"], 30)]
    elif escenario == "soak":
        niveles = [(CFG["soak_seguro"]["vus"], CFG["soak_seguro"]["duracion_s"])]
    else:
        niveles = [tuple(n) for n in CFG["breakpoint"]["niveles"]]

    degradacion = None
    for vus, dur in niveles:
        if vus > LIM["MAX_VUS"] or not presupuesto_disponible():
            print(f"  omitido nivel {vus} VUs (limite)")
            break
        print(f"  nivel {vus} VUs por {dur}s ...")
        t0 = time.time()
        rs = correr_nivel(vus, dur, preguntas, f"{escenario}{vus}")
        real = time.time() - t0
        res = resumir(rs, vus, f"{escenario}-{vus}vus", real)
        can = snapshot_canarias(canarias[:5], f"carga-{vus}vus")
        res["canarias_bajo_carga"] = comparar_canarias(base_canarias, can)
        out["niveles"].append(res)
        print(f"    req={res['requests']} rps={res['rps']} p95={res['p95_ms']}ms err={res['error_rate_pct']}% "
              f"timeouts={res['timeouts']} estabilidad={res['canarias_bajo_carga']['top5_stability_pct']}%")
        # criterios de parada
        if res["error_rate_pct"] and res["error_rate_pct"] > THR["fail_fast"]["error_rate_pct_ventana"]:
            degradacion = f"error_rate {res['error_rate_pct']}% en {vus} VUs"; break
        if res["p95_ms"] and res["p95_ms"] > lat_base * THR["fail_fast"]["p95_vs_baseline_factor"]:
            degradacion = f"p95 {res['p95_ms']}ms > {THR['fail_fast']['p95_vs_baseline_factor']}x baseline ({lat_base:.0f}ms) en {vus} VUs"
            print(f"    DEGRADACION: {degradacion}")
            break

    print("  canarias post-carga...")
    out["canarias_post"] = snapshot_canarias(canarias, "post")
    out["comparacion_post"] = comparar_canarias(base_canarias, out["canarias_post"])
    out["primer_punto_degradacion"] = degradacion
    out["total_requests"] = _total_requests
    print(f"  post-carga estabilidad Top-5 = {out['comparacion_post']['top5_stability_pct']}%")

    os.makedirs(os.path.join(BASE, "results", "raw_results"), exist_ok=True)
    dest = os.path.join(BASE, "results", f"load_{escenario}.json")
    with open(dest, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    print(f"  -> {dest} (total requests={_total_requests})")


if __name__ == "__main__":
    main()
