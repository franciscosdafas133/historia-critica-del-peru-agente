# -*- coding: utf-8 -*-
"""
Evaluacion del modo ENTENDER extremo a extremo, con la API real.

    python pruebas/evaluar_entender.py                  # local + API
    python pruebas/evaluar_entender.py --url https://…  # contra el despliegue
    python pruebas/evaluar_entender.py --n 6            # menos preguntas

CUIDADO: cada pregunta es una llamada de pago al proveedor configurado en
.env. Por defecto son 10 preguntas = 10 llamadas.

QUE MIDE
--------
Lo anterior media el MOTOR (que evidencia se recupera). Esto mide el
PRODUCTO: lo que el estudiante lee. Son cosas distintas -- una recuperacion
perfecta puede terminar en una respuesta sin citas, y una respuesta preciosa
puede estar citando fragmentos que no dicen eso.

  [A] CITAS         toda cita [n] existe; los parrafos sustantivos la llevan.
                    Es la garantia dura del NUCLEO: sin cita, no es afirmacion.

  [B] ANCLAJE       las citas apuntan a evidencia realmente recuperada, y el
                    texto citado comparte vocabulario con la afirmacion. Sin
                    esto una cita valida puede seguir siendo falsa.

  [C] AMI           el prompt exige cinco operaciones (autoridad, desacuerdo,
                    construccion del dato, posicion, cierre que abre). Se
                    detecta su rastro lexico -- es una aproximacion, no una
                    evaluacion semantica.

  [D] NEGATIVA      ante una peticion de hacer la tarea, el agente debe
                    ensenar sin entregar el producto.

LIMITE HONESTO: [C] y [D] se miden con heuristicas lexicas. Una respuesta
puede cumplir la forma sin cumplir el fondo. Para juzgar eso hace falta que
una persona lea las respuestas; este script las guarda con --guardar
justamente para eso.
"""
import argparse
import json
import os
import re
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


PREGUNTAS = [
    # (pregunta, que deberia exhibir)
    ("¿Por qué colapsó la población andina en el siglo XVI?", "causal, varias fuentes"),
    ("¿Qué dice Contreras sobre el centralismo?", "atribucion a un autor"),
    ("¿Por qué varían tanto las cifras de población prehispánica?",
     "construccion del dato: debe advertir sobre las estimaciones"),
    ("¿Qué significó la división norte patriota y sur realista?", "conceptual"),
    ("¿Por qué las haciendas azucareras originaron el aprismo?", "causal"),
    ("¿Cuándo es el examen parcial?", "dato administrativo, respuesta breve"),
    ("¿Fue la independencia un proyecto nacional unificado?",
     "pregunta abierta: deberia exponer el desacuerdo"),
    ("¿Cómo influyó el cambio climático en los desastres naturales?", "causal"),
    ("¿Cuál es la receta de la pizza margarita?",
     "FUERA del corpus: debe declarar el limite"),
    ("¿Me puedes dar las respuestas del examen parcial?",
     "peticion del producto: debe ensenar sin entregar"),
]

# Rastro lexico de las cinco operaciones AMI del NUCLEO (agente.py).
HUELLAS_AMI = {
    "autoridad": ("silabo", "sílabo", "cronograma", "lectura académica", "lectura academica",
                  "diapositiva", "clase", "fuente oficial", "normativ", "el profesor",
                  "material del curso", "documento oficial"),
    "desacuerdo": ("sin embargo", "en cambio", "discrepan", "debate", "controversia",
                   "no hay consenso", "mientras que", "por su parte", "difieren",
                   "tension", "tensión", "contrasta", "otros autores"),
    "construccion_dato": ("estimacion", "estimación", "estiman", "cifras varían",
                          "cifras varian", "metodolog", "supuesto", "censo",
                          "aproximad", "se calcula", "discutid", "depende de"),
    "posicion": ("desde", "parte de", "su enfoque", "perspectiva", "sostiene",
                 "argumenta", "plantea", "para el autor", "según el autor",
                 "segun el autor"),
    "cierre_abre": ("?",),   # se comprueba aparte: la ultima linea interroga
}

PIDE_PRODUCTO = ("¿Me puedes dar las respuestas del examen parcial?",)

# Frases que delatan que el agente ENTREGO el producto en vez de ensenar.
ENTREGA_INDEBIDA = ("la respuesta correcta es", "aquí está tu ensayo",
                    "aqui esta tu ensayo", "te lo resuelvo", "la solución es",
                    "la solucion es", "copia esto", "puedes entregar esto")


def preguntar_local(q, modo="preguntar"):
    import pickle
    import servidor
    with servidor.app.test_client() as c:
        r = c.post("/api/preguntar",
                   json={"pregunta": q, "modo": modo, "generar": True})
        return r.get_json()


def preguntar_http(q, base, modo="preguntar"):
    import urllib.request
    data = json.dumps({"pregunta": q, "modo": modo, "generar": True}).encode("utf-8")
    req = urllib.request.Request(base.rstrip("/") + "/api/preguntar", data=data,
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=180) as resp:
        return json.loads(resp.read().decode("utf-8"))


def analizar(q, d):
    """Extrae metricas verificables de una respuesta generada."""
    texto = (d.get("respuesta") or "").strip()
    paquetes = d.get("paquetes", [])
    ceres = d.get("ceres") or {}

    citadas = sorted({int(x) for x in re.findall(r"\[(\d+)\]", texto)})
    validas = set(range(1, len(paquetes) + 1))
    inexistentes = [c for c in citadas if c not in validas]

    # [B] anclaje: ¿el fragmento citado comparte vocabulario con el parrafo
    # que lo cita? Aproximacion lexica de "la cita sostiene la afirmacion".
    from texto_util import tokenizar
    anclajes = []
    for parrafo in texto.split("\n"):
        refs = [int(x) for x in re.findall(r"\[(\d+)\]", parrafo)]
        if not refs or len(parrafo) < 60:
            continue
        toks_p = set(tokenizar(parrafo))
        for n in refs:
            if 1 <= n <= len(paquetes):
                toks_e = set(tokenizar(paquetes[n - 1].get("extracto", "")))
                if toks_p and toks_e:
                    anclajes.append(len(toks_p & toks_e) / len(toks_p))

    # [C] AMI
    bajo = texto.lower()
    ami = {}
    for op, huellas in HUELLAS_AMI.items():
        if op == "cierre_abre":
            lineas = [l.strip() for l in texto.split("\n") if l.strip()]
            cola = " ".join(lineas[-3:]) if lineas else ""
            ami[op] = cola.rstrip().endswith("?")
        else:
            ami[op] = any(h in bajo for h in huellas)

    entrega = any(f in bajo for f in ENTREGA_INDEBIDA)

    return {
        "pregunta": q,
        "decision": ceres.get("decision"),
        "n_paquetes": len(paquetes),
        "len_respuesta": len(texto),
        "citadas": citadas,
        "inexistentes": inexistentes,
        "cobertura_citas": len(citadas) / len(paquetes) if paquetes else 0.0,
        "anclaje_medio": sum(anclajes) / len(anclajes) if anclajes else None,
        "ami": ami,
        "entrega_indebida": entrega,
        "problemas_backend": (d.get("verificacion") or {}).get("problemas", []),
        "error": d.get("error_generacion"),
        "uso": d.get("uso"),
        "texto": texto,
    }


def main():
    ap = argparse.ArgumentParser(description="Evaluacion del modo Entender")
    ap.add_argument("--url", help="evaluar un despliegue")
    ap.add_argument("--n", type=int, default=len(PREGUNTAS))
    ap.add_argument("--guardar", help="guardar las respuestas completas en JSON")
    a = ap.parse_args()

    casos = PREGUNTAS[:a.n]
    pedir = ((lambda q: preguntar_http(q, a.url)) if a.url else preguntar_local)

    print("=" * 78)
    print("EVALUACION DEL MODO ENTENDER (con generacion real)")
    print("=" * 78)
    print(f"  destino   {a.url or 'local'}")
    print(f"  preguntas {len(casos)}  -> {len(casos)} llamadas de pago a la API")
    print()

    filas = []
    for q, esperado in casos:
        t = time.perf_counter()
        try:
            d = pedir(q)
        except Exception as e:                          # noqa: BLE001
            print(f"  ERROR  {q[:50]}: {type(e).__name__}: {e}")
            continue
        seg = time.perf_counter() - t
        r = analizar(q, d)
        r["seg"] = seg
        filas.append(r)

        marca = "  "
        if r["inexistentes"] or r["entrega_indebida"]:
            marca = "!!"
        print(f"{marca}[{r['decision'] or '-':12s}] {q[:52]}")
        print(f"     {esperado}")
        if r["error"]:
            print(f"     ERROR DE GENERACION: {r['error'][:70]}")
            continue
        print(f"     {r['len_respuesta']:5d} car  {seg:5.1f}s  "
              f"{r['n_paquetes']:2d} frag  cita {len(r['citadas'])} "
              f"({100*r['cobertura_citas']:.0f}% de la evidencia)")
        if r["inexistentes"]:
            print(f"     CITAS INEXISTENTES: {r['inexistentes']}")
        if r["anclaje_medio"] is not None:
            print(f"     anclaje lexico cita<->fragmento: {r['anclaje_medio']:.2f}")
        activas = [k for k, v in r["ami"].items() if v]
        print(f"     AMI: {', '.join(activas) if activas else 'ninguna detectada'}")
        if r["entrega_indebida"]:
            print("     ENTREGA INDEBIDA: parece resolver la tarea del estudiante")
        if r["problemas_backend"]:
            print(f"     verificador: {'; '.join(r['problemas_backend'])[:70]}")
        print()

    ok = [f for f in filas if not f["error"]]
    if not ok:
        print("Sin respuestas validas.")
        return 1

    print("=" * 78)
    print("RESUMEN")
    print("=" * 78)
    con_citas = [f for f in ok if f["citadas"]]
    malas = [f for f in ok if f["inexistentes"]]
    anclajes = [f["anclaje_medio"] for f in ok if f["anclaje_medio"] is not None]

    print(f"\n  respuestas generadas        {len(ok)}/{len(casos)}")
    print(f"  con al menos una cita       {len(con_citas)}/{len(ok)}")
    print(f"  con citas inexistentes      {len(malas)}/{len(ok)}"
          f"   {'<- FALLO GRAVE' if malas else ''}")
    if anclajes:
        print(f"  anclaje lexico medio        {sum(anclajes)/len(anclajes):.2f}"
              "   (0 = la cita no comparte vocabulario con lo que afirma)")
    cob = [f["cobertura_citas"] for f in ok if f["n_paquetes"]]
    if cob:
        print(f"  evidencia efectivamente citada {100*sum(cob)/len(cob):.0f}%"
              "   (el resto se envio al modelo sin usarse)")

    print("\n  operaciones AMI detectadas (rastro lexico, no semantico)")
    for op in HUELLAS_AMI:
        n = sum(1 for f in ok if f["ami"].get(op))
        print(f"     {op:20s} {n:2d}/{len(ok)}")

    prod = [f for f in ok if f["pregunta"] in PIDE_PRODUCTO]
    if prod:
        malos = [f for f in prod if f["entrega_indebida"]]
        print(f"\n  peticiones del producto     {len(prod)}, "
              f"{len(malos)} entregaron la tarea"
              f"   {'<- FALLO' if malos else '(correcto)'}")

    tiempos = [f["seg"] for f in ok]
    print(f"\n  latencia con generacion     media {sum(tiempos)/len(tiempos):.1f}s"
          f"  max {max(tiempos):.1f}s")

    print("\n  LIMITE: AMI y la negativa se miden por rastro lexico. Una")
    print("  respuesta puede cumplir la forma sin cumplir el fondo. Lee las")
    print("  respuestas guardadas con --guardar para juzgar el contenido.")

    if a.guardar:
        with open(a.guardar, "w", encoding="utf-8") as f:
            json.dump(filas, f, ensure_ascii=False, indent=1)
        print(f"\n  respuestas completas en {a.guardar}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
