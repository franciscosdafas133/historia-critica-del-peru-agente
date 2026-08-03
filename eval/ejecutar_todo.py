# -*- coding: utf-8 -*-
"""
Comando principal de la bateria de evaluacion. Equivalente a `make eval`
del protocolo de auditoria -- se usa un script Python en vez de un
Makefile porque este proyecto no tiene `make` disponible en el entorno
de desarrollo real (Windows sin toolchain de compilacion) y ya sigue la
convencion de scripts Python con argparse para todas sus herramientas
(construir_corpus.py, indexar_corpus.py, evaluar.py, validar_corpus.py).

Uso:
    python eval/ejecutar_todo.py unit          # tests unitarios (paper_conformance)
    python eval/ejecutar_todo.py retrieval     # Track A/B offline, un presupuesto
    python eval/ejecutar_todo.py curva         # Track A/B, los 7 presupuestos del protocolo
    python eval/ejecutar_todo.py robustez      # tests de robustez + matriz completa
    python eval/ejecutar_todo.py modos         # tests de separacion de modos
    python eval/ejecutar_todo.py carga         # smoke + uso real (rapido)
    python eval/ejecutar_todo.py carga-completa  # escalamiento 1-50 + soak (mas lento)
    python eval/ejecutar_todo.py todo          # todo lo anterior, sin LLM, en orden
"""
import argparse
import subprocess
import sys
import os

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PYTHON = sys.executable


def correr(cmd, descripcion):
    print(f"\n{'=' * 70}\n{descripcion}\n{'=' * 70}")
    r = subprocess.run(cmd, cwd=RAIZ)
    if r.returncode != 0:
        print(f"\nFALLO: {descripcion} (exit code {r.returncode})")
        return False
    return True


def cmd_unit():
    return correr([PYTHON, "-m", "pytest", "tests/paper_conformance/", "-v"],
                   "Tests unitarios de conformidad (metodo real, sin LLM)")


def cmd_retrieval():
    return correr([PYTHON, "eval/evaluar_recuperacion.py", "--presupuesto", "256",
                    "--json", "eval/results/track_a_b256.json"],
                   "Track A/B: recuperacion offline, presupuesto=256")


def cmd_curva():
    ok = True
    for b in [128, 256, 512, 1024, 2048, 4096, 8192]:
        ok = correr([PYTHON, "eval/evaluar_recuperacion.py", "--presupuesto", str(b),
                      "--json", f"eval/results/track_a_b{b}.json"],
                     f"Track A/B: curva de presupuesto B={b}") and ok
    return ok


def cmd_robustez():
    ok = correr([PYTHON, "-m", "pytest", "tests/robustness/", "-v"],
                 "Robustez: hard requirement (ninguna perturbacion causa excepcion)")
    ok = correr([PYTHON, "tests/robustness/test_perturbaciones_consulta.py",
                 "--json", "eval/results/robustness_matrix.json"],
                "Robustez: matriz completa de perturbaciones") and ok
    return ok


def cmd_modos():
    return correr([PYTHON, "-m", "pytest", "tests/modes/", "-v"],
                   "Separacion observable de los 8 modos reales")


def cmd_carga():
    return correr([PYTHON, "-m", "pytest", "tests/load/carga_recuperacion.py", "-v"],
                   "Carga: smoke (1 usuario) + uso real (2 usuarios)")


def cmd_carga_completa():
    ok = correr([PYTHON, "tests/load/carga_recuperacion.py", "--escalamiento",
                 "--json", "eval/results/load_escalamiento.json"],
                "Carga: escalamiento 1/2/5/10/20/50 usuarios")
    ok = correr([PYTHON, "tests/load/carga_recuperacion.py", "--soak",
                 "--json", "eval/results/load_soak.json"],
                "Carga: soak test (200 requests)") and ok
    return ok


def cmd_todo():
    resultados = {
        "unit": cmd_unit(),
        "modos": cmd_modos(),
        "robustez": cmd_robustez(),
        "retrieval": cmd_retrieval(),
        "carga": cmd_carga(),
    }
    print(f"\n{'=' * 70}\nRESUMEN\n{'=' * 70}")
    for nombre, ok in resultados.items():
        print(f"  {nombre:<15} {'OK' if ok else 'FALLO'}")
    print("\nNota: 'curva' (los 7 presupuestos) y 'carga-completa' (escalamiento "
          "hasta 50 usuarios) no se incluyen en 'todo' por ser mas lentos -- "
          "correrlos por separado si se necesitan para el reporte final.")
    return all(resultados.values())


COMANDOS = {
    "unit": cmd_unit, "retrieval": cmd_retrieval, "curva": cmd_curva,
    "robustez": cmd_robustez, "modos": cmd_modos, "carga": cmd_carga,
    "carga-completa": cmd_carga_completa, "todo": cmd_todo,
}


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("comando", choices=list(COMANDOS.keys()))
    a = ap.parse_args()

    ok = COMANDOS[a.comando]()
    sys.exit(0 if ok else 1)
