# -*- coding: utf-8 -*-
"""
Suite de evaluacion de CERES-Omega: estres, calidad, invariantes y ablacion.

    python pruebas/evaluar_motor.py                  # todo, en local
    python pruebas/evaluar_motor.py --url https://…  # contra un despliegue
    python pruebas/evaluar_motor.py --solo estres
    python pruebas/evaluar_motor.py --json salida.json

QUE MIDE CADA BLOQUE
--------------------
[1] ESTRES      latencia p50/p90/p95/p99, arranque en frio, throughput,
                concurrencia, estabilidad. Es lo que decide si el motor
                aguanta una clase entera usandolo a la vez.

[2] GATE        responder vs abstenerse, por familia de dificultad. Es la
                unica medida de calidad posible sin banco anotado, y la que
                mas ha cambiado al ampliar el banco.

[3] INVARIANTES propiedades estructurales que el motor debe cumplir siempre
                (un autor pedido aparece arriba, una fecha no arrastra
                libros). No-regresion, no calidad.

[4] ABLACION    apaga una senal de la frontera hibrida a la vez y mide el
                efecto. Responde "¿que etapa se gana su coste?" -- el paper
                (Apendice B) lo exige: "¿el resultado se mantiene al retirar
                titulos, entidades o estructura de forma individual?"

LIMITE HONESTO: nada de esto mide si la evidencia recuperada es la CORRECTA.
Eso exige anotar los bloques de oro por pregunta (seccion 8.3 del paper).
Un motor puede sacar 100% en todo lo de arriba y recuperar mal.
"""
import argparse
import json
import os
import statistics
import sys
import time
from collections import Counter
from concurrent.futures import ThreadPoolExecutor

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pruebas.banco_preguntas import (  # noqa: E402
    DENTRO, FUERA, FAMILIAS_DENTRO, FAMILIAS_FUERA, INVARIANTES, ADVERSARIALES,
)


# --------------------------------------------------------------- utilidades

def percentil(vals, p):
    if not vals:
        return 0.0
    s = sorted(vals)
    k = (len(s) - 1) * (p / 100.0)
    lo = int(k)
    hi = min(lo + 1, len(s) - 1)
    return s[lo] + (s[hi] - s[lo]) * (k - lo)


def barra(frac, ancho=28):
    lleno = int(round(frac * ancho))
    return "#" * lleno + "." * (ancho - lleno)


class MotorLocal:
    etiqueta = "local (indice en memoria)"

    def __init__(self):
        import pickle
        raiz = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        with open(os.path.join(raiz, "corpus", "indice.pkl"), "rb") as f:
            self.idx = pickle.load(f)
        from ceres_omega import recuperar
        self._rec = recuperar

    def __call__(self, pregunta, modo="preguntar"):
        t = time.perf_counter()
        r = self._rec(pregunta, self.idx, modo_interaccion=modo)
        return {
            "ms": (time.perf_counter() - t) * 1000,
            "decision": r["ceres"]["decision"],
            "paquetes": r["paquetes"],
            "n": len(r["paquetes"]),
            "tokens": r["plan"]["tokens_usados"],
            "tipo": r["plan"]["tipo"],
            "filtros": r["plan"]["filtros"],
            "requisitos": r["ceres"]["requirements"],
            "error": None,
        }


class MotorHTTP:
    def __init__(self, url):
        self.base = url.rstrip("/")
        self.etiqueta = self.base

    def __call__(self, pregunta, modo="preguntar"):
        import urllib.request
        import urllib.error
        data = json.dumps({"pregunta": pregunta, "modo": modo,
                           "generar": False}).encode("utf-8")
        req = urllib.request.Request(
            self.base + "/api/preguntar", data=data,
            headers={"Content-Type": "application/json"})
        t = time.perf_counter()
        try:
            with urllib.request.urlopen(req, timeout=120) as resp:
                d = json.loads(resp.read().decode("utf-8"))
        except Exception as e:                       # noqa: BLE001
            return {"ms": (time.perf_counter() - t) * 1000, "decision": None,
                    "paquetes": [], "n": 0, "tokens": 0, "tipo": None,
                    "filtros": {}, "requisitos": [],
                    "error": f"{type(e).__name__}: {e}"}
        ceres = d.get("ceres") or {}
        return {
            "ms": (time.perf_counter() - t) * 1000,
            "decision": ceres.get("decision", "SIN_CERES"),
            "paquetes": d.get("paquetes", []),
            "n": len(d.get("paquetes", [])),
            "tokens": d.get("tokens_evidencia", 0),
            "tipo": d.get("tipo"),
            "filtros": d.get("filtros", {}),
            "requisitos": ceres.get("requirements", []),
            "error": None,
        }


# ------------------------------------------------------------------ [1] estres

def bloque_estres(motor, repeticiones, concurrencia, res):
    print("\n" + "=" * 78)
    print("[1] ESTRES: latencia, arranque en frio, throughput, concurrencia")
    print("=" * 78)

    fria = motor(DENTRO[0])
    caliente = motor(DENTRO[0])
    print(f"\n  arranque en frio  {fria['ms']:8.1f} ms")
    print(f"  segunda consulta  {caliente['ms']:8.1f} ms   "
          f"(factor {fria['ms'] / max(caliente['ms'], 0.01):.0f}x)")
    print("  -> la primera carga el indice (local) o despierta el servicio")
    print("     (Render gratuito). Se excluye de los percentiles.")

    trabajos = [(q, "dentro") for q in DENTRO] + [(q, "fuera") for q in FUERA]
    trabajos *= repeticiones

    print(f"\n  recorrido secuencial: {len(trabajos)} consultas")
    t0 = time.perf_counter()
    muestras = []
    for q, grupo in trabajos:
        m = motor(q)
        m["grupo"] = grupo
        muestras.append(m)
    total = time.perf_counter() - t0

    ok = [m for m in muestras if m["error"] is None]
    fallos = [m for m in muestras if m["error"] is not None]
    ms = [m["ms"] for m in ok]

    print(f"\n  {'':14s}{'p50':>9s}{'p90':>9s}{'p95':>9s}{'p99':>9s}{'max':>10s}")
    print(f"  {'latencia (ms)':14s}{percentil(ms,50):9.1f}{percentil(ms,90):9.1f}"
          f"{percentil(ms,95):9.1f}{percentil(ms,99):9.1f}{max(ms):10.1f}")
    print(f"\n  consultas OK      {len(ok)}/{len(muestras)}")
    print(f"  fallos            {len(fallos)}")
    print(f"  throughput        {len(trabajos)/total:.1f} consultas/s")

    dentro_ms = [m["ms"] for m in ok if m["grupo"] == "dentro"]
    fuera_ms = [m["ms"] for m in ok if m["grupo"] == "fuera"]
    if dentro_ms and fuera_ms:
        print(f"\n  p50 preguntas del curso   {percentil(dentro_ms,50):7.1f} ms")
        print(f"  p50 preguntas ajenas      {percentil(fuera_ms,50):7.1f} ms"
              f"   <- se abstiene antes de buscar")

    res["estres"] = {
        "frio_ms": fria["ms"], "caliente_ms": caliente["ms"],
        "p50": percentil(ms, 50), "p95": percentil(ms, 95),
        "p99": percentil(ms, 99), "max": max(ms),
        "consultas": len(muestras), "fallos": len(fallos),
        "throughput": len(trabajos) / total,
    }

    if concurrencia > 1:
        print(f"\n  carga concurrente: {concurrencia} hilos")
        t0 = time.perf_counter()
        with ThreadPoolExecutor(max_workers=concurrencia) as ex:
            futs = [ex.submit(motor, q) for q, _g in trabajos]
            conc = [f.result() for f in futs]
        tc = time.perf_counter() - t0
        ok_c = [m for m in conc if m["error"] is None]
        ms_c = [m["ms"] for m in ok_c]
        print(f"    p50 {percentil(ms_c,50):8.1f} ms   p95 {percentil(ms_c,95):8.1f} ms"
              f"   max {max(ms_c):8.1f} ms")
        print(f"    throughput {len(trabajos)/tc:.1f} consultas/s"
              f"   fallos {len(conc)-len(ok_c)}")
        deg = percentil(ms_c, 95) / max(percentil(ms, 95), 0.01)
        print(f"    degradacion p95: {deg:.1f}x respecto a secuencial")
        if len(conc) - len(ok_c) == 0:
            print("    -> sin errores bajo carga: el motor es reentrante")
        res["estres"]["concurrencia"] = {
            "hilos": concurrencia, "p95": percentil(ms_c, 95),
            "fallos": len(conc) - len(ok_c), "degradacion": deg,
        }


# -------------------------------------------------------------------- [2] gate

def bloque_gate(motor, res):
    print("\n" + "=" * 78)
    print("[2] GATE DE ALCANCE: responder cuando debe, abstenerse cuando debe")
    print("=" * 78)

    fn, fp = [], []
    dec_d, dec_f = Counter(), Counter()

    print("\n  DENTRO del temario (debe responder)")
    for fam, qs in FAMILIAS_DENTRO.items():
        malas = []
        for q in qs:
            r = motor(q)
            dec_d[r["decision"]] += 1
            if r["decision"] == "INSUFFICIENT":
                malas.append(q)
                fn.append((fam, q))
        acierto = (len(qs) - len(malas)) / len(qs)
        print(f"    {fam:16s} {barra(acierto)} {len(qs)-len(malas):2d}/{len(qs):2d}"
              f"  {100*acierto:5.1f}%")
        for q in malas:
            print(f"        FALLA: {q}")

    print("\n  FUERA del temario (debe abstenerse)")
    for fam, qs in FAMILIAS_FUERA.items():
        malas = []
        for q in qs:
            r = motor(q)
            dec_f[r["decision"]] += 1
            if r["decision"] not in ("INSUFFICIENT", None):
                malas.append((q, r["decision"], r["n"]))
                fp.append((fam, q, r["decision"], r["n"]))
        acierto = (len(qs) - len(malas)) / len(qs)
        print(f"    {fam:40s} {barra(acierto)} {len(qs)-len(malas):2d}/{len(qs):2d}"
              f"  {100*acierto:5.1f}%")
        for q, d, n in malas:
            print(f"        FALLA [{d}, {n} frag]: {q}")

    vp = len(DENTRO) - len(fn)
    vn = len(FUERA) - len(fp)
    prec = vp / (vp + len(fp)) if (vp + len(fp)) else 0.0
    rec = vp / (vp + len(fn)) if (vp + len(fn)) else 0.0
    f1 = 2 * prec * rec / (prec + rec) if (prec + rec) else 0.0
    total = len(DENTRO) + len(FUERA)

    print(f"\n  {'':26s}{'aciertos':>12s}{'%':>9s}")
    print(f"  {'responde lo del curso':26s}{vp:>8d}/{len(DENTRO):<4d}"
          f"{100*vp/len(DENTRO):>8.1f}")
    print(f"  {'rechaza lo ajeno':26s}{vn:>8d}/{len(FUERA):<4d}"
          f"{100*vn/len(FUERA):>8.1f}")
    print(f"  {'GLOBAL':26s}{vp+vn:>8d}/{total:<4d}{100*(vp+vn)/total:>8.1f}")
    print(f"\n  precision {prec:.3f}   recall {rec:.3f}   F1 {f1:.3f}")
    print(f"  decisiones dentro: {dict(dec_d)}")
    print(f"  decisiones fuera : {dict(dec_f)}")

    if fp:
        print("\n  DONDE ESTA EL PROBLEMA")
        por_fam = Counter(f[0] for f in fp)
        for fam, n in por_fam.most_common():
            print(f"    {n} falsos positivos en '{fam}'")

    res["gate"] = {
        "dentro_ok": vp, "dentro_total": len(DENTRO),
        "fuera_ok": vn, "fuera_total": len(FUERA),
        "precision": prec, "recall": rec, "f1": f1,
        "falsos_negativos": [q for _f, q in fn],
        "falsos_positivos": [{"familia": f, "pregunta": q, "decision": d, "frag": n}
                             for f, q, d, n in fp],
    }


# ------------------------------------------------------------- [3] invariantes

def bloque_invariantes(motor, res):
    print("\n" + "=" * 78)
    print("[3] INVARIANTES ESTRUCTURALES (no-regresion)")
    print("=" * 78)
    print()

    resultados = []
    for q, prop, desc in INVARIANTES:
        r = motor(q)
        docs = [p["documento"] if "documento" in p else p.get("doc", "")
                for p in r["paquetes"]]
        ok, detalle = True, ""

        if prop == "pocos_paquetes":
            ok = 0 < r["n"] <= 4
            detalle = f"{r['n']} fragmentos (esperado 1-4)"
        elif prop == "autor_arriba":
            ok = any("contreras" in d.lower() for d in docs[:3])
            detalle = f"top-3: {[d[:26] for d in docs[:3]]}"
        elif prop == "filtro_semana":
            ok = "semana" in (r["filtros"] or {})
            detalle = f"filtros={r['filtros']}"
        elif prop == "multi_documento":
            ok = len({d for d in docs}) >= 2
            detalle = f"{len(set(docs))} documentos distintos"
        elif prop == "dos_autores":
            bajos = " ".join(docs).lower()
            ok = "contreras" in bajos and ("klar" in bajos)
            detalle = f"{len(set(docs))} docs: {[d[:22] for d in docs[:4]]}"

        marca = "OK  " if ok else "MAL "
        print(f"  {marca}{desc}")
        print(f"       {q}")
        print(f"       {detalle}")
        resultados.append({"pregunta": q, "propiedad": prop, "ok": ok,
                           "detalle": detalle})

    n_ok = sum(1 for r in resultados if r["ok"])
    print(f"\n  {n_ok}/{len(resultados)} invariantes se cumplen")
    res["invariantes"] = resultados


# ------------------------------------------------------------ [3b] adversarial

def bloque_adversarial(motor, res):
    """Entradas hostiles o malformadas.

    Distingue QUIEN debe contener cada riesgo. El motor de recuperacion no
    puede negarse a "dame las respuestas del examen": su trabajo es traer
    evidencia, y el cronograma es evidencia legitima para esa consulta. Quien
    debe negarse es el prompt (seccion TRABAJOS Y EVALUACIONES del NUCLEO en
    agente.py). Mezclar las dos capas lleva a exigirle al motor algo que no
    le toca -- y a no comprobar lo que si le toca: no romperse.
    """
    print("\n" + "=" * 78)
    print("[3b] ADVERSARIAL: entradas hostiles y malformadas")
    print("=" * 78)
    print("\n  El motor solo debe garantizar NO ROMPERSE. Negarse a hacer la")
    print("  tarea del estudiante es responsabilidad del prompt, no del motor.")
    print()

    filas = []
    for q, riesgo, responsable in ADVERSARIALES:
        try:
            r = motor(q)
            roto = r["error"] is not None
            estado = f"{r['decision']}, {r['n']} frag" if not roto else r["error"][:40]
        except Exception as e:                        # noqa: BLE001
            roto, estado = True, f"EXCEPCION {type(e).__name__}: {e}"[:60]

        marca = "MAL " if roto else "OK  "
        etiqueta = q if len(q) <= 42 else q[:39] + "..."
        print(f"  {marca}[{responsable:8s}] {etiqueta!r:46s} -> {estado}")
        if roto:
            print(f"         riesgo: {riesgo}")
        filas.append({"pregunta": q[:80], "riesgo": riesgo,
                      "responsable": responsable, "roto": roto,
                      "estado": estado})

    rotos = sum(1 for f in filas if f["roto"])
    print(f"\n  {len(filas)-rotos}/{len(filas)} entradas manejadas sin romper el motor")
    if rotos:
        print(f"  {rotos} provocaron un fallo -> son bugs del motor")

    del_prompt = [f for f in filas if f["responsable"] == "prompt" and not f["roto"]]
    if del_prompt:
        print(f"\n  {len(del_prompt)} consultas piden que el agente haga la tarea del")
        print("  estudiante. El motor devuelve evidencia (correcto); quien debe")
        print("  negarse a resolverla es el prompt. VERIFICAR A MANO en la web")
        print("  que el agente ensena pero no entrega el producto.")

    res["adversarial"] = filas


# ---------------------------------------------------------------- [4] ablacion

def bloque_ablacion(res):
    """Apaga una senal de la frontera a la vez.

    Apendice B del paper: "¿El resultado se mantiene al retirar titulos,
    entidades o estructura de forma individual?" Si apagar una senal no
    cambia nada, esa senal no se esta ganando su coste.

    Solo corre en local: necesita tocar el modulo por dentro.
    """
    print("\n" + "=" * 78)
    print("[4] ABLACION: que senal de la frontera se gana su coste")
    print("=" * 78)

    import pickle
    import ceres_omega as C

    raiz = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    with open(os.path.join(raiz, "corpus", "indice.pkl"), "rb") as f:
        idx = pickle.load(f)

    originales = {
        "bm25": C._ranking_bm25,
        "denso": C._ranking_denso,
        "titulo": C._ranking_titulo,
        "entidad": C._ranking_entidad,
        "estructura": C._ranking_estructura,
    }

    def limpiar_cache():
        for k in ("_ceres_toks", "_ceres_ctx", "_ceres_idf",
                  "_ceres_autores", "_ceres_ref_bm25"):
            idx.pop(k, None)

    def medir():
        """Firma de evidencia por pregunta + latencia media.

        Se mide QUE EVIDENCIA cambia, no si el motor responde. Medir la
        decision era inutil: el gate de alcance decide ANTES de construir la
        frontera, asi que apagar una senal daba delta 0 en todas y parecia
        que ninguna aportaba. El solape de Jaccard entre la evidencia base y
        la evidencia sin la senal si mide la contribucion real.
        """
        firmas, tiempos = {}, []
        for q in DENTRO:
            t = time.perf_counter()
            r = C.recuperar(q, idx)
            tiempos.append((time.perf_counter() - t) * 1000)
            firmas[q] = {p["bloque_id"] for p in r["paquetes"]}
        return firmas, statistics.mean(tiempos)

    print("\n  midiendo linea base...")
    limpiar_cache()
    base_firmas, base_ms = medir()
    n_base = sum(len(v) for v in base_firmas.values())
    print(f"  base: {n_base} fragmentos en {len(DENTRO)} preguntas, "
          f"{base_ms:.1f} ms/consulta")

    print(f"\n  {'senal apagada':16s}{'solape':>9s}{'identicas':>12s}"
          f"{'frag':>7s}{'ms':>8s}")
    filas = []
    for nombre, fn_orig in originales.items():
        limpiar_cache()
        setattr(C, "_ranking_" + nombre, lambda *a, **k: [])
        try:
            firmas, ms = medir()
        finally:
            setattr(C, "_ranking_" + nombre, fn_orig)
            limpiar_cache()

        solapes, iguales = [], 0
        for q in DENTRO:
            a, b = base_firmas[q], firmas[q]
            if a or b:
                solapes.append(len(a & b) / len(a | b))
            if a == b:
                iguales += 1
        solape = sum(solapes) / len(solapes) if solapes else 1.0
        n_frag = sum(len(v) for v in firmas.values())

        print(f"  {'sin ' + nombre:16s}{solape:>9.3f}{iguales:>8d}/{len(DENTRO):<3d}"
              f"{n_frag:>7d}{ms:>8.1f}")
        filas.append({"senal": nombre, "solape": solape, "identicas": iguales,
                      "fragmentos": n_frag, "ms": ms})

    print("\n  solape = Jaccard entre la evidencia con y sin esa senal.")
    print("  1.000 y todas identicas -> la senal no influye: sobra.")
    print("  solape bajo -> la senal cambia mucho que evidencia se recupera.")
    print("\n  ADVERTENCIA: 'cambia la evidencia' no es 'la mejora'. Decidir")
    print("  cual version es mejor exige los bloques de oro anotados que")
    print("  todavia no existen (seccion 8.3 del paper).")
    res["ablacion"] = {"base_fragmentos": n_base, "base_ms": base_ms,
                       "filas": filas}


# -------------------------------------------------------------------- informe

def veredicto(res):
    print("\n" + "=" * 78)
    print("VEREDICTO")
    print("=" * 78)

    g = res.get("gate")
    e = res.get("estres")
    if e:
        rapido = e["p95"] < 1000
        estable = e["fallos"] == 0
        print(f"\n  velocidad    {'OK ' if rapido else 'MAL'}  "
              f"p95 {e['p95']:.0f} ms, p99 {e['p99']:.0f} ms")
        print(f"  estabilidad  {'OK ' if estable else 'MAL'}  "
              f"{e['fallos']} fallos en {e['consultas']} consultas")
    if g:
        d = g["dentro_ok"] / g["dentro_total"]
        f = g["fuera_ok"] / g["fuera_total"]
        print(f"  cobertura    {'OK ' if d >= 0.95 else 'MAL'}  "
              f"responde {100*d:.1f}% de lo que el curso cubre")
        print(f"  abstencion   {'OK ' if f >= 0.90 else 'MAL'}  "
              f"rechaza {100*f:.1f}% de lo ajeno")

        if f < 0.90:
            print("\n  LIMITACION PRINCIPAL")
            print("  El gate mide PRESENCIA DE TERMINOS, no tema. Una pregunta")
            print("  de historia peruana fuera del corpus usa el mismo")
            print("  vocabulario que una de dentro, asi que la metrica no las")
            print("  separa. No se arregla moviendo el umbral: hay que decidir")
            print("  con la evidencia realmente recuperada, no con estadistica")
            print("  de terminos sobre el corpus entero.")

    print("\n  LO QUE ESTA SUITE NO PUEDE DECIRTE")
    print("  Si la evidencia recuperada es la CORRECTA. Para eso hace falta")
    print("  anotar los bloques de oro por pregunta (seccion 8.3 del paper).")
    print("  Un motor puede aprobar todo lo anterior y recuperar mal.")


def main():
    ap = argparse.ArgumentParser(description="Evaluacion de CERES-Omega")
    ap.add_argument("--url", help="evaluar un despliegue en vez del motor local")
    ap.add_argument("--repeticiones", type=int, default=2)
    ap.add_argument("--concurrencia", type=int, default=8)
    ap.add_argument("--solo", choices=["estres", "gate", "invariantes",
                                       "adversarial", "ablacion"])
    ap.add_argument("--json", help="guardar resultados en un archivo JSON")
    a = ap.parse_args()

    motor = MotorHTTP(a.url) if a.url else MotorLocal()

    print("=" * 78)
    print("EVALUACION DE CERES-OMEGA")
    print("=" * 78)
    print(f"  destino      {motor.etiqueta}")
    print(f"  banco        {len(DENTRO)} dentro + {len(FUERA)} fuera "
          f"= {len(DENTRO)+len(FUERA)} preguntas")
    print(f"  fecha        {time.strftime('%Y-%m-%d %H:%M')}")

    res = {"destino": motor.etiqueta, "fecha": time.strftime("%Y-%m-%d %H:%M")}

    if a.solo in (None, "estres"):
        bloque_estres(motor, a.repeticiones, a.concurrencia, res)
    if a.solo in (None, "gate"):
        bloque_gate(motor, res)
    if a.solo in (None, "invariantes"):
        bloque_invariantes(motor, res)
    if a.solo in (None, "adversarial"):
        bloque_adversarial(motor, res)
    if a.solo in (None, "ablacion"):
        if a.url:
            print("\n[4] ABLACION: omitida (requiere el motor local)")
        else:
            bloque_ablacion(res)

    if a.solo is None:
        veredicto(res)

    if a.json:
        with open(a.json, "w", encoding="utf-8") as f:
            json.dump(res, f, ensure_ascii=False, indent=1)
        print(f"\nresultados guardados en {a.json}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
