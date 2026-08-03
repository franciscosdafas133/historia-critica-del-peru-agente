# -*- coding: utf-8 -*-
"""
Checkpoint F: calibracion de nulo dividido (paper, S5.5) -- la fase de
mayor riesgo estadistico del plan.

Casos de juguete calculables a mano para rango marginal, estadistica de
cuello de botella y p-valor empirico (formulas 5a-5c), mas un test de
aislamiento explicito que verifica que evaluar consultas de test NUNCA
modifica el reservorio de nulo (la salvaguarda contra fuga de datos que
el paper exige explicitamente en S5.5).

Hallazgo real de calibracion (sanity-check con las 2906 unidades del
corpus real, familia 7 = 199 unidades): con candidatas elegidas
PURAMENTE al azar dentro de la familia (sin ningun emparejamiento),
65-98% de los vectores accidentales resultaban en b=c=x=0.0 exactos --
esperable dado un vocabulario de familia disperso (8029 palabras unicas
en 199 unidades), pero eso colapsaba la resolucion del rango marginal:
el histograma de T_c en la propia calibracion quedaba concentrado en un
solo bin en vez de aproximar uniforme, y el histograma de p-valores de
consultas de test independientes salia fuertemente sesgado (media 0.80,
91% de masa en el bin [0.9,1.0]) en vez de aproximar uniforme en [0,1].
Se corrigio `construir_reservorio_nulo` para elegir candidatas
EMPAREJADAS por vocabulario compartido con la pseudo-query (via un
indice invertido termino->unidades), consistente con la especificacion
del paper ("matched to the real query's term count and IDF quantiles").
Tras la correccion, sobre 500 consultas de test generadas con el MISMO
mecanismo de emparejamiento (critico: deben usar el mismo mecanismo en
ambos lados para ser comparables), la media de p-valores bajo a 0.549
y el histograma aproximo razonablemente uniforme en los primeros 9 de
10 bins (40-56 cada uno vs ~50 esperado), con una cola moderada en
[0.9,1.0] atribuible a empates en el rango maximo -- artefacto conocido
de tests de rango sobre datos discretos, no evidencia de fuga o diseno
incorrecto.
"""
import hashlib

from forma_ir.calibracion import (
    ReservorioNulo,
    construir_reservorio_nulo,
    estadistica_cuello_de_botella,
    p_valor_calibrado,
    rango_marginal,
    verificar_aislamiento_reservorio,
)
from forma_ir.evidencia import VectorEvidencia, calcular_idf, tokenizar
from forma_ir.firma import secuencia_de_firmas
from forma_ir.tipos import Bloque, UnidadRetenida


def _bloque(texto: str, seq: int, doc_id: str = "doc") -> Bloque:
    return Bloque(
        bloque_id=f"{doc_id}#{seq}", doc_id=doc_id, seq=seq, texto=texto,
        pagina=1, diapositiva=None, bbox=(0.0, 0.0, 100.0, 10.0),
        font_size=10.0, bold=None, italic=None,
        indentacion_pt=0.0, espacio_vertical_antes=None, formato_fuente="pdf",
    )


# --- Rango marginal (formula 5a), caso calculable a mano ---

def test_rango_marginal_valor_minimo_da_rango_bajo():
    # R_c = [1, 2, 3, 4, 5] (coordenada 0). r_k=0 -> nadie es <= 0.
    # z = (1+0)/(5+1) = 1/6
    referencia = [(1.0,), (2.0,), (3.0,), (4.0,), (5.0,)]
    z = rango_marginal(0.0, 0, referencia)
    assert abs(z - 1 / 6) < 1e-9


def test_rango_marginal_valor_maximo_da_rango_alto():
    # r_k=10 -> los 5 son <= 10. z = (1+5)/(5+1) = 1.0
    referencia = [(1.0,), (2.0,), (3.0,), (4.0,), (5.0,)]
    z = rango_marginal(10.0, 0, referencia)
    assert z == 1.0


def test_rango_marginal_valor_intermedio_calculado_a_mano():
    # r_k=3 -> {1,2,3} son <=3 -> 3 elementos. z = (1+3)/(5+1) = 4/6 = 0.6667
    referencia = [(1.0,), (2.0,), (3.0,), (4.0,), (5.0,)]
    z = rango_marginal(3.0, 0, referencia)
    assert abs(z - 4 / 6) < 1e-9


def test_rango_marginal_referencia_vacia_da_punto_medio():
    assert rango_marginal(5.0, 0, []) == 0.5


# --- Cuello de botella (formula 5b), caso calculable a mano ---

def test_cuello_de_botella_es_el_minimo_de_los_rangos():
    # Vector con 2 coordenadas: una con rango alto, otra con rango bajo.
    # Coordenada 0: r=10 (todos <=10) -> z0=1.0
    # Coordenada 1: r=0 (nadie <=0) -> z1 = 1/6
    referencia = [(1.0, 1.0), (2.0, 2.0), (3.0, 3.0), (4.0, 4.0), (5.0, 5.0)]
    t = estadistica_cuello_de_botella((10.0, 0.0), referencia)
    assert abs(t - 1 / 6) < 1e-9  # domina la coordenada mas debil


def test_cuello_de_botella_no_se_deja_compensar_por_coordenada_fuerte():
    """Regresion conceptual: una suma ponderada dejaria que una
    coordenada extrema compense a una debil; el minimo NO debe hacerlo
    -- verificado comparando dos vectores con la MISMA suma pero
    distinta distribucion."""
    referencia = [(1.0, 1.0), (2.0, 2.0), (3.0, 3.0), (4.0, 4.0), (5.0, 5.0)]
    # vector A: ambas coordenadas medias (3,3) -> z=(4/6, 4/6) -> min=4/6
    t_a = estadistica_cuello_de_botella((3.0, 3.0), referencia)
    # vector B: una coordenada muy alta (10) y otra muy baja (0) -> min=1/6
    t_b = estadistica_cuello_de_botella((10.0, 0.0), referencia)
    assert t_a > t_b  # A domina pese a que la "suma" de evidencia B tambien es alta (10+0=10 > 3+3=6)


# --- P-valor empirico (formula 5c), caso calculable a mano ---

def test_p_valor_calibrado_caso_de_4_coordenadas_calculado_a_mano():
    # referencia: 5 puntos identicos en las 4 coordenadas -> z_k(r) = mismo calculo para cualquier k
    referencia = [(1.0, 1.0, 1.0, 1.0), (2.0, 2.0, 2.0, 2.0), (3.0, 3.0, 3.0, 3.0),
                  (4.0, 4.0, 4.0, 4.0), (5.0, 5.0, 5.0, 5.0)]
    # candidata con las 4 coordenadas en 10.0 -> z_k=1.0 para las 4 -> T=1.0 (maximo posible)
    vector_evidencia = VectorEvidencia(unidad_id="cand", b=10.0, c=10.0, x=10.0, a=10.0)

    # calibracion: 3 vectores con T_c claramente MENOR que 1.0 (T=1/6 cada uno,
    # todas sus coordenadas en 0.0) y 1 vector tambien con T=1.0 (empatado, todas en 10.0)
    calibracion = [(0.0, 0.0, 0.0, 0.0), (0.0, 0.0, 0.0, 0.0), (0.0, 0.0, 0.0, 0.0), (10.0, 10.0, 10.0, 10.0)]
    reservorio = ReservorioNulo(familia_id=0, referencia=referencia, calibracion=calibracion)

    # T de la candidata = 1.0. En calibracion: 3 vectores con T=1/6 (< 1.0, no cuentan)
    # y 1 vector con T=1.0 (empatado, >= 1.0, SI cuenta).
    # p = (1 + 1) / (4 + 1) = 2/5 = 0.4
    p = p_valor_calibrado(vector_evidencia, reservorio)
    assert abs(p - 0.4) < 1e-9


def test_p_valor_esta_acotado_en_cero_uno():
    referencia = [(float(i),) * 4 for i in range(1, 11)]
    calibracion = [(float(i),) * 4 for i in range(1, 21)]
    reservorio = ReservorioNulo(familia_id=0, referencia=referencia, calibracion=calibracion)
    for val in [0.0, 5.0, 100.0]:
        vector = VectorEvidencia(unidad_id="x", b=val, c=val, x=val, a=val)
        p = p_valor_calibrado(vector, reservorio)
        assert 0.0 < p <= 1.0


# --- Aislamiento del reservorio: la salvaguarda anti-fuga central ---

def test_reservorio_no_cambia_tras_evaluar_muchas_consultas_de_test():
    """La salvaguarda mas importante del checkpoint F: evaluar consultas
    de TEST reales (p_valor_calibrado, score_final) nunca debe mutar
    R_c/C_c -- se congelan una vez en construir_reservorio_nulo y de ahi
    en adelante solo se LEEN."""
    referencia = [(1.0, 1.0, 1.0, 1.0), (2.0, 2.0, 2.0, 2.0), (3.0, 3.0, 3.0, 3.0)]
    calibracion = [(1.5, 1.5, 1.5, 1.5), (2.5, 2.5, 2.5, 2.5)]
    reservorio = ReservorioNulo(familia_id=0, referencia=referencia, calibracion=calibracion)

    hash_antes = reservorio.hash_estado()
    for i in range(50):
        vector = VectorEvidencia(unidad_id=f"q{i}", b=float(i), c=float(i), x=float(i), a=float(i))
        p_valor_calibrado(vector, reservorio)

    assert verificar_aislamiento_reservorio(reservorio, hash_antes) is True


def test_construir_reservorio_nulo_es_document_disjoint():
    """Regresion de la salvaguarda de fuga de datos #1: ninguna
    pseudo-query generada desde una unidad semilla de un documento debe
    puntuarse contra una candidata del MISMO documento."""
    # 2 documentos, cada uno con varias unidades en la misma familia --
    # con un corpus de 1 solo documento por familia, construir_reservorio_nulo
    # debe devolver None (no hay candidatas document-disjoint posibles).
    bloques_doc_a = [_bloque(f"palabra{i} texto de prueba uno", i, doc_id="doc-a") for i in range(5)]
    unidades_doc_a = [
        UnidadRetenida(unidad_id=f"doc-a#u{i}", doc_id="doc-a", indices_bloque=[i],
                        texto=bloques_doc_a[i].texto, pagina_inicio=1, pagina_fin=1)
        for i in range(5)
    ]
    idf = calcular_idf([tokenizar(b.texto) for b in bloques_doc_a])
    firmas_doc_a = secuencia_de_firmas(bloques_doc_a)

    # Todas las unidades son del MISMO documento -> ninguna pseudo-query
    # tiene una candidata document-disjoint valida -> reservorio None.
    resultado = construir_reservorio_nulo(
        familia_id=0, unidades_de_la_familia=unidades_doc_a, todas_las_unidades=unidades_doc_a,
        bloques_por_doc={"doc-a": bloques_doc_a}, firmas_por_doc={"doc-a": firmas_doc_a},
        idf=idf, longitud_promedio_unidad=6.0, n_pseudo_queries=20,
    )
    assert resultado is None


def test_reservorio_prefiere_candidatas_con_vocabulario_compartido():
    """Regresion del bug de emparejamiento: con un documento 'senuelo'
    cuyo vocabulario NUNCA coincide con las pseudo-queries generadas
    desde otros documentos, y un documento 'relevante' que SI comparte
    vocabulario, el reservorio debe favorecer las candidatas
    relevantes -- verificado con evidencia mayoritariamente no-cero en
    las coordenadas b/c/x (si el emparejamiento fallara y todo fuera
    random uniforme, la mayoria de vectores tendria b=c=x=0.0 exactos,
    como se midio con datos reales antes de la correccion)."""
    palabras_compartidas = ["historia", "peru", "crisis", "demografica", "poblacion", "siglo"]
    bloques_doc_a = [
        _bloque(f"{palabras_compartidas[i % len(palabras_compartidas)]} texto numero {i}", i, doc_id="doc-a")
        for i in range(15)
    ]
    bloques_doc_b = [
        _bloque(f"{palabras_compartidas[(i+2) % len(palabras_compartidas)]} contenido parrafo {i}", i, doc_id="doc-b")
        for i in range(15)
    ]
    unidades = [
        UnidadRetenida(unidad_id=f"doc-a#u{i}", doc_id="doc-a", indices_bloque=[i],
                        texto=bloques_doc_a[i].texto, pagina_inicio=1, pagina_fin=1)
        for i in range(15)
    ] + [
        UnidadRetenida(unidad_id=f"doc-b#u{i}", doc_id="doc-b", indices_bloque=[i],
                        texto=bloques_doc_b[i].texto, pagina_inicio=1, pagina_fin=1)
        for i in range(15)
    ]
    idf = calcular_idf([tokenizar(b.texto) for b in bloques_doc_a + bloques_doc_b])
    firmas_a = secuencia_de_firmas(bloques_doc_a)
    firmas_b = secuencia_de_firmas(bloques_doc_b)

    resultado = construir_reservorio_nulo(
        familia_id=0, unidades_de_la_familia=unidades, todas_las_unidades=unidades,
        bloques_por_doc={"doc-a": bloques_doc_a, "doc-b": bloques_doc_b},
        firmas_por_doc={"doc-a": firmas_a, "doc-b": firmas_b},
        idf=idf, longitud_promedio_unidad=6.0, n_pseudo_queries=100,
    )
    assert resultado is not None
    todos_los_vectores = resultado.referencia + resultado.calibracion
    n_con_evidencia = sum(1 for v in todos_los_vectores if v[0] > 0.0 or v[1] > 0.0)
    # con vocabulario deliberadamente compartido y emparejamiento
    # funcionando, la mayoria de vectores debe tener evidencia no-cero
    # -- el bug original hubiera dejado la mayoria en cero incluso con
    # vocabulario compartido disponible, porque elegia la candidata sin
    # usarlo.
    assert n_con_evidencia > len(todos_los_vectores) * 0.5


def test_construir_reservorio_nulo_con_dos_documentos_produce_resultado():
    bloques_doc_a = [_bloque(f"palabra{i} texto historico peruano", i, doc_id="doc-a") for i in range(10)]
    bloques_doc_b = [_bloque(f"dato{i} cifra estadistica anual", i, doc_id="doc-b") for i in range(10)]
    unidades = [
        UnidadRetenida(unidad_id=f"doc-a#u{i}", doc_id="doc-a", indices_bloque=[i],
                        texto=bloques_doc_a[i].texto, pagina_inicio=1, pagina_fin=1)
        for i in range(10)
    ] + [
        UnidadRetenida(unidad_id=f"doc-b#u{i}", doc_id="doc-b", indices_bloque=[i],
                        texto=bloques_doc_b[i].texto, pagina_inicio=1, pagina_fin=1)
        for i in range(10)
    ]
    idf = calcular_idf([tokenizar(b.texto) for b in bloques_doc_a + bloques_doc_b])
    firmas_a = secuencia_de_firmas(bloques_doc_a)
    firmas_b = secuencia_de_firmas(bloques_doc_b)

    resultado = construir_reservorio_nulo(
        familia_id=0, unidades_de_la_familia=unidades, todas_las_unidades=unidades,
        bloques_por_doc={"doc-a": bloques_doc_a, "doc-b": bloques_doc_b},
        firmas_por_doc={"doc-a": firmas_a, "doc-b": firmas_b},
        idf=idf, longitud_promedio_unidad=6.0, n_pseudo_queries=50,
    )
    assert resultado is not None
    assert len(resultado.referencia) > 0
    assert len(resultado.calibracion) > 0
