# -*- coding: utf-8 -*-
"""
Orquestador de Fase D sobre el corpus segmentado completo
(forma_ir_corpus/unidades.jsonl, producido por pipeline_segmentacion.py).

Recalcula la firma orto-tipografica por documento (no se persistio en
Fase B/C -- es barata de recalcular, ~segundos para todo el corpus) para
poder calcular `soporte_repeticion`, luego construye el vector de
features estructurales de cada unidad y clusteriza sobre el corpus
completo (Fase D requiere volumen, ver checkpoint D del plan).
"""
import json
import os

from forma_ir.familias import calcular_features, elegir_k_y_clusterizar
from forma_ir.firma import secuencia_de_firmas
from forma_ir.tipos import Bloque, UnidadRetenida

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CORPUS = os.path.join(RAIZ, "forma_ir_corpus")


def _cargar_bloques_por_doc(ruta: str) -> dict[str, list[Bloque]]:
    docs: dict[str, list[Bloque]] = {}
    with open(ruta, encoding="utf-8") as f:
        for line in f:
            d = json.loads(line)
            docs.setdefault(d["doc_id"], []).append(Bloque(**d))
    for doc_id in docs:
        docs[doc_id].sort(key=lambda b: b.seq)
    return docs


def _cargar_unidades_por_doc(ruta: str) -> dict[str, list[UnidadRetenida]]:
    docs: dict[str, list[UnidadRetenida]] = {}
    with open(ruta, encoding="utf-8") as f:
        for line in f:
            d = json.loads(line)
            docs.setdefault(d["doc_id"], []).append(UnidadRetenida(**d))
    return docs


def construir_familias(carpeta_corpus: str = CORPUS, verbose: bool = True):
    bloques_por_doc = _cargar_bloques_por_doc(os.path.join(carpeta_corpus, "bloques.jsonl"))
    unidades_por_doc = _cargar_unidades_por_doc(os.path.join(carpeta_corpus, "unidades.jsonl"))

    todas_las_features = []
    todas_las_unidades = []
    for doc_id, unidades_doc in sorted(unidades_por_doc.items()):
        bloques_doc = bloques_por_doc.get(doc_id, [])
        if not bloques_doc:
            continue
        firmas_doc = secuencia_de_firmas(bloques_doc)
        for u in unidades_doc:
            f = calcular_features(u, bloques_doc, firmas_doc, len(bloques_doc))
            todas_las_features.append(f)
            todas_las_unidades.append(u)

    etiquetas, k = elegir_k_y_clusterizar(todas_las_features)
    for u, etiqueta in zip(todas_las_unidades, etiquetas):
        u.familia_id = int(etiqueta)

    if verbose:
        from collections import Counter
        conteo = Counter(etiquetas)
        print(f"k elegido: {k}")
        print(f"Total unidades clusterizadas: {len(todas_las_unidades)}")
        for fam_id in sorted(conteo.keys()):
            print(f"  familia {fam_id}: {conteo[fam_id]} unidades")

    return todas_las_unidades, todas_las_features, k


def guardar_unidades_con_familia(unidades: list[UnidadRetenida], salida: str = CORPUS):
    with open(os.path.join(salida, "unidades.jsonl"), "w", encoding="utf-8") as f:
        for u in unidades:
            f.write(json.dumps(u.__dict__, ensure_ascii=False) + "\n")


if __name__ == "__main__":
    unidades, features, k = construir_familias()
    guardar_unidades_con_familia(unidades)
    print(f"\nActualizado {CORPUS}/unidades.jsonl con familia_id (k={k})")
