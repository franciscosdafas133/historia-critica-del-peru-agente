# -*- coding: utf-8 -*-
"""
Capa de proveedores de modelo - Historia Critica del Peru

Aisla la generacion del resto del sistema: el corpus, los indices y la
recuperacion no dependen de que modelo se use. Cambiar de proveedor no
toca ninguna otra pieza.

Proveedores soportados:
  gemini     (Google)     GEMINI_API_KEY
  anthropic  (Anthropic)  ANTHROPIC_API_KEY
  groq       (Groq)       GROQ_API_KEY

Las claves se leen de un archivo .env local que NUNCA se sube a ningun
repositorio (esta en .gitignore). Nada en este modulo imprime la clave.

Uso:
    from proveedor import generar, proveedor_activo
    r = generar(sistema, mensaje_usuario)
    r["texto"], r["entrada"], r["salida"], r["modelo"]
"""
import os, time, random

# Carga .env si existe. No falla si falta python-dotenv.
try:
    from dotenv import load_dotenv
    load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env"))
except ImportError:
    pass


# Modelos por defecto de cada proveedor. Se pueden cambiar con MODELO_AGENTE.
#
# gemini-flash-latest es un alias: apunta siempre al Flash vigente, asi que no
# se rompe cuando Google retira una version concreta (gemini-2.5-flash dejo de
# aceptar usuarios nuevos y devuelve 404).
DEFECTO = {
    "gemini": "gemini-flash-latest",
    "anthropic": "claude-sonnet-5",
    "groq": "llama-3.3-70b-versatile",
}

# Modelo de reserva por proveedor: si el principal sigue caido (503) o sin
# cupo (429) despues de reintentar, se prueba una vez con este antes de
# rendirse. gemini-2.0-flash es una version anterior con capacidad separada
# de gemini-flash-latest, asi que un pico de demanda en uno no suele afectar
# al otro al mismo tiempo.
RESERVA = {
    "gemini": "gemini-2.0-flash",
    "anthropic": "claude-haiku-4-5",
    "groq": "llama-3.1-8b-instant",
}


def proveedor_activo():
    """Devuelve (proveedor, modelo) segun las claves disponibles.

    PROVEEDOR fuerza uno concreto; si no, se elige el primero que tenga clave.
    Devuelve (None, None) cuando no hay ninguna configurada.
    """
    forzado = (os.environ.get("PROVEEDOR") or "").strip().lower()
    disponibles = []
    if os.environ.get("GEMINI_API_KEY"):
        disponibles.append("gemini")
    if os.environ.get("ANTHROPIC_API_KEY"):
        disponibles.append("anthropic")
    if os.environ.get("GROQ_API_KEY"):
        disponibles.append("groq")

    if forzado:
        prov = forzado if forzado in disponibles else None
    else:
        prov = disponibles[0] if disponibles else None

    if not prov:
        return None, None
    return prov, os.environ.get("MODELO_AGENTE") or DEFECTO[prov]


def _generar_gemini(sistema, usuario, modelo, max_tokens):
    from google import genai
    from google.genai import types

    cli = genai.Client(api_key=os.environ["GEMINI_API_KEY"])
    resp = cli.models.generate_content(
        model=modelo,
        contents=usuario,
        config=types.GenerateContentConfig(
            system_instruction=sistema,
            max_output_tokens=max_tokens,
            # temperatura baja: las respuestas deben ceñirse a la evidencia,
            # no explorar formulaciones alternativas
            temperature=0.3,
        ),
    )
    um = resp.usage_metadata
    # candidates_token_count llega como None cuando el modelo razona internamente;
    # en ese caso el total menos la entrada es la mejor estimacion de salida.
    salida = getattr(um, "candidates_token_count", None)
    entrada = getattr(um, "prompt_token_count", 0) or 0
    if not salida:
        total = getattr(um, "total_token_count", 0) or 0
        salida = max(total - entrada, 0)
    return {
        "texto": resp.text or "",
        "entrada": entrada,
        "salida": salida,
        "cache_lectura": getattr(um, "cached_content_token_count", 0) or 0,
        "cache_escritura": 0,
        "rechazado": not (resp.text or "").strip(),
    }


def _generar_anthropic(sistema, usuario, modelo, max_tokens):
    from anthropic import Anthropic

    cli = Anthropic()
    resp = cli.messages.create(
        model=modelo,
        max_tokens=max_tokens,
        # el prompt de sistema es estable entre consultas: cachearlo hace que
        # a partir de la segunda pregunta cueste una fraccion
        system=[{"type": "text", "text": sistema,
                 "cache_control": {"type": "ephemeral"}}],
        messages=[{"role": "user", "content": usuario}],
    )
    return {
        "texto": "".join(b.text for b in resp.content if b.type == "text"),
        "entrada": resp.usage.input_tokens,
        "salida": resp.usage.output_tokens,
        "cache_lectura": getattr(resp.usage, "cache_read_input_tokens", 0) or 0,
        "cache_escritura": getattr(resp.usage, "cache_creation_input_tokens", 0) or 0,
        "rechazado": resp.stop_reason == "refusal",
    }


def _generar_groq(sistema, usuario, modelo, max_tokens):
    from groq import Groq

    cli = Groq()
    resp = cli.chat.completions.create(
        model=modelo,
        max_tokens=max_tokens,
        temperature=0.3,
        messages=[
            {"role": "system", "content": sistema},
            {"role": "user", "content": usuario},
        ],
    )
    texto = resp.choices[0].message.content or ""
    return {
        "texto": texto,
        "entrada": resp.usage.prompt_tokens,
        "salida": resp.usage.completion_tokens,
        "cache_lectura": 0,
        "cache_escritura": 0,
        "rechazado": not texto.strip(),
    }


def _es_transitorio(e):
    """Distingue un fallo pasajero (sobrecarga, cuota, red) de un error real
    de la peticion (clave invalida, modelo inexistente, prompt rechazado).
    Solo los primeros vale la pena reintentar o cambiar de modelo."""
    s = str(e).lower()
    return any(x in s for x in (
        "503", "unavailable", "overloaded",
        "429", "resource_exhausted", "rate limit", "quota",
        "timeout", "timed out", "connection",
        "500", "internal",
    ))


def _con_reintentos(fn, intentos=3, base=1.5):
    """Reintenta fn() ante errores transitorios con backoff exponencial y
    jitter. Deja pasar de inmediato cualquier error que no sea transitorio
    (una clave invalida no se arregla reintentando)."""
    ultimo = None
    for i in range(intentos):
        try:
            return fn()
        except Exception as e:
            ultimo = e
            if not _es_transitorio(e) or i == intentos - 1:
                raise
            time.sleep(base * (2 ** i) + random.uniform(0, 0.5))
    raise ultimo


def generar(sistema, usuario, max_tokens=6000):
    """Genera una respuesta con el proveedor configurado.

    max_tokens es holgado a proposito: los modelos Gemini Flash consumen parte
    del presupuesto razonando internamente antes de escribir, asi que un limite
    ajustado al largo de la respuesta la corta a media frase.

    Ante un pico de demanda (503) o cuota agotada (429) del modelo principal,
    reintenta con backoff y, si sigue caido, prueba una vez con el modelo de
    reserva del mismo proveedor antes de rendirse -- no cambia de proveedor,
    porque eso implicaria otra clave.

    Devuelve un dict con texto, tokens y metadatos. Lanza RuntimeError si no
    hay ninguna clave configurada, o la excepcion original si el fallo no es
    transitorio (clave invalida, modelo inexistente, prompt rechazado).
    """
    prov, modelo = proveedor_activo()
    if not prov:
        raise RuntimeError(
            "No hay clave de API configurada. Crea un archivo .env con "
            "GEMINI_API_KEY=... (o ANTHROPIC_API_KEY=..., o GROQ_API_KEY=...)"
        )

    FUNCIONES = {"gemini": _generar_gemini, "anthropic": _generar_anthropic, "groq": _generar_groq}
    fn = FUNCIONES[prov]
    t0 = time.time()
    modelo_usado = modelo
    try:
        r = _con_reintentos(lambda: fn(sistema, usuario, modelo, max_tokens))
    except Exception as e:
        reserva = RESERVA.get(prov)
        if not _es_transitorio(e) or not reserva or reserva == modelo:
            raise
        r = _con_reintentos(lambda: fn(sistema, usuario, reserva, max_tokens), intentos=2)
        modelo_usado = reserva

    r["proveedor"] = prov
    r["modelo"] = modelo_usado
    r["ms"] = round((time.time() - t0) * 1000)
    return r


if __name__ == "__main__":
    import sys, io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    prov, modelo = proveedor_activo()
    if not prov:
        print("Sin clave configurada.")
        print("Crea un archivo .env en esta carpeta con una linea:")
        print("  GEMINI_API_KEY=tu-clave-aqui")
        sys.exit(1)
    print(f"proveedor : {prov}")
    print(f"modelo    : {modelo}")
    print("probando conexion...")
    r = generar("Responde en una sola linea.", "Di 'conexion correcta' y nada mas.", 60)
    print(f"respuesta : {r['texto'].strip()}")
    print(f"tokens    : entrada {r['entrada']} · salida {r['salida']} · {r['ms']} ms")
