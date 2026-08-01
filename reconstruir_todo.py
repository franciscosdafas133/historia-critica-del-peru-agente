# -*- coding: utf-8 -*-
"""
Reconstruccion completa del ecosistema.

Ejecuta en orden las cuatro fases y deja el sistema listo para usar:
  1. construir corpus   (incorpora el OCR disponible en corpus/_ocr/)
  2. validar corpus
  3. indexar
  4. benchmark comparativo

Correr despues de anadir material nuevo o de completar el OCR.

Uso:  python reconstruir_todo.py
"""
import sys, io, os, subprocess
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace", line_buffering=True)

RAIZ = os.path.dirname(os.path.abspath(__file__))
PY = sys.executable

PASOS = [
    ("Construir corpus", ["construir_corpus.py"], True),
    ("Validar corpus",   ["validar_corpus.py"],   False),  # avisos no detienen
    ("Indexar",          ["indexar_corpus.py"],   True),
    ("Benchmark",        ["evaluar.py", "--csv", "corpus/evaluacion.csv"], True),
]

for titulo, cmd, critico in PASOS:
    print("\n" + "=" * 74)
    print(f"  {titulo}")
    print("=" * 74)
    r = subprocess.run([PY] + cmd, cwd=RAIZ)
    if r.returncode != 0:
        if critico:
            print(f"\nFALLO en '{titulo}' (codigo {r.returncode}). Se detiene.")
            sys.exit(r.returncode)
        print(f"\n'{titulo}' termino con avisos (codigo {r.returncode}). Continuo.")

print("\n" + "=" * 74)
print("  ECOSISTEMA RECONSTRUIDO")
print("=" * 74)
print("""
Listo para usar:

  python recuperar.py "tu pregunta"          ver que evidencia recupera
  python agente.py "tu pregunta"             armar el prompt completo
  python agente.py "tu pregunta" --enviar    generar la respuesta (requiere API key)
  python evaluar.py --estrato multihop       comparar estrategias
""")
