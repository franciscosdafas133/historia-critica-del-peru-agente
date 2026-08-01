# -*- coding: utf-8 -*-
"""
Recuperador - Historia Critica del Peru

Fase 3 del metodo: construccion de evidencia en tiempo de consulta.

Implementa la pieza que si es propia de la propuesta:
los bloques almacenados son finos y objetivos (pagina/diapositiva),
pero el paquete que se entrega se construye DESPUES de conocer la pregunta,
expandiendo por vecindad y por estructura, bajo presupuesto adaptativo.

NO implementa todavia: grafo de relaciones inferidas, verificacion de
suficiencia por LLM, verificacion de citas. Esas capas se agregan solo si
la medicion justifica su costo.

Uso:
    python recuperar.py "¿por qué colapsó la población andina en el siglo XVI?"
    python recuperar.py --semana 11 "norte patriota sur realista"
    python recuperar.py --modo completo "¿cómo se relacionan las unidades?"
"""
import sys, io, os, json, re, pickle, argparse, unicodedata

import numpy as np
from sklearn.metrics.pairwise import cosine_similarity

from texto_util import normtxt, tokenizar   # mismo tokenizador que uso el indice

RAIZ = os.path.dirname(os.path.abspath(__file__))
IDX = os.path.join(RAIZ, "corpus", "indice.pkl")

# Palabras de metadiscurso argumentativo: aparecen en tesis y posturas del
# estudiante (modo debate) pero nunca en el corpus historico, porque no son
# contenido, son la forma de la afirmacion. Si se cuentan en la cobertura
# lexica, diluyen la señal real y una tesis larga puede quedar sin evidencia
# aunque el tema si este cubierto -- un falso negativo peor que el problema
# que el filtro de cobertura queria resolver.
METADISCURSO = {"creo", "creemos", "pienso", "considero", "opino", "sostengo",
                "explican", "explica", "explicar", "solo", "todo", "toda",
                "factor", "menor", "mayor", "mas", "menos", "fue", "son",
                "es", "no", "estoy", "acuerdo", "desacuerdo", "postura",
                "tesis", "argumento", "creeria", "diria"}


# ============ Paso 1: entender que evidencia pide la pregunta ============
# Sin LLM. Reglas + senales lexicas. Barato, determinista, auditable.
# Si la medicion muestra que no basta, aqui es donde entraria un modelo.

PISTAS_GLOBAL = ["todas las", "en general", "a lo largo del curso", "relacion entre",
                 "relacionan", "compara", "comparar", "diferencia entre", "sintesis",
                 "resumen del curso", "panorama", "evolucion general", "hilo conductor"]
PISTAS_MULTI  = ["por que", "porque", "causas", "consecuencias", "explica", "como afecto",
                 "que relacion", "en que medida", "analiza", "argumenta", "contrasta"]
PISTAS_LOCAL  = ["cuando", "que fecha", "cuantos", "cual es la definicion", "define",
                 "quien es", "que dice el silabo", "cuanto vale", "fecha del examen"]

def analizar_pregunta(q, idx):
    n = normtxt(q)
    demandas, tipo = [], "explicativa"
    if any(p in n for p in PISTAS_LOCAL):   tipo = "local"
    if any(p in n for p in PISTAS_MULTI):   tipo = "explicativa"
    if any(p in n for p in PISTAS_GLOBAL):  tipo = "global"

    # filtros estructurales detectables sin modelo
    filtros = {}
    m = re.search(r"semana\s*(\d+)", n)
    if m: filtros["semana"] = int(m.group(1))
    m = re.search(r"unidad\s*(\d)", n)
    if m: filtros["unidad"] = int(m.group(1))
    if any(w in n for w in ["examen", "nota", "evaluacion", "calificado", "silabo",
                            "cronograma", "fecha", "entrega", "peso"]):
        filtros["autoridad"] = "oficial"
    for a in idx["por_autor"]:
        if a in n and len(a) > 4: filtros["autor"] = a; break

    # presupuesto adaptativo: no "pocos tokens", sino los necesarios
    presupuesto = {"local": 3000, "explicativa": 9000, "global": 30000}[tipo]
    k_semillas  = {"local": 4, "explicativa": 10, "global": 24}[tipo]
    return {"tipo": tipo, "filtros": filtros, "presupuesto": presupuesto,
            "k": k_semillas, "terminos": tokenizar(q)}


# ============ Paso 2-3: localizar y recuperar semillas (hibrido) ============

def buscar(q, idx, plan, pool=60):
    N = len(idx["bloques"])
    toks = tokenizar(q)

    s_bm = np.array(idx["bm25"].get_scores(toks), dtype=float)
    qv = idx["tfidf"].transform([q])
    s_tf = cosine_similarity(qv, idx["M"]).ravel()

    def z(v):
        sd = v.std()
        return (v - v.mean()) / sd if sd > 1e-9 else np.zeros_like(v)
    score = 0.6 * z(s_bm) + 0.4 * z(s_tf)

    # El score normalizado siempre produce un ganador relativo, aunque ningun
    # bloque tenga relacion con la pregunta. Conservamos la senal cruda para
    # poder distinguir "el mejor de todos" de "suficientemente pertinente".
    plan["_crudo_max"] = float(s_bm.max()) if len(s_bm) else 0.0
    plan["_tf_max"] = float(s_tf.max()) if len(s_tf) else 0.0

    # Cobertura de terminos: que fraccion de los terminos de la pregunta
    # aparece realmente en el bloque. Es mejor discriminador que el score
    # absoluto, porque una pregunta ajena al curso puede compartir alguna
    # palabra suelta ("capital", "region") y aun asi puntuar alto.
    vocab = idx["tfidf"].vocabulary_
    presentes = [t for t in toks if t in vocab]
    plan["_cobertura_vocab"] = len(presentes) / len(toks) if toks else 0.0

    # filtrado estructural duro (antes del ranking, no despues)
    f = plan["filtros"]
    permitido = None
    for clave, mapa in (("semana", "por_semana"), ("unidad", "por_unidad"),
                        ("autoridad", "por_autoridad"), ("autor", "por_autor")):
        if clave in f:
            s = set(idx[mapa].get(f[clave], []))
            permitido = s if permitido is None else (permitido & s)
    if permitido is not None and permitido:
        mask = np.full(N, -1e9)
        for i in permitido: mask[i] = 0
        score = score + mask

    orden = np.argsort(-score)[:pool]
    # Por cada candidato calculamos cuantos terminos distintos de la pregunta
    # aparecen en su texto. Un bloque que solo comparte una palabra generica
    # no es evidencia, por muy arriba que quede en el ranking.
    #
    # En modo debate la "pregunta" es una tesis del estudiante, con palabras
    # de metadiscurso ("creo", "solo", "factor") que nunca van a aparecer en
    # el corpus historico. Contarlas en el denominador de cobertura castiga
    # tesis largas y bien argumentadas exactamente igual que preguntas ajenas
    # al curso -- se excluyen del calculo, no de la busqueda BM25/TF-IDF.
    B = idx["bloques"]
    unicos = set(toks)
    if plan.get("_modo_interaccion") == "debate":
        unicos = unicos - METADISCURSO or unicos   # nunca vaciar del todo
    salida = []
    for i in orden:
        if score[i] <= -1e8: continue
        i = int(i)
        tb = set(tokenizar(B[i]["_full"] if "_full" in B[i] else B[i]["texto"]))
        cob = len(unicos & tb) / len(unicos) if unicos else 0.0
        salida.append((i, float(score[i]), float(s_bm[i]), cob))
    return salida


# ============ Paso 4: expansion estructural POST-consulta ============
# Aqui esta la diferencia con RAG top-k: los limites del fragmento entregado
# no estaban fijados de antemano; se deciden ahora, alrededor de cada semilla.

def expandir(semilla, idx, score, radio=1):
    """Crece un span alrededor de la semilla usando vecindad real del documento."""
    v = idx["vecinos"]
    span = [semilla]
    cur = semilla
    for _ in range(radio):
        a = v.get(cur, {}).get("anterior")
        if a is not None: span.insert(0, a); cur = a
        else: break
    cur = semilla
    for _ in range(radio):
        s = v.get(cur, {}).get("siguiente")
        if s is not None: span.append(s); cur = s
        else: break
    return span


# ============ Paso 5-6: construir paquetes y seleccionar bajo presupuesto ============

def construir_paquetes(q, idx, plan, verbose=False):
    cand = buscar(q, idx, plan)
    if not cand: return [], plan

    B, D = idx["bloques"], idx["docs"]
    radio = {"local": 0, "explicativa": 1, "global": 2}[plan["tipo"]]

    usados, paquetes, tokens = set(), [], 0
    vistos_doc = {}

    # Pertinencia: el bloque debe compartir una fraccion minima de los terminos
    # de la pregunta, no solo quedar arriba del ranking. Sin este corte, una
    # pregunta ajena al curso devuelve evidencia de apariencia legitima.
    #
    # Se desactiva cuando un filtro estructural ya acoto el conjunto: en
    # "¿que se ve en la semana 13?" el unico termino util es "semana", que se
    # consumio como filtro. Exigir cobertura lexica sobre lo que queda
    # descartaria toda la semana pese a estar correctamente localizada.
    #
    # LIMITE CONOCIDO: el filtro detecta preguntas cuyo vocabulario no existe
    # en el corpus ("receta de tallarines"), pero no las que reusan terminos
    # que si existen en otro sentido ("la capital de Francia" -> "capital"
    # aparece en historia economica). Filtrar ese caso requiere semantica, no
    # lexico; es una de las cosas que los embeddings deberian aportar, y una
    # razon concreta para medir si vale su costo. Mientras tanto lo cubre la
    # regla 2 del prompt: responder solo con la evidencia y declarar cuando
    # no alcanza.
    COBERTURA_MIN = 0.0 if plan["filtros"] else 0.34

    for i, sc, crudo, cob in cand:
        if len(paquetes) >= plan["k"]: break
        if i in usados: continue
        if cob < COBERTURA_MIN: continue
        d = D[B[i]["doc_id"]]

        # diversidad: no dejar que un documento gigante acapare el paquete
        cupo = 3 if plan["tipo"] != "global" else 5
        if vistos_doc.get(d["doc_id"], 0) >= cupo: continue

        span = [j for j in expandir(i, idx, sc, radio) if j not in usados]
        if not span: continue
        tk = sum(B[j]["tokens"] for j in span)

        if tokens + tk > plan["presupuesto"]:
            span = [i] if i not in usados else []      # degradar a solo el nucleo
            tk = B[i]["tokens"] if span else 0
            if not span or tokens + tk > plan["presupuesto"]: continue

        usados.update(span)
        vistos_doc[d["doc_id"]] = vistos_doc.get(d["doc_id"], 0) + 1
        tokens += tk

        unidad_lbl = "pagina" if "pagina" in B[span[0]]["fuente"] else "diapositiva"
        pgs = [B[j]["fuente"].get(unidad_lbl) for j in span]
        paquetes.append({
            "nucleo": B[i]["bloque_id"], "score": round(sc, 3), "bm25": round(crudo, 2),
            "cobertura": round(cob, 2),
            "doc": d["titulo"], "cita": d.get("cita") or d["titulo"],
            "tipo": d["tipo"], "autoridad": d["autoridad"],
            "unidad": d.get("unidad"), "semana": d.get("semana"),
            "paginas": f"{unidad_lbl} {min(pgs)}-{max(pgs)}" if len(pgs) > 1 else f"{unidad_lbl} {pgs[0]}",
            "archivo": d["archivo"], "tokens": tk,
            "texto": "\n\n".join(B[j]["texto"] for j in span),
            "ocr": any(B[j]["fuente"].get("ocr") for j in span),
        })

    plan["tokens_usados"] = tokens
    return paquetes, plan


# ============ Paso 7: comprobacion de suficiencia (barata, sin LLM) ============

def comprobar_suficiencia(paquetes, plan):
    avisos = []
    if not paquetes:
        avisos.append("SIN EVIDENCIA: ninguna fuente autorizada responde a esto.")
        return avisos
    cob = plan["tokens_usados"] / plan["presupuesto"]
    if cob < 0.15:
        avisos.append(f"Evidencia escasa ({plan['tokens_usados']} tok de {plan['presupuesto']} disponibles).")
    if len({p["doc"] for p in paquetes}) == 1 and plan["tipo"] != "local":
        avisos.append("Toda la evidencia proviene de un solo documento: cobertura posiblemente parcial.")
    if any(p["ocr"] for p in paquetes):
        avisos.append("Parte de la evidencia proviene de OCR: puede contener errores de transcripcion.")
    if plan["tipo"] == "global" and len(paquetes) < 6:
        avisos.append("Pregunta global con pocas fuentes: considerar modo de contexto completo.")
    return avisos


# Ajuste de presupuesto por modo de interaccion (agente.py). No cambia como
# se clasifica ni se busca la pregunta -- solo cuanto espacio se le da al
# resultado. RESUMEN pide deliberadamente mas cobertura, porque por diseño
# cubre un tema o una semana entera, no un punto puntual; los demas modos
# usan el presupuesto que analizar_pregunta ya calculo.
MULTIPLICADOR_MODO = {"resumen": 1.6, "practicar": 1.3, "evaluar": 1.3}

def recuperar(q, idx, verbose=True, modo_interaccion=None):
    plan = analizar_pregunta(q, idx)
    plan["_modo_interaccion"] = modo_interaccion
    mult = MULTIPLICADOR_MODO.get(modo_interaccion)
    if mult:
        plan["presupuesto"] = int(plan["presupuesto"] * mult)
        plan["k"] = int(plan["k"] * mult)
    paquetes, plan = construir_paquetes(q, idx, plan)
    avisos = comprobar_suficiencia(paquetes, plan)
    return {"pregunta": q, "plan": plan, "paquetes": paquetes, "avisos": avisos}


def imprimir(r, texto=False):
    p = r["plan"]
    print(f"\nPREGUNTA: {r['pregunta']}")
    print(f"  tipo={p['tipo']}  presupuesto={p['presupuesto']} tok  "
          f"usados={p['tokens_usados']} tok  paquetes={len(r['paquetes'])}")
    if p["filtros"]: print(f"  filtros estructurales: {p['filtros']}")
    print("-" * 96)
    for k, pq in enumerate(r["paquetes"], 1):
        marca = " [OCR]" if pq["ocr"] else ""
        print(f"[{k}] {pq['doc'][:52]}  ({pq['paginas']}) U{pq['unidad'] or '-'}/S{pq['semana'] or '-'} "
              f"{pq['tokens']}tok score={pq['score']}{marca}")
        print(f"    fuente: {pq['cita'][:100]}")
        if texto:
            t = re.sub(r"\s+", " ", pq["texto"])[:320]
            print(f"    | {t}...")
    if r["avisos"]:
        print("\nAVISOS DE SUFICIENCIA:")
        for a in r["avisos"]: print(f"  - {a}")


if __name__ == "__main__":
    # solo al ejecutarse directamente: al importarse, el wrapper lo pone quien importa
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8",
                                  errors="replace", line_buffering=True)
    ap = argparse.ArgumentParser()
    ap.add_argument("pregunta", nargs="*")
    ap.add_argument("--texto", action="store_true", help="mostrar extractos")
    a = ap.parse_args()
    idx = pickle.load(open(IDX, "rb"))
    q = " ".join(a.pregunta)
    if not q:
        print("uso: python recuperar.py \"tu pregunta\""); sys.exit(0)
    imprimir(recuperar(q, idx), texto=a.texto)
