# -*- coding: utf-8 -*-
"""
Orquestador de Fases B-C4 sobre el corpus fisico completo (Fase A ya
persistida en forma_ir_corpus/bloques.jsonl). Para cada documento:
firma orto-tipografica (B) -> gramatica SEQUITUR (C1) -> anotacion de
reglas (C2) -> candidatos de limite (C3a) -> particion optima por MDL
(C4) -> UnidadRetenida por cada region resultante.

Documentos con 0 bloques (los 3 escaneados sin OCR, ver manifiesto.json)
se saltan silenciosamente -- no hay nada que segmentar.
"""
import json
import os
import time

from forma_ir.anotacion import anotar_reglas
from forma_ir.firma import secuencia_de_firmas
from forma_ir.gramatica import inducir_gramatica
from forma_ir.mdl import segmentar_por_mdl
from forma_ir.segmentacion import candidatos_limite
from forma_ir.tipos import Bloque, UnidadRetenida

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CORPUS = os.path.join(RAIZ, "forma_ir_corpus")


def _cargar_bloques_por_doc(ruta_bloques_jsonl: str) -> dict[str, list[Bloque]]:
    docs: dict[str, list[Bloque]] = {}
    with open(ruta_bloques_jsonl, encoding="utf-8") as f:
        for line in f:
            d = json.loads(line)
            docs.setdefault(d["doc_id"], []).append(Bloque(**d))
    for doc_id in docs:
        docs[doc_id].sort(key=lambda b: b.seq)
    return docs


def segmentar_documento(bloques_doc: list[Bloque]) -> list[UnidadRetenida]:
    """Aplica B->C4 a un solo documento y devuelve sus UnidadRetenida."""
    if not bloques_doc:
        return []

    firmas = secuencia_de_firmas(bloques_doc)
    alfabeto: dict = {}
    simbolos = []
    for f in firmas:
        if f not in alfabeto:
            alfabeto[f] = len(alfabeto)
        simbolos.append(alfabeto[f])

    reglas, top = inducir_gramatica(simbolos)
    anotaciones = anotar_reglas(reglas, top, bloques_doc)
    candidatos = candidatos_limite(bloques_doc, reglas, top, anotaciones, firmas_doc=firmas)
    fronteras = segmentar_por_mdl(bloques_doc, firmas, candidatos, reglas, top, anotaciones)

    n = len(bloques_doc)
    cortes = sorted(set([0] + fronteras + [n]))
    doc_id = bloques_doc[0].doc_id

    unidades = []
    for k, (a, b) in enumerate(zip(cortes[:-1], cortes[1:])):
        region = bloques_doc[a:b]
        paginas = [x.pagina for x in region if x.pagina is not None]
        unidades.append(UnidadRetenida(
            unidad_id=f"{doc_id}#u{k}",
            doc_id=doc_id,
            indices_bloque=list(range(a, b)),
            texto=" ".join(x.texto for x in region),
            pagina_inicio=min(paginas) if paginas else None,
            pagina_fin=max(paginas) if paginas else None,
        ))
    return unidades


def segmentar_corpus(ruta_bloques_jsonl: str | None = None, verbose: bool = True) -> list[UnidadRetenida]:
    ruta = ruta_bloques_jsonl or os.path.join(CORPUS, "bloques.jsonl")
    docs = _cargar_bloques_por_doc(ruta)

    todas_las_unidades: list[UnidadRetenida] = []
    for doc_id, bloques_doc in sorted(docs.items()):
        t0 = time.time()
        unidades = segmentar_documento(bloques_doc)
        todas_las_unidades.extend(unidades)
        if verbose:
            print(f"  {doc_id:<55} {len(bloques_doc):>6} bloques -> {len(unidades):>4} unidades  ({time.time()-t0:.1f}s)")

    if verbose:
        print(f"\nTotal unidades retenidas: {len(todas_las_unidades)}")
    return todas_las_unidades


def guardar_unidades(unidades: list[UnidadRetenida], salida: str = CORPUS):
    os.makedirs(salida, exist_ok=True)
    with open(os.path.join(salida, "unidades.jsonl"), "w", encoding="utf-8") as f:
        for u in unidades:
            f.write(json.dumps(u.__dict__, ensure_ascii=False) + "\n")


if __name__ == "__main__":
    unidades = segmentar_corpus()
    guardar_unidades(unidades)
    print(f"\nGuardado en {CORPUS}/unidades.jsonl")
