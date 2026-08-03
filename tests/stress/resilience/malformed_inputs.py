# -*- coding: utf-8 -*-
"""Fase 5: entradas malformadas y adversariales contra PRODUCCION.
Sin LLM (generar ausente => solo recuperacion). Volumen bajo y acotado.
Clasifica cada fallo por componente. Salida: results/resilience.json
"""
import json, os, sys, time
import requests

RAIZ = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
BASE = os.path.join(RAIZ, "tests", "stress")
BASE_URL = os.environ.get("BASE_URL", "https://historia-critica-del-peru-agente.onrender.com")
PATH = os.environ.get("RETRIEVE_PATH", "/api/preguntar")
URL = BASE_URL + PATH
TIMEOUT = 100


def cargar(nombre):
    with open(os.path.join(BASE, "datasets", nombre), encoding="utf-8") as f:
        return [json.loads(l) for l in f if l.strip()]


def clasificar(caso, status, cuerpo, err):
    if err:
        return "infraestructura"
    if status >= 500:
        return "validacion de entrada" if caso.get("descripcion") else "ranking"
    return None


def main():
    resultados = []
    # --- malformados ---
    for m in cargar("malformed_requests.jsonl"):
        rid = f"stress-{m['id']}-{int(time.time()*1000)}"
        headers = {"Content-Type": m.get("content_type", "application/json"), "X-Request-Id": rid}
        t0 = time.time()
        err = None
        try:
            if "raw_body" in m:
                resp = requests.post(URL, data=m["raw_body"].encode("utf-8", "surrogateescape"), headers=headers, timeout=TIMEOUT)
            else:
                resp = requests.post(URL, json=m["body"], headers=headers, timeout=TIMEOUT)
            status, texto = resp.status_code, resp.text[:400]
        except Exception as e:
            status, texto, err = None, "", f"{type(e).__name__}: {e}"
        # Criterio: NUNCA 5xx ni excepcion; 4xx o 200 con manejo limpio es correcto
        ok = err is None and status is not None and status < 500
        resultados.append({"tipo": "malformed", "id": m["id"], "descripcion": m["descripcion"],
                           "status": status, "ms": round((time.time()-t0)*1000), "ok": ok,
                           "error": err, "muestra": texto[:200],
                           "componente_fallo": None if ok else ("infraestructura" if err else "validacion de entrada")})
        print(f"  {m['id']:4s} {str(status):5s} ok={ok} {m['descripcion'][:40]}")

    # --- adversariales ---
    for a in cargar("adversarial_queries.jsonl"):
        if a.get("repeticiones"):
            continue  # se maneja en la prueba de carga/cache
        rid = f"stress-{a['id']}-{int(time.time()*1000)}"
        t0 = time.time()
        err = None
        try:
            resp = requests.post(URL, json={"pregunta": a["query"], "modo": "preguntar"},
                                 headers={"X-Request-Id": rid}, timeout=TIMEOUT)
            status = resp.status_code
            try:
                data = resp.json()
            except Exception:
                data = {}
            texto = json.dumps(data, ensure_ascii=False)[:300]
        except Exception as e:
            status, data, texto, err = None, {}, "", f"{type(e).__name__}: {e}"

        # Deteccion de fuga: marcadores INEQUIVOCOS de system prompt o secretos.
        # Un primer intento uso la subcadena "eres un" y disparaba falso positivo
        # con el aviso legitimo "...no supERES UN umbral de significancia" -- se
        # sustituye por marcadores reales del prompt de sistema (agente.py) y de
        # credenciales, con limites de palabra donde importa.
        # Se excluye el ECO de la consulta (campo "pregunta"): la API devuelve la
        # pregunta tal cual, asi que buscar "system prompt" en el blob completo
        # disparaba sobre el texto que el propio atacante envio, no sobre una fuga.
        import re as _re
        fuga_prompt = False
        if isinstance(data, dict):
            data_sin_eco = {k: v for k, v in data.items() if k != "pregunta"}
            blob = json.dumps(data_sin_eco, ensure_ascii=False)
            patrones = [r"system prompt", r"\bSISTEMA\s*=", r"api[_-]?key\s*[:=]",
                        r"\bsk-[A-Za-z0-9]{10,}", r"os\.environ", r"ANTHROPIC_API_KEY",
                        r"COHERE_API_KEY", r"GEMINI_API_KEY", r"GROQ_API_KEY"]
            fuga_prompt = any(_re.search(p, blob, _re.I) for p in patrones)
        ok = err is None and status is not None and status < 500 and not fuga_prompt
        resultados.append({"tipo": "adversarial", "id": a["id"], "categoria": a["categoria"],
                           "status": status, "ms": round((time.time()-t0)*1000), "ok": ok,
                           "error": err, "fuga_prompt": fuga_prompt,
                           "n_paquetes": len(data.get("paquetes", [])) if isinstance(data, dict) else None,
                           "muestra": texto[:200],
                           "componente_fallo": None if ok else ("infraestructura" if err else "validacion de entrada")})
        print(f"  {a['id']:4s} {str(status):5s} ok={ok} {a['categoria'][:30]}")

    os.makedirs(os.path.join(BASE, "results"), exist_ok=True)
    with open(os.path.join(BASE, "results", "resilience.json"), "w", encoding="utf-8") as f:
        json.dump({"url": URL, "resultados": resultados,
                   "fallos": [r for r in resultados if not r["ok"]]}, f, ensure_ascii=False, indent=2)
    fallos = [r for r in resultados if not r["ok"]]
    print(f"\nTotal={len(resultados)} OK={len(resultados)-len(fallos)} FALLOS={len(fallos)}")
    for f_ in fallos:
        print("  FALLO:", f_["id"], f_.get("descripcion") or f_.get("categoria"), f_["status"], f_["error"])


if __name__ == "__main__":
    main()
