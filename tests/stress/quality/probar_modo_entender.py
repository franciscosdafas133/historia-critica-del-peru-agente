# -*- coding: utf-8 -*-
"""Prueba del modo ENTENDER contra PRODUCCION con preguntas reales de estudiante.

Mide SOLO recuperacion (sin generar) para no gastar cuota de LLM:
  - documento esperado recuperado (anotado a mano contra el temario real)
  - cobertura de la mejor evidencia
  - si aparece el cronograma/silabo cuando NO deberia (documento indice)
  - sensibilidad a los acentos (misma pregunta con y sin tildes)

Uso: python tests/stress/quality/probar_modo_entender.py
"""
import json, os, statistics, sys, time, unicodedata
import requests

RAIZ = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
BASE = os.path.join(RAIZ, "tests", "stress")
URL = os.environ.get("BASE_URL", "https://historia-critica-del-peru-agente.onrender.com") + "/api/preguntar"
TIMEOUT = 180

# Preguntas como las escribiria un estudiante, con el documento esperado
# anotado A MANO contra el temario y las lecturas reales del curso.
# `espera` es una subcadena distintiva del nombre de archivo esperado.
PREGUNTAS = [
    # --- Unidad 1: demografia ---
    ("¿Por qué colapsó la población indígena en el siglo XVI?", "Contreras_2020", "demografia"),
    ("¿Qué papel tuvieron las epidemias en la caída demográfica colonial?", "Contreras_2020", "demografia"),
    ("¿Cuántos habitantes tenía el imperio inca antes de la conquista?", "Contreras_2020", "demografia"),
    ("¿Qué es la transición demográfica?", None, "demografia"),
    ("¿Qué explica la explosión demográfica del siglo XX en el Perú?", "Contreras_1994", "demografia"),
    ("¿Cómo cambió la fecundidad en el Perú en las últimas décadas?", None, "demografia"),
    ("¿Qué es el bono demográfico?", None, "demografia"),
    ("¿Cómo ha sido la migración interna en el Perú?", "Aramburú", "demografia"),
    # --- Unidad 1: territorio y medioambiente ---
    ("¿Por qué el Perú es un país de montañas tropicales?", "Amat", "territorio"),
    ("¿Qué impacto tuvo el fenómeno del Niño en la historia peruana?", "Cavieses", "territorio"),
    ("¿Cómo afecta el retroceso de los glaciares al Perú?", "Carey", "territorio"),
    ("¿Qué cambios hubo en los paisajes de la costa norte?", "Rivasplata", "territorio"),
    # --- Unidad 2: procesos socioeconomicos ---
    ("¿Qué dice Contreras sobre el centralismo peruano?", "Contreras_2002", "centralismo"),
    ("¿Por qué Lima concentró tanto poder frente al resto del país?", "Contreras_2002", "centralismo"),
    ("¿Cómo surgieron las haciendas azucareras y el APRA?", "Klaren", "haciendas"),
    ("¿Qué relación hay entre las haciendas azucareras y el aprismo?", "Klaren", "haciendas"),
    ("¿Qué fueron las regiones vivas y activas?", "Aldana", "regiones"),
    ("¿Qué pasó con el caucho en la Amazonía?", None, "regiones"),
    ("¿Cómo se reorganizó el Perú según Espinoza?", "Espinoza", "regiones"),
    ("¿Qué papel tuvo la minería colonial en Potosí?", None, "colonial"),
    # --- Independencia ---
    ("¿Qué significó la división entre norte patriota y sur realista?", "Phelan", "independencia"),
    ("¿Cómo se financió la independencia del Perú?", "Cahill", "independencia"),
    ("¿Qué fue la disputa de jurisdicciones?", "Sobrevilla", "independencia"),
    # --- administrativas (documento indice ES el correcto aqui) ---
    ("¿Cuándo es el examen parcial?", "122005", "administrativa"),
    ("¿Cómo se califica el curso?", "122005", "administrativa"),
    ("¿Qué lecturas hay para la semana 2?", "Cronograma", "administrativa"),
    ("¿Quién es el profesor del curso?", None, "administrativa"),
]

INDICE_DOCS = ("Cronograma", "122005")  # documentos "indice"/administrativos


def sin_tildes(s):
    return "".join(c for c in unicodedata.normalize("NFD", s) if unicodedata.category(c) != "Mn")


def consultar(pregunta):
    r = requests.post(URL, json={"pregunta": pregunta, "modo": "preguntar"}, timeout=TIMEOUT)
    return r.json()


def evaluar(d, espera, categoria):
    paquetes = d.get("paquetes", [])
    archivos = [p.get("archivo", "") for p in paquetes]
    cobs = [p.get("cobertura") or 0 for p in paquetes]
    hit = None
    if espera:
        hit = any(espera.lower() in (a or "").lower() for a in archivos)
    # ¿se colo un documento indice donde no corresponde?
    indice_intruso = (categoria != "administrativa" and
                      any(any(i.lower() in (a or "").lower() for i in INDICE_DOCS) for a in archivos))
    return {"n": len(paquetes), "archivos": [os.path.basename(a)[:42] for a in archivos[:3]],
            "cob_max": max(cobs) if cobs else 0, "hit": hit, "indice_intruso": indice_intruso,
            "ms": d.get("ms_recuperacion"), "avisos": len(d.get("avisos") or [])}


def main():
    filas = []
    print(f"{'':4s} {'cat':14s} {'hit':5s} {'cob':>5s} {'idx':4s}  pregunta")
    for i, (q, espera, cat) in enumerate(PREGUNTAS, 1):
        try:
            d = consultar(q)
            ev = evaluar(d, espera, cat)
        except Exception as e:
            print(f"{i:3d}. ERROR {type(e).__name__}")
            filas.append({"q": q, "error": str(e)}); continue
        marca = {True: "HIT", False: "MISS", None: "-"}[ev["hit"]]
        print(f"{i:3d}. {cat:14s} {marca:5s} {ev['cob_max']:5.2f} {'SI' if ev['indice_intruso'] else '  ':4s}  {q[:52]}")
        if ev["hit"] is False:
            print(f"       esperaba '{espera}' | trajo: {ev['archivos']}")
        filas.append({"q": q, "espera": espera, "categoria": cat, **ev})

    # --- sensibilidad a acentos ---
    print("\n--- sensibilidad a los acentos (misma pregunta con/sin tildes) ---")
    difs = 0
    muestra = [p for p in PREGUNTAS if any(c in p[0] for c in "áéíóúñ")][:8]
    for q, espera, cat in muestra:
        try:
            a = evaluar(consultar(q), espera, cat)
            b = evaluar(consultar(sin_tildes(q)), espera, cat)
        except Exception:
            continue
        igual = a["archivos"] == b["archivos"]
        difs += 0 if igual else 1
        print(f"   {'IGUAL' if igual else 'DIFIERE':8s} cob {a['cob_max']:.2f} vs {b['cob_max']:.2f} | {q[:46]}")

    con_gold = [f for f in filas if f.get("hit") is not None]
    aciertos = sum(1 for f in con_gold if f["hit"])
    intrusos = sum(1 for f in filas if f.get("indice_intruso"))
    no_admin = [f for f in filas if f.get("categoria") and f["categoria"] != "administrativa"]
    resumen = {
        "n_preguntas": len(filas),
        "con_documento_esperado_anotado": len(con_gold),
        "acierto_documento_pct": round(100 * aciertos / len(con_gold), 1) if con_gold else None,
        "cobertura_media": round(statistics.mean([f["cob_max"] for f in filas if "cob_max" in f]), 3),
        "cobertura_perfecta_pct": round(100 * sum(1 for f in filas if f.get("cob_max", 0) >= 0.999) / len(filas), 1),
        "documento_indice_intruso_pct": round(100 * intrusos / len(no_admin), 1) if no_admin else None,
        "acentos_cambian_resultado": difs,
        "ms_mediana": statistics.median([f["ms"] for f in filas if f.get("ms")]),
    }
    print("\n" + json.dumps(resumen, ensure_ascii=False, indent=2))
    with open(os.path.join(BASE, "results", "modo_entender.json"), "w", encoding="utf-8") as f:
        json.dump({"resumen": resumen, "filas": filas}, f, ensure_ascii=False, indent=2)


if __name__ == "__main__":
    main()
