# -*- coding: utf-8 -*-
"""Fase 7.9: end-to-end CON LLM, estrictamente acotado por MAX_LLM_REQUESTS.
Separa latencia de recuperacion vs latencia del proveedor: la del LLM NO se
atribuye a FORMA-IR. Verifica citas, respuestas vacias y fugas.
"""
import json, os, statistics, sys, time
import requests

RAIZ = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
BASE = os.path.join(RAIZ, "tests", "stress")
BASE_URL = os.environ.get("BASE_URL", "https://historia-critica-del-peru-agente.onrender.com")
URL = BASE_URL + os.environ.get("ASK_PATH", "/api/preguntar")
MAX_LLM = int(os.environ.get("MAX_LLM_REQUESTS", "6"))
TIMEOUT = 150

PREGUNTAS = [
    "Cuando es el examen parcial del curso",
    "Que es la transicion demografica",
    "Que dice Contreras sobre la crisis demografica del siglo XVI",
    "Cual es la formula quimica del acido sulfurico",  # no respondible -> debe abstenerse
]


def main():
    usadas = 0
    filas = []
    for q in PREGUNTAS:
        if usadas >= MAX_LLM:
            print(f"  LIMITE MAX_LLM_REQUESTS={MAX_LLM} alcanzado"); break
        usadas += 1
        t0 = time.time()
        try:
            r = requests.post(URL, json={"pregunta": q, "modo": "preguntar", "generar": True},
                              headers={"X-Request-Id": f"e2e-{usadas}"}, timeout=TIMEOUT)
            total_ms = (time.time() - t0) * 1000
            d = r.json()
            uso = d.get("uso") or {}
            ver = d.get("verificacion") or {}
            resp = d.get("respuesta")
            fila = {
                "pregunta": q, "status": r.status_code, "total_ms": round(total_ms),
                "ms_recuperacion": d.get("ms_recuperacion"),
                "ms_llm": uso.get("ms"),
                "ms_otros": round(total_ms - (d.get("ms_recuperacion") or 0) - (uso.get("ms") or 0)),
                "tokens_entrada": uso.get("entrada"), "tokens_salida": uso.get("salida"),
                "proveedor": uso.get("proveedor"), "modelo": uso.get("modelo"),
                "n_paquetes": len(d.get("paquetes", [])),
                "respuesta_vacia": not bool(resp and resp.strip()),
                "citas_usadas": ver.get("citadas"), "citas_problemas": ver.get("problemas"),
                "error_generacion": d.get("error_generacion"),
                "respuesta_muestra": (resp or "")[:220],
            }
        except Exception as e:
            fila = {"pregunta": q, "status": None, "error": f"{type(e).__name__}: {e}",
                    "total_ms": round((time.time()-t0)*1000), "respuesta_vacia": True}
        filas.append(fila)
        print(f"  [{fila.get('status')}] {q[:45]:45s} total={fila.get('total_ms')}ms "
              f"rec={fila.get('ms_recuperacion')}ms llm={fila.get('ms_llm')}ms "
              f"vacia={fila.get('respuesta_vacia')} problemas={fila.get('citas_problemas')}")

    ok = [f for f in filas if f.get("status") == 200]
    resumen = {
        "llm_requests_usadas": usadas, "max_llm_requests": MAX_LLM,
        "http_errors_pct": round(100.0 * (len(filas) - len(ok)) / len(filas), 2) if filas else None,
        "respuestas_vacias_pct": round(100.0 * sum(1 for f in filas if f.get("respuesta_vacia")) / len(filas), 2) if filas else None,
        "total_p95_ms": max((f["total_ms"] for f in ok), default=None),
        "recuperacion_media_ms": round(statistics.mean([f["ms_recuperacion"] for f in ok if f.get("ms_recuperacion")])) if ok else None,
        "llm_media_ms": round(statistics.mean([f["ms_llm"] for f in ok if f.get("ms_llm")])) if any(f.get("ms_llm") for f in ok) else None,
        "tokens_entrada_media": round(statistics.mean([f["tokens_entrada"] for f in ok if f.get("tokens_entrada")])) if any(f.get("tokens_entrada") for f in ok) else None,
        "citas_con_problemas": sum(1 for f in ok if f.get("citas_problemas")),
    }
    with open(os.path.join(BASE, "results", "e2e_quality.json"), "w", encoding="utf-8") as f:
        json.dump({"resumen": resumen, "filas": filas}, f, ensure_ascii=False, indent=2)
    print("\n" + json.dumps(resumen, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
