# -*- coding: utf-8 -*-
"""
Fase I: conexion del pipeline FORMA-IR completo (A->H) al dataset de
evaluacion existente. Reimplementa el bucle de eval/evaluar_recuperacion.py
SIN MODIFICAR ese archivo, reutilizando eval/metricas.py tal cual (import,
no copia). No importa nada de recuperar.py/agente.py/servidor.py -- corre
FORMA-IR de punta a punta como un sistema independiente.

LIMITACION HEREDADA (identica a la de eval/evaluar_recuperacion.py, ver su
docstring): el dataset dorado (eval/data/golden_dataset.jsonl) tiene 0 de
57 preguntas con expected_document_ids/acceptable_answers anotados. Sin
esa anotacion humana, Recall@k/MRR/evidence-F1 REALES no se pueden
calcular para NINGUN metodo, FORMA-IR incluido -- este script reporta
proxies declaradas como tales (cobertura, latencia, fraccion de evidencia
retenida en el empaquetado), nunca sustituye la ausencia de gold por un
numero inventado.

Uso:
    python -m forma_ir.comparar_con_produccion
"""
import json
import os
import time
from collections import defaultdict

from forma_ir.calibracion import construir_reservorios_por_familia, p_valor_calibrado
from forma_ir.documento import agregar_documentos, rankear_unidades_de_documento
from forma_ir.empaquetado import empaquetar_por_cobertura_submodular
from forma_ir.evidencia import VectorEvidencia, calcular_idf, calcular_vector_evidencia, tokenizar
from forma_ir.firma import secuencia_de_firmas
from forma_ir.tipos import Bloque, UnidadRetenida

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CORPUS = os.path.join(RAIZ, "forma_ir_corpus")


def _cargar_dataset(path: str | None = None) -> list[dict]:
    path = path or os.path.join(RAIZ, "eval", "data", "golden_dataset.jsonl")
    filas = []
    with open(path, encoding="utf-8") as f:
        for linea in f:
            linea = linea.strip()
            if linea:
                filas.append(json.loads(linea))
    return filas


def _cargar_corpus_segmentado():
    bloques_por_doc: dict[str, list[Bloque]] = defaultdict(list)
    with open(os.path.join(CORPUS, "bloques.jsonl"), encoding="utf-8") as f:
        for line in f:
            d = json.loads(line)
            bloques_por_doc[d["doc_id"]].append(Bloque(**d))
    for doc_id in bloques_por_doc:
        bloques_por_doc[doc_id].sort(key=lambda b: b.seq)

    unidades_por_familia: dict[int, list[UnidadRetenida]] = defaultdict(list)
    todas_las_unidades: list[UnidadRetenida] = []
    unidades_por_doc: dict[str, list[UnidadRetenida]] = defaultdict(list)
    with open(os.path.join(CORPUS, "unidades.jsonl"), encoding="utf-8") as f:
        for line in f:
            d = json.loads(line)
            u = UnidadRetenida(**d)
            unidades_por_familia[u.familia_id].append(u)
            todas_las_unidades.append(u)
            unidades_por_doc[u.doc_id].append(u)

    firmas_por_doc = {doc_id: secuencia_de_firmas(bloques) for doc_id, bloques in bloques_por_doc.items()}
    return bloques_por_doc, firmas_por_doc, unidades_por_familia, todas_las_unidades, unidades_por_doc


def preparar_indice():
    """Construye una sola vez todo lo que el pipeline de consulta
    necesita: IDF global, reservorios de nulo por familia. Costoso
    (construccion de reservorios ~1-2s), se hace UNA vez por proceso,
    no por consulta."""
    bloques_por_doc, firmas_por_doc, unidades_por_familia, todas_las_unidades, unidades_por_doc = _cargar_corpus_segmentado()

    idf = calcular_idf([tokenizar(b.texto) for bloques in bloques_por_doc.values() for b in bloques])
    longitudes = [len(u.texto.split()) for u in todas_las_unidades]
    longitud_promedio = sum(longitudes) / len(longitudes) if longitudes else 1.0

    reservorios = construir_reservorios_por_familia(
        dict(unidades_por_familia), todas_las_unidades, bloques_por_doc, firmas_por_doc, idf, longitud_promedio
    )

    return {
        "bloques_por_doc": bloques_por_doc,
        "firmas_por_doc": firmas_por_doc,
        "unidades_por_doc": unidades_por_doc,
        "todas_las_unidades": todas_las_unidades,
        "idf": idf,
        "longitud_promedio": longitud_promedio,
        "reservorios": reservorios,
    }


def responder_consulta(query: str, indice: dict, presupuesto_tokens: int = 2048, epsilon: float = 0.1,
                         top_k_documentos: int = 5) -> dict:
    """Pipeline completo E->F->G->H para una sola consulta. Devuelve un
    dict auditable (S5.8: exact extractive text, document identifier,
    page, calibrated score, document correction, token count)."""
    t0 = time.time()

    idf = indice["idf"]
    longitud_promedio = indice["longitud_promedio"]
    reservorios = indice["reservorios"]
    bloques_por_doc = indice["bloques_por_doc"]
    firmas_por_doc = indice["firmas_por_doc"]

    # E + F: vector de evidencia y p-valor calibrado, SOLO para unidades
    # cuya familia tiene reservorio (familias sin muestra suficiente,
    # ver Fase F, quedan fuera del ranking calibrado -- limitacion
    # documentada, no error silencioso).
    p_valores_por_doc: dict[str, dict[str, float]] = defaultdict(dict)
    # Vectores de evidencia retenidos por unidad_id -- necesarios para
    # reportar cobertura/score en la salida final (bug de integracion
    # encontrado al conectar con produccion: sin esto, el frontend
    # recibia cobertura=None para TODA unidad, y evidenceMapping.ts
    # clasifica soporte "direct" solo cuando cobertura>0.6, asi que
    # ninguna evidencia se mostraba nunca como respaldo fuerte).
    vectores_por_unidad: dict[str, VectorEvidencia] = {}
    for u in indice["todas_las_unidades"]:
        reservorio = reservorios.get(u.familia_id)
        if reservorio is None:
            continue
        bloques_doc = bloques_por_doc.get(u.doc_id)
        firmas_doc = firmas_por_doc.get(u.doc_id)
        if not bloques_doc:
            continue
        vector = calcular_vector_evidencia(query, u, bloques_doc, firmas_doc, idf, longitud_promedio)
        # Solo se calibra si hay ALGUNA evidencia lexica real -- evita
        # gastar tiempo calibrando ruido puro (b=c=x=a=0).
        if vector.b == 0.0 and vector.c == 0.0 and vector.a == 0.0:
            continue
        p = p_valor_calibrado(vector, reservorio)
        p_valores_por_doc[u.doc_id][u.unidad_id] = p
        vectores_por_unidad[u.unidad_id] = vector

    if not p_valores_por_doc:
        return {
            "query": query, "documentos": [], "unidades_empaquetadas": [],
            "tokens_totales": 0, "latencia_s": time.time() - t0, "cobertura": False,
        }

    # G: agregacion Bonferroni a nivel documento
    resultados_doc = agregar_documentos(dict(p_valores_por_doc))
    top_docs = resultados_doc[:top_k_documentos]

    # H: empaquetado submodular sobre las unidades de los documentos top
    unidad_por_id = {u.unidad_id: u for u in indice["todas_las_unidades"]}
    candidatas_para_empaquetar = []
    for rd in top_docs:
        ranking_unidades = rankear_unidades_de_documento(rd.doc_id, p_valores_por_doc[rd.doc_id])
        for unidad_id, _p in ranking_unidades[:3]:  # hasta 3 unidades por documento top
            candidatas_para_empaquetar.append(unidad_por_id[unidad_id])

    # Bug de integracion encontrado al conectar con produccion
    # (forma_ir_recuperar.py): `presupuesto_tokens` era un parametro
    # aceptado pero NUNCA pasado al empaquetado -- el greedy solo se
    # detenia por el objetivo de cobertura (epsilon), sin ningun tope
    # duro de tokens. Corregido pasando `presupuesto_max_tokens`.
    resultado_empaquetado = empaquetar_por_cobertura_submodular(
        candidatas_para_empaquetar, query, idf, tokenizar, epsilon=epsilon,
        presupuesto_max_tokens=presupuesto_tokens,
    )

    unidades_finales = [unidad_por_id[uid] for uid in resultado_empaquetado.unidades_seleccionadas]

    return {
        "query": query,
        "documentos": [{"doc_id": rd.doc_id, "p_doc": rd.p_doc, "m_d": rd.m_d} for rd in top_docs],
        "unidades_empaquetadas": [
            # Texto COMPLETO -- el truncamiento a [:300] de una version
            # anterior era razonable solo para la previsualizacion del
            # reporte de evaluacion (Fase I), pero es incorrecto para
            # cualquier consumidor real (el LLM de produccion necesita
            # el texto completo de la unidad como evidencia, no un
            # fragmento cortado a ciegas en el caracter 300).
            {"unidad_id": u.unidad_id, "doc_id": u.doc_id, "pagina_inicio": u.pagina_inicio,
             "texto": u.texto,
             # score/cobertura del vector de evidencia (Fase E) -- el
             # frontend usa `cobertura` para clasificar soporte
             # "direct" vs "context" (ver evidenceMapping.ts), asi que
             # dejarlo en None siempre habria degradado silenciosamente
             # esa clasificacion visual para toda respuesta de FORMA-IR.
             "score": vectores_por_unidad[u.unidad_id].b if u.unidad_id in vectores_por_unidad else None,
             "cobertura": vectores_por_unidad[u.unidad_id].c if u.unidad_id in vectores_por_unidad else None}
            for u in unidades_finales
        ],
        "tokens_totales": resultado_empaquetado.tokens_totales,
        "fraccion_evidencia_retenida": resultado_empaquetado.fraccion_evidencia_retenida,
        "latencia_s": time.time() - t0,
        "cobertura": len(unidades_finales) > 0,
    }


def ejecutar_evaluacion(limite_preguntas: int | None = None, verbose: bool = True) -> dict:
    dataset = _cargar_dataset()
    if limite_preguntas:
        dataset = dataset[:limite_preguntas]

    if verbose:
        print("Preparando indice (IDF + reservorios de nulo por familia)...")
    t0 = time.time()
    indice = preparar_indice()
    if verbose:
        print(f"Indice listo en {time.time()-t0:.1f}s ({len(indice['reservorios'])} familias calibradas)\n")

    resultados = []
    n_con_cobertura = 0
    for fila in dataset:
        pregunta = fila["question"]
        r = responder_consulta(pregunta, indice)
        r["question_id"] = fila["question_id"]
        resultados.append(r)
        if r["cobertura"]:
            n_con_cobertura += 1
        if verbose:
            top_doc = r["documentos"][0]["doc_id"] if r["documentos"] else "(ninguno)"
            print(f"  {fila['question_id']:<14} cobertura={r['cobertura']!s:<6} "
                  f"top_doc={top_doc[:40]:<40} tokens={r['tokens_totales']:>5} "
                  f"latencia={r['latencia_s']*1000:.0f}ms")

    tasa_cobertura = n_con_cobertura / len(dataset) if dataset else 0.0
    latencias = [r["latencia_s"] for r in resultados]
    fracciones_evidencia = [r.get("fraccion_evidencia_retenida", 0.0) for r in resultados if r["cobertura"]]

    # Distribucion de p_doc del mejor documento por pregunta -- la senal
    # mas honesta de que tan bien funciono la calibracion en un caso
    # real: p_doc bajo = evidencia genuinamente fuerte contra el nulo;
    # p_doc alto (cerca de 1.0) = el documento gano por ser "el menos
    # malo" entre candidatas debiles, no por evidencia fuerte.
    # Hallazgo real (57 preguntas, corpus completo): solo 3/57 preguntas
    # alcanzaron p_doc < 0.1; 48/57 quedaron con p_doc > 0.5 -- esperable
    # dado que el dataset usa preguntas parafraseadas en lenguaje natural
    # y el metodo es puramente lexico (BM25F sin sinonimos/expansion,
    # sin LLM) -- una limitacion honesta del ENFOQUE lexico puro sobre
    # ESTE dataset, no un bug del pipeline (verificado inspeccionando
    # casos con p_doc bajo: cuando hay coincidencia lexica literal con
    # el titulo/tema del documento, el ranking es correcto).
    p_docs = [r["documentos"][0]["p_doc"] for r in resultados if r["documentos"]]
    n_evidencia_fuerte = sum(1 for p in p_docs if p < 0.1)
    n_evidencia_debil = sum(1 for p in p_docs if p > 0.5)

    resumen = {
        "n_preguntas": len(dataset),
        "n_con_cobertura": n_con_cobertura,
        "tasa_cobertura": tasa_cobertura,
        "latencia_media_s": sum(latencias) / len(latencias) if latencias else 0.0,
        "latencia_maxima_s": max(latencias) if latencias else 0.0,
        "fraccion_evidencia_retenida_media": sum(fracciones_evidencia) / len(fracciones_evidencia) if fracciones_evidencia else 0.0,
        "n_preguntas_con_evidencia_fuerte_p_doc_menor_0_1": n_evidencia_fuerte,
        "n_preguntas_con_evidencia_debil_p_doc_mayor_0_5": n_evidencia_debil,
        "limitacion": (
            "0/57 preguntas del dataset tienen expected_document_ids/acceptable_answers "
            "anotados -- Recall@k, MRR y evidence-F1 REALES no son calculables. Las metricas "
            "reportadas aqui (cobertura, latencia, fraccion de evidencia retenida) son proxies "
            "declaradas como tales, no sustituyen evaluacion con gold humano."
        ),
    }

    if verbose:
        print(f"\n{'='*70}")
        print(f"Preguntas evaluadas: {resumen['n_preguntas']}")
        print(f"Tasa de cobertura (>=1 unidad devuelta): {resumen['tasa_cobertura']:.1%}")
        print(f"Latencia media por consulta: {resumen['latencia_media_s']*1000:.0f}ms")
        print(f"Latencia maxima: {resumen['latencia_maxima_s']*1000:.0f}ms")
        print(f"Fraccion de evidencia retenida (media, solo con cobertura): {resumen['fraccion_evidencia_retenida_media']:.1%}")
        print(f"Preguntas con evidencia FUERTE contra el nulo (p_doc<0.1): {resumen['n_preguntas_con_evidencia_fuerte_p_doc_menor_0_1']}/{resumen['n_preguntas']}")
        print(f"Preguntas con evidencia DEBIL / ganador por default (p_doc>0.5): {resumen['n_preguntas_con_evidencia_debil_p_doc_mayor_0_5']}/{resumen['n_preguntas']}")
        print(f"\nLIMITACION: {resumen['limitacion']}")

    return {"resumen": resumen, "resultados": resultados}


if __name__ == "__main__":
    salida = ejecutar_evaluacion()
    ruta_salida = os.path.join(RAIZ, "forma_ir_corpus", "evaluacion_57_preguntas.json")
    with open(ruta_salida, "w", encoding="utf-8") as f:
        json.dump(salida, f, ensure_ascii=False, indent=1)
    print(f"\nResultado detallado guardado en {ruta_salida}")
