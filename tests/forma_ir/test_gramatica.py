# -*- coding: utf-8 -*-
"""
Checkpoint C1: SEQUITUR (induccion de gramatica organizacional).

El caso canonico ("a b c a b c a b c d" -> regla R->a b c usada 3 veces)
es el mismo que aparece en la literatura de referencia de SEQUITUR
(Nevill-Manning & Witten 1997) -- se prueba ANTES de tocar datos reales,
tal como exige el checkpoint del plan.

Nota historica de desarrollo: la primera implementacion (mutacion
in-place con indices numericos, estilo "descripcion de libro de texto")
fallo este mismo test -- la reconstruccion no coincidia con el original
por indices desactualizados tras los reemplazos. Se detecto ANTES de
avanzar a Fase C2, exactamente el proposito de este checkpoint.
"""
from forma_ir.gramatica import inducir_gramatica, expandir_regla


def _reconstruye(secuencia_original):
    reglas, top = inducir_gramatica(secuencia_original)
    return expandir_regla(top, reglas), reglas, top


# --- Caso canonico de la literatura ---

def test_caso_canonico_tres_repeticiones():
    """a b c a b c a b c d -> una regla R->[a,b,c] usada 3 veces + d."""
    original = [1, 2, 3, 1, 2, 3, 1, 2, 3, 4]
    reconstruido, reglas, top = _reconstruye(original)

    assert reconstruido == original

    # Debe existir exactamente una regla que expanda a [1,2,3]
    reglas_que_expanden_a_abc = [
        rid for rid in reglas
        if expandir_regla(reglas[rid].cuerpo, reglas) == [1, 2, 3]
    ]
    assert len(reglas_que_expanden_a_abc) == 1
    id_regla_abc = reglas_que_expanden_a_abc[0]

    # Esa regla debe estar referenciada exactamente 3 veces en el top
    assert top.count(-id_regla_abc) == 3
    assert reglas[id_regla_abc].usos == 3


# --- Reconstruccion exacta en todos los casos, incluyendo bordes ---

def test_secuencia_sin_ninguna_repeticion_no_crea_reglas():
    original = [1, 2, 3, 4, 5]
    reconstruido, reglas, top = _reconstruye(original)
    assert reconstruido == original
    assert reglas == {}
    assert top == original


def test_un_solo_simbolo():
    original = [1]
    reconstruido, reglas, _top = _reconstruye(original)
    assert reconstruido == original
    assert reglas == {}


def test_secuencia_vacia_no_lanza_excepcion():
    reconstruido, reglas, top = _reconstruye([])
    assert reconstruido == []
    assert reglas == {}
    assert top == []


def test_repeticion_simple_de_un_digrama():
    original = [1, 2, 1, 2]
    reconstruido, reglas, top = _reconstruye(original)
    assert reconstruido == original
    assert len(reglas) == 1
    assert top == [-1, -1]


def test_mismo_simbolo_repetido_muchas_veces_no_crea_regla_degenerada():
    """Regresion del bug real encontrado: [-r,-r] tras comprimir una
    regla no debe volver a comprimirse en una regla de un solo uso real
    (eso duplicaba el conteo de usos y era matematicamente incorrecto)."""
    original = [7, 7, 7, 7, 7, 7]
    reconstruido, reglas, _top = _reconstruye(original)
    assert reconstruido == original
    # Debe existir solo la regla de base [7,7] -- no una segunda regla
    # que comprima pares de esa regla entre si.
    assert len(reglas) == 1


def test_dos_patrones_distintos_en_la_misma_secuencia():
    original = [1, 2, 1, 2, 3, 4, 3, 4, 3, 4]
    reconstruido, reglas, _top = _reconstruye(original)
    assert reconstruido == original
    # Debe haber al menos 2 reglas (una por cada patron detectado)
    assert len(reglas) >= 2


def test_reglas_solo_creadas_para_digramas_usados_dos_o_mas_veces():
    """Rule utility: toda regla en el resultado final debe estar usada
    >= 2 veces -- si quedara con 1 uso deberia haberse re-expandido."""
    original = [1, 2, 3, 1, 2, 3, 1, 2, 3, 4, 5, 6]
    _reconstruido, reglas, _top = _reconstruye(original)
    for r in reglas.values():
        assert r.usos >= 2, f"regla {r.id} quedo con solo {r.usos} usos"


def test_expandir_regla_reconstruye_recursivamente_reglas_anidadas():
    """expandir_regla debe poder resolver una regla que a su vez
    referencia a otra regla (no-terminal dentro de no-terminal)."""
    original = [1, 2, 3, 1, 2, 3, 1, 2, 3, 4]
    _reconstruido, reglas, top = _reconstruye(original)
    # al menos una regla debe tener un no-terminal en su cuerpo (regla anidada)
    assert any(any(s < 0 for s in r.cuerpo) for r in reglas.values())
    assert expandir_regla(top, reglas) == original


def test_rendimiento_no_se_degrada_en_secuencia_larga_con_repeticion_moderada():
    """Regresion de rendimiento: la primera implementacion (un digrama
    por pasada) tomaba mas de 2 minutos sin terminar sobre un documento
    real de 11,421 bloques con ~1880 simbolos unicos -- la reescritura a
    Re-Pair por lotes lo resuelve en <1s. Este test usa una secuencia
    sintetica de tamano comparable (no depende de archivos del corpus,
    para que el test siga funcionando aunque el corpus cambie) con un
    limite de tiempo generoso pero real."""
    import random
    import time

    rng = random.Random(42)
    # simula un documento con vocabulario de firma moderado y bastante
    # repeticion, similar en escala a un documento largo real
    alfabeto = list(range(50))
    secuencia = [rng.choice(alfabeto) for _ in range(12000)]

    t0 = time.time()
    reglas, top = inducir_gramatica(secuencia, max_pasadas=200)
    dt = time.time() - t0

    assert expandir_regla(top, reglas) == secuencia
    assert dt < 10.0, f"induccion tardo {dt:.2f}s, se esperaba <10s (regresion de rendimiento)"
