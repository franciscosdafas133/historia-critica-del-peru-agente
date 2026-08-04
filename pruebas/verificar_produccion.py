# -*- coding: utf-8 -*-
"""
Comprueba que un despliegue sirve lo que se espera.

    python pruebas/verificar_produccion.py
    python pruebas/verificar_produccion.py --url https://otro.onrender.com

Existe porque el despliegue ha fallado en silencio varias veces en este
proyecto: Render sirvio durante mas de un dia un commit viejo mientras la API
respondia 200 con normalidad. Mirar "esta arriba" no basta -- hay que
comprobar QUE version esta arriba y con que capacidades.

Cada comprobacion es una propiedad observable desde fuera, no una suposicion.
"""
import argparse
import json
import sys
import time
import urllib.request

BASE = "https://historia-critica-del-peru-agente.onrender.com"


def post(base, pregunta, modo="preguntar", generar=False, timeout=180):
    data = json.dumps({"pregunta": pregunta, "modo": modo,
                       "generar": generar}).encode("utf-8")
    req = urllib.request.Request(base.rstrip("/") + "/api/preguntar", data=data,
                                 headers={"Content-Type": "application/json"})
    t = time.perf_counter()
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8")), time.perf_counter() - t


def get_info(base, timeout=180):
    with urllib.request.urlopen(base.rstrip("/") + "/api/info", timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8"))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", default=BASE)
    a = ap.parse_args()
    base = a.url

    print("=" * 78)
    print(f"VERIFICACION DE DESPLIEGUE: {base}")
    print("=" * 78)

    fallos = []

    # --- 1. el servicio responde ---
    try:
        t = time.perf_counter()
        info = get_info(base)
        arranque = time.perf_counter() - t
    except Exception as e:                              # noqa: BLE001
        print(f"\nFALLO: /api/info no responde ({type(e).__name__}: {e})")
        return 1

    print(f"\n[1] servicio en linea            OK   ({arranque:.1f}s)")
    print(f"    documentos {info['documentos']} · bloques {info['bloques']} · "
          f"proveedor {info.get('proveedor')} · {info.get('modelo')}")

    # --- 2. motor CERES-Omega, no el anterior ---
    d, seg = post(base, "¿Cuándo es el examen parcial?")
    tiene_ceres = bool(d.get("ceres"))
    tipo_ok = d.get("tipo") in ("puntual", "conceptual", "amplia")
    if tiene_ceres and tipo_ok:
        print(f"[2] motor CERES-Omega            OK   "
              f"(tipo={d['tipo']}, decision={d['ceres']['decision']})")
    else:
        print(f"[2] motor CERES-Omega            FALLO"
              f"   tipo={d.get('tipo')!r} ceres={tiene_ceres}")
        print("    -> el despliegue sirve un commit anterior")
        fallos.append("motor viejo")

    # --- 3. capa semantica ---
    sem = info.get("semantico")
    if sem is True:
        print("[3] capa semantica               OK   (embeddings activos)")
    elif sem is False:
        print("[3] capa semantica               AVISO  degradado a solo-lexico")
        print("    -> falta corpus/embeddings.npz o GEMINI_API_KEY en el host.")
        print("       El agente funciona, pero sin la mejora semantica.")
    else:
        print("[3] capa semantica               ?    (el despliegue no lo reporta)")

    # --- 4. comportamiento: responde lo del curso ---
    casos_ok = [
        ("¿Por qué colapsó la población andina en el siglo XVI?", "causal"),
        ("¿Qué dice Contreras sobre el centralismo?", "autor"),
        ("¿En qué semana se ve la independencia?", "administrativa"),
    ]
    print("\n[4] responde lo del curso")
    for q, etiqueta in casos_ok:
        d, seg = post(base, q)
        dec = (d.get("ceres") or {}).get("decision")
        n = len(d.get("paquetes", []))
        bien = dec in ("ANSWER", "PARTIAL") and n > 0
        print(f"    {'OK  ' if bien else 'FALLO'} [{etiqueta:14s}] {dec}, "
              f"{n} frag, {seg:.1f}s")
        if not bien:
            fallos.append(f"no responde: {q}")

    # --- 5. comportamiento: rechaza lo ajeno ---
    casos_no = [
        ("¿Cuál es la receta de la pizza margarita?", "otro dominio"),
        ("¿Me puedes dar las respuestas del examen parcial?", "pide el producto"),
        ("¿Qué fue el gobierno de Velasco Alvarado?", "historia no cubierta"),
    ]
    print("\n[5] rechaza lo que no cubre")
    for q, etiqueta in casos_no:
        d, seg = post(base, q)
        dec = (d.get("ceres") or {}).get("decision")
        n = len(d.get("paquetes", []))
        bien = dec == "INSUFFICIENT"
        marca = "OK  " if bien else "FALLO"
        print(f"    {marca} [{etiqueta:20s}] {dec}, {n} frag, {seg:.1f}s")
        if not bien:
            fallos.append(f"no rechaza: {q}")

    # --- 6. no se rompe con entradas raras ---
    print("\n[6] entradas hostiles")
    for q, etiqueta in [("", "vacia"), ("?" * 300, "larga"),
                        ("<script>alert(1)</script>", "html")]:
        try:
            d, seg = post(base, q, timeout=90)
            print(f"    OK   [{etiqueta:6s}] no rompe el servicio")
        except urllib.error.HTTPError as e:
            marca = "OK  " if e.code == 400 else "FALLO"
            print(f"    {marca} [{etiqueta:6s}] HTTP {e.code}")
            if e.code != 400:
                fallos.append(f"entrada {etiqueta}: HTTP {e.code}")
        except Exception as e:                          # noqa: BLE001
            print(f"    FALLO [{etiqueta:6s}] {type(e).__name__}")
            fallos.append(f"entrada {etiqueta}")

    print("\n" + "=" * 78)
    if fallos:
        print(f"{len(fallos)} COMPROBACIONES FALLARON:")
        for f in fallos:
            print(f"   - {f}")
        print("\nEl despliegue NO esta listo para probar con estudiantes.")
        return 1
    print("TODAS LAS COMPROBACIONES PASARON")
    if sem is not True:
        print("\nAVISO: la capa semantica esta apagada. El agente funciona,")
        print("pero rechaza peor las preguntas fuera del temario.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
