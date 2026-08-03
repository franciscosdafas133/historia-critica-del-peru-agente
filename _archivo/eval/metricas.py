# -*- coding: utf-8 -*-
"""
Metricas de evaluacion de recuperacion, y bootstrap pareado para
intervalos de confianza. Codigo nuevo de evaluacion -- no toca
recuperar.py/agente.py/servidor.py.
"""
import random


def answer_containment(texto_recuperado_normalizado, respuestas_aceptables_normalizadas):
    """True si alguna respuesta aceptable aparece como substring del texto
    recuperado (ya normalizado por texto_util.normtxt en el llamador).
    Es una medida deliberadamente laxa (string containment), documentada
    como tal -- no reemplaza revision humana."""
    if not respuestas_aceptables_normalizadas:
        return None  # no hay con que comparar -- no confundir con "False"
    return any(r in texto_recuperado_normalizado for r in respuestas_aceptables_normalizadas)


def evidence_precision_recall_f1(hashes_recuperados, hashes_gold):
    """Precision/recall/F1 de evidencia a nivel de hash de texto normalizado.
    hashes_recuperados: set de text_hash de los fragmentos que el metodo trajo.
    hashes_gold: set de text_hash de la evidencia dorada para esa pregunta.
    Devuelve (precision, recall, f1); None si no hay gold (no confundir con 0)."""
    if not hashes_gold:
        return None, None, None
    if not hashes_recuperados:
        return 0.0, 0.0, 0.0
    interseccion = hashes_recuperados & hashes_gold
    precision = len(interseccion) / len(hashes_recuperados)
    recall = len(interseccion) / len(hashes_gold)
    f1 = 0.0 if (precision + recall) == 0 else 2 * precision * recall / (precision + recall)
    return precision, recall, f1


def recall_at_k(rank_del_documento_correcto, k):
    """rank_del_documento_correcto: posicion (1-indexed) del primer
    resultado que pertenece a expected_document_ids, o None si nunca aparecio."""
    if rank_del_documento_correcto is None:
        return 0.0
    return 1.0 if rank_del_documento_correcto <= k else 0.0


def mrr(rank_del_documento_correcto):
    if rank_del_documento_correcto is None:
        return 0.0
    return 1.0 / rank_del_documento_correcto


def bootstrap_pareado_ic95(valores_a, valores_b, n_muestras=10000, seed=1234):
    """Bootstrap pareado sobre la diferencia (a - b), para poder decir si
    un metodo es mejor que otro con un intervalo de confianza del 95%,
    en vez de solo comparar promedios. Requiere listas de igual longitud
    (mismo orden de preguntas en ambos metodos).

    Devuelve (diferencia_media, ic_bajo, ic_alto). Si el intervalo incluye
    cero, la diferencia no es estadisticamente concluyente -- el llamador
    NO debe declarar un ganador en ese caso.
    """
    assert len(valores_a) == len(valores_b), "las listas deben ser pareadas (misma pregunta, mismo indice)"
    n = len(valores_a)
    if n == 0:
        return 0.0, 0.0, 0.0

    diffs = [a - b for a, b in zip(valores_a, valores_b)]
    diferencia_media = sum(diffs) / n

    rng = random.Random(seed)
    remuestreos = []
    for _ in range(n_muestras):
        muestra = [diffs[rng.randrange(n)] for _ in range(n)]
        remuestreos.append(sum(muestra) / n)
    remuestreos.sort()
    ic_bajo = remuestreos[int(0.025 * n_muestras)]
    ic_alto = remuestreos[int(0.975 * n_muestras) - 1]
    return diferencia_media, ic_bajo, ic_alto


def diferencia_es_concluyente(ic_bajo, ic_alto):
    """El intervalo de confianza NO debe incluir cero para declarar diferencia."""
    return not (ic_bajo <= 0 <= ic_alto)
