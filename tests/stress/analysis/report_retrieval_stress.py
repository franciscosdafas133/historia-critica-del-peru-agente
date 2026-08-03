# -*- coding: utf-8 -*-
"""Reporte del ESTRES DE RECUPERACION (calidad bajo presion, no infraestructura)."""
import json, os

RAIZ = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
BASE = os.path.join(RAIZ, "tests", "stress")


def main():
    d = json.load(open(os.path.join(BASE, "results", "stress_retrieval_core.json"), encoding="utf-8"))
    A, C, D, E, F, G = d["A_acierto_escala"], d["C_robustez_lexica"], d["D_sensibilidad_tamano"], d["E_estabilidad_parafrasis"], d["F_eficiencia"], d["G_calibracion"]

    gates = []
    def g(nombre, valor, umbral, ok, lectura):
        gates.append({"prueba": nombre, "valor": valor, "umbral": umbral,
                      "estado": "PASS" if ok else "FAIL", "lectura": lectura})

    g("A · Acierto: Recall@1 con texto literal", f"{A['recall_1_pct']}%", ">=90%", (A['recall_1_pct'] or 0) >= 90,
      "Una frase copiada del documento deberia devolverlo como top-1 casi siempre")
    g("A · Acierto: Recall@3", f"{A['recall_3_pct']}%", ">=95%", (A['recall_3_pct'] or 0) >= 95,
      "El documento correcto deberia estar en el top-3")
    g("A · Acierto: unidad exacta recuperada", f"{A['unidad_exacta_pct']}%", ">=70%", (A['unidad_exacta_pct'] or 0) >= 70,
      "El fragmento exacto de origen deberia venir empaquetado")
    g("A · El doc correcto NO aparece ni en top-5", f"{A['no_aparece_pct']}%", "<=5%", (A['no_aparece_pct'] or 100) <= 5,
      "Fallo total de recuperacion: el documento no figura en ningun puesto")
    g("C · Robustez: caida por degradacion lexica", f"{C['caida_total_pp']} pp", "<=15 pp", abs(C['caida_total_pp']) <= 15,
      "Sin tildes + typos no deberian hundir el acierto")
    g("E · Estabilidad ante distintas ventanas del mismo doc", f"{E['mismo_top1_en_3_ventanas_pct']}%", ">=80%",
      (E['mismo_top1_en_3_ventanas_pct'] or 0) >= 80,
      "Tres fragmentos del MISMO documento deberian converger al mismo top-1")
    g("F · Eficiencia: latencia p95 por consulta", f"{F['lat_global_p95_ms']} ms", "<=1500 ms",
      (F['lat_global_p95_ms'] or 9e9) <= 1500, "Coste computacional del motor por consulta")
    # Separacion RELATIVA, no absoluta: tras las correcciones los p-valores
    # viven en otra escala (0.004 vs 0.067), donde una diferencia absoluta de
    # 0.10 es imposible por construccion. Lo que importa es que el p_doc de
    # los fallos sea varias veces mayor que el de los aciertos.
    p_ac = G.get("p_doc_top1_medio_en_aciertos")
    p_fa = G.get("p_doc_top1_medio_en_fallos")
    ratio = (p_fa / p_ac) if (p_ac and p_fa and p_ac > 0) else None
    g("G · Calibracion discrimina acierto vs fallo", f"fallo/acierto = {ratio:.1f}x" if ratio else "n/d",
      ">=2x", (ratio or 0) >= 2.0,
      "p_doc debe ser MENOR en aciertos que en fallos (ratio alto = discrimina bien)")
    # OJO: menos saturacion es MEJOR. El umbral es un maximo tolerado, y 0%
    # es el resultado ideal -- una comparacion previa marcaba FAIL en 0.0%.
    sat = G.get("saturados_en_1.0_pct")
    g("G · p_doc saturado en 1.0 (menos es mejor)", f"{sat}%", "<=10%", sat is not None and sat <= 10,
      "Saturacion masiva = empate arbitrario en el ranking")

    fallidos = [x for x in gates if x["estado"] == "FAIL"]
    md = [f"""# Estrés de RECUPERACIÓN — calidad del motor bajo presión

**Fecha:** 2026-08-03 · **Corpus:** {d['n_documentos']} documentos · {d['n_unidades']} unidades · índice en {d['indice_build_s']}s
**Sin LLM, sin infraestructura:** mide si el motor **acierta**, no si aguanta.

## Veredicto: {len(gates)-len(fallidos)}/{len(gates)} pruebas superadas

| Prueba | Valor | Umbral | Estado |
|---|---|---|---|"""]
    for x in gates:
        md.append(f"| {x['prueba']} | **{x['valor']}** | {x['umbral']} | {'✅ PASS' if x['estado']=='PASS' else '❌ **FAIL**'} |")

    md.append(f"""
## A · Acierto a escala ({A['n']} consultas de texto literal)

Cada consulta es una frase **copiada textualmente** de una unidad real del corpus.
Es el caso más favorable posible: si algo debe acertar, es esto.

| Métrica | Valor |
|---|---|
| Recall@1 | {A['recall_1_pct']}% |
| Recall@3 | {A['recall_3_pct']}% |
| Recall@5 | {A['recall_5_pct']}% |
| Unidad exacta recuperada | {A['unidad_exacta_pct']}% |
| MRR | {A['mrr']} |
| Documento correcto ausente del top-5 | {A['no_aparece_pct']}% |

## C · Robustez léxica (degradación progresiva)

| Nivel | Escritura | Recall@3 | Latencia p50 |
|---|---|---|---|""")
    for r in C["curva"]:
        md.append(f"| {r['nivel']} | {r['descripcion']} | {r['recall_3_pct']}% | {r['lat_p50_ms']} ms |")
    md.append(f"\n**Caída total:** {C['caida_total_pp']} puntos porcentuales entre escritura intacta y degradada.")

    md.append("\n## D · Sensibilidad al tamaño del documento\n\n| Unidades del doc | n | Recall@1 | Recall@3 | p_doc medio |\n|---|---|---|---|---|")
    for r in D:
        md.append(f"| {r['rango_unidades']} | {r['n']} | {r['recall_1_pct']}% | {r['recall_3_pct']}% | {r['p_doc_correcto_medio']} |")
    md.append("\n> Si el acierto cae al crecer el documento, el ranking está sesgado por tamaño y no por evidencia.")

    md.append(f"""
## E · Estabilidad semántica

Tres ventanas distintas del **mismo documento** como consulta: ¿convergen al mismo top-1?
**{E['mismo_top1_en_3_ventanas_pct']}%** de los casos ({E['n']} documentos probados).

## F · Eficiencia

| Palabras en la consulta | p50 | p95 |
|---|---|---|""")
    for r in F["curva"]:
        md.append(f"| {r['palabras_consulta']} | {r['lat_p50_ms']} ms | {r['lat_p95_ms']} ms |")
    md.append(f"\n**Global:** p50 = {F['lat_global_p50_ms']} ms · p95 = {F['lat_global_p95_ms']} ms")

    md.append(f"""
## G · ¿La calibración sirve para algo?

| Métrica | Valor |
|---|---|
| p_doc medio cuando ACIERTA | {G['p_doc_top1_medio_en_aciertos']} |
| p_doc medio cuando FALLA | {G['p_doc_top1_medio_en_fallos']} |
| Separación (fallo − acierto) | **{G['separacion']}** |
| Consultas con p_doc saturado en 1.0 | **{G['saturados_en_1.0_pct']}%** |

{G['_lectura']}

## Documentos más perjudicados

Veces que el texto literal de un documento **no** lo devolvió como top-1:

| Fallos | Unidades del doc | Documento |
|---|---|---|""")
    for x in d["B_discriminacion"]["docs_mas_perjudicados"]:
        md.append(f"| {x['fallos']} | {x['tam']} | {x['doc'][:55]} |")

    dest = os.path.join(BASE, "reports", "RETRIEVAL_STRESS_REPORT.md")
    open(dest, "w", encoding="utf-8").write("\n".join(md) + "\n")
    # La consola de Windows usa cp1252 y no puede imprimir los emojis del
    # reporte: se imprime una version ASCII del veredicto, el archivo va completo.
    for x in gates:
        print(f"  [{x['estado']}] {x['prueba']:52s} {str(x['valor']):>14s} (umbral {x['umbral']})")
    print(f"\n-> {dest}")


if __name__ == "__main__":
    main()
