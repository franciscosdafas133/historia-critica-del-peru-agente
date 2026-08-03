# -*- coding: utf-8 -*-
"""
Checkpoint H: empaquetado de contexto restringido por evidencia
(paper, S5.7).

Caso de juguete central (calculado a mano) donde el optimo greedy por
GANANCIA MARGINAL POR TOKEN difiere del optimo por GANANCIA ABSOLUTA:

  Consulta con 3 atomos {z1, z2, z3}, cada uno con IDF=1.0 -> F_max=3.0.
  Unidad X: cubre los 3 atomos, cuesta 30 tokens -> ganancia/token = 3/30 = 0.1
  Unidad Y: cubre solo z1, cuesta 2 tokens -> ganancia/token = 1/2 = 0.5

Un greedy por GANANCIA ABSOLUTA elegiria X primero (cubre mas atomos de
una vez). El greedy correcto del paper (ganancia marginal / costo en
tokens) debe elegir Y primero -- mucho mas barato por unidad de
evidencia, aunque cubra menos en total.
"""
from forma_ir.empaquetado import (
    calcular_F,
    contar_tokens,
    empaquetar_por_cobertura_submodular,
)
from forma_ir.evidencia import tokenizar
from forma_ir.tipos import UnidadRetenida


def _unidad(unidad_id: str, texto: str) -> UnidadRetenida:
    return UnidadRetenida(unidad_id=unidad_id, doc_id="doc-test", indices_bloque=[0],
                            texto=texto, pagina_inicio=1, pagina_fin=1)


def test_checkpoint_h_greedy_por_costo_elige_diferente_que_por_ganancia_absoluta():
    # z1, z2, z3 son los 3 atomos de la consulta.
    texto_x = "z1 z2 z3 " + "relleno " * 27  # ~30 tokens totales, cubre los 3 atomos
    texto_y = "z1 " + "otro " * 1  # 2 tokens, cubre solo z1

    unidad_x = _unidad("x", texto_x)
    unidad_y = _unidad("y", texto_y)

    idf = {"z1": 1.0, "z2": 1.0, "z3": 1.0}

    # Verifica el diseno del caso de juguete antes de correr el algoritmo:
    assert contar_tokens(texto_x) == 30
    assert contar_tokens(texto_y) == 2

    resultado = empaquetar_por_cobertura_submodular(
        [unidad_x, unidad_y], "z1 z2 z3", idf, tokenizar, epsilon=0.7,
        # epsilon alto: solo exige cubrir 30% de la evidencia, que Y sola
        # ya alcanza (1/3 = 0.33 >= 0.3) -- si el greedy fuera por
        # ganancia absoluta, elegiria X primero de todas formas.
    )

    assert resultado.unidades_seleccionadas[0] == "y"


def test_greedy_por_ganancia_absoluta_habria_elegido_diferente():
    """Confirma explicitamente que el caso de juguete SI distingue los
    dos criterios -- si un greedy ingenuo por ganancia absoluta corriera
    sobre las mismas dos unidades, elegiria X primero (mayor cobertura
    de una vez), lo opuesto al resultado correcto verificado arriba."""
    ganancia_absoluta_x = 3.0  # cubre 3 atomos
    ganancia_absoluta_y = 1.0  # cubre 1 atomo
    assert ganancia_absoluta_x > ganancia_absoluta_y  # X ganaria por ganancia absoluta

    ganancia_por_token_x = 3.0 / 30
    ganancia_por_token_y = 1.0 / 2
    assert ganancia_por_token_y > ganancia_por_token_x  # Y gana por ganancia/costo


def test_empaquetado_alcanza_cobertura_completa_con_ambas_unidades():
    texto_x = "z1 z2 z3 " + "relleno " * 27
    texto_y = "z1 " + "otro " * 1
    idf = {"z1": 1.0, "z2": 1.0, "z3": 1.0}

    resultado = empaquetar_por_cobertura_submodular(
        [_unidad("x", texto_x), _unidad("y", texto_y)], "z1 z2 z3", idf, tokenizar, epsilon=0.01,
    )
    # con epsilon bajo, se exige casi toda la evidencia -> debe terminar
    # incluyendo X tambien (Y sola no cubre z2/z3)
    assert set(resultado.unidades_seleccionadas) == {"y", "x"}
    assert resultado.fraccion_evidencia_retenida >= 0.99


def test_empaquetado_nunca_corta_una_unidad():
    """El costo en tokens reportado debe ser la suma EXACTA de tokens de
    las unidades completas seleccionadas -- nunca una fraccion."""
    texto_x = "z1 z2 z3 " + "relleno " * 27
    idf = {"z1": 1.0, "z2": 1.0, "z3": 1.0}
    resultado = empaquetar_por_cobertura_submodular(
        [_unidad("x", texto_x)], "z1 z2 z3", idf, tokenizar, epsilon=0.5,
    )
    assert resultado.tokens_totales == contar_tokens(texto_x)


def test_calcular_F_suma_idf_de_atomos_cubiertos():
    atomos = {"a": 2.0, "b": 3.0, "c": 1.0}
    assert calcular_F({"a", "c"}, atomos) == 3.0
    assert calcular_F(set(), atomos) == 0.0
    assert calcular_F({"a", "b", "c"}, atomos) == 6.0


def test_empaquetado_sin_ninguna_cobertura_posible_devuelve_vacio():
    unidad = _unidad("x", "palabras que no coinciden con la consulta")
    idf = {"inexistente": 1.0}
    resultado = empaquetar_por_cobertura_submodular([unidad], "inexistente", idf, tokenizar)
    # "inexistente" SI aparece como atomo de la query pero la unidad no lo tiene
    assert resultado.unidades_seleccionadas == []


def test_empaquetado_query_sin_atomos_validos_devuelve_vacio():
    unidad = _unidad("x", "cualquier texto de prueba")
    resultado = empaquetar_por_cobertura_submodular([unidad], "terminos sin idf conocido", {}, tokenizar)
    assert resultado.cobertura_maxima_f == 0.0
    assert resultado.unidades_seleccionadas == []


# --- Presupuesto de tokens duro (bug de integracion con produccion) ---

def test_presupuesto_max_tokens_detiene_el_greedy_antes_de_excederlo():
    """Bug real encontrado al conectar FORMA-IR a produccion
    (forma_ir_recuperar.py): el parametro presupuesto_tokens de
    responder_consulta() se aceptaba pero nunca se aplicaba como limite
    real -- el greedy solo paraba por el objetivo de cobertura. Con un
    presupuesto duro de 5 tokens y 3 unidades de 5 tokens cada una que
    cubren atomos DISTINTOS (asi que la cobertura objetivo solo se
    alcanza con las 3), el resultado debe detenerse en 1 sola unidad,
    no exceder el presupuesto."""
    idf = {"z1": 1.0, "z2": 1.0, "z3": 1.0}
    unidad_a = _unidad("a", "z1 relleno relleno relleno relleno")  # 5 tokens, cubre z1
    unidad_b = _unidad("b", "z2 relleno relleno relleno relleno")  # 5 tokens, cubre z2
    unidad_c = _unidad("c", "z3 relleno relleno relleno relleno")  # 5 tokens, cubre z3

    resultado = empaquetar_por_cobertura_submodular(
        [unidad_a, unidad_b, unidad_c], "z1 z2 z3", idf, tokenizar,
        epsilon=0.01, presupuesto_max_tokens=5,
    )
    assert resultado.tokens_totales <= 5
    assert len(resultado.unidades_seleccionadas) == 1


def test_sin_presupuesto_max_tokens_preserva_comportamiento_anterior():
    """El parametro es opcional (default None) -- sin especificarlo, el
    comportamiento debe ser identico al de antes de la correccion
    (solo se detiene por el objetivo de cobertura)."""
    idf = {"z1": 1.0, "z2": 1.0, "z3": 1.0}
    unidad_a = _unidad("a", "z1 relleno relleno relleno relleno")
    unidad_b = _unidad("b", "z2 relleno relleno relleno relleno")
    unidad_c = _unidad("c", "z3 relleno relleno relleno relleno")

    resultado = empaquetar_por_cobertura_submodular(
        [unidad_a, unidad_b, unidad_c], "z1 z2 z3", idf, tokenizar, epsilon=0.01,
    )
    assert len(resultado.unidades_seleccionadas) == 3
