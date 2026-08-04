# -*- coding: utf-8 -*-
"""
Indice semantico: convierte cada bloque del corpus en un vector.

    python indexar_embeddings.py            # construye corpus/embeddings.npz
    python indexar_embeddings.py --probar    # comprueba el indice ya hecho

POR QUE EXISTE
--------------
La frontera de CERES-Omega (seccion 4.3 del paper) pide fusionar BM25 con una
senal DENSA. Hasta ahora ese hueco lo ocupaba TF-IDF/coseno, que no es densa:
sigue contando palabras. Eso hacia que el motor fallara en los dos sentidos:

  - "¿Como afectaron las epidemias coloniales?" recuperaba poco, porque los
    textos dicen "viruela", "sarampion" y "patogenos", no "epidemias".
  - "¿Que fue el gobierno de Velasco Alvarado?" recuperaba mucho, porque el
    corpus tiene las palabras "gobierno" y "velasco" sueltas, aunque no trate
    ese tema.

Medido con la API de embeddings sobre frases de prueba:
    "viruela y sarampion diezmaron..."  <->  "colapso demografico siglo XVI"   0.757
    "viruela y sarampion diezmaron..."  <->  "Velasco Alvarado, reforma 1969"  0.562
    "viruela y sarampion diezmaron..."  <->  "receta de pizza margarita"       0.442

El significado si separa lo que las palabras no separaban.

POR QUE PRECOMPUTADO Y NO UN MODELO LOCAL
-----------------------------------------
El backend corre en el plan gratuito de Render: 512 MB de RAM. Cargar
sentence-transformers con PyTorch se los come. Asi que los vectores de los
bloques se calculan UNA VEZ aqui y se suben al repo (~4 MB); en produccion
solo se carga un array de numpy y se embebe la consulta, que es una sola
llamada de API por pregunta.

DIMENSION
---------
gemini-embedding-001 devuelve 3072 dimensiones. Se truncan a 768 y se
renormaliza: es Matryoshka, esta entrenado para que el prefijo conserve la
mayor parte de la senal. 1310 bloques x 3072 float32 = 16 MB; a 768, 4 MB.
"""
import argparse
import os
import pickle
import re
import sys
import time

import numpy as np

RAIZ = os.path.dirname(os.path.abspath(__file__))
IDX = os.path.join(RAIZ, "corpus", "indice.pkl")
OUT = os.path.join(RAIZ, "corpus", "embeddings.npz")

# Proveedor de embeddings. Cohere es el preferido cuando hay clave:
#
#   - acepta 96 textos por peticion (Gemini, 32), asi que el corpus entero
#     cabe en 14 llamadas en vez de 41. Con cuotas gratuitas que cuentan
#     PETICIONES y no textos, esa diferencia decide si el indice se puede
#     construir de una sentada.
#   - es el mismo proveedor que ya genera las respuestas en produccion, asi
#     que no hace falta una segunda clave en el host.
#
# Se aprendio a la mala: la cuota diaria de Gemini para embeddings es de 1000
# peticiones y se agoto a mitad del corpus (bloque 896 de 1310).
REINTENTOS = 6

# Cada proveedor admite sus propias dimensiones de salida. embed-v4.0 solo
# acepta 256/512/1024/1536 -- pedirle 768 devuelve un 422. Se usa 1024, que
# para 1310 bloques son 5 MB: asumible en el repo y en la RAM de Render.
PROVEEDORES = {
    "cohere": {"modelo": "embed-v4.0", "lote": 96, "dim": 1024},
    "gemini": {"modelo": "gemini-embedding-001", "lote": 32, "dim": 768},
}

# El tier gratuito permite 100 peticiones por minuto para embed_content. Con
# lotes de 32 son ~41 peticiones para todo el corpus, pero enviadas seguidas
# agotan la cuota igual: el limite cuenta peticiones, no textos. Se espera
# entre lotes para quedarse holgadamente por debajo.
PAUSA = 1.2        # segundos entre lotes
PARCIAL = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                       "corpus", "_embeddings_parcial.npy")


def cliente(preferido=None):
    """Devuelve (nombre_proveedor, cliente). Prefiere Cohere si hay clave."""
    try:
        from dotenv import load_dotenv
        load_dotenv(os.path.join(RAIZ, ".env"))
    except ImportError:
        pass

    orden = [preferido] if preferido else ["cohere", "gemini"]
    for nombre in orden:
        if nombre == "cohere" and os.environ.get("COHERE_API_KEY"):
            import cohere
            return "cohere", cohere.ClientV2(api_key=os.environ["COHERE_API_KEY"])
        if nombre == "gemini" and os.environ.get("GEMINI_API_KEY"):
            from google import genai
            return "gemini", genai.Client(api_key=os.environ["GEMINI_API_KEY"])

    print("Falta COHERE_API_KEY o GEMINI_API_KEY en .env — sin una de las dos")
    print("no se puede construir el indice semantico.")
    sys.exit(1)


def embeber(prov, cli, textos, tipo):
    """Embebe textos con reintentos ante limite de cuota.

    `tipo` es "documento" o "consulta": los dos proveedores distinguen ambos
    casos internamente, y usar el mismo para los dos degrada la busqueda.
    """
    for intento in range(REINTENTOS):
        try:
            if prov == "cohere":
                r = cli.embed(
                    texts=textos,
                    model=PROVEEDORES["cohere"]["modelo"],
                    input_type=("search_document" if tipo == "documento"
                                else "search_query"),
                    embedding_types=["float"],
                    output_dimension=PROVEEDORES["cohere"]["dim"],
                )
                return [list(v) for v in r.embeddings.float_]

            from google.genai import types
            cfg = types.EmbedContentConfig(
                task_type=("RETRIEVAL_DOCUMENT" if tipo == "documento"
                           else "RETRIEVAL_QUERY"),
                output_dimensionality=PROVEEDORES["gemini"]["dim"])
            r = cli.models.embed_content(
                model=PROVEEDORES["gemini"]["modelo"], contents=textos, config=cfg)
            return [e.values for e in r.embeddings]
        except Exception as e:                          # noqa: BLE001
            msg = str(e)
            if intento == REINTENTOS - 1:
                raise
            # La API dice cuanto esperar cuando es cuota agotada; obedecerlo
            # es mas rapido y mas fiable que adivinar con backoff ciego.
            espera = 5 * (2 ** intento)
            m = re.search(r"retry in ([\d.]+)s", msg, re.IGNORECASE)
            if not m:
                m = re.search(r"'retryDelay': '(\d+)s'", msg)
            if m:
                espera = float(m.group(1)) + 2
            # Tope: el backoff exponencial llegaba a esperas de varios minutos
            # y el proceso parecia colgado. El limite del tier gratuito es por
            # minuto, asi que esperar mas de eso no aporta.
            espera = min(espera, 75)
            print(f"    reintento {intento+1} en {espera:.0f}s "
                  f"({type(e).__name__})", flush=True)
            time.sleep(espera)
    return []


def normalizar(M):
    M = np.asarray(M, dtype="float32")
    n = np.linalg.norm(M, axis=1, keepdims=True)
    n[n == 0] = 1.0
    return M / n


def construir(preferido=None):
    idx = pickle.load(open(IDX, "rb"))
    bloques = idx["bloques"]
    docs = idx["docs"]
    print(f"corpus: {len(bloques)} bloques")

    # Se embebe el titulo del documento + el texto: sin el titulo, un bloque
    # suelto de la pagina 200 de Klaren pierde toda pista de a que obra
    # pertenece, y el vector queda a merced del fragmento concreto.
    textos = []
    for b in bloques:
        d = docs.get(b["doc_id"], {})
        cab = (d.get("cita") or d.get("titulo") or "").replace("_", " ")
        cuerpo = b["texto"][:1800]
        textos.append(f"{cab}\n\n{cuerpo}".strip())

    prov, cli = cliente(preferido)
    lote_n = PROVEEDORES[prov]["lote"]
    print(f"proveedor: {prov} ({PROVEEDORES[prov]['modelo']}), "
          f"lotes de {lote_n} -> ~{-(-len(textos)//lote_n)} peticiones")

    # Reanudar: cada lote cuesta cuota real. Si el proceso muere a mitad, no
    # tiene sentido volver a pagar por lo ya calculado.
    #
    # OJO: el parcial solo se puede reutilizar con el MISMO proveedor. Los
    # vectores de Cohere y de Gemini viven en espacios distintos; mezclarlos
    # produce un indice que parece valido y recupera basura.
    vectores = []
    marca = os.path.join(RAIZ, "corpus", "_embeddings_proveedor.txt")
    prov_previo = None
    if os.path.exists(marca):
        with open(marca, encoding="utf-8") as f:
            prov_previo = f.read().strip()

    if os.path.exists(PARCIAL):
        if prov_previo == prov:
            vectores = list(np.load(PARCIAL))
            print(f"  reanudando: {len(vectores)} bloques ya embebidos")
        else:
            print(f"  el parcial es de '{prov_previo}' y ahora se usa '{prov}':")
            print("  se descarta y se empieza de cero (espacios incompatibles)")
            os.remove(PARCIAL)

    with open(marca, "w", encoding="utf-8") as f:
        f.write(prov)

    t0 = time.time()
    try:
        for i in range(len(vectores), len(textos), lote_n):
            lote = textos[i:i + lote_n]
            vectores.extend(embeber(prov, cli, lote, "documento"))
            np.save(PARCIAL, np.array(vectores, dtype="float32"))

            hechos = len(vectores)
            transcurrido = time.time() - t0
            nuevos = hechos - i
            ritmo = nuevos / transcurrido if transcurrido else 0
            queda = (len(textos) - hechos) / ritmo if ritmo else 0
            print(f"  {hechos}/{len(textos)} bloques  "
                  f"({transcurrido:.0f}s, faltan ~{queda:.0f}s)", flush=True)
            time.sleep(PAUSA)
    except KeyboardInterrupt:
        print(f"\ninterrumpido: {len(vectores)} bloques guardados en el parcial")
        print("vuelve a correr el script para continuar desde ahi")
        return

    M = normalizar(vectores)
    ids = np.array([b["bloque_id"] for b in bloques])
    # Se guarda el proveedor: la consulta DEBE embeberse con el mismo, o las
    # similitudes no significan nada.
    np.savez_compressed(OUT, M=M, ids=ids, dim=PROVEEDORES[prov]["dim"],
                        proveedor=prov, modelo=PROVEEDORES[prov]["modelo"])

    mb = os.path.getsize(OUT) / 1e6
    print(f"\nescrito {OUT}")
    print(f"  {M.shape[0]} vectores x {M.shape[1]} dim   {mb:.1f} MB")
    print(f"  tiempo total: {time.time()-t0:.0f}s")

    for tmp in (PARCIAL, os.path.join(RAIZ, "corpus", "_embeddings_proveedor.txt")):
        if os.path.exists(tmp):
            os.remove(tmp)


def probar():
    if not os.path.exists(OUT):
        print(f"No existe {OUT}. Corre primero sin --probar.")
        return 1
    z = np.load(OUT, allow_pickle=True)
    M, ids = z["M"], z["ids"]
    prov_idx = str(z["proveedor"]) if "proveedor" in z else "gemini"
    print(f"indice: {M.shape[0]} vectores x {M.shape[1]} dim  "
          f"({os.path.getsize(OUT)/1e6:.1f} MB)  proveedor={prov_idx}")

    idx = pickle.load(open(IDX, "rb"))
    pos = {b["bloque_id"]: i for i, b in enumerate(idx["bloques"])}
    prov, cli = cliente(prov_idx)

    CONSULTAS = [
        "¿Cómo afectaron las epidemias coloniales a la población indígena?",
        "¿Qué fue el gobierno de Velasco Alvarado?",
        "¿Cuál es la receta de la pizza margarita?",
        "¿Qué dice Contreras sobre el centralismo?",
    ]
    for q in CONSULTAS:
        v = normalizar(embeber(prov, cli, [q], "consulta"))[0]
        sims = M @ v
        orden = np.argsort(-sims)[:4]
        print(f"\n{q}")
        print(f"   mejor similitud: {sims[orden[0]]:.3f}")
        for j in orden:
            bid = str(ids[j])
            b = idx["bloques"][pos[bid]]
            print(f"     {sims[j]:.3f}  {b['doc_id'][:44]:46s} {b['texto'][:56].strip()!r}")
    return 0


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--probar", action="store_true")
    ap.add_argument("--proveedor", choices=["cohere", "gemini"],
                    help="forzar proveedor (por defecto: cohere si hay clave)")
    a = ap.parse_args()
    sys.exit(probar() if a.probar else (construir(a.proveedor) or 0))
