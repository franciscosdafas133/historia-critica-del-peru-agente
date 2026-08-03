# -*- coding: utf-8 -*-
"""
Checkpoint C4: objetivo MDL completo (ecuacion 1 del paper, S5.2).

Sobre el fixture real del cronograma (8 paginas, estructura clara de
"Semana" / sub-temas numerados / header de pagina repetido), se calculan
tres particiones candidatas -- correcta, sobre-segmentada (todas las
candidatas de C3a activadas), sub-segmentada (ninguna frontera, un solo
bloque gigante) -- y se verifica que costo_particion asigna menor costo
a la correcta, tal como exige el checkpoint del plan.

Historia de calibracion (documentada porque cada version fallo un
checkpoint real, mismo patron que gramatica.py/anotacion.py):
  v1: L(W|T) usaba SOLO frecuencias globales del documento como modelo
      -- la suma total de bits sobre TODAS las palabras del documento
      resulta identica sin importar donde se corte (constante entre
      particiones), asi que el termino no aportaba ninguna senal.
      El objetivo terminaba dominado por L(Y|T), que favorece menos
      fronteras siempre -> el optimo colapsaba a 0 fronteras.
  v2: se corrigio L(W|T) a un codigo MDL de dos partes con modelo LOCAL
      por region, pero el costo de "declarar el modelo"
      (v_local * log2(v_global)) resulto matematicamente incapaz de
      compensarse: una palabra compartida entre dos regiones se paga
      DOS VECES al fragmentar, asi que fragmentar SIEMPRE constaba mas
      en ese termino sin excepcion (demostrado con una cuenta minima de
      2 palabras). Se reemplazo por el codigo de Rissanen estandar
      (0.5*v_local*log2(n_local)), que crece con el TAMANO de la region
      en vez de con el vocabulario global.
  v3 (actual): con L(W|T) ya corregido, aparecio un problema de ESCALA:
      L(W|T) vive naturalmente en miles de bits (agrega sobre cada
      palabra del documento) mientras L(T|G) con un codigo de Shannon
      sobre tasa base circular vivia en decenas de bits -- casi
      cualquier frontera candidata "pagaba su costo" y el optimo elegia
      84 de 86 candidatas (deberia podar las malas). Se recalibro el
      costo por frontera extra contra el ahorro promedio medido en
      datos reales (una frontera buena ahorra ~190 bits en L(W|T); el
      promedio sobre TODAS las candidatas, mezclando buenas y malas, es
      ~96 bits) -- el costo por frontera debe caer entre esos dos
      valores para que el objetivo discrimine.
"""
import os

from forma_ir.ingesta import extraer_pdf
from forma_ir.firma import secuencia_de_firmas
from forma_ir.gramatica import inducir_gramatica
from forma_ir.anotacion import anotar_reglas
from forma_ir.segmentacion import candidatos_limite, _inicios_de_reglas_candidatas
from forma_ir.mdl import (
    costo_particion,
    segmentar_por_mdl,
    costo_L_S_dado_T_G,
    costo_L_Y_dado_T,
    _entropia_cruzada_laplace,
    _costo_por_frontera_extra,
)
from collections import Counter

RAIZ = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
FIXTURE_CRONOGRAMA = os.path.join(RAIZ, "tests", "forma_ir", "fixtures", "cronograma_fixture.pdf")

# Particion "razonable" construida a mano inspeccionando el fixture:
# inicios reales de "Semana" y de sub-temas numerados dentro de las
# primeras 2 semanas del cronograma (ver texto de cada indice abajo).
_FRONTERAS_RAZONABLES = [0, 3, 11, 19, 36, 53, 62, 65, 82]


def _preparar(bloques):
    firmas = secuencia_de_firmas(bloques)
    alfabeto, simbolos = {}, []
    for f in firmas:
        if f not in alfabeto:
            alfabeto[f] = len(alfabeto)
        simbolos.append(alfabeto[f])
    reglas, top = inducir_gramatica(simbolos)
    anotaciones = anotar_reglas(reglas, top, bloques)
    candidatos = candidatos_limite(bloques, reglas, top, anotaciones, firmas_doc=firmas)
    return firmas, reglas, top, anotaciones, candidatos


def test_particion_razonable_cuesta_menos_que_sobre_segmentada():
    """Activar TODAS las candidatas de C3a (86 en este fixture, muchas
    de ellas ruido de puntuacion/pie de pagina) debe costar mas que la
    particion razonable de 9 fronteras que capturan Semana/sub-temas
    reales."""
    bloques = extraer_pdf(FIXTURE_CRONOGRAMA, "cronograma-test")
    firmas, reglas, top, anotaciones, candidatos = _preparar(bloques)
    fronteras_predichas = _inicios_de_reglas_candidatas(reglas, top, anotaciones, bloques, firmas)
    vocab = Counter(" ".join(b.texto for b in bloques).lower().split())
    n_total = sum(vocab.values())

    costo_razonable = costo_particion(bloques, firmas, _FRONTERAS_RAZONABLES, vocab, n_total, fronteras_predichas)
    costo_sobre_segmentada = costo_particion(bloques, firmas, sorted(candidatos.keys()), vocab, n_total, fronteras_predichas)

    assert costo_razonable < costo_sobre_segmentada


def test_particion_razonable_cuesta_menos_que_sub_segmentada():
    """Ninguna frontera (todo el documento como un solo bloque) pierde
    toda la homogeneidad de forma/layout por region que S5.2 recompensa
    -- debe costar mas que reconocer los cortes reales de Semana."""
    bloques = extraer_pdf(FIXTURE_CRONOGRAMA, "cronograma-test")
    firmas, reglas, top, anotaciones, candidatos = _preparar(bloques)
    fronteras_predichas = _inicios_de_reglas_candidatas(reglas, top, anotaciones, bloques, firmas)
    vocab = Counter(" ".join(b.texto for b in bloques).lower().split())
    n_total = sum(vocab.values())

    costo_razonable = costo_particion(bloques, firmas, _FRONTERAS_RAZONABLES, vocab, n_total, fronteras_predichas)
    costo_sub_segmentada = costo_particion(bloques, firmas, [], vocab, n_total, fronteras_predichas)

    assert costo_razonable < costo_sub_segmentada


def test_busqueda_dp_no_colapsa_a_cero_fronteras():
    """Regresion del bug v1: la busqueda por DP no debe colapsar
    sistematicamente a 'sin fronteras' -- debe elegir un numero de
    fronteras estrictamente positivo en un documento con estructura
    real y candidatos disponibles."""
    bloques = extraer_pdf(FIXTURE_CRONOGRAMA, "cronograma-test")
    firmas, reglas, top, anotaciones, candidatos = _preparar(bloques)
    fronteras = segmentar_por_mdl(bloques, firmas, candidatos, reglas, top, anotaciones)
    assert len(fronteras) > 0


def test_busqueda_dp_no_acepta_casi_todas_las_candidatas():
    """Regresion del bug v2/v3: la busqueda por DP no debe colapsar al
    otro extremo (aceptar casi todas las candidatas sin podar) -- debe
    quedarse estrictamente por debajo de la mitad del total de
    candidatos disponibles en este fixture."""
    bloques = extraer_pdf(FIXTURE_CRONOGRAMA, "cronograma-test")
    firmas, reglas, top, anotaciones, candidatos = _preparar(bloques)
    fronteras = segmentar_por_mdl(bloques, firmas, candidatos, reglas, top, anotaciones)
    assert len(fronteras) < len(candidatos) * 0.5


def test_fronteras_elegidas_por_dp_caen_dentro_de_los_candidatos():
    bloques = extraer_pdf(FIXTURE_CRONOGRAMA, "cronograma-test")
    firmas, reglas, top, anotaciones, candidatos = _preparar(bloques)
    fronteras = segmentar_por_mdl(bloques, firmas, candidatos, reglas, top, anotaciones)
    assert set(fronteras).issubset(set(candidatos.keys()))


# --- Terminos individuales, casos calculables a mano ---

def test_costo_L_S_region_homogenea_es_cero():
    """Una region con una sola firma repetida (misma forma en todos los
    bloques) tiene entropia de Shannon 0 -- costo cero."""
    from forma_ir.firma import FirmaForma
    firma_x = FirmaForma(1, 1, 1, False, False, False, "normal", None, "", 0, 0, 0)
    assert costo_L_S_dado_T_G([], [firma_x] * 5) == 0.0


def test_costo_L_S_region_mixta_es_mayor_que_cero():
    from forma_ir.firma import FirmaForma
    firma_a = FirmaForma(1, 1, 1, False, False, False, "normal", None, "", 0, 0, 0)
    firma_b = FirmaForma(2, 2, 2, True, False, False, "Titulo", ".", "", 0, 0, 1)
    assert costo_L_S_dado_T_G([], [firma_a, firma_b, firma_a, firma_b]) > 0.0


def test_entropia_cruzada_region_vacia_es_cero():
    assert _entropia_cruzada_laplace([], Counter(), 0) == 0.0


def test_entropia_cruzada_region_repetitiva_es_mas_barata_que_dispersa():
    """A igual cantidad de palabras, una region que repite las mismas
    pocas palabras debe costar menos bits que una con vocabulario todo
    distinto -- es el mecanismo central por el que L(W|T) premia
    coherencia tematica dentro de una region."""
    repetitiva = ["gato", "gato", "gato", "gato", "gato", "gato"]
    dispersa = ["gato", "perro", "casa", "arbol", "cielo", "mar"]
    vocab_vacio = Counter()
    costo_rep = _entropia_cruzada_laplace(repetitiva, vocab_vacio, 0)
    costo_disp = _entropia_cruzada_laplace(dispersa, vocab_vacio, 0)
    assert costo_rep < costo_disp


def test_costo_por_frontera_extra_crece_con_mas_candidatos():
    """log2(n_candidatos) creciente -> mas candidatos disponibles hace
    mas caro (en bits) senalar cual se activa, como corresponde a un
    codigo que distingue entre mas alternativas."""
    assert _costo_por_frontera_extra(10) < _costo_por_frontera_extra(1000)


def test_rendimiento_no_se_degrada_en_documento_real_grande():
    """Regresion de rendimiento: la primera implementacion de
    segmentar_por_mdl (DP sin ventana, costo_region recalculado desde
    cero por par) no termino en el limite practico de 2 minutos sobre
    Contreras 2020 (949 bloques, 294 candidatos de C3a) -- la
    reescritura con ventana acotada + Counter incremental lo resuelve en
    ~6s. Este test usa el mismo fixture real (no uno sintetico) porque
    el problema original era especifico a la distribucion real de
    candidatos de un documento denso, dificil de replicar sinteticamente
    sin reconstruir todo el pipeline C3a."""
    import time

    bloques = extraer_pdf(os.path.join(RAIZ, "tests", "forma_ir", "fixtures", "contreras_fixture.pdf"), "contreras-test")
    firmas, reglas, top, anotaciones, candidatos = _preparar(bloques)

    t0 = time.time()
    fronteras = segmentar_por_mdl(bloques, firmas, candidatos, reglas, top, anotaciones)
    dt = time.time() - t0

    assert dt < 30.0, f"segmentacion MDL tardo {dt:.2f}s, se esperaba <30s (regresion de rendimiento)"
    assert len(fronteras) > 0
    assert len(fronteras) < len(candidatos)
