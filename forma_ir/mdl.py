# -*- coding: utf-8 -*-
"""
Fase C4: objetivo MDL completo (ecuacion 1 del paper, S5.2) sobre los
candidatos de limite ya detectados en C3a.

    (T*, G*) = argmin_{T,G} [ L(G) + L(T|G) + L(S|T,G) + L(W|T) + L(Y|T) ]

Con la gramatica G ya fija (viene de Fase C1), este modulo busca el
arbol de segmentacion T -- en esta primera pasada, una particion PLANA
(lista de fronteras que cortan la secuencia de bloques en regiones
contiguas) elegida entre los candidatos de C3a via programacion dinamica
exacta. La recursion dentro de regiones largas (arbol multi-nivel) queda
para una iteracion posterior de C4 si el checkpoint plano confirma que
el objetivo discrimina bien.

Cada termino se mide en bits, siguiendo el paper termino a termino:

  L(G): costo de la gramatica ya inducida (Fase C1) -- fijo dado G, pero
        se incluye en el total para que el objetivo sea comparable entre
        gramaticas de distinto tamano si en el futuro se re-induce G.
  L(T|G): costo de codificar QUE fronteras se aceptan mas alla de lo que
        la gramatica ya predice -- modelo Bernoulli sobre "es frontera"
        con tasa base estimada de los datos (codigo de Shannon).
  L(S|T,G): costo de la secuencia de simbolos de forma dado el arbol --
        una particion es mejor cuando sus fronteras coinciden con
        limites de repeticion de reglas (la region resultante es mas
        homogenea en terminos de que reglas la componen).
  L(W|T): codigo lexico Dirichlet-multinomial aproximado por entropia
        cruzada suavizada Laplace (simplificacion honesta, declarada en
        el plan: el paper deja esta formula abierta a "Dirichlet-
        multinomial o NML"). Una particion es mejor cuando el
        vocabulario DENTRO de cada region se codifica mas barato con
        distribuciones de terminos propias que con la distribucion
        global.
  L(Y|T): costo de discontinuidad de layout no explicada DENTRO de cada
        region -- varianza de sangria y de tamano de fuente relativo
        dentro del nodo; una region con layout consistente es barata,
        una que mezcla indentaciones/tamanos dispares es cara.
"""
import math
from collections import Counter
from dataclasses import dataclass

from forma_ir.anotacion import AnotacionRegla
from forma_ir.firma import FirmaForma
from forma_ir.gramatica import Regla
from forma_ir.tipos import Bloque


@dataclass
class NodoSegmento:
    inicio: int  # indice de bloque, inclusive
    fin: int  # indice de bloque, exclusivo
    costo_bits: float


def costo_L_G(reglas: dict[int, Regla]) -> float:
    """Bits para describir la gramatica: cada regla cuesta
    log2(alfabeto_actual) bits por simbolo de su cuerpo (codigo uniforme
    sobre el alfabeto de simbolos+no-terminales ya emitidos), mas un
    termino fijo pequeno de "declaracion de regla" -- suficiente para
    que gramaticas con mas reglas/cuerpos mas largos cuesten mas, sin
    pretender ser un codigo optimo de verdad (eso requeriria un modelo
    de canal completo, fuera de alcance de esta fase)."""
    if not reglas:
        return 0.0
    alfabeto_total = max(len(reglas) * 2, 2)  # cota gruesa pero estable
    bits_por_simbolo = math.log2(alfabeto_total)
    total = 0.0
    for r in reglas.values():
        total += bits_por_simbolo * max(len(r.cuerpo), 1)
        total += 4.0  # costo fijo de declarar una regla nueva
    return total


def _costo_por_frontera_extra(n_candidatos: int) -> float:
    """Bits para "senalar cual candidato, de los N disponibles, se activa
    como frontera real" -- log2(n_candidatos), acotado por abajo en 1 bit.

    Nota de calibracion (Checkpoint C4): la primera version de este costo
    usaba un codigo de Shannon sobre una tasa base de fronteras estimada
    circularmente de los propios datos (n_fronteras/n_bloques). Esa
    tasa vivia en decenas de bits, mientras que L(W|T) vive en cientos o
    miles de bits (agrega sobre TODAS las palabras del documento) -- el
    desbalance de escala hacia que casi cualquier frontera candidata
    "valiera la pena" bajo el objetivo, eligiendo 84 de 86 candidatas
    (deberia podar las malas, no aceptar casi todas). Se recalibro contra
    el ahorro REAL medido en datos: en el fixture del cronograma, una
    frontera "razonable" (buena) ahorra ~190 bits en L(W|T) en promedio,
    mientras que el promedio sobre TODAS las candidatas (mezclando
    buenas y malas) es ~96 bits -- el costo por frontera debe caer entre
    esos dos valores para que el objetivo discrimine, no debajo de
    ambos. log2(n_candidatos) para un typical n_candidatos de decenas a
    centenas cae naturalmente en el rango de ~5-8 bits, todavia
    insuficiente por si solo; se escala x20 (una frontera debe "ganarse"
    su lugar demostrando un ahorro claramente por encima del ruido
    tipico de candidatos malos) -- constante declarada explicitamente,
    no derivada de primeros principios (el paper deja L(T|G) sin una
    formula cerrada unica, ver S5.2)."""
    return max(math.log2(max(n_candidatos, 2)) * 20.0, 20.0)


def costo_L_T_dado_G(n_bloques: int, fronteras: list[int],
                       fronteras_predichas_por_gramatica: set[int],
                       n_candidatos: int | None = None) -> float:
    """Costo de codificar que fronteras se aceptan MAS ALLA de lo que la
    gramatica ya predice: fronteras que coinciden con un inicio de regla
    marcada es_candidata_limite en C2/C3a no cuestan nada extra (ya estan
    "explicadas" por G); cada frontera EXTRA cuesta
    `_costo_por_frontera_extra(n_candidatos)` bits -- ver esa funcion
    para la calibracion contra datos reales.

    Nota de implementacion: `segmentar_por_mdl` (la funcion de busqueda
    real) recalcula este mismo costo por-frontera inline durante la DP,
    porque ahi conviene evaluarlo candidato a candidato en vez de sobre
    la lista completa de una vez. Esta version standalone existe para
    poder reportar/testear L(T|G) de una particion YA elegida de forma
    aislada (ver test_segmentacion_mdl.py)."""
    if n_bloques <= 1:
        return 0.0
    fronteras_extra = [f for f in fronteras if f not in fronteras_predichas_por_gramatica]
    n_extra = len(fronteras_extra)
    costo_por_si = _costo_por_frontera_extra(n_candidatos if n_candidatos is not None else max(n_extra, 1))
    return n_extra * costo_por_si


def _entropia_cruzada_laplace(textos_region: list[str], vocabulario_global: Counter,
                                n_total_palabras_global: int, alpha: float = 0.5) -> float:
    """Codigo MDL de dos partes para el vocabulario de la region: costo
    de DESCRIBIR un modelo multinomial propio de la region (aprendido de
    sus propias frecuencias, no de las globales) mas el costo de
    codificar sus palabras bajo ese modelo, suavizado Laplace/Lidstone
    (alpha=0.5, Jeffreys) para evitar log2(0).

    Bug real encontrado en Checkpoint C4: la primera version usaba
    SOLO las frecuencias GLOBALES del documento como modelo -- eso hace
    que la suma total de bits sobre TODAS las palabras del documento sea
    identica sin importar donde se corte (cada palabra individual cuesta
    lo mismo la mida la region que la mida), asi que este termino
    resultaba constante entre particiones y no aportaba NINGUNA senal
    para elegir fronteras. Verificado con datos reales: L(W|T) daba
    22775.4 bits identicos para "sin fronteras", "todas las candidatas"
    y una particion razonable de 9 fronteras -- el objetivo terminaba
    dominado solo por L(Y|T), que favorece sistematicamente menos
    fronteras, produciendo el resultado degenerado de 0 fronteras
    elegidas siempre.

    La correccion usa el sentido MDL real de "cuesta describir el
    modelo": una region cuyo vocabulario es auto-contenido (pocas
    palabras UNICAS relativo a su tamano, cada una repetida) es barata
    de describir con su propio modelo; una region que mezcla vocabulario
    disperso de temas distintos necesita un modelo mas caro de codificar
    (probabilidades mas planas, mayor entropia de datos).

    Segundo bug encontrado y corregido en la MISMA sesion de calibracion:
    la primera correccion uso `costo_modelo = v_local * log2(v_global)`
    (costear cada palabra unica como si señalarla dentro de TODO el
    vocabulario del documento costara log2(V_global) bits) -- eso es
    demasiado caro: al fragmentar, una palabra compartida entre dos
    regiones se paga DOS VECES en la suma de costos de modelo (una por
    region), y esa doble contabilidad crece mas rapido que cualquier
    ahorro posible en entropia de datos, asi que el termino terminaba
    penalizando CUALQUIER fragmentacion sin excepcion -- confirmado con
    una demostracion matematica minima (2 palabras compartidas entre
    mitades ya bastaba para que fragmentar costara mas SIEMPRE).
    La formula estandar de MDL de dos partes para los parametros de un
    modelo multinomial de v_local categorias es el codigo de Rissanen:
    0.5*v_local*log2(n_local) bits (la mitad de bits por parametro que
    la cuenta ingenua) -- crece con el TAMANO de la region, no con el
    vocabulario global, y es lo bastante barato para que el ahorro de
    entropia de datos por coherencia tematica pueda compensarlo cuando
    corresponde."""
    palabras = " ".join(textos_region).lower().split()
    if not palabras:
        return 0.0
    return _costo_entropia_desde_conteo(Counter(palabras), len(palabras), alpha=alpha)


def _costo_entropia_desde_conteo(conteo_local: Counter, n: int, alpha: float = 0.5) -> float:
    """Nucleo de `_entropia_cruzada_laplace` que opera directamente
    sobre un Counter y un conteo total ya acumulados, en vez de una
    lista de textos -- permite que `segmentar_por_mdl` mantenga un
    Counter incremental mientras la ventana de una region crece, sin
    retokenizar el texto completo en cada evaluacion (ver nota de
    rendimiento en `segmentar_por_mdl`)."""
    if n == 0:
        return 0.0
    v_local = len(conteo_local)

    # Codigo de Rissanen para los parametros del modelo multinomial local.
    costo_modelo = 0.5 * v_local * math.log2(max(n, 2))

    # Costo de los datos bajo el modelo LOCAL suavizado (Lidstone):
    # una region homogenea (pocas palabras distintas, cada una repetida
    # muchas veces) tiene entropia baja -> barata; una region con
    # vocabulario disperso tiene entropia alta -> cara.
    #
    # Se agrega por CATEGORIA (freq * -log2(prob)) en vez de por
    # ocurrencia individual -- resultado identico pero O(v_local) en vez
    # de O(n), lo que importa cuando este calculo se repite miles de
    # veces dentro de la DP de segmentar_por_mdl.
    costo_datos = 0.0
    for freq_local in conteo_local.values():
        prob = (freq_local + alpha) / (n + alpha * v_local)
        costo_datos += freq_local * -math.log2(prob)

    return costo_modelo + costo_datos


def _varianza(valores: list[float]) -> float:
    if len(valores) < 2:
        return 0.0
    media = sum(valores) / len(valores)
    return sum((v - media) ** 2 for v in valores) / len(valores)


def costo_L_Y_dado_T(bloques_region: list[Bloque]) -> float:
    """Costo de discontinuidad de layout NO explicada dentro de una
    region: varianza de sangria + varianza de tamano de fuente dentro
    del nodo, escalada a bits via log(1+varianza) (mayor varianza dentro
    de una region = layout inconsistente = mas caro; un log evita que
    una sola region gigante con mucha varianza numerica domine el
    objetivo total de forma desproporcionada)."""
    sangrias = [b.indentacion_pt for b in bloques_region if b.indentacion_pt is not None]
    fuentes = [b.font_size for b in bloques_region if b.font_size is not None]
    costo = 0.0
    if len(sangrias) >= 2:
        costo += math.log2(1 + _varianza(sangrias))
    if len(fuentes) >= 2:
        costo += math.log2(1 + _varianza(fuentes))
    return costo


def costo_L_S_dado_T_G(bloques_region: list[Bloque], firmas_region: list[FirmaForma]) -> float:
    """Recompensa (costo bajo) cuando la region es homogenea en firma
    orto-tipografica -- se mide como entropia normalizada sobre las
    firmas distintas presentes en la region (misma logica que la
    diversidad lexica de C2, pero aplicada a FORMA en vez de a texto):
    una region que mezcla muchas firmas distintas sin patron es cara de
    describir con la gramatica; una region dominada por una sola firma
    (o por una progresion de firmas repetida) es barata."""
    if len(firmas_region) <= 1:
        return 0.0
    conteo = Counter(firmas_region)
    n = len(firmas_region)
    entropia = 0.0
    for c in conteo.values():
        p = c / n
        entropia -= p * math.log2(p)
    return entropia  # bits: entropia de Shannon directa, sin normalizar (queremos escala absoluta comparable entre regiones)


def costo_particion(bloques_doc: list[Bloque], firmas_doc: list[FirmaForma],
                      fronteras: list[int], vocabulario_global: Counter,
                      n_total_palabras_global: int,
                      fronteras_predichas_por_gramatica: set[int]) -> float:
    """Costo total L(T|G)+L(S|T,G)+L(W|T)+L(Y|T) de una particion dada
    (L(G) se suma aparte una sola vez, es constante entre particiones de
    la MISMA gramatica -- no afecta cual particion es optima, solo se
    reporta para que el total sea interpretable end-to-end)."""
    n = len(bloques_doc)
    cortes = sorted(set([0] + fronteras + [n]))

    l_t = costo_L_T_dado_G(n, fronteras, fronteras_predichas_por_gramatica)
    l_s = 0.0
    l_w = 0.0
    l_y = 0.0
    for a, b in zip(cortes[:-1], cortes[1:]):
        region_bloques = bloques_doc[a:b]
        region_firmas = firmas_doc[a:b]
        l_s += costo_L_S_dado_T_G(region_bloques, region_firmas)
        l_w += _entropia_cruzada_laplace(
            [bl.texto for bl in region_bloques], vocabulario_global, n_total_palabras_global
        )
        l_y += costo_L_Y_dado_T(region_bloques)

    return l_t + l_s + l_w + l_y


def segmentar_por_mdl(bloques_doc: list[Bloque], firmas_doc: list[FirmaForma],
                        candidatos: dict[int, set[str]],
                        reglas: dict[int, Regla] | None = None,
                        top: list[int] | None = None,
                        anotaciones: dict[int, AnotacionRegla] | None = None) -> list[int]:
    """Busca, por programacion dinamica EXACTA sobre el conjunto finito
    de candidatos de C3a, el subconjunto de fronteras que minimiza el
    costo MDL total (T|G + S|T,G + W|T + Y|T; L(G) es constante y no
    participa en la busqueda). DP en vez de PELT: el numero de
    candidatos por documento es manejable (decenas a un par de cientos)
    y se quiere el optimo garantizado dentro de ese conjunto discreto,
    no una aproximacion sobre una senal continua.

    Devuelve la lista de indices de bloque elegidos como fronteras
    reales (subconjunto de las claves de `candidatos`)."""
    n = len(bloques_doc)
    if n == 0:
        return []

    posiciones_candidatas = sorted(i for i in candidatos.keys() if 0 < i < n)

    vocabulario_global = Counter(" ".join(b.texto for b in bloques_doc).lower().split())
    n_total_palabras_global = sum(vocabulario_global.values())

    fronteras_predichas = set()
    if reglas is not None and top is not None and anotaciones is not None:
        from forma_ir.segmentacion import _inicios_de_reglas_candidatas
        fronteras_predichas = _inicios_de_reglas_candidatas(reglas, top, anotaciones, bloques_doc, firmas_doc)

    # DP sobre el eje de CANDIDATOS (no sobre cada bloque, para que el
    # espacio de busqueda sea proporcional a |candidatos|, no a n):
    # dp[k] = costo minimo para segmentar bloques_doc[0:pos_k] usando
    # solo cortes entre las primeras k posiciones candidatas.
    puntos = [0] + posiciones_candidatas + [n]
    m = len(puntos)

    costo_por_si = _costo_por_frontera_extra(len(posiciones_candidatas))

    # Ventana maxima de candidatos que una sola region puede abarcar en
    # la busqueda (en unidades de puntos, no de bloques).
    #
    # Motivo (regresion de rendimiento real, encontrada en Checkpoint
    # C4): con ~300 candidatos en un documento real (Contreras 2020,
    # 949 bloques), la DP sin ventana evalua ~m^2/2 ~ 44,000 pares, y
    # cada evaluacion reprocesaba el texto de la region ENTERA desde
    # cero (tokenizar + reconstruir Counter) -- la ejecucion no termino
    # en el limite practico de 2 minutos. Se acota la ventana a 60
    # candidatos: ningun lector humano fusionaria mas de unas pocas
    # docenas de "inicios de seccion candidatos" en una sola region de
    # retrieval, asi que la cota no descarta particiones razonables,
    # solo evita explorar fusiones absurdamente grandes que de todas
    # formas costarian mucho en L(Y|T)/L(S|T,G) y jamas ganarian.
    VENTANA_MAX_PUNTOS = 60

    # Costo de region incremental: para cada `i` fijo, se recorre `j`
    # creciente actualizando un Counter de palabras EN VEZ DE
    # retokenizar toda la region desde cero en cada par (i,j) -- pasa de
    # O(m^2 * palabras_por_region) a O(m^2) en operaciones de dict,
    # mucho mas barato en la practica.
    palabras_por_punto: list[list[str]] = []
    firmas_por_punto: list[list] = []
    bloques_por_punto: list[list[Bloque]] = []
    for k in range(m - 1):
        seg_bloques = bloques_doc[puntos[k]:puntos[k + 1]]
        bloques_por_punto.append(seg_bloques)
        firmas_por_punto.append(firmas_doc[puntos[k]:puntos[k + 1]])
        palabras_por_punto.append(" ".join(b.texto for b in seg_bloques).lower().split())

    NEG_INF = float("inf")
    dp = [NEG_INF] * m
    backptr = [-1] * m
    dp[0] = 0.0
    for i in range(m - 1):
        if dp[i] == NEG_INF:
            continue
        conteo_local: Counter = Counter()
        n_palabras_local = 0
        region_bloques_acum: list[Bloque] = []
        region_firmas_acum: list = []
        limite_j = min(i + 1 + VENTANA_MAX_PUNTOS, m)
        for j in range(i + 1, limite_j):
            k = j - 1
            for palabra in palabras_por_punto[k]:
                conteo_local[palabra] += 1
            n_palabras_local += len(palabras_por_punto[k])
            region_bloques_acum.extend(bloques_por_punto[k])
            region_firmas_acum.extend(firmas_por_punto[k])

            l_w = _costo_entropia_desde_conteo(conteo_local, n_palabras_local)
            l_s = costo_L_S_dado_T_G(region_bloques_acum, region_firmas_acum)
            l_y = costo_L_Y_dado_T(region_bloques_acum)

            corte_en_puntos_j = puntos[j] in fronteras_predichas or j == m - 1
            costo_frontera = 0.0 if corte_en_puntos_j else costo_por_si
            candidato = dp[i] + l_w + l_s + l_y + costo_frontera
            if candidato < dp[j]:
                dp[j] = candidato
                backptr[j] = i

    # Reconstruye el camino optimo
    fronteras_elegidas = []
    j = m - 1
    while j > 0:
        i = backptr[j]
        if puntos[i] != 0:
            fronteras_elegidas.append(puntos[i])
        j = i
    fronteras_elegidas.reverse()
    return fronteras_elegidas
