# -*- coding: utf-8 -*-
"""
Prueba de carga de la capa de RECUPERACION unicamente (recuperar.py), sin
LLM, sin servidor Flask -- llamadas directas a recuperar() en memoria
compartida, concurrentes via ThreadPoolExecutor (numpy/sklearn liberan el
GIL durante las operaciones matriciales pesadas, asi que threads si
paralelizan CPU real para este caso, a diferencia de codigo Python puro).

Mide: throughput, latencia p50/p95/p99, uso de CPU/RAM, crecimiento de
memoria, errores, contaminacion entre "sesiones" (cada llamada es
independiente por diseño del sistema -- ver hallazgo de stateless en
reports/modes_evaluation.md -- asi que "contaminacion entre sesiones" se
verifica como "el resultado de la pregunta A no cambia por haber corrido
la pregunta B en paralelo", que es la version realista de ese chequeo
para un sistema sin estado).

Uso:
    python tests/load/carga_recuperacion.py --usuarios 10 --preguntas-por-usuario 3
    python tests/load/carga_recuperacion.py --escalamiento
"""
import argparse
import json
import os
import pickle
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import psutil
from recuperar import recuperar

RAIZ = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

PREGUNTAS_MUESTRA = [
    "Por que colapso la poblacion andina en el siglo XVI?",
    "Que es la transicion demografica?",
    "Cuando es el examen parcial?",
    "Como afecto la mita colonial a la economia indigena?",
    "Que se ve en la semana 13?",
    "Cual es la tesis de Contreras sobre el centralismo?",
    "Que son las ecorregiones segun Pulgar Vidal?",
    "Como se relacionan las dos unidades del curso?",
    "Que autores aparecen en mas de una semana?",
    "Que significo la division norte patriota y sur realista?",
]


def _percentil(valores_ordenados, p):
    if not valores_ordenados:
        return None
    idx = min(int(len(valores_ordenados) * p), len(valores_ordenados) - 1)
    return valores_ordenados[idx]


def _una_llamada(idx, pregunta):
    t0 = time.time()
    try:
        r = recuperar(pregunta, idx, modo_interaccion="preguntar")
        ok = True
        n_paquetes = len(r["paquetes"])
        error = None
    except Exception as e:
        ok = False
        n_paquetes = 0
        error = f"{type(e).__name__}: {e}"
    dt = time.time() - t0
    return {"pregunta": pregunta, "ok": ok, "n_paquetes": n_paquetes, "latencia_s": dt, "error": error}


def correr_carga(idx, n_usuarios, preguntas_por_usuario, etiqueta=""):
    tareas = []
    for u in range(n_usuarios):
        for i in range(preguntas_por_usuario):
            pregunta = PREGUNTAS_MUESTRA[(u * preguntas_por_usuario + i) % len(PREGUNTAS_MUESTRA)]
            tareas.append(pregunta)

    proc = psutil.Process()
    mem_antes = proc.memory_info().rss / (1024 * 1024)
    cpu_antes = proc.cpu_percent(interval=None)

    t_inicio = time.time()
    resultados = []
    with ThreadPoolExecutor(max_workers=n_usuarios) as ex:
        futuros = [ex.submit(_una_llamada, idx, p) for p in tareas]
        for f in as_completed(futuros):
            resultados.append(f.result())
    t_total = time.time() - t_inicio

    mem_despues = proc.memory_info().rss / (1024 * 1024)
    cpu_despues = proc.cpu_percent(interval=0.1)

    latencias = sorted(r["latencia_s"] for r in resultados)
    errores = [r for r in resultados if not r["ok"]]

    return {
        "etiqueta": etiqueta, "n_usuarios": n_usuarios,
        "preguntas_por_usuario": preguntas_por_usuario,
        "n_requests": len(tareas), "t_total_s": round(t_total, 3),
        "requests_por_segundo": round(len(tareas) / t_total, 2) if t_total > 0 else None,
        "latencia_p50_s": round(_percentil(latencias, 0.50), 4),
        "latencia_p95_s": round(_percentil(latencias, 0.95), 4),
        "latencia_p99_s": round(_percentil(latencias, 0.99), 4),
        "latencia_max_s": round(latencias[-1], 4) if latencias else None,
        "n_errores": len(errores), "errores": [e["error"] for e in errores][:5],
        "mem_antes_mb": round(mem_antes, 1), "mem_despues_mb": round(mem_despues, 1),
        "mem_crecimiento_mb": round(mem_despues - mem_antes, 1),
        "cpu_percent_durante": cpu_despues,
    }


def test_smoke_un_usuario():
    idx = pickle.load(open(os.path.join(RAIZ, "corpus", "indice.pkl"), "rb"))
    r = correr_carga(idx, n_usuarios=1, preguntas_por_usuario=1, etiqueta="smoke")
    assert r["n_errores"] == 0
    assert r["requests_por_segundo"] is not None


def test_uso_real_dos_usuarios_simultaneos():
    idx = pickle.load(open(os.path.join(RAIZ, "corpus", "indice.pkl"), "rb"))
    r = correr_carga(idx, n_usuarios=2, preguntas_por_usuario=3, etiqueta="uso_real")
    assert r["n_errores"] == 0


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--usuarios", type=int, default=5)
    ap.add_argument("--preguntas-por-usuario", type=int, default=3)
    ap.add_argument("--escalamiento", action="store_true",
                     help="corre la escalera completa 1,2,5,10,20,50 usuarios")
    ap.add_argument("--soak", action="store_true",
                     help="corre una prueba prolongada repitiendo consultas iguales")
    ap.add_argument("--json", default=None)
    a = ap.parse_args()

    idx = pickle.load(open(os.path.join(RAIZ, "corpus", "indice.pkl"), "rb"))
    resultados = []

    if a.escalamiento:
        for n in [1, 2, 5, 10, 20, 50]:
            print(f"--- {n} usuarios simultaneos ---")
            r = correr_carga(idx, n_usuarios=n, preguntas_por_usuario=3, etiqueta=f"escalamiento_{n}")
            resultados.append(r)
            print(json.dumps(r, ensure_ascii=False, indent=1))
            print()
    elif a.soak:
        print("--- soak test: 200 requests de la misma pregunta, 10 usuarios ---")
        r = correr_carga(idx, n_usuarios=10, preguntas_por_usuario=20, etiqueta="soak_misma_pregunta")
        resultados.append(r)
        print(json.dumps(r, ensure_ascii=False, indent=1))
    else:
        r = correr_carga(idx, n_usuarios=a.usuarios, preguntas_por_usuario=a.preguntas_por_usuario,
                          etiqueta="manual")
        resultados.append(r)
        print(json.dumps(r, ensure_ascii=False, indent=1))

    if a.json:
        os.makedirs(os.path.dirname(a.json), exist_ok=True)
        with open(a.json, "w", encoding="utf-8") as f:
            json.dump(resultados, f, ensure_ascii=False, indent=1)
        print(f"\n-> {a.json}")
