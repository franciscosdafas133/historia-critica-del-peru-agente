# -*- coding: utf-8 -*-
"""
Genera el paper del metodo en PDF.

    python paper/generar_paper.py

Formato de articulo academico: A4, dos columnas, numeracion de secciones y
figuras. Se compone con PyMuPDF, que es la unica dependencia de PDF ya
presente en el proyecto (se usa para leer el corpus).

El contenido es EL METODO: que problema resuelve, por que las alternativas
obvias no funcionan, como se construye la decision y que se midio. Los
detalles de operacion, despliegue y producto quedan fuera a proposito.
"""
import os
import sys

import fitz

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SALIDA = os.path.join(RAIZ, "paper", "CERES_Omega_metodo.pdf")

# --- geometria de pagina (puntos: 1 pt = 1/72") ---
A4 = fitz.paper_rect("a4")          # 595 x 842
MARGEN_X = 52
MARGEN_SUP = 62
MARGEN_INF = 56
CANAL = 20                           # separacion entre columnas
ANCHO_COL = (A4.width - 2 * MARGEN_X - CANAL) / 2

# --- tipografia ---
#
# Las fuentes base-14 del PDF (Times-Roman y compania) solo cubren Latin-1 en
# la practica: "Ω", "ó" y "í" salian como espacios o puntos sueltos. Se
# incrustan fuentes del sistema con cobertura Unicode completa. Si no se
# encuentran, se cae a las base-14 y se transcribe el texto a ASCII, que es
# feo pero legible -- nunca se emite un PDF con caracteres perdidos.
F_TIT = "tit"
F_TXT = "txt"
F_ITA = "ita"
F_NEG = "tit"
F_MON = "mon"

FUENTES_SISTEMA = {
    "txt": [r"C:\Windows\Fonts\georgia.ttf", r"C:\Windows\Fonts\times.ttf"],
    "tit": [r"C:\Windows\Fonts\georgiab.ttf", r"C:\Windows\Fonts\timesbd.ttf"],
    "ita": [r"C:\Windows\Fonts\georgiai.ttf", r"C:\Windows\Fonts\timesi.ttf"],
    "mon": [r"C:\Windows\Fonts\consola.ttf", r"C:\Windows\Fonts\cour.ttf"],
}
BASE14 = {"txt": "Times-Roman", "tit": "Times-Bold",
          "ita": "Times-Italic", "mon": "Courier"}
_ARCHIVO_FUENTE = {}                 # alias -> ruta, resuelto al arrancar


def resolver_fuentes():
    """Localiza las fuentes del sistema una sola vez."""
    for alias, rutas in FUENTES_SISTEMA.items():
        for r in rutas:
            if os.path.exists(r):
                _ARCHIVO_FUENTE[alias] = r
                break
    return len(_ARCHIVO_FUENTE) == len(FUENTES_SISTEMA)

T_TITULO = 17
T_SUB = 10.5
T_H1 = 10.5
T_H2 = 9.5
T_TXT = 9.2
T_PIE = 8.0
T_TAB = 8.2

INTERL = 1.26                        # multiplicador de interlineado

NEGRO = (0.10, 0.09, 0.08)
GRIS = (0.42, 0.40, 0.37)
OCRE = (0.42, 0.28, 0.13)
REGLA = (0.72, 0.70, 0.66)


def escribir(pagina, punto, texto, fontname, fontsize, color):
    """insert_text con la fuente correcta registrada en la pagina.

    PyMuPDF exige declarar la fuente incrustada en cada pagina donde se use;
    olvidarlo devuelve al base-14 y pierde los acentos en silencio.
    """
    if fontname in _ARCHIVO_FUENTE:
        pagina.insert_text(punto, texto, fontname=fontname,
                           fontfile=_ARCHIVO_FUENTE[fontname],
                           fontsize=fontsize, color=color)
    else:
        pagina.insert_text(punto, _ascii(texto), fontname=BASE14[fontname],
                           fontsize=fontsize, color=color)


_OBJ_FUENTE = {}                     # alias -> fitz.Font, para medir


def ancho_txt(texto, fontname, fontsize):
    """Ancho del texto con la fuente que realmente se va a usar.

    get_text_length() no acepta `fontfile`, asi que para las fuentes
    incrustadas se mide con un objeto Font. Medir con una fuente distinta a
    la que se dibuja descuadra el justificado y desborda la columna.
    """
    if fontname in _ARCHIVO_FUENTE:
        f = _OBJ_FUENTE.get(fontname)
        if f is None:
            f = fitz.Font(fontfile=_ARCHIVO_FUENTE[fontname])
            _OBJ_FUENTE[fontname] = f
        return f.text_length(texto, fontsize=fontsize)
    return fitz.get_text_length(_ascii(texto), fontname=BASE14[fontname],
                                fontsize=fontsize)


def _ascii(s):
    """Ultimo recurso si no hay fuentes Unicode: transcribe lo imprescindible."""
    tabla = {"Ω": "Omega", "≥": ">=", "≤": "<=", "→": "->", "⊆": "subset de",
             "σ": "sigma", "φ": "phi", "Σ": "Suma", "∈": "en", "·": "-",
             "—": "-", "–": "-", "«": '"', "»": '"', "“": '"', "”": '"',
             "’": "'", "…": "...", "%": "%"}
    for k, v in tabla.items():
        s = s.replace(k, v)
    return s.encode("latin-1", "replace").decode("latin-1")


class Compositor:
    """Compone texto en dos columnas, saltando de columna y de pagina."""

    def __init__(self, doc, y_inicial=None):
        self.doc = doc
        self.pag = None
        self.col = 0
        self.y = 0.0
        self.n_pag = 0
        self._nueva_pagina()
        # La primera pagina lleva portada y resumen a todo el ancho; el
        # cuerpo en columnas arranca por debajo, no en el margen superior.
        # Sin esto la columna derecha se imprimia ENCIMA del titulo.
        self.y_tope_col = {}
        if y_inicial is not None:
            self.y = y_inicial
            self.y_tope_col[1] = y_inicial

    # -- geometria --
    def _x_col(self):
        return MARGEN_X + self.col * (ANCHO_COL + CANAL)

    def _fondo_col(self):
        return A4.height - MARGEN_INF

    def _nueva_pagina(self):
        self.pag = self.doc.new_page(width=A4.width, height=A4.height)
        self.n_pag += 1
        self.col = 0
        self.y = MARGEN_SUP
        if hasattr(self, "y_tope_col"):
            self.y_tope_col = {}
        self._pie()

    def _pie(self):
        escribir(self.pag, (A4.width / 2 - 8, A4.height - 32), str(self.n_pag),
                 F_TXT, T_PIE, GRIS)

    def _salto(self, alto):
        """Asegura `alto` puntos disponibles; salta de columna o pagina."""
        if self.y + alto <= self._fondo_col():
            return
        if self.col == 0:
            self.col = 1
            self.y = self.y_tope_col.get(1, MARGEN_SUP)
        else:
            self._nueva_pagina()

    # -- primitivas --
    def parrafo(self, texto, fuente=F_TXT, tam=T_TXT, color=NEGRO,
                sangria=0, esp_antes=0, esp_despues=4.5, justificar=True):
        if esp_antes:
            self.y += esp_antes
        ancho = ANCHO_COL - sangria
        alto_linea = tam * INTERL

        palabras = texto.split()
        lineas, actual = [], ""
        for p in palabras:
            prueba = (actual + " " + p).strip()
            if ancho_txt(prueba, fuente, tam) <= ancho:
                actual = prueba
            else:
                if actual:
                    lineas.append(actual)
                actual = p
        if actual:
            lineas.append(actual)

        for i, linea in enumerate(lineas):
            self._salto(alto_linea)
            x = self._x_col() + sangria
            ultima = (i == len(lineas) - 1)
            if justificar and not ultima and len(linea.split()) > 1:
                self._linea_justificada(linea, x, self.y, ancho, fuente, tam, color)
            else:
                escribir(self.pag, (x, self.y), linea, fuente, tam, color)
            self.y += alto_linea
        self.y += esp_despues

    def _linea_justificada(self, linea, x, y, anc, fuente, tam, color):
        palabras = linea.split()
        suma = sum(ancho_txt(p, fuente, tam) for p in palabras)
        espacio = (anc - suma) / max(len(palabras) - 1, 1)
        # Un espaciado desmedido delata la justificacion; se cae a bandera.
        if espacio > ancho_txt(" ", fuente, tam) * 3.2:
            escribir(self.pag, (x, y), linea, fuente, tam, color)
            return
        cx = x
        for p in palabras:
            escribir(self.pag, (cx, y), p, fuente, tam, color)
            cx += ancho_txt(p, fuente, tam) + espacio

    def seccion(self, numero, titulo):
        self._salto(30)
        self.y += 8
        self.parrafo(f"{numero}  {titulo.upper()}", fuente=F_TIT, tam=T_H1,
                     esp_despues=3.5, justificar=False)

    def subseccion(self, numero, titulo):
        self._salto(24)
        self.y += 3
        self.parrafo(f"{numero}  {titulo}", fuente=F_ITA, tam=T_H2,
                     esp_despues=2.5, justificar=False)

    def vineta(self, texto):
        self.parrafo("•  " + texto, sangria=9, esp_despues=2.5)

    def ecuacion(self, texto):
        self._salto(20)
        self.y += 4
        for linea in texto.split("\n"):
            ancho_l = ancho_txt(linea, F_MON, 8.4)
            x = self._x_col() + max(0, (ANCHO_COL - ancho_l) / 2)
            self._salto(11)
            escribir(self.pag, (x, self.y), linea, F_MON, 8.4, NEGRO)
            self.y += 11
        self.y += 6

    def tabla(self, cabeceras, filas, anchos, titulo=""):
        """Tabla de una columna. `anchos` son fracciones que suman 1."""
        alto = 13 + 11 * len(filas) + (26 if titulo else 0)
        self._salto(alto)
        self.y += 5

        cols = [ANCHO_COL * a for a in anchos]
        x0 = self._x_col()

        # cabecera
        self.pag.draw_line(fitz.Point(x0, self.y - 8),
                           fitz.Point(x0 + ANCHO_COL, self.y - 8),
                           color=NEGRO, width=0.7)
        cx = x0
        for i, c in enumerate(cabeceras):
            derecha = i > 0
            tx = (cx + cols[i] - ancho_txt(c, F_TIT, T_TAB) - 2
                  if derecha else cx)
            escribir(self.pag, (tx, self.y), c, F_TIT, T_TAB, NEGRO)
            cx += cols[i]
        self.y += 3
        self.pag.draw_line(fitz.Point(x0, self.y), fitz.Point(x0 + ANCHO_COL, self.y),
                           color=NEGRO, width=0.5)
        self.y += 9

        for fila in filas:
            cx = x0
            for i, celda in enumerate(fila):
                negrita = celda.startswith("*")
                txt = celda[1:] if negrita else celda
                fte = F_NEG if negrita else F_TXT
                derecha = i > 0
                tx = (cx + cols[i] - ancho_txt(txt, fte, T_TAB) - 2
                      if derecha else cx)
                escribir(self.pag, (tx, self.y), txt, fte, T_TAB, NEGRO)
                cx += cols[i]
            self.y += 11

        self.pag.draw_line(fitz.Point(x0, self.y - 7),
                           fitz.Point(x0 + ANCHO_COL, self.y - 7),
                           color=NEGRO, width=0.5)
        self.y += 2
        if titulo:
            self.parrafo(titulo, tam=T_PIE, color=GRIS, esp_despues=6)
        else:
            self.y += 5


def construir():
    if not resolver_fuentes():
        print("AVISO: faltan fuentes del sistema; se usaran las base-14 y el")
        print("       texto se transcribira a ASCII (se pierden los acentos).")

    doc = fitz.open()
    c = Compositor(doc)
    p = c.pag

    # ---------------------------------------------------------------- portada
    y = MARGEN_SUP
    escribir(p, (MARGEN_X, y), "MANUSCRITO TÉCNICO DE INVESTIGACIÓN",
             F_TXT, 8, OCRE)
    y += 22

    titulo = ["CERES-Ω: recuperación de evidencia con",
              "abstención explícita para tutores académicos"]
    for ln in titulo:
        escribir(p, (MARGEN_X, y), ln, F_TIT, T_TITULO, NEGRO)
        y += T_TITULO + 5
    y += 4

    sub = ("Por qué ninguna métrica de presencia de términos distingue "
           "«fuera del temario» de «dentro del temario»")
    for ln in _envolver(sub, F_ITA, T_SUB, A4.width - 2 * MARGEN_X):
        escribir(p, (MARGEN_X, y), ln, F_ITA, T_SUB, GRIS)
        y += T_SUB + 3
    y += 14

    escribir(p, (MARGEN_X, y), "Francisco Luis Delgado Santana",
             F_NEG, 9.5, NEGRO)
    y += 12
    escribir(p, (MARGEN_X, y),
             "Universidad del Pacífico · Departamento de Humanidades · Lima, Perú",
             F_TXT, 8.6, GRIS)
    y += 11
    escribir(p, (MARGEN_X, y), "5 de agosto de 2026 · versión 1.0",
             F_TXT, 8.6, GRIS)
    y += 16

    p.draw_line(fitz.Point(MARGEN_X, y), fitz.Point(A4.width - MARGEN_X, y),
                color=NEGRO, width=1.1)
    y += 20

    # resumen a todo el ancho
    escribir(p, (MARGEN_X, y), "RESUMEN", F_TIT, 8.5, NEGRO)
    y += 13
    for parr in RESUMEN:
        for ln in _envolver(parr, F_TXT, 9.0, A4.width - 2 * MARGEN_X):
            escribir(p, (MARGEN_X, y), ln, F_TXT, 9.0, NEGRO)
            y += 12
        y += 5
    y += 4
    p.draw_line(fitz.Point(MARGEN_X, y), fitz.Point(A4.width - MARGEN_X, y),
                color=REGLA, width=0.6)

    # El cuerpo en dos columnas arranca debajo del resumen, en AMBAS columnas.
    # Registrar el tope de la columna derecha es lo que impide que su texto se
    # imprima encima del titulo al saltar de columna.
    c.y = y + 18
    c.y_tope_col[1] = c.y

    # ------------------------------------------------------------ cuerpo
    c.seccion("1", "El problema de decidir cuándo no responder")
    c.parrafo(
        "Un tutor académico restringido a los materiales de un curso enfrenta "
        "una decisión asimétrica: debe responder todo lo que el material cubre "
        "y no responder nada de lo que no cubre. La segunda mitad es la difícil, "
        "y es la que determina si el sistema es utilizable: un tutor que "
        "responde con evidencia irrelevante pero citada enseña peor que uno "
        "que declara su límite.")
    c.parrafo(
        "Formalmente, dado un corpus C y una consulta q, el sistema debe "
        "producir una decisión d(q) con dos valores posibles —responder o "
        "abstenerse— y, cuando responde, un subconjunto de evidencia E(q) del "
        "corpus. Este trabajo estudia d(q); la calidad de E(q) se discute "
        "en §7.")
    c.parrafo(
        "La dificultad del dominio es específica y, sostenemos, general: las "
        "preguntas ajenas que un estudiante formula con más frecuencia "
        "pertenecen al mismo campo que el corpus. En un curso de historia "
        "peruana, las preguntas fuera del temario son sobre historia peruana. "
        "Comparten vocabulario, autores y período con el material autorizado.")

    c.seccion("2", "Arquitectura de referencia")
    c.parrafo(
        "El método se implementa sobre la arquitectura CERES-Ω [1], que separa "
        "cuatro problemas: cobertura de frontera, compromiso con una cadena de "
        "razonamiento, compatibilidad del conjunto de evidencia y prueba "
        "atómica. Las etapas relevantes para este trabajo son la frontera de "
        "alta cobertura (§4.3 de [1]) y el verificador con abstención (§4.8).")
    c.parrafo(
        "La frontera fusiona rankings heterogéneos mediante Reciprocal Rank "
        "Fusion y no por suma de puntajes. La razón es de escala: BM25 no está "
        "acotado y el coseno vive en [0,1], de modo que sumarlos otorga el peso "
        "a BM25 por magnitud y no por calidad. RRF fusiona por posición, que sí "
        "es comparable entre rankings:")
    c.ecuacion("RRF(d) = suma_i  1 / (k + rank_i(d)),   k = 60")
    c.parrafo(
        "Los componentes entrenados del manuscrito original —un scorer de "
        "conjuntos y un lector atómico supervisado— se sustituyen por "
        "equivalentes deterministas con el mismo contrato. La sustitución se "
        "declara explícitamente: no afirmamos haber reproducido CERES-Ω "
        "completo, sino su arquitectura de decisión.")

    c.seccion("3", "Tres formulaciones y por qué fallan")
    c.parrafo(
        "Construimos el criterio de abstención en tres iteraciones. Reportamos "
        "las tres porque el patrón del fallo, y no la solución, es el resultado "
        "principal de este trabajo.")

    c.subseccion("3.1", "Fracción de términos concentrada")
    c.parrafo(
        "Primera formulación: la consulta está cubierta si sus términos, "
        "ponderados por rareza, se concentran en algún bloque del corpus. "
        "Sea T(q) el conjunto de términos de contenido de q y w(t) su peso IDF:")
    c.ecuacion("             suma de w(t) para t en T(q) y en b\n"
               "phi(q) = max ----------------------------------\n"
               "        b en C   suma de w(t) para t en T(q)")
    c.parrafo(
        "La métrica resulta idéntica para ambas clases. Medido sobre el corpus "
        "descrito en §5, «reforma agraria 1969» (ajena al temario) obtiene "
        "φ = 1,000, exactamente igual que «colapso población andina» (cubierta). "
        "Ningún umbral separa 1,000 de 1,000.")

    c.subseccion("3.2", "Magnitud del mejor puntaje BM25")
    c.parrafo(
        "Segunda formulación: la fuerza de la mejor coincidencia BM25 "
        "discrimina, dado que BM25 ya pondera por frecuencia inversa y por "
        "longitud del documento. Tampoco separa:")
    c.tabla(
        ["Consulta", "BM25"],
        [["«mundial de fútbol 2022» (ajena)", "11,98"],
         ["«colapso población andina» (cubierta)", "12,14"]],
        [0.72, 0.28],
        "Tabla 1. Puntajes indistinguibles para clases opuestas.")
    c.parrafo(
        "La causa es estructural: «mundial» aparece en 77 bloques del corpus "
        "(guerra mundial, sistema mundial) y «2022» en 28 (años de "
        "publicación). El puntaje asciende por coincidencias accidentales de "
        "términos frecuentes, no por pertinencia temática.")

    c.subseccion("3.3", "Densidad de repetición")
    c.parrafo(
        "Tercera formulación, la primera que aporta señal: un texto que "
        "desarrolla un tema repite sus términos; uno que lo menciona de paso, "
        "no. Definimos la densidad como repeticiones por mil tokens en el "
        "bloque que más concentra, y la combinamos con la media de los diez "
        "mejores puntajes BM25 —si el corpus trata el tema hay varios bloques "
        "buenos, no uno solo—:")
    c.ecuacion("sigma(q) = 0,7 x (densidad/100) + (bm25_top10/10)")
    c.tabla(
        ["Clase", "Mediana", "Máx"],
        [["Dentro del temario", "153,8", "500,0"],
         ["Fuera del temario", "12,6", "59,5"]],
        [0.50, 0.26, 0.24],
        "Tabla 2. Densidad (repeticiones por mil tokens). Separa las medianas, "
        "pero los rangos se solapan.")
    c.parrafo(
        "La formulación eleva la exactitud global de 79,2 % a 93,5 %, y sin "
        "embargo rechaza 0 de 8 preguntas de historia peruana no cubierta: "
        "precisamente los casos donde el corpus desarrolla temas adyacentes con "
        "vocabulario compartido.")

    c.subseccion("3.4", "Diagnóstico")
    c.parrafo(
        "El fallo no es de calibración sino de representación. Toda función de "
        "la presencia y frecuencia de términos es ciega a la diferencia entre "
        "«el corpus contiene estas palabras» y «el corpus desarrolla este "
        "tema», cuando ambas clases pertenecen al mismo dominio léxico. "
        "Ninguna elección de umbral corrige una representación que no codifica "
        "la distinción buscada.")

    c.seccion("4", "El criterio propuesto")
    c.parrafo(
        "Introducimos una señal semántica densa: cada bloque se representa como "
        "un vector de 1024 dimensiones, y la decisión considera la similitud "
        "coseno máxima entre la consulta y el corpus. La distribución de esa "
        "similitud sí separa las clases, aunque no perfectamente:")
    c.tabla(
        ["Clase", "Mediana", "Mín", "Máx"],
        [["Dentro del temario", "0,525", "0,298", "0,725"],
         ["Fuera del temario", "0,291", "0,169", "0,495"]],
        [0.40, 0.21, 0.19, 0.20],
        "Tabla 3. Similitud coseno máxima, banco de 77 preguntas.")
    c.parrafo(
        "Las distribuciones se solapan entre 0,30 y 0,51, de modo que un umbral "
        "único tampoco basta. Un primer diseño delegaba esa franja intermedia a "
        "la señal léxica y no produjo mejora alguna: las preguntas que se "
        "colaban caen justo en esa franja, y la señal léxica es precisamente la "
        "que ya fallaba con ellas.")
    c.parrafo(
        "El criterio final define tres regiones. Fuera de la zona de solape "
        "decide la semántica; dentro de ella se exige conjunción de ambas "
        "señales:")
    c.ecuacion(
        "          responder    si sim(q) >= 0,51\n"
        "d(q) =    abstenerse   si sim(q) <  0,30\n"
        "          responder    si sigma(q) >= 1,4\n"
        "          abstenerse   en otro caso")
    c.parrafo(
        "La conjunción es la pieza esencial. Una consulta legítima que cae en "
        "la franja intermedia lo hace por vocabulario poco frecuente, pero "
        "tiene respaldo léxico fuerte porque el corpus la desarrolla. Una "
        "consulta ajena tiene similitud media por compartir dominio, pero "
        "ningún bloque la desarrolla. Exigir ambas condiciones separa lo que "
        "ninguna separa por sí sola.")
    c.parrafo(
        "El umbral 1,4 se elige por barrido sobre las 27 preguntas del banco "
        "que caen en la franja, no por convención. La curva completa se reporta "
        "en §6.2.")

    c.subseccion("4.1", "Rutas exentas")
    c.parrafo(
        "Tres clases de consulta no pasan por el criterio porque las resuelve "
        "el índice estructural y no la búsqueda: las ancladas a una semana o "
        "unidad del programa, las dirigidas a un autor del corpus, y las "
        "administrativas con vocabulario del sílabo. Someterlas al criterio "
        "producía falsos rechazos —«¿en qué semana se ve la independencia?» no "
        "tiene términos de contenido que buscar—.")

    c.seccion("5", "Protocolo experimental")
    c.parrafo(
        "Corpus: 39 documentos de un curso universitario real, 738 363 tokens, "
        "1310 bloques anclados a su fuente. Dos libros concentran el 33 % del "
        "texto, lo que obliga a un cupo por documento en la selección; el 26 % "
        "del material requirió OCR para ser legible.")
    c.parrafo(
        "Banco de evaluación: 77 preguntas etiquetadas manualmente contra el "
        "programa del curso —49 cubiertas, 28 ajenas—. Las ajenas se organizan "
        "en cuatro familias de dificultad creciente, según cuánto comparten con "
        "el dominio del corpus. La familia difícil (historia peruana no "
        "cubierta) es la que motiva el trabajo.")
    c.parrafo(
        "Métricas: proporción de consultas cubiertas que el sistema responde, "
        "proporción de ajenas que rechaza, exactitud global y F1. La etiqueta "
        "es binaria y precede a la ejecución del sistema.")

    c.seccion("6", "Resultados")
    c.tabla(
        ["Formulación", "Cubre", "Rechaza", "Global"],
        [["Fracción de términos", "48/49", "13/28", "79,2 %"],
         ["Densidad + BM25", "49/49", "23/28", "93,5 %"],
         ["*Conjunción semántica", "*47/49", "*28/28", "*97,4 %"]],
        [0.42, 0.19, 0.20, 0.19],
        "Tabla 4. Comparación de las tres formulaciones sobre el banco "
        "completo. F1 = 0,857 / 0,951 / 0,979.")

    c.subseccion("6.1", "Rechazo por familia")
    c.tabla(
        ["Familia de preguntas ajenas", "Léxico", "Final"],
        [["Otro dominio", "8/8", "8/8"],
         ["Cultura general", "3/8", "8/8"],
         ["*Historia peruana no cubierta", "*0/8", "*8/8"],
         ["Extracción de respuestas", "2/4", "4/4"]],
        [0.56, 0.22, 0.22],
        "Tabla 5. La familia difícil pasa de rechazo nulo a rechazo total.")

    c.subseccion("6.2", "Selección del umbral de conjunción")
    c.tabla(
        ["Umbral sigma", "Pierde", "Deja pasar"],
        [["1,0", "1/13", "6/14"],
         ["1,2", "3/13", "4/14"],
         ["*1,4", "*4/13", "*1/14"],
         ["1,6", "7/13", "0/14"]],
        [0.34, 0.33, 0.33],
        "Tabla 6. Barrido sobre las 27 preguntas de la franja intermedia. "
        "No existe corte limpio.")
    c.parrafo(
        "El criterio final rechaza dos preguntas legítimas del temario. "
        "Umbrales más permisivos resultan estrictamente peores: pierden las "
        "mismas dos consultas y además admiten ajenas. Se acepta el costo "
        "porque el fallo corregido producía invención —el sistema devolvía diez "
        "fragmentos sobre ferrocarriles ante una consulta sobre un movimiento "
        "político de los años ochenta—.")

    c.subseccion("6.3", "Ablación de la frontera")
    c.tabla(
        ["Señal desactivada", "Solape", "Iguales"],
        [["BM25", "0,471", "9/49"],
         ["Densa", "0,626", "9/49"],
         ["Título", "0,861", "27/49"],
         ["Entidad", "0,870", "33/49"],
         ["Estructura", "0,883", "41/49"]],
        [0.48, 0.26, 0.26],
        "Tabla 7. Solape de Jaccard entre la evidencia con y sin cada señal.")
    c.parrafo(
        "BM25 y la señal densa dominan la composición de la evidencia. "
        "Advertimos que «cambia la evidencia» no equivale a «la mejora»: "
        "decidir cuál variante recupera mejor exige anotación de bloques de "
        "oro, que este trabajo no posee (§7.2).")

    c.seccion("7", "Amenazas a la validez")

    c.subseccion("7.1", "Degradación silenciosa de la medición")
    c.parrafo(
        "La misma configuración produjo 97,4 % y 90,9 % en corridas distintas. "
        "La causa: la capa semántica devuelve un valor nulo cuando el proveedor "
        "de embeddings falla, y el criterio cae a la señal léxica sin "
        "señalarlo. Al agotarse la cuota del proveedor, el sistema medía su "
        "propia línea base sin que nada lo indicara.")
    c.parrafo(
        "Corregimos instrumentando la capa: toda medición reporta llamadas, "
        "fallos y tasa de fallo, y declara cuándo las cifras no reflejan el "
        "sistema completo. Consideramos que esta degradación es un riesgo "
        "general de las arquitecturas con respaldo: el sistema sigue "
        "respondiendo, peor, y la métrica no lo distingue.")

    c.subseccion("7.2", "Ausencia de bloques de oro")
    c.parrafo(
        "Ninguna métrica de este trabajo mide si la evidencia recuperada es la "
        "correcta; miden si el sistema decide bien cuándo responder. Un motor "
        "puede acertar todas las decisiones y recuperar fragmentos "
        "irrelevantes. Medirlo exige anotar, por consulta, qué bloques "
        "constituyen evidencia necesaria, con anotación previa a la ejecución "
        "y particiones disjuntas por documento [1, §8.3].")

    c.subseccion("7.3", "Sesgo del banco")
    c.parrafo(
        "Las 77 preguntas fueron etiquetadas por una sola persona, que también "
        "eligió las ajenas. Un banco anterior de 34 preguntas asignaba 97,1 % a "
        "una formulación que, ampliado el banco con preguntas del mismo "
        "dominio, obtuvo 83,5 %. La diferencia no estuvo en el sistema sino en "
        "las preguntas. La cifra reportada debe leerse como optimista frente a "
        "consultas reales de estudiantes.")

    c.subseccion("7.4", "Alcance de la afirmación")
    c.parrafo(
        "No reclamamos el umbral de completitud estricta superior a 90 % del "
        "manuscrito de referencia. Ese resultado se deriva de recall publicado "
        "con modelos de 70 mil millones de parámetros; una implementación "
        "económica no lo hereda.")

    c.seccion("8", "Conclusión")
    c.parrafo(
        "Para un sistema de recuperación restringido a un corpus, la decisión "
        "de abstenerse es tan importante como la de responder, y resulta más "
        "difícil cuando las consultas ajenas comparten dominio con el material. "
        "Nuestro resultado principal es negativo y creemos que generaliza: "
        "ninguna función de presencia o frecuencia de términos separa esas dos "
        "clases. La separación exige una representación del significado, y "
        "además su conjunción con la señal léxica en la zona donde ambas "
        "distribuciones se solapan.")
    c.parrafo(
        "El criterio propuesto responde el 95,9 % de las consultas cubiertas y "
        "rechaza el 100 % de las ajenas del banco. Queda pendiente el trabajo "
        "que decidiría si además recupera bien: construir el banco de bloques "
        "de oro y comparar contra BM25 puro. Esa comparación importa: en una "
        "iteración previa de este proyecto, un método que parecía superior "
        "perdió contra BM25 al medirse (96,5 % contra 98,5 % Recall@1).")

    c.seccion("", "Referencias")
    for i, r in enumerate(REFERENCIAS, 1):
        c.parrafo(f"[{i}]  {r}", tam=8.2, sangria=0, esp_despues=3.5)

    os.makedirs(os.path.dirname(SALIDA), exist_ok=True)
    doc.save(SALIDA, garbage=4, deflate=True)
    doc.close()
    return SALIDA


def _envolver(texto, fuente, tam, ancho):
    palabras, lineas, actual = texto.split(), [], ""
    for p in palabras:
        prueba = (actual + " " + p).strip()
        if ancho_txt(prueba, fuente, tam) <= ancho:
            actual = prueba
        else:
            lineas.append(actual)
            actual = p
    if actual:
        lineas.append(actual)
    return lineas


RESUMEN = [
    "Un sistema de recuperación restringido a un corpus debe decidir, antes de "
    "responder, si el corpus cubre la consulta. Reportamos que esa decisión no "
    "admite solución mediante métricas de presencia de términos cuando las "
    "consultas ajenas pertenecen al mismo dominio léxico que el corpus: sobre "
    "un banco de 77 preguntas etiquetadas, tres formulaciones sucesivas "
    "—fracción de términos, magnitud BM25 y densidad de repetición— rechazan "
    "respectivamente 0, 0 y 0 de las 8 consultas del caso difícil, pese a que "
    "la tercera alcanza 93,5 % de exactitud global.",

    "El criterio que sí resuelve el caso combina una señal semántica densa con "
    "la señal léxica mediante conjunción en la zona donde ambas distribuciones "
    "se solapan, y alcanza 97,4 % de exactitud global con rechazo completo de "
    "las consultas ajenas. Documentamos además una amenaza a la validez "
    "detectada en nuestras propias mediciones: la misma configuración produjo "
    "97,4 % y 90,9 % en corridas distintas porque la capa semántica degradaba "
    "en silencio al agotarse la cuota del proveedor.",
]

REFERENCIAS = [
    "Delgado Santana, F. L. (2026). CERES-Ω: recuperación abierta de conjuntos "
    "de evidencia con cobertura superior al 90 %. Manuscrito técnico, v3.0.",
    "Bacellar, A. (2026). BridgeRAG: Training-Free Bridge-Conditioned Retrieval "
    "for Multi-Hop Question Answering. arXiv:2604.03384.",
    "Song, M., & Lee, J.-Y. (2026). Retrieving a Set, Not Independent Passages: "
    "Set-Level Compatibility Learning for Efficient Set Exploration. "
    "arXiv:2607.05712.",
    "Zhang, J., et al. (2024). End-to-End Beam Retrieval for Multi-Hop Question "
    "Answering. NAACL 2024, 1718–1731.",
    "Robertson, S., & Zaragoza, H. (2009). The Probabilistic Relevance "
    "Framework: BM25 and Beyond. Foundations and Trends in Information "
    "Retrieval, 3(4), 333–389.",
    "Cormack, G. V., Clarke, C. L. A., & Buettcher, S. (2009). Reciprocal Rank "
    "Fusion Outperforms Condorcet and Individual Rank Learning Methods. "
    "SIGIR 2009, 758–759.",
]


if __name__ == "__main__":
    ruta = construir()
    print(f"PDF generado: {ruta}")
    print(f"  {os.path.getsize(ruta)/1024:.0f} KB")
    d = fitz.open(ruta)
    print(f"  {d.page_count} páginas")
    d.close()
    sys.exit(0)
