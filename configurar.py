# -*- coding: utf-8 -*-
"""
Configuracion de la clave de API.

Pide la clave, la guarda en un archivo .env local, comprueba que funciona
y deja el sistema listo. La clave nunca se muestra completa en pantalla
ni se sube a ningun sitio: .env esta en .gitignore.

Uso:  python configurar.py
"""
import sys, io, os, re
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace", line_buffering=True)

RAIZ = os.path.dirname(os.path.abspath(__file__))
ENV = os.path.join(RAIZ, ".env")


def enmascarar(k):
    return k[:6] + "…" + k[-4:] if len(k) > 14 else "…"


def detectar_proveedor(k):
    """Deduce el proveedor por la forma de la clave."""
    if k.startswith("sk-ant-"):
        return "anthropic"
    if k.startswith(("AIza", "AQ.")):
        return "gemini"
    return None


print("=" * 64)
print("  Configuración del agente · Historia Crítica del Perú")
print("=" * 64)

# --- si ya hay .env, avisar antes de sobrescribir ---
if os.path.exists(ENV):
    actual = ""
    for linea in open(ENV, encoding="utf-8"):
        m = re.match(r"\s*(GEMINI_API_KEY|ANTHROPIC_API_KEY)\s*=\s*(\S+)", linea)
        if m:
            actual = f"{m.group(1)} = {enmascarar(m.group(2))}"
            break
    if actual:
        print(f"\nYa hay una clave configurada:  {actual}")
        r = input("¿Reemplazarla? (s/N): ").strip().lower()
        if r != "s":
            print("Sin cambios."); sys.exit(0)

print("""
Pega tu clave de API. Puede ser de:

  Google Gemini    https://aistudio.google.com/apikey
  Anthropic        https://console.anthropic.com

La clave se guardará en un archivo .env de esta carpeta, que está
excluido de git y nunca sale de esta máquina.
""")

clave = input("Clave: ").strip().strip('"').strip("'")
if not clave:
    print("No escribiste nada. Cancelado."); sys.exit(1)

prov = detectar_proveedor(clave)
if prov is None:
    print(f"\nNo reconozco el formato de esa clave ({enmascarar(clave)}).")
    print("  1) Google Gemini")
    print("  2) Anthropic")
    op = input("¿Cuál es? (1/2): ").strip()
    prov = {"1": "gemini", "2": "anthropic"}.get(op)
    if not prov:
        print("Opción no válida. Cancelado."); sys.exit(1)

var = "GEMINI_API_KEY" if prov == "gemini" else "ANTHROPIC_API_KEY"

with open(ENV, "w", encoding="utf-8") as f:
    f.write("# Clave de API — este archivo NO debe subirse a ningún repositorio.\n")
    f.write("# Está excluido en .gitignore. Generado por configurar.py\n\n")
    f.write(f"{var}={clave}\n")

print(f"\n-> .env creado · {var} = {enmascarar(clave)}  ({prov})")

# --- probar la conexion ---
print("\nProbando la conexión...")
os.environ[var] = clave
try:
    from proveedor import generar, proveedor_activo
    p, modelo = proveedor_activo()
    r = generar("Responde en una sola línea, sin preámbulo.",
                "Di exactamente: conexión correcta", 60)
    print(f"   modelo    : {modelo}")
    print(f"   respuesta : {r['texto'].strip()[:80]}")
    print(f"   tokens    : entrada {r['entrada']} · salida {r['salida']} · {r['ms']} ms")
    print("\n" + "=" * 64)
    print("  LISTO. Ahora arranca el servidor:")
    print("      python servidor.py --red")
    print("=" * 64)
except Exception as e:
    print(f"\n   FALLÓ: {type(e).__name__}: {e}")
    print("\n   La clave quedó guardada en .env, pero no funcionó.")
    print("   Revisa que esté completa y que sea del proveedor correcto,")
    print("   y vuelve a correr: python configurar.py")
    sys.exit(1)
