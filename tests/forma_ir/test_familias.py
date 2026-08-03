# -*- coding: utf-8 -*-
"""
Checkpoint D: familias estructurales (paper, S5.3).

Historia de calibracion: la primera version de `_bic_kmeans` uso una
varianza UNICA compartida entre todos los clusters (inercia total /
(n-k)) -- con eso, ampliar k SIEMPRE reduce la inercia total y la
ganancia de verosimilitud casi nunca se compensa con la penalizacion
lineal en k, asi que el BIC no encontraba NINGUN minimo interior:
verificado probando k=2..150 sobre las 2906 unidades reales del corpus
completo, monotonicamente decreciente todo el rango. Se corrigio a
varianza LOCAL por cluster (formulacion X-means, Pelleg & Moore), que
si permite que clusters ya compactos dejen de "ganar" al subdividirse
mas.

Sobre el corpus real (2906 unidades, 39 documentos), el checkpoint
humano (inspeccionar unidades de familias elegidas al azar) confirmo
agrupaciones estructuralmente coherentes cruzando documentos distintos:
una familia agrupo tablas numericas densas de 3 documentos distintos
(rangos porcentuales, anios, distancias en km); otra agrupo
exclusivamente entradas de indice con puntos suspensivos; otras dos
agruparon prosa academica densa de multiples documentos (incluyendo
texto en ingles), sin usar ninguna etiqueta de genero declarada.
"""
import numpy as np

from forma_ir.familias import (
    FeaturesEstructurales,
    _bic_kmeans,
    _densidad_numerica,
    _densidad_puntuacion,
    _dispersion_longitud_oracion,
    _entropia_shannon_palabras,
    _type_token_ratio,
    elegir_k_y_clusterizar,
)
from sklearn.cluster import KMeans


# --- Features individuales, casos calculables a mano ---

def test_entropia_shannon_texto_repetitivo_es_cero():
    assert _entropia_shannon_palabras("gato gato gato gato") == 0.0


def test_entropia_shannon_texto_vacio_es_cero():
    assert _entropia_shannon_palabras("") == 0.0


def test_type_token_ratio_todas_palabras_distintas_es_uno():
    assert _type_token_ratio("uno dos tres cuatro") == 1.0


def test_type_token_ratio_todas_repetidas():
    assert _type_token_ratio("gato gato gato") == 1 / 3


def test_densidad_numerica_solo_digitos():
    assert _densidad_numerica("12345") == 1.0


def test_densidad_numerica_sin_digitos():
    assert _densidad_numerica("solo letras") == 0.0


def test_densidad_puntuacion_cuenta_solo_no_alfanumerico_no_espacio():
    # "a,b." -> 2 de 4 caracteres son puntuacion (',' y '.')
    assert _densidad_puntuacion("a,b.") == 0.5


def test_dispersion_longitud_oracion_una_sola_oracion_es_cero():
    assert _dispersion_longitud_oracion("una sola oracion sin punto final") == 0.0


def test_dispersion_longitud_oracion_oraciones_uniformes_es_baja():
    texto = "dos palabras. dos palabras. dos palabras."
    assert _dispersion_longitud_oracion(texto) == 0.0


def test_dispersion_longitud_oracion_oraciones_variables_es_mayor_que_cero():
    texto = "una. dos palabras aqui son mas. tres."
    assert _dispersion_longitud_oracion(texto) > 0.0


# --- BIC: regresion del bug de varianza compartida ---

def _features_dos_grupos_bien_separados() -> list[FeaturesEstructurales]:
    """20 unidades sinteticas en 2 grupos MUY separados en el espacio de
    features (uno con longitud/entropia altas, otro con densidad
    numerica alta) -- un buen criterio de seleccion de k debe preferir
    k=2 sobre k=1 aqui, sin necesitar mas de 2."""
    grupo_a = [
        FeaturesEstructurales(f"a{i}", log_longitud=8.0, entropia_lexica=5.0,
                                type_token_ratio=0.9, densidad_numerica=0.0,
                                densidad_puntuacion=0.05, dispersion_longitud_oracion=3.0,
                                profundidad_indentacion=10.0, soporte_repeticion=0.1,
                                posicion_relativa=0.3)
        for i in range(10)
    ]
    grupo_b = [
        FeaturesEstructurales(f"b{i}", log_longitud=2.0, entropia_lexica=0.5,
                                type_token_ratio=0.2, densidad_numerica=0.8,
                                densidad_puntuacion=0.3, dispersion_longitud_oracion=0.0,
                                profundidad_indentacion=50.0, soporte_repeticion=0.9,
                                posicion_relativa=0.7)
        for i in range(10)
    ]
    return grupo_a + grupo_b


def test_bic_penaliza_dividir_un_cluster_ya_compacto():
    """Regresion del bug de varianza compartida: sobre datos sinteticos
    de un UNICO grupo compacto (sin estructura real de sub-clusters),
    el BIC con varianza local debe preferir k=1 (o muy pocos clusters)
    sobre partir el grupo en muchos pedazos artificiales -- el bug
    original hacia que mas clusters SIEMPRE ganara."""
    rng = np.random.RandomState(7)
    un_solo_grupo = rng.normal(loc=0.0, scale=1.0, size=(60, 5))

    modelo_k2 = KMeans(n_clusters=2, random_state=42, n_init=10).fit(un_solo_grupo)
    modelo_k20 = KMeans(n_clusters=20, random_state=42, n_init=10).fit(un_solo_grupo)

    bic_k2 = _bic_kmeans(un_solo_grupo, modelo_k2)
    bic_k20 = _bic_kmeans(un_solo_grupo, modelo_k20)

    # con el bug original, bic_k20 < bic_k2 SIEMPRE (mas clusters ganaba
    # sin limite); con la correccion, dividir un grupo homogeneo en 20
    # piezas artificiales debe costar mas que dejarlo en 2.
    assert bic_k2 < bic_k20


def test_elegir_k_sobre_dos_grupos_bien_separados_no_colapsa_a_uno():
    features = _features_dos_grupos_bien_separados()
    etiquetas, k = elegir_k_y_clusterizar(features, k_min=2, k_max=6)
    assert k >= 2
    assert len(set(etiquetas)) == k


def test_elegir_k_con_pocas_unidades_no_produce_clusters_degenerados():
    """Con muy pocas unidades (menos que 2*k_min), todas deben caer en
    una sola familia -- evita clusters de 1 solo miembro sin sentido
    estadistico."""
    features = _features_dos_grupos_bien_separados()[:3]
    etiquetas, k = elegir_k_y_clusterizar(features, k_min=2)
    assert k == 1
    assert etiquetas == [0, 0, 0]


def test_todas_las_unidades_reciben_una_etiqueta():
    features = _features_dos_grupos_bien_separados()
    etiquetas, _k = elegir_k_y_clusterizar(features, k_min=2, k_max=6)
    assert len(etiquetas) == len(features)
