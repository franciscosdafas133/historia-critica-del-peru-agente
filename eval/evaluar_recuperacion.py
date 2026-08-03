# -*- coding: utf-8 -*-
"""
Track A/B de evaluacion offline de recuperacion. No llama al LLM, no
consume tokens de ninguna API. Compara el metodo real (recuperar.py)
contra los baselines de eval/baselines.py sobre el dataset dorado.

LIMITACION CENTRAL, por diseño explicito: el dataset dorado
(eval/data/golden_dataset.jsonl) tiene 0 de 57 preguntas con
gold_evidence/expected_document_ids anotados (ver eval/data/ESQUEMA.md).
Sin esa anotacion humana, Recall@k/MRR/nDCG/evidence-F1 REALES no se
pueden calcular -- este script los reporta como "no_disponible" en vez
de inventar un numero o sustituirlos en silencio por una proxy.

Lo que SI se calcula sin anotacion humana (proxies declaradas como tales):
  - tasa_sin_evidencia: fraccion de preguntas donde el metodo no
    devolvio ningun paquete (util para detectar fallos duros de cobertura).
  - cobertura_lexica_media: promedio del campo 'cobertura' que ya calcula
    recuperar.py (fraccion de terminos de la pregunta presentes en el
    texto recuperado) -- NO es lo mismo que answer/evidence recall.
  - tokens_usados, n_fragmentos, latencia: costo y composicion, igual que
    evaluar.py ya hacia.
  - repeticion_de_documento_top: si el documento con mejor score coincide
    entre el metodo real y cada baseline, como señal indirecta de acuerdo
    entre metodos (no de correctness).

En cuanto se anoten preguntas (ver eval/data/PLANTILLA_ANOTACION.md), este
mismo script calculara Recall@1/3/5, MRR y evidence-F1 reales sobre las
preguntas anotadas -- el codigo ya esta preparado (ver calcular_metricas_gold),
simplemente no tiene con que operar todavia.

Uso:
    python eval/evaluar_recuperacion.py
    python eval/evaluar_recuperacion.py --presupuesto 256
    python eval/evaluar_recuperacion.py --presupuestos 128,256,512,1024,2048,4096,8192
    python eval/evaluar_recuperacion.py --json eval/results/track_a.json
"""
import sys, os, io, json, pickle, time, argparse

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace", line_buffering=True)
RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RAIZ)

from recuperar import recuperar
from texto_util import normtxt
from eval.baselines import BASELINES
from eval.metricas import answer_containment, recall_at_k, mrr


def cargar_dataset(path=None):
    path = path or os.path.join(RAIZ, "eval", "data", "golden_dataset.jsonl")
    filas = []
    with open(path, encoding="utf-8") as f:
        for linea in f:
            linea = linea.strip()
            if linea:
                filas.append(json.loads(linea))
    return filas


def medir_metodo_real(pregunta, idx, presupuesto=None):
    t0 = time.time()
    r = recuperar(pregunta, idx, modo_interaccion="preguntar")
    dt = time.time() - t0
    paquetes = r["paquetes"]
    if presupuesto is not None:
        # recorta al presupuesto pedido para poder comparar curvas de
        # presupuesto contra los baselines (recuperar() ya aplica su
        # propio presupuesto por tipo de pregunta; para la curva B se
        # necesita el mismo B para todos los metodos).
        paquetes = _recortar_a_presupuesto(paquetes, presupuesto)
    return paquetes, dt, r["plan"]["tipo"]


def _recortar_a_presupuesto(paquetes, presupuesto):
    salida, usados = [], 0
    for p in paquetes:
        if usados + p["tokens"] > presupuesto:
            continue
        salida.append(p)
        usados += p["tokens"]
    return salida


def calcular_proxies_sin_gold(pregunta, paquetes):
    """Metricas calculables SIN anotacion humana. Ver docstring del modulo."""
    if not paquetes:
        return {"sin_evidencia": True, "n_fragmentos": 0, "tokens": 0,
                "cobertura_media": None, "doc_top": None}
    coberturas = [p.get("cobertura") for p in paquetes if p.get("cobertura") is not None]
    return {
        "sin_evidencia": False,
        "n_fragmentos": len(paquetes),
        "tokens": sum(p["tokens"] for p in paquetes),
        "cobertura_media": round(sum(coberturas) / len(coberturas), 4) if coberturas else None,
        "doc_top": paquetes[0]["doc"],
    }


def calcular_metricas_gold(fila, paquetes):
    """Metricas REALES contra evidencia dorada -- solo producen numero si
    la fila tiene annotation_status == 'annotated'. En caso contrario
    devuelve None explicito en cada campo, para que el reporte distinga
    "no hay evidencia relevante" (0.0) de "no se pudo medir" (None)."""
    if fila.get("annotation_status") != "annotated":
        return {"recall_at_1": None, "recall_at_3": None, "recall_at_5": None,
                "mrr": None, "evidence_precision": None, "evidence_recall": None,
                "evidence_f1": None, "answer_containment": None}

    expected_docs = set(fila.get("expected_document_ids", []))
    rank = None
    for i, p in enumerate(paquetes, 1):
        if p["doc"] in expected_docs or p.get("archivo") in expected_docs:
            rank = i
            break

    # Evidence precision/recall por CONTENCION de texto normalizado, no por
    # igualdad de hash exacto: el bloque recuperado por el metodo real casi
    # siempre es mas grande que la oracion anotada como gold_evidence (la
    # expansion de vecindad trae paginas/diapositivas completas), asi que
    # comparar hashes exactos subestimaria sistematicamente el recall. Se
    # considera "encontrado" un elemento de gold_evidence si su
    # normalized_text aparece como substring en el texto normalizado de
    # ALGUN paquete recuperado. Limitacion explicita: esto puede dar falsos
    # positivos con fragmentos cortos y genericos (ej. una fecha sola que
    # aparece en varios documentos) -- no reemplaza revision humana.
    gold_evidencia = fila.get("gold_evidence", [])
    if not gold_evidencia:
        ep, er, ef1 = None, None, None
    else:
        textos_recuperados_norm = [normtxt(p["texto"]) for p in paquetes]
        encontrados = 0
        for ev in gold_evidencia:
            objetivo = ev.get("normalized_text", "")
            if objetivo and any(objetivo in t for t in textos_recuperados_norm):
                encontrados += 1
        er = encontrados / len(gold_evidencia)
        # precision: de los paquetes recuperados, cuantos contienen AL MENOS
        # un elemento de gold_evidence -- aproximacion, no 1:1 con el paper.
        con_evidencia = sum(
            1 for t in textos_recuperados_norm
            if any(ev.get("normalized_text", "") in t for ev in gold_evidencia if ev.get("normalized_text"))
        )
        ep = con_evidencia / len(paquetes) if paquetes else 0.0
        ef1 = 0.0 if (ep + er) == 0 else 2 * ep * er / (ep + er)

    respuestas_norm = [normtxt(a) for a in fila.get("acceptable_answers", [])]
    texto_concat_norm = normtxt(" ".join(p["texto"] for p in paquetes))
    containment = answer_containment(texto_concat_norm, respuestas_norm)

    return {
        "recall_at_1": recall_at_k(rank, 1), "recall_at_3": recall_at_k(rank, 3),
        "recall_at_5": recall_at_k(rank, 5), "mrr": mrr(rank),
        "evidence_precision": ep, "evidence_recall": er, "evidence_f1": ef1,
        "answer_containment": containment,
    }


def evaluar(dataset, idx, metodos, presupuesto=None):
    resultados = []
    for fila in dataset:
        pregunta = fila["question"]
        for nombre in metodos:
            if nombre == "metodo_real":
                paquetes, dt, tipo_detectado = medir_metodo_real(pregunta, idx, presupuesto)
            else:
                t0 = time.time()
                paquetes = BASELINES[nombre](pregunta, idx, presupuesto or 9000)
                dt = time.time() - t0
                tipo_detectado = None

            proxies = calcular_proxies_sin_gold(pregunta, paquetes)
            gold = calcular_metricas_gold(fila, paquetes)
            resultados.append({
                "question_id": fila["question_id"], "question_type": fila["question_type"],
                "metodo": nombre, "presupuesto": presupuesto,
                "latencia_s": round(dt, 4), "tipo_detectado": tipo_detectado,
                **proxies, **gold,
            })
    return resultados


def resumir(resultados):
    from collections import defaultdict
    por_metodo = defaultdict(list)
    for r in resultados:
        por_metodo[r["metodo"]].append(r)

    resumen = {}
    for metodo, filas in por_metodo.items():
        n = len(filas)
        sin_evidencia = sum(1 for f in filas if f["sin_evidencia"])
        coberturas = [f["cobertura_media"] for f in filas if f["cobertura_media"] is not None]
        tokens = [f["tokens"] for f in filas]
        latencias = sorted(f["latencia_s"] for f in filas)

        def percentil(lst, p):
            if not lst:
                return None
            idx_p = min(int(len(lst) * p), len(lst) - 1)
            return lst[idx_p]

        anotadas = [f for f in filas if f["recall_at_1"] is not None]
        resumen[metodo] = {
            "n_preguntas": n,
            "tasa_sin_evidencia": round(sin_evidencia / n, 4) if n else None,
            "cobertura_lexica_media": round(sum(coberturas) / len(coberturas), 4) if coberturas else None,
            "tokens_promedio": round(sum(tokens) / n, 1) if n else None,
            "latencia_p50_s": percentil(latencias, 0.50),
            "latencia_p95_s": percentil(latencias, 0.95),
            "latencia_p99_s": percentil(latencias, 0.99),
            "n_preguntas_con_gold": len(anotadas),
            "recall_at_1_medio": (round(sum(f["recall_at_1"] for f in anotadas) / len(anotadas), 4)
                                    if anotadas else None),
            "mrr_medio": (round(sum(f["mrr"] for f in anotadas) / len(anotadas), 4)
                          if anotadas else None),
        }
    return resumen


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--presupuesto", type=int, default=None,
                     help="Si se da, TODOS los metodos usan este presupuesto fijo (para comparar curvas). "
                          "Si se omite, metodo_real usa su presupuesto adaptativo por tipo de pregunta.")
    ap.add_argument("--metodos", default="metodo_real,fixed_128,fixed_256,parrafo,sentence_top")
    ap.add_argument("--dataset", default=None)
    ap.add_argument("--json", help="ruta para guardar resultados crudos en JSON")
    a = ap.parse_args()

    dataset = cargar_dataset(a.dataset)
    metodos = a.metodos.split(",")
    idx = pickle.load(open(os.path.join(RAIZ, "corpus", "indice.pkl"), "rb"))

    print(f"Dataset: {len(dataset)} preguntas | Metodos: {metodos} | Presupuesto: {a.presupuesto or 'adaptativo (metodo_real) / 9000 (baselines)'}")
    anotadas = sum(1 for f in dataset if f.get("annotation_status") == "annotated")
    print(f"Preguntas con evidencia gold anotada: {anotadas} / {len(dataset)}")
    if anotadas == 0:
        print("AVISO: sin anotacion, Recall@k/MRR/evidence-F1 se reportan como null. Solo hay proxies sin gold.")
    print()

    resultados = evaluar(dataset, idx, metodos, a.presupuesto)
    resumen = resumir(resultados)

    print(f"{'metodo':<15}{'n':>4}{'sin_ev':>9}{'cob.lex':>9}{'tok.prom':>10}{'p50 lat':>9}{'p95 lat':>9}{'recall@1':>10}{'mrr':>8}")
    for metodo, s in resumen.items():
        recall1 = f"{s['recall_at_1_medio']:.3f}" if s['recall_at_1_medio'] is not None else "n/d"
        mrr_v = f"{s['mrr_medio']:.3f}" if s['mrr_medio'] is not None else "n/d"
        cob = f"{s['cobertura_lexica_media']:.3f}" if s['cobertura_lexica_media'] is not None else "n/d"
        print(f"{metodo:<15}{s['n_preguntas']:>4}{s['tasa_sin_evidencia']:>9.2%}{cob:>9}"
              f"{s['tokens_promedio']:>10.0f}{s['latencia_p50_s']:>9.4f}{s['latencia_p95_s']:>9.4f}"
              f"{recall1:>10}{mrr_v:>8}")

    if a.json:
        os.makedirs(os.path.dirname(a.json), exist_ok=True)
        with open(a.json, "w", encoding="utf-8") as f:
            json.dump({"resultados": resultados, "resumen": resumen}, f, ensure_ascii=False, indent=1)
        print(f"\n-> {a.json}")
