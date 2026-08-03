# -*- coding: utf-8 -*-
"""
Orquestador end-to-end de FORMA-IR. Por ahora solo implementa Fase A
(construir_corpus_fisico) -- las fases siguientes se agregan
incrementalmente segun el plan, cada una con su checkpoint.
"""
import hashlib
import json
import os
import re
import unicodedata

from forma_ir.ingesta import extraer_pdf, extraer_pdf_ocr, extraer_pptx, extraer_docx
from forma_ir.tipos import Bloque

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CARPETA_FUENTE = os.path.join(RAIZ, "carpeta_documentos")
SALIDA = os.path.join(RAIZ, "forma_ir_corpus")

# Prioridad de formato cuando un documento existe en mas de uno: se prefiere
# el formato "nativo" del autor (pptx para diapositivas, docx para guiones y
# ejercicios redactados en Word) sobre un PDF exportado, porque el nativo
# preserva mejor la informacion de posicion/fuente que FORMA-IR necesita --
# un PDF exportado desde PPTX/DOCX a veces aplana la fuente o el layout.
PRIORIDAD_FORMATO = [".pptx", ".docx", ".pdf"]


def _slug(texto: str) -> str:
    """doc_id legible y estable, sin depender de encoding fragil de la ruta."""
    t = unicodedata.normalize("NFKD", texto)
    t = "".join(c for c in t if not unicodedata.combining(c))
    t = re.sub(r"[^a-zA-Z0-9]+", "-", t).strip("-").lower()
    return t


def _listar_archivos_fuente(carpeta: str) -> dict[str, dict[str, str]]:
    """Devuelve {stem: {ext: ruta_completa}} recorriendo SOLO la subcarpeta
    real del curso, no la raiz de carpeta_documentos/ (que tambien contiene
    el propio paper de FORMA-IR y otros documentos de trabajo ajenos al
    corpus del curso)."""
    por_stem: dict[str, dict[str, str]] = {}
    subcarpeta_curso = None
    for entrada in os.listdir(carpeta):
        ruta = os.path.join(carpeta, entrada)
        if os.path.isdir(ruta) and entrada.lower().startswith("historia"):
            subcarpeta_curso = ruta
            break
    if subcarpeta_curso is None:
        raise RuntimeError(f"No se encontro la subcarpeta del curso dentro de {carpeta}")

    for root, _dirs, files in os.walk(subcarpeta_curso):
        for f in files:
            stem, ext = os.path.splitext(f)
            ext = ext.lower()
            if ext not in (".pdf", ".pptx", ".docx"):
                continue
            por_stem.setdefault(stem, {})[ext] = os.path.join(root, f)
    return por_stem


def _elegir_formato(disponibles: dict[str, str]) -> tuple[str, str]:
    """Aplica PRIORIDAD_FORMATO y devuelve (extension_elegida, ruta)."""
    for ext in PRIORIDAD_FORMATO:
        if ext in disponibles:
            return ext, disponibles[ext]
    # No deberia pasar dado que solo se listan .pdf/.pptx/.docx, pero por
    # seguridad devuelve lo primero que haya.
    ext = next(iter(disponibles))
    return ext, disponibles[ext]


def _es_pdf_escaneado(ruta: str) -> bool:
    """Heuristica barata: si get_text('dict') no produce ningun span con
    texto no vacio en las primeras 2 paginas, se asume escaneado y se
    busca el OCR pre-generado en produccion (corpus/_ocr/) -- reutilizado
    solo como INSUMO de texto, nunca importando codigo de produccion."""
    import fitz
    doc = fitz.open(ruta)
    try:
        for pagina in doc[:2]:
            d = pagina.get_text("dict")
            for block in d["blocks"]:
                for line in block.get("lines", []):
                    for span in line["spans"]:
                        if span["text"].strip():
                            return False
        return True
    finally:
        doc.close()


def construir_corpus_fisico(carpeta: str = CARPETA_FUENTE, verbose: bool = True) -> tuple[list[Bloque], dict]:
    """Fase A completa: recorre todos los documentos fuente, resuelve
    duplicados por prioridad de formato, extrae bloques con pistas
    fisicas. Devuelve (todos_los_bloques, manifiesto_docs)."""
    por_stem = _listar_archivos_fuente(carpeta)
    todos_los_bloques: list[Bloque] = []
    manifiesto: dict[str, dict] = {}
    saltados_ocr = []

    for stem, disponibles in sorted(por_stem.items()):
        ext, ruta = _elegir_formato(disponibles)
        doc_id = _slug(stem)

        try:
            if ext == ".pdf":
                if _es_pdf_escaneado(ruta):
                    saltados_ocr.append((doc_id, ruta))
                    # Sin OCR propio en esta fase experimental -- se
                    # documenta como bloque vacio, no se inventa texto.
                    # (El pipeline de produccion si tiene OCR cacheado en
                    # corpus/_ocr/, pero conectarlo queda fuera del
                    # alcance de Fase A; ver limitaciones del checkpoint.)
                    bloques = []
                else:
                    bloques = extraer_pdf(ruta, doc_id)
            elif ext == ".pptx":
                bloques = extraer_pptx(ruta, doc_id)
            elif ext == ".docx":
                bloques = extraer_docx(ruta, doc_id)
            else:
                bloques = []
        except Exception as e:
            if verbose:
                print(f"  ERROR extrayendo {stem} ({ext}): {type(e).__name__}: {e}")
            bloques = []

        todos_los_bloques.extend(bloques)
        manifiesto[doc_id] = {
            "doc_id": doc_id,
            "titulo_original": stem,
            "formato_elegido": ext,
            "formatos_disponibles": sorted(disponibles.keys()),
            "ruta": ruta,
            "n_bloques": len(bloques),
            "hash": hashlib.sha256(open(ruta, "rb").read()).hexdigest()[:16],
        }
        if verbose:
            print(f"  {doc_id:<55} {ext:<6} {len(bloques):>5} bloques")

    if verbose:
        print(f"\nTotal documentos procesados: {len(manifiesto)}")
        print(f"Total bloques extraidos: {len(todos_los_bloques)}")
        if saltados_ocr:
            print(f"Documentos escaneados (sin OCR en esta fase, bloques vacios): {len(saltados_ocr)}")
            for doc_id, ruta in saltados_ocr:
                print(f"   - {doc_id}")

    return todos_los_bloques, manifiesto


def guardar_corpus_fisico(bloques: list[Bloque], manifiesto: dict, salida: str = SALIDA):
    os.makedirs(salida, exist_ok=True)
    with open(os.path.join(salida, "bloques.jsonl"), "w", encoding="utf-8") as f:
        for b in bloques:
            f.write(json.dumps(b.__dict__, ensure_ascii=False) + "\n")
    with open(os.path.join(salida, "manifiesto.json"), "w", encoding="utf-8") as f:
        json.dump(manifiesto, f, ensure_ascii=False, indent=1)


if __name__ == "__main__":
    bloques, manifiesto = construir_corpus_fisico()
    guardar_corpus_fisico(bloques, manifiesto)
    print(f"\nGuardado en {SALIDA}/")
