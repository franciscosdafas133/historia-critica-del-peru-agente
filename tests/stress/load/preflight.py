# -*- coding: utf-8 -*-
"""Fase 7.1: preflight. Si algo falla aqui, la suite se detiene."""
import json, os, socket, ssl, sys, time
from urllib.parse import urlparse
import requests

RAIZ = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
BASE = os.path.join(RAIZ, "tests", "stress")
BASE_URL = os.environ.get("BASE_URL", "https://historia-critica-del-peru-agente.onrender.com")
FRONTEND_URL = os.environ.get("FRONTEND_URL", "https://historia-critica-del-peru-agente.vercel.app")

CAMPOS_REQUERIDOS = ["pregunta", "modo", "paquetes", "avisos", "ms_recuperacion", "tokens_evidencia"]
CAMPOS_PAQUETE = ["documento", "cita", "ubicacion", "archivo", "unidad", "tokens", "score", "cobertura", "extracto"]


def main():
    out = {"base_url": BASE_URL, "frontend_url": FRONTEND_URL, "checks": []}
    def check(nombre, ok, detalle=""):
        out["checks"].append({"check": nombre, "ok": bool(ok), "detalle": str(detalle)[:300]})
        print(f"  [{'OK ' if ok else 'FAIL'}] {nombre}: {str(detalle)[:120]}")
        return ok

    host = urlparse(BASE_URL).hostname
    # DNS
    t0 = time.time()
    try:
        ip = socket.gethostbyname(host); dns_ms = (time.time()-t0)*1000
        check("dns", True, f"{host} -> {ip} en {dns_ms:.0f}ms")
    except Exception as e:
        check("dns", False, e); return fin(out, False)
    # TLS
    try:
        ctx = ssl.create_default_context()
        with ctx.wrap_socket(socket.socket(), server_hostname=host) as s:
            s.settimeout(15); s.connect((host, 443)); cert = s.getpeercert()
        check("tls", True, f"valido hasta {cert.get('notAfter')}")
    except Exception as e:
        check("tls", False, e); return fin(out, False)
    # Health
    try:
        t0 = time.time(); r = requests.get(BASE_URL + "/api/info", timeout=120)
        info = r.json(); ms = (time.time()-t0)*1000
        ok = r.status_code == 200 and info.get("documentos", 0) > 0
        check("health /api/info", ok, f"{r.status_code} docs={info.get('documentos')} bloques={info.get('bloques')} prov={info.get('proveedor')} {ms:.0f}ms")
        out["info"] = info
    except Exception as e:
        check("health /api/info", False, e); return fin(out, False)
    # Frontend
    try:
        r = requests.get(FRONTEND_URL, timeout=60)
        check("frontend publico (sin login)", r.status_code == 200 and "vercel.com/login" not in r.url, f"{r.status_code} url_final={r.url[:80]}")
    except Exception as e:
        check("frontend publico (sin login)", False, e)
    # Consulta minima + contrato
    try:
        t0 = time.time()
        r = requests.post(BASE_URL + "/api/preguntar", json={"pregunta": "examen parcial", "modo": "preguntar"},
                          headers={"X-Request-Id": "preflight-1"}, timeout=120)
        d = r.json(); ms = (time.time()-t0)*1000
        out["baseline_ms"] = ms
        out["baseline_ms_recuperacion"] = d.get("ms_recuperacion")
        faltan = [c for c in CAMPOS_REQUERIDOS if c not in d]
        check("consulta minima", r.status_code == 200 and not faltan, f"{r.status_code} en {ms:.0f}ms, ms_recuperacion={d.get('ms_recuperacion')}, faltan={faltan}")
        paqs = d.get("paquetes", [])
        check("devuelve evidencia", len(paqs) > 0, f"{len(paqs)} paquetes")
        if paqs:
            faltan_p = [c for c in CAMPOS_PAQUETE if c not in paqs[0]]
            check("contrato de procedencia en paquete", not faltan_p, f"faltan={faltan_p}")
            # OJO: `unidad` es el metadato CURRICULAR (unidad del curso), no el
            # unidad_id de FORMA-IR (ese va en `nucleo`, que la API no expone).
            # La procedencia publica se compone de archivo + ubicacion + cita.
            check("procedencia no vacia", bool(paqs[0].get("archivo")) and bool(paqs[0].get("ubicacion")),
                  f"archivo={paqs[0].get('archivo')} ubicacion={paqs[0].get('ubicacion')} cita={str(paqs[0].get('cita'))[:40]}")
    except Exception as e:
        check("consulta minima", False, e); return fin(out, False)
    # Consulta real (una segunda, warm)
    try:
        t0 = time.time()
        r = requests.post(BASE_URL + "/api/preguntar", json={"pregunta": "transiciones demograficas en el Peru", "modo": "preguntar"}, timeout=120)
        ms = (time.time()-t0)*1000; d = r.json()
        out["warm_ms"] = ms
        check("consulta real (warm)", r.status_code == 200, f"{ms:.0f}ms ms_recuperacion={d.get('ms_recuperacion')} paquetes={len(d.get('paquetes',[]))}")
    except Exception as e:
        check("consulta real (warm)", False, e)
    return fin(out, all(c["ok"] for c in out["checks"]))


def fin(out, ok):
    out["preflight_ok"] = bool(ok)
    os.makedirs(os.path.join(BASE, "results"), exist_ok=True)
    with open(os.path.join(BASE, "results", "preflight.json"), "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    print("\nPREFLIGHT:", "OK" if ok else "FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
