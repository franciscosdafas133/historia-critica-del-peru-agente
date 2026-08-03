# -*- coding: utf-8 -*-
"""
Adaptador de integracion: expone FORMA-IR con la MISMA firma que
recuperar.recuperar(q, idx, modo_interaccion=...), para poder
reemplazar el metodo de recuperacion de produccion cambiando una sola
linea en agente.py (ver integrar_forma_ir()).

Este archivo vive en la raiz del proyecto (no en forma_ir/) porque es
la capa de INTEGRACION con produccion, no parte del metodo en si -- el
paquete forma_ir/ permanece agnostico de agente.py/servidor.py.

ADVERTENCIA DE RIESGO (documentada, decision explicita del usuario):
la evaluacion de Fase I sobre las 57 preguntas reales del curso mostro
que solo 3/57 (5%) producen evidencia lexica FUERTE contra el nulo
calibrado; el resto queda con el documento "menos malo" entre
candidatas debiles. FORMA-IR es puramente lexico (BM25F sin sinonimos
ni expansion, sin LLM en el nucleo) -- para preguntas parafraseadas que
no comparten vocabulario literal con el texto fuente, es esperable que
la calidad de la evidencia recuperada sea inferior a la del metodo
anterior (recuperar.py, que combina BM25 + TF-IDF/coseno). El usuario
opto explicitamente por reemplazar de todas formas, tras ver este
hallazgo.
"""
import os
import pickle
import time

from forma_ir.comparar_con_produccion import preparar_indice, responder_consulta

RAIZ = os.path.dirname(os.path.abspath(__file__))
IDX_PRODUCCION = os.path.join(RAIZ, "corpus", "indice.pkl")

_INDICE_FORMA_IR = None  # cache de proceso -- se construye una sola vez
_MANIFIESTO_DOCS = None  # metadatos reales (tipo/autoridad/cita) por doc_id, del indice de produccion


def _cargar_metadatos_documentos():
    """Reutiliza los metadatos YA calculados por construir_corpus.py
    (tipo, autoridad, cita, archivo, unidad, semana) via el pickle de
    produccion -- se LEE, nunca se modifica ni se reconstruye ese
    indice. FORMA-IR aporta la recuperacion; los metadatos de
    procedencia/autoridad siguen viniendo del pipeline de produccion,
    que ya los calcula correctamente desde la ruta de cada archivo."""
    global _MANIFIESTO_DOCS
    if _MANIFIESTO_DOCS is not None:
        return _MANIFIESTO_DOCS
    with open(IDX_PRODUCCION, "rb") as f:
        idx_prod = pickle.load(f)
    _MANIFIESTO_DOCS = idx_prod["docs"]
    return _MANIFIESTO_DOCS


def _cargar_indice_forma_ir():
    global _INDICE_FORMA_IR
    if _INDICE_FORMA_IR is not None:
        return _INDICE_FORMA_IR
    t0 = time.time()
    _INDICE_FORMA_IR = preparar_indice()
    print(f"[forma_ir_recuperar] indice FORMA-IR listo en {time.time()-t0:.1f}s "
          f"({len(_INDICE_FORMA_IR['reservorios'])} familias calibradas)")
    return _INDICE_FORMA_IR


_PRESUPUESTO_POR_MODO = {
    None: 9000, "preguntar": 9000, "resumen": 14400, "explicacion": 9000,
    "debate": 9000, "resolver": 9000, "practicar": 11700, "evaluar": 11700, "repasar": 9000,
}


def _traducir_a_paquetes(resultado_forma_ir: dict, metadatos_docs: dict) -> list[dict]:
    """Convierte la salida de responder_consulta() al shape de paquete
    que agente.bloque_evidencia() espera (cita/paginas/archivo/tipo/
    autoridad/ocr/texto) -- el mismo contrato que recuperar.py ya
    produce, para no tocar agente.py mas alla del punto de import."""
    paquetes = []
    for u in resultado_forma_ir["unidades_empaquetadas"]:
        doc_id = u["doc_id"]
        meta = metadatos_docs.get(doc_id, {})
        pagina = u.get("pagina_inicio")
        paquetes.append({
            "nucleo": u["unidad_id"],
            "score": u.get("score"),  # BM25F de la Fase E -- no es la misma escala que el score BM25+TFIDF anterior
            "bm25": None,  # FORMA-IR no separa un BM25 puro del BM25F combinado con ancestro
            "cobertura": u.get("cobertura"),  # cobertura IDF de la Fase E -- usado por el frontend para "direct" vs "context"
            "doc": meta.get("titulo", doc_id),
            "cita": meta.get("cita") or meta.get("titulo", doc_id),
            "tipo": meta.get("tipo", "desconocido"),
            "autoridad": meta.get("autoridad", "desconocida"),
            "unidad": meta.get("unidad"),
            "semana": meta.get("semana"),
            "paginas": f"pagina {pagina}" if pagina else "(sin paginacion)",
            "archivo": meta.get("archivo", doc_id),
            "tokens": len(u["texto"].split()),
            "texto": u["texto"],
            "ocr": False,
        })
    return paquetes


def recuperar(q: str, idx=None, verbose: bool = True, modo_interaccion: str | None = None) -> dict:
    """Firma identica a recuperar.recuperar() -- `idx` se ignora (FORMA-IR
    tiene su propio indice interno cacheado), se acepta solo para
    compatibilidad posicional con el llamador existente en agente.py."""
    indice_fi = _cargar_indice_forma_ir()
    metadatos_docs = _cargar_metadatos_documentos()

    presupuesto = _PRESUPUESTO_POR_MODO.get(modo_interaccion, 9000)
    resultado = responder_consulta(q, indice_fi, presupuesto_tokens=presupuesto)

    paquetes = _traducir_a_paquetes(resultado, metadatos_docs)

    avisos = []
    if not paquetes:
        avisos.append("SIN EVIDENCIA: ninguna fuente autorizada responde a esto.")
    else:
        p_docs_debiles = [d["p_doc"] for d in resultado.get("documentos", []) if d["p_doc"] > 0.5]
        if resultado.get("documentos") and resultado["documentos"][0]["p_doc"] > 0.5:
            avisos.append(
                "Evidencia lexica debil (FORMA-IR): el documento mejor puntuado no supero el "
                "umbral de significancia contra el nulo calibrado -- la respuesta puede no ser "
                "la evidencia mas pertinente disponible."
            )

    plan = {
        "tipo": modo_interaccion or "preguntar",
        "filtros": {},
        "presupuesto": presupuesto,
        "k": len(paquetes),
        "tokens_usados": resultado.get("tokens_totales", 0),
        "_metodo": "forma_ir",
    }

    return {"pregunta": q, "plan": plan, "paquetes": paquetes, "avisos": avisos}


def analizar_pregunta(q: str, idx=None) -> dict:
    """Stub minimo de compatibilidad -- agente.py importa esta funcion
    de recuperar.py en algunos puntos (ver import en agente.py); FORMA-IR
    no clasifica preguntas por tipo local/explicativa/global como el
    metodo anterior, asi que se devuelve un plan neutro."""
    return {"tipo": "preguntar", "filtros": {}, "presupuesto": 9000, "k": 10, "terminos": q.split()}
