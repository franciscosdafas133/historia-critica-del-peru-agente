# -*- coding: utf-8 -*-
"""
Validacion del corpus - control de calidad tras la ingesta.

Comprueba que el corpus este completo y sea utilizable:
  - documentos sin texto o con densidad anormalmente baja
  - cobertura por semana frente a la estructura oficial del cronograma
  - integridad del anclaje (todo bloque resoluble a archivo + pagina)
  - calidad del texto OCR
  - documentos citables (con referencia bibliografica asignada)

Uso:  python validar_corpus.py
"""
import sys, io, os, json, re, collections
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace", line_buffering=True)

RAIZ = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(RAIZ, "corpus")

bloques = [json.loads(l) for l in open(os.path.join(OUT, "corpus.jsonl"), encoding="utf-8")]
man = json.load(open(os.path.join(OUT, "manifiesto.json"), encoding="utf-8"))
docs = man["documentos"]
semanas = man["semanas"]

errores, avisos = [], []

print("VALIDACION DEL CORPUS")
print("=" * 78)
print(f"documentos: {len(docs)}   bloques: {len(bloques)}   "
      f"tokens: {sum(d['tokens'] for d in docs):,}\n")

# --- 1. documentos vacios o casi vacios ---
vacios = [d for d in docs if d["tokens"] == 0]
pobres = [d for d in docs if 0 < d["tokens"] < 600]
if vacios:
    errores.append(f"{len(vacios)} documento(s) sin texto extraido")
    for d in vacios: print(f"  VACIO  {d['titulo'][:56]}  ({d['unidades_fisicas']} {d['etiqueta_unidad']}s)")
if pobres:
    for d in pobres: print(f"  BAJO   {d['titulo'][:56]}  {d['tokens']} tok")
    avisos.append(f"{len(pobres)} documento(s) con muy poco texto")

# --- 2. cobertura por semana ---
print("\nCOBERTURA POR SEMANA")
por_sem = collections.defaultdict(lambda: [0, 0])
for d in docs:
    if d["semana"]:
        por_sem[d["semana"]][0] += 1
        por_sem[d["semana"]][1] += d["tokens"]
huecos = []
for s in sorted(semanas, key=int):
    si = int(s)
    n, t = por_sem.get(si, [0, 0])
    tema = semanas[s]["tema"]
    if "EXAMEN" in tema.upper():
        print(f"  S{si:<2}  --  (semana de examenes, sin material)   {tema[:40]}")
        continue
    est = "ok " if t > 3000 else ("VAC" if t == 0 else "BAJ")
    if est != "ok ": huecos.append(si)
    print(f"  S{si:<2} {est} {n:>2} docs {t:>8,} tok   {tema[:44]}")
if huecos:
    avisos.append(f"semanas con material insuficiente: {huecos}")

# --- 3. integridad del anclaje ---
print("\nANCLAJE A LA FUENTE")
sin_ancla = [b for b in bloques
             if not b["fuente"].get("archivo")
             or not (b["fuente"].get("pagina") or b["fuente"].get("diapositiva")
                     or b["fuente"].get("documento"))]
ids = [b["bloque_id"] for b in bloques]
dup = [k for k, v in collections.Counter(ids).items() if v > 1]
print(f"  bloques sin coordenada de origen : {len(sin_ancla)}")
print(f"  identificadores duplicados       : {len(dup)}")
if sin_ancla: errores.append(f"{len(sin_ancla)} bloques sin anclaje")
if dup: errores.append(f"{len(dup)} bloque_id duplicados")

# --- 4. calidad OCR ---
ocr_docs = [d for d in docs if d.get("ocr")]
ocr_bloques = [b for b in bloques if b["fuente"].get("ocr")]
print(f"\nOCR")
print(f"  documentos reconstruidos por OCR : {len(ocr_docs)}")
print(f"  bloques marcados como OCR        : {len(ocr_bloques)}")
for d in ocr_docs:
    dens = d["tokens"] / max(d["unidades_fisicas"], 1)
    print(f"    {d['titulo'][:50]:<52} {d['tokens']:>7,} tok  {dens:>6.0f} tok/pag")
if ocr_bloques:
    def ratio_palabras(t):
        if not t: return 0
        pal = sum(len(w) for w in re.findall(r"[a-zA-ZáéíóúñÁÉÍÓÚÑ]{3,}", t))
        return pal / len(t)
    malos = [b for b in ocr_bloques if ratio_palabras(b["texto"]) < 0.55]
    print(f"  bloques OCR con texto degradado  : {len(malos)} de {len(ocr_bloques)}")
    if len(malos) > len(ocr_bloques) * 0.25:
        avisos.append("mas del 25% de los bloques OCR tienen texto degradado")

# --- 5. citabilidad ---
print("\nCITABILIDAD")
lecturas = [d for d in docs if d["tipo"] == "lectura"]
sin_cita = [d for d in lecturas if not d.get("cita")]
print(f"  lecturas con referencia bibliografica : {len(lecturas)-len(sin_cita)}/{len(lecturas)}")
for d in sin_cita: print(f"    sin cita: {d['titulo'][:56]}")
if sin_cita: avisos.append(f"{len(sin_cita)} lectura(s) sin referencia bibliografica")

sin_anio = [d for d in lecturas if not d.get("anio")]
if sin_anio:
    print(f"  lecturas sin anio: {[d['titulo'][:34] for d in sin_anio]}")

# --- veredicto ---
print("\n" + "=" * 78)
if errores:
    print("ERRORES (bloquean el uso del corpus):")
    for e in errores: print(f"  - {e}")
if avisos:
    print("AVISOS (no bloquean, pero conviene saberlos):")
    for a in avisos: print(f"  - {a}")
if not errores and not avisos:
    print("CORPUS VALIDO: sin errores ni avisos.")
elif not errores:
    print("CORPUS UTILIZABLE con las salvedades anotadas.")
sys.exit(1 if errores else 0)
