# -*- coding: utf-8 -*-
"""
Fase C1-C2: induccion de gramatica organizacional.

C1: SEQUITUR / Re-Pair sobre la secuencia de simbolos de firma
orto-tipografica. Se implementa el algoritmo completo (no una
aproximacion), en Python puro, sin dependencia externa -- no existe un
paquete PyPI maduro y mantenido para esto (verificado en la fase de
diseno).

C2: anotacion de reglas con estabilidad posicional, diversidad lexica y
compatibilidad de anidamiento, para distinguir una regla que capta
"header repetido" (diversidad lexica ~0) de una que capta "patron real
de subseccion" (diversidad lexica alta).

Historia de implementacion (documentada porque cada version fallo un
checkpoint real, no es color de fondo):
  v1: mutacion in-place de listas con indices numericos ("descripcion de
      libro de texto" de SEQUITUR online). Fallo el checkpoint C1: la
      reconstruccion no coincidia con la secuencia original -- indices
      desactualizados tras los reemplazos.
  v2: lista enlazada doble (representacion "de referencia" de SEQUITUR
      online, simbolo a simbolo). Reconstruia bien pero comprimia
      suboptimo: no repropagaba correctamente tras cada sustitucion (el
      caso canonico de 3 repeticiones solo detectaba 2).
  v3: pasadas iterativas, UN digrama (el mas frecuente) por pasada.
      Reconstruia y comprimia correctamente, PERO es O(n) pasadas en el
      peor caso -> O(n^2) total. Medido: >2 minutos sin terminar sobre el
      documento real mas grande del corpus (11,421 bloques).
  v4 (actual): Re-Pair por lotes -- en cada pasada se comprimen TODOS los
      digramas empatados en la frecuencia maxima de esa pasada, no solo
      uno. Esto es el algoritmo Re-Pair estandar (Larsson & Moffat 1999),
      reduce el numero de pasadas a O(log n) en la practica, y es la
      variante que de hecho se usa para compresion por gramatica sobre
      secuencias largas -- SEQUITUR online simbolo-a-simbolo es mejor
      para explicar el concepto, Re-Pair por lotes es mejor para volumen.
"""
from dataclasses import dataclass, field


@dataclass
class Regla:
    id: int
    cuerpo: list[int] = field(default_factory=list)  # >=0 terminal, <0 no-terminal (-id de otra Regla)
    usos: int = 0


def _contar_digramas_no_solapados(secuencia: list[int]) -> dict[tuple[int, int], int]:
    """Cuenta ocurrencias de cada digrama consecutivo, saltando la
    segunda posicion de cada ocurrencia contada para no contar
    solapamientos (ej. en [1,1,1] el digrama (1,1) ocurre 1 vez
    no-solapada, no 2)."""
    conteo: dict[tuple[int, int], int] = {}
    i = 0
    n = len(secuencia)
    while i < n - 1:
        d = (secuencia[i], secuencia[i + 1])
        conteo[d] = conteo.get(d, 0) + 1
        i += 2 if d[0] == d[1] else 1
        # nota: el salto de 2 solo evita doble-conteo cuando ambos
        # simbolos del digrama son iguales (caso [1,1,1,1]); en el caso
        # general (digrama con simbolos distintos) SI se permite
        # solapamiento de CONTEO porque una ocurrencia en i y otra en i+1
        # con simbolos distintos consumen posiciones distintas de todas
        # formas al reemplazar -- el reemplazo real (mas abajo) es el que
        # aplica no-solapamiento estricto de izquierda a derecha.
    return conteo


def _comprimir_una_pasada_multi_digrama(
    secuencia: list[int],
    reglas: dict[int, Regla],
    cuerpo_a_id: dict[tuple[int, int], int],
    siguiente_id: int,
) -> tuple[list[int], int, bool]:
    """Una pasada de Re-Pair: comprime TODOS los digramas que empatan en
    la frecuencia maxima de esta pasada, en un solo recorrido de
    izquierda a derecha (greedy, sin solapamiento). Ver docstring del
    modulo para la comparacion de rendimiento contra comprimir un solo
    digrama por pasada."""
    conteo = _contar_digramas_no_solapados(secuencia)
    # Un digrama formado por el MISMO no-terminal repetido dos veces
    # (ej. (-2,-2), producto de 3+ ocurrencias consecutivas de una regla
    # ya comprimida en una pasada previa) no debe comprimirse en una
    # regla nueva: crearia una regla auxiliar degenerada que en la
    # practica solo tiene sentido como "regla de regla" y complica el
    # conteo de usos sin aportar compresion real distinguible.
    repetidos = {d: c for d, c in conteo.items() if c >= 2 and not (d[0] < 0 and d[0] == d[1])}
    if not repetidos:
        return secuencia, siguiente_id, False

    frecuencia_maxima = max(repetidos.values())
    digramas_a_comprimir = {d for d, c in repetidos.items() if c == frecuencia_maxima}

    ids_asignados: dict[tuple[int, int], int] = {}
    for d in digramas_a_comprimir:
        if d in cuerpo_a_id:
            ids_asignados[d] = cuerpo_a_id[d]
        else:
            rid = siguiente_id
            siguiente_id += 1
            a, b = d
            reglas[rid] = Regla(id=rid, cuerpo=[a, b], usos=0)
            cuerpo_a_id[d] = rid
            ids_asignados[d] = rid

    resultado: list[int] = []
    usos_esta_pasada: dict[int, int] = {}
    i, n = 0, len(secuencia)
    while i < n:
        rid = None
        if i < n - 1:
            rid = ids_asignados.get((secuencia[i], secuencia[i + 1]))
        if rid is not None:
            resultado.append(-rid)
            usos_esta_pasada[rid] = usos_esta_pasada.get(rid, 0) + 1
            i += 2
        else:
            resultado.append(secuencia[i])
            i += 1

    for rid, n_usos in usos_esta_pasada.items():
        reglas[rid].usos += n_usos

    # Reglas creadas en esta pasada que terminaron sin ningun uso real
    # (posible si su unica ocurrencia candidata quedo consumida por otro
    # digrama de igual frecuencia procesado antes en el mismo recorrido)
    # se descartan -- nunca debe quedar una Regla con usos=0.
    for d, rid in list(ids_asignados.items()):
        if reglas[rid].usos == 0:
            del reglas[rid]
            del cuerpo_a_id[d]

    return resultado, siguiente_id, True


def inducir_gramatica(simbolos: list[int], max_pasadas: int = 500) -> tuple[dict[int, Regla], list[int]]:
    """Induce una gramatica de digramas repetidos por pasadas Re-Pair
    hasta punto fijo.

    Devuelve (reglas, secuencia_top): `reglas` es {id: Regla}, cada una
    usada >= 2 veces; `secuencia_top` es la secuencia de entrada ya
    reescrita con no-terminales donde aplique.
    """
    secuencia = list(simbolos)
    reglas: dict[int, Regla] = {}
    siguiente_id = 1
    cuerpo_a_id: dict[tuple[int, int], int] = {}

    for _pasada in range(max_pasadas):
        if len(secuencia) < 2:
            break
        secuencia, siguiente_id, hubo_cambio = _comprimir_una_pasada_multi_digrama(
            secuencia, reglas, cuerpo_a_id, siguiente_id
        )
        if not hubo_cambio:
            break

    # Rule utility: cualquier regla que haya quedado con 1 solo uso total
    # se re-expande (inline) -- una regla que solo se usa una vez no
    # comprime nada, es puro overhead de la gramatica.
    cambiado = True
    while cambiado:
        cambiado = False
        for rid in list(reglas.keys()):
            if reglas[rid].usos <= 1:
                cuerpo_regla = reglas[rid].cuerpo
                nueva_secuencia = []
                for s in secuencia:
                    if s == -rid:
                        nueva_secuencia.extend(cuerpo_regla)
                        for v in cuerpo_regla:
                            if v < 0 and -v in reglas:
                                reglas[-v].usos += 1
                    else:
                        nueva_secuencia.append(s)
                secuencia = nueva_secuencia
                del reglas[rid]
                cambiado = True

    return reglas, secuencia


def expandir_regla(cuerpo: list[int], reglas: dict[int, Regla]) -> list[int]:
    """Expande recursivamente una secuencia (top o de una regla) a su
    secuencia completa de terminales -- para debug/verificacion."""
    resultado = []
    for s in cuerpo:
        if s < 0:
            resultado.extend(expandir_regla(reglas[-s].cuerpo, reglas))
        else:
            resultado.append(s)
    return resultado
