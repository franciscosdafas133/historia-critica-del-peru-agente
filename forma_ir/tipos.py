# -*- coding: utf-8 -*-
"""
Estructuras de datos compartidas por todas las fases de FORMA-IR.
Se agregan incrementalmente conforme cada fase se implementa (ver plan).
"""
from dataclasses import dataclass, field


@dataclass
class Bloque:
    """Una linea visual (PDF) o un parrafo (PPTX/DOCX). Nunca una pagina
    completa ni un span de palabra suelta -- ver Fase A del plan.

    `pistas` (y_i en el paper) contiene SOLO senales directamente medibles:
    nunca una etiqueta semantica de parser (TITLE, H1, etc.) -- eso
    importaria un esquema externo, prohibido por diseno del metodo.
    """

    bloque_id: str
    doc_id: str
    seq: int  # orden absoluto dentro del documento, 0-indexed
    texto: str  # x_i

    # o_i: coordenadas de origen
    pagina: int | None  # 1-indexed; None si no aplica (ej. DOCX)
    diapositiva: int | None  # 1-indexed; None si no aplica
    bbox: tuple[float, float, float, float] | None  # (x0, y0, x1, y1) en puntos

    # y_i: pistas medibles, todas opcionales (None si no observable en ese formato)
    font_size: float | None
    bold: bool | None
    italic: bool | None
    indentacion_pt: float | None  # bbox.x0 relativo al margen de la caja/pagina
    espacio_vertical_antes: float | None  # gap con el bloque anterior en la misma columna

    formato_fuente: str  # "pdf" | "pptx" | "docx" | "pdf_ocr"

    def __post_init__(self):
        # Estas dos SI son derivables solo del texto, no requieren layout --
        # se calculan siempre, incluso para bloques de OCR sin bbox.
        pass


def mayusculas_ratio(texto: str) -> float:
    """Fraccion de caracteres alfabeticos que estan en mayuscula.
    0.0 si no hay ningun caracter alfabetico (evita division por cero)."""
    letras = [c for c in texto if c.isalpha()]
    if not letras:
        return 0.0
    return sum(1 for c in letras if c.isupper()) / len(letras)


def termina_en_puntuacion(texto: str) -> str | None:
    """Ultimo caracter de puntuacion relevante del texto, o None si el
    texto no termina en uno de los signos que nos interesan."""
    t = texto.rstrip()
    if not t:
        return None
    ultimo = t[-1]
    return ultimo if ultimo in ".,:;?!)—-" else None


@dataclass
class UnidadRetenida:
    """Fase D en adelante: una region contigua de bloques, resultado de
    aplicar las fronteras elegidas por el objetivo MDL (Fase C4) sobre un
    documento. Es la unidad NATIVA de recuperacion -- lo que se indexa,
    se puntua (Fase E/F), se agrega a nivel documento (Fase G) y se
    empaqueta bajo presupuesto de tokens (Fase H).

    No incluye el texto de los bloques directamente: la referencia via
    `indices_bloque` evita duplicar texto en memoria/disco cuando se
    persiste junto al corpus de bloques ya existente."""

    unidad_id: str
    doc_id: str
    indices_bloque: list[int]  # posiciones `seq` (0-indexed) que esta unidad cubre, contiguas
    texto: str  # concatenacion de los bloques cubiertos, cacheada para no releer bloques.jsonl en cada fase
    pagina_inicio: int | None
    pagina_fin: int | None

    # Features estructurales no-semanticas (Fase D, S5.3 del paper):
    # log_longitud, entropia_lexica, type_token_ratio, densidad_numerica,
    # densidad_puntuacion, dispersion_longitud_oracion, profundidad_indentacion,
    # soporte_repeticion, posicion_relativa -- se agregan en familias.py
    # como un vector separado (no aqui) para mantener esta dataclass
    # estable mientras el conjunto de features todavia puede cambiar.
    familia_id: int | None = None  # asignado en Fase D
