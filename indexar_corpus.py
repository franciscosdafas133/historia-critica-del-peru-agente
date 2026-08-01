# -*- coding: utf-8 -*-
"""
Indice de recuperacion sobre el corpus - Historia Critica del Peru

Fase 2 del metodo: almacenamiento e indexacion.

Construye tres indices complementarios, todos sobre los mismos bloques
anclados a la fuente:

  1. LEXICO (BM25)      - terminos exactos, nombres propios, anios
  2. TF-IDF (coseno)    - similitud de superficie, complementa BM25
  3. ESTRUCTURAL        - unidad / semana / tipo / autoridad / autor
                          filtrado duro, sin costo y sin error de modelo

Deliberadamente NO usa embeddings todavia: esa decision sigue abierta
(no cerrar tecnologia antes de medir). El indice lexico ya permite
consultar el corpus completo y sirve de baseline honesto.

Salida: corpus/indice.pkl
"""
import sys, io, os, json, re, pickle, unicodedata, collections
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace", line_buffering=True)

import numpy as np
from rank_bm25 import BM25Okapi
from sklearn.feature_extraction.text import TfidfVectorizer

from texto_util import normtxt, tokenizar   # modulo compartido: ver texto_util.py

RAIZ = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(RAIZ, "corpus")

# ---------- cargar corpus ----------
bloques = [json.loads(l) for l in open(os.path.join(OUT, "corpus.jsonl"), encoding="utf-8")]
man = json.load(open(os.path.join(OUT, "manifiesto.json"), encoding="utf-8"))
docs = {d["doc_id"]: d for d in man["documentos"]}
print(f"bloques cargados: {len(bloques)}  documentos: {len(docs)}")

# Descarta bloques sin contenido util (paginas en blanco, portadas)
utiles = [b for b in bloques if len(b["texto"].strip()) >= 40]
print(f"bloques indexables: {len(utiles)}  (descartados {len(bloques)-len(utiles)} casi vacios)")

# ---------- enriquecer cada bloque con su contexto estructural ----------
# El texto indexado incluye el encabezado del documento: asi una consulta por
# autor o por tema del curso encuentra el bloque aunque el termino no aparezca
# literalmente dentro de la pagina. Es contextualizacion barata y trazable.
for b in utiles:
    d = docs[b["doc_id"]]
    cab = [d["titulo"].replace("_", " ")]
    if d.get("autores"): cab.append(" ".join(d["autores"]))
    if d.get("semana_tema"): cab.append(d["semana_tema"])
    if d.get("unidad_nombre"): cab.append(d["unidad_nombre"])
    b["_ctx"] = " | ".join(cab)
    b["_full"] = b["_ctx"] + "\n" + b["texto"]

# ---------- 1. indice lexico BM25 ----------
print("construyendo BM25...")
tok_corpus = [tokenizar(b["_full"]) for b in utiles]
bm25 = BM25Okapi(tok_corpus)

# ---------- 2. indice TF-IDF ----------
print("construyendo TF-IDF...")
tfidf = TfidfVectorizer(analyzer="word", tokenizer=tokenizar, lowercase=False,
                        token_pattern=None, min_df=2, max_df=0.6, sublinear_tf=True)
M = tfidf.fit_transform([b["_full"] for b in utiles])
print(f"  vocabulario: {len(tfidf.vocabulary_):,} terminos  matriz {M.shape}")

# ---------- 3. indices estructurales (filtrado duro, sin modelo) ----------
por_semana  = collections.defaultdict(list)
por_unidad  = collections.defaultdict(list)
por_tipo    = collections.defaultdict(list)
por_doc     = collections.defaultdict(list)
por_autor   = collections.defaultdict(list)
por_autoridad = collections.defaultdict(list)
for i, b in enumerate(utiles):
    d = docs[b["doc_id"]]
    if b.get("semana"): por_semana[b["semana"]].append(i)
    if b.get("unidad"): por_unidad[b["unidad"]].append(i)
    por_tipo[b["tipo"]].append(i)
    por_doc[b["doc_id"]].append(i)
    por_autoridad[b["autoridad"]].append(i)
    for a in d.get("autores") or []:
        por_autor[normtxt(a)].append(i)

# ---------- 4. vecindad: cada bloque conoce a su anterior y siguiente ----------
# Relacion objetiva, no inferida. Es la base de la expansion estructural.
vecinos = {}
for doc_id, idxs in por_doc.items():
    idxs = sorted(idxs, key=lambda i: utiles[i]["fuente"].get("pagina",
                                     utiles[i]["fuente"].get("diapositiva", 0)))
    for pos, i in enumerate(idxs):
        vecinos[i] = {"anterior": idxs[pos-1] if pos > 0 else None,
                      "siguiente": idxs[pos+1] if pos < len(idxs)-1 else None,
                      "doc_pos": pos, "doc_total": len(idxs)}

indice = {
    "bloques": utiles, "docs": docs, "curso": man["curso"],
    "semanas": man["semanas"], "unidades": man["unidades"],
    "bm25": bm25, "tfidf": tfidf, "M": M,
    "por_semana": dict(por_semana), "por_unidad": dict(por_unidad),
    "por_tipo": dict(por_tipo), "por_doc": dict(por_doc),
    "por_autor": dict(por_autor), "por_autoridad": dict(por_autoridad),
    "vecinos": vecinos,
}
with open(os.path.join(OUT, "indice.pkl"), "wb") as f:
    pickle.dump(indice, f)

print(f"\nINDICE CONSTRUIDO -> corpus/indice.pkl")
print(f"  bloques indexados : {len(utiles)}")
print(f"  tokens totales    : {sum(b['tokens'] for b in utiles):,}")
print(f"  semanas cubiertas : {sorted(por_semana)}")
print(f"  tipos             : {dict((k,len(v)) for k,v in por_tipo.items())}")
print(f"  autoridades       : {dict((k,len(v)) for k,v in por_autoridad.items())}")
print(f"  autores indexados : {len(por_autor)}")
