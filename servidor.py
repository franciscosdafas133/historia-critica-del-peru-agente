# -*- coding: utf-8 -*-
"""
Servidor web del agente - Historia Critica del Peru (122005-A, 2026-1)

Interfaz para probar el sistema desde el navegador, accesible en la red local.

Dos modos, segun haya o no credencial de API:

  SIN API key   muestra que evidencia recupera el sistema, de que paginas,
                cuantos tokens y por que. Todo local, sin costo.

  CON API key   ademas genera la respuesta pedagogica con citas y verifica
                que cada cita exista realmente.

El corpus y los indices nunca salen de esta maquina. Cuando se genera una
respuesta, los fragmentos seleccionados si viajan a la API de Anthropic.

Uso:
    python servidor.py                    # solo esta maquina
    python servidor.py --red              # accesible desde la red local
    python servidor.py --puerto 8080
    set ANTHROPIC_API_KEY=sk-...          # habilita la generacion
"""
import sys, io, os, json, pickle, argparse, socket, time, traceback
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace", line_buffering=True)

from flask import Flask, request, jsonify, Response
from flask_cors import CORS

from recuperar import recuperar, analizar_pregunta
from agente import (SISTEMA, sistema_para, MODOS, prompt_recuperacion,
                    prompt_completo, verificar_citas, ntok,
                    parsear_practica, parsear_tarjeta)
from proveedor import generar as generar_respuesta, proveedor_activo

MODOS_VALIDOS = set(MODOS.keys())

RAIZ = os.path.dirname(os.path.abspath(__file__))
IDX_PATH = os.path.join(RAIZ, "corpus", "indice.pkl")

app = Flask(__name__)
IDX = None

# CORS restringido a /api/* -- nunca abierto ("*"): detras de estos endpoints
# hay una API de pago (Gemini), y un origen abierto permitiria que cualquier
# sitio externo dispare llamadas que consuman esa cuota. En desarrollo se
# permite el puerto por defecto de Vite; en produccion, FRONTEND_URL se
# configura como variable de entorno en el panel del hosting del backend.
ORIGENES_PERMITIDOS = [o for o in [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    os.environ.get("FRONTEND_URL", ""),
] if o]
CORS(app, resources={r"/api/*": {"origins": ORIGENES_PERMITIDOS}})


def cargar_indice():
    global IDX
    if IDX is None:
        IDX = pickle.load(open(IDX_PATH, "rb"))
    return IDX


def hay_api_key():
    return proveedor_activo()[0] is not None


# ---------------------------------------------------------------- API

@app.route("/api/info")
def api_info():
    idx = cargar_indice()
    docs = idx["docs"]
    prov, modelo = proveedor_activo()
    return jsonify({
        "curso": idx["curso"],
        "documentos": len(docs),
        "bloques": len(idx["bloques"]),
        "tokens": sum(d["tokens"] for d in docs.values()),
        "semanas": sorted(idx["por_semana"].keys()),
        "api_disponible": prov is not None,
        "proveedor": prov,
        "modelo": modelo,
    })


@app.route("/api/preguntar", methods=["POST"])
def api_preguntar():
    datos = request.get_json(force=True)
    pregunta = (datos.get("pregunta") or "").strip()
    modo = (datos.get("modo") or "preguntar").strip().lower()
    if modo not in MODOS_VALIDOS:
        modo = "preguntar"
    generar = bool(datos.get("generar")) and hay_api_key()
    if not pregunta:
        return jsonify({"error": "Escribe una pregunta."}), 400

    idx = cargar_indice()
    t0 = time.time()
    r = recuperar(pregunta, idx, modo_interaccion=modo)
    t_recuperacion = time.time() - t0

    paquetes = [{
        "n": i,
        "documento": p["doc"].replace("_", " "),
        "cita": p["cita"],
        "ubicacion": p["paginas"],
        "archivo": os.path.basename(p["archivo"]),
        "tipo": p["tipo"],
        "autoridad": p["autoridad"],
        "unidad": p["unidad"],
        "semana": p["semana"],
        "tokens": p["tokens"],
        "score": p["score"],
        "cobertura": p.get("cobertura"),
        "ocr": p["ocr"],
        "extracto": p["texto"][:600],
    } for i, p in enumerate(r["paquetes"], 1)]

    salida = {
        "pregunta": pregunta,
        "modo": modo,
        "tipo": r["plan"]["tipo"],
        "presupuesto": r["plan"]["presupuesto"],
        "tokens_evidencia": r["plan"]["tokens_usados"],
        "filtros": r["plan"]["filtros"],
        "paquetes": paquetes,
        "avisos": r["avisos"],
        "ms_recuperacion": round(t_recuperacion * 1000, 1),
        "respuesta": None,
        "verificacion": None,
        "uso": None,
        "error_generacion": None,
        "estructurado": None,
    }

    if not generar or not r["paquetes"]:
        return jsonify(salida)

    # --- generacion ---
    try:
        user, _ = prompt_recuperacion(pregunta, idx, modo=modo)
        g = generar_respuesta(sistema_para(modo), user)
        salida["respuesta"] = g["texto"]
        salida["verificacion"] = verificar_citas(g["texto"], r["paquetes"])
        salida["uso"] = {
            "entrada": g["entrada"], "salida": g["salida"],
            "cache_lectura": g["cache_lectura"],
            "cache_escritura": g["cache_escritura"],
            "ms": g["ms"], "proveedor": g["proveedor"], "modelo": g["modelo"],
        }
        if g["rechazado"]:
            salida["error_generacion"] = "El modelo no devolvió texto para esta consulta."
        elif modo in ("practicar", "evaluar"):
            salida["estructurado"] = parsear_practica(g["texto"])
        elif modo == "repasar":
            salida["estructurado"] = parsear_tarjeta(g["texto"])
    except Exception as e:
        salida["error_generacion"] = f"{type(e).__name__}: {e}"
        print("ERROR generacion:", traceback.format_exc(), file=sys.stderr)

    return jsonify(salida)


@app.route("/api/comparar", methods=["POST"])
def api_comparar():
    """Compara el costo de las tres estrategias para una misma pregunta."""
    datos = request.get_json(force=True)
    pregunta = (datos.get("pregunta") or "").strip()
    if not pregunta:
        return jsonify({"error": "Escribe una pregunta."}), 400
    idx = cargar_indice()

    user_r, r = prompt_recuperacion(pregunta, idx)
    t_rec = ntok(SISTEMA) + ntok(user_r) if user_r else 0

    plan = analizar_pregunta(pregunta, idx)
    sem = plan["filtros"].get("semana")
    if sem is None and r["paquetes"]:
        sem = r["paquetes"][0]["semana"]
    t_sec = 0
    if sem:
        user_s, _ = prompt_completo(pregunta, idx, {"semana": sem})
        t_sec = ntok(SISTEMA) + ntok(user_s)

    user_c, n_docs = prompt_completo(pregunta, idx)
    t_com = ntok(SISTEMA) + ntok(user_c)

    return jsonify({
        "recuperacion": t_rec, "seccion": t_sec, "completo": t_com,
        "semana": sem, "documentos_completo": n_docs,
    })


@app.route("/")
def index():
    return Response(PAGINA, mimetype="text/html; charset=utf-8")


# ---------------------------------------------------------------- HTML

PAGINA = r"""<!doctype html>
<html lang="es"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Agente · Historia Crítica del Perú</title>
<style>
 :root{
   --papel:#F7F4EF; --papel2:#EFEAE1; --papel3:#E7E0D2; --linea:#DCD3C5;
   --tinta:#241F1A; --tinta2:#5C5348; --meta:#8A7A66;
   --ocre:#B4552D; --ocre-suave:#E8D4C6; --verde:#4A6B52;
   --verde-suave:#DCE5DA; --azul:#3D5A73; --azul-suave:#DCE3E8; --rojo:#A63D2F;
   --serif:"Iowan Old Style","Palatino Linotype",Palatino,Georgia,serif;
   --sans:"Segoe UI",-apple-system,Roboto,Helvetica,Arial,sans-serif;
   --mono:"Cascadia Mono",Consolas,"SF Mono",Menlo,monospace;
   --sombra:0 1px 2px rgba(36,31,26,.05), 0 6px 18px -10px rgba(36,31,26,.16);
 }
 @media (prefers-color-scheme:dark){
   :root{--papel:#181512;--papel2:#211D19;--papel3:#2A241E;--linea:#332D26;--tinta:#EDE6DB;
     --tinta2:#B5AA9B;--meta:#8A7C6B;--ocre:#D9764A;--ocre-suave:#3A2419;
     --verde:#8DB396;--verde-suave:#1E2A21;--azul:#8FB0C9;--azul-suave:#1E2A32;--rojo:#D98878;
     --sombra:0 1px 2px rgba(0,0,0,.35), 0 6px 18px -10px rgba(0,0,0,.5);}
 }
 :root[data-theme="dark"]{--papel:#181512;--papel2:#211D19;--papel3:#2A241E;--linea:#332D26;--tinta:#EDE6DB;
   --tinta2:#B5AA9B;--meta:#8A7C6B;--ocre:#D9764A;--ocre-suave:#3A2419;
   --verde:#8DB396;--verde-suave:#1E2A21;--azul:#8FB0C9;--azul-suave:#1E2A32;--rojo:#D98878;
   --sombra:0 1px 2px rgba(0,0,0,.35), 0 6px 18px -10px rgba(0,0,0,.5);}
 :root[data-theme="light"]{--papel:#F7F4EF; --papel2:#EFEAE1; --papel3:#E7E0D2; --linea:#DCD3C5;
   --tinta:#241F1A; --tinta2:#5C5348; --meta:#8A7A66;
   --ocre:#B4552D; --ocre-suave:#E8D4C6; --verde:#4A6B52;
   --verde-suave:#DCE5DA; --azul:#3D5A73; --azul-suave:#DCE3E8; --rojo:#A63D2F;
   --sombra:0 1px 2px rgba(36,31,26,.05), 0 6px 18px -10px rgba(36,31,26,.16);}
 *{box-sizing:border-box}
 body{margin:0;background:var(--papel);color:var(--tinta);font-family:var(--sans);
   line-height:1.6;-webkit-font-smoothing:antialiased}
 .wrap{max-width:980px;margin:0 auto;padding:26px 20px 90px}
 header{border-bottom:1px solid var(--linea);padding-bottom:16px;margin-bottom:20px;
   display:flex;justify-content:space-between;align-items:flex-end;flex-wrap:wrap;gap:12px}
 .eyebrow{font-family:var(--mono);font-size:11px;letter-spacing:.14em;
   text-transform:uppercase;color:var(--ocre);margin-bottom:8px}
 h1{font-family:var(--serif);font-size:clamp(22px,3.6vw,30px);margin:0 0 6px;
   font-weight:600;letter-spacing:-.015em;text-wrap:balance}
 .stats{font-family:var(--mono);font-size:11px;color:var(--meta);
   display:flex;flex-wrap:wrap;gap:3px 16px;margin-top:2px}
 .badge{display:inline-flex;align-items:center;gap:6px;font-family:var(--mono);
   font-size:10.5px;letter-spacing:.06em;text-transform:uppercase;
   padding:5px 10px;border-radius:20px;white-space:nowrap}
 .badge.on{background:var(--verde-suave);color:var(--verde);
   border:1px solid color-mix(in srgb,var(--verde) 30%,transparent)}
 .badge.off{background:var(--papel2);color:var(--meta);border:1px solid var(--linea)}

 /* --- navegacion de modos --- */
 nav.modos{display:grid;grid-template-columns:repeat(4,1fr);gap:8px;margin-bottom:22px}
 .modo-btn{background:var(--papel2);border:1px solid var(--linea);border-radius:8px;
   padding:13px 12px;cursor:pointer;text-align:left;transition:border-color .12s,background .12s}
 .modo-btn:hover{border-color:color-mix(in srgb,var(--ocre) 45%,var(--linea))}
 .modo-btn.activo{background:var(--ocre);border-color:var(--ocre)}
 .modo-ico{font-family:var(--serif);font-size:19px;line-height:1;margin-bottom:6px;
   color:var(--ocre)}
 .modo-btn.activo .modo-ico{color:#fff}
 .modo-nom{font-weight:600;font-size:13.5px;color:var(--tinta);display:block}
 .modo-btn.activo .modo-nom{color:#fff}
 .modo-desc{font-size:11.5px;color:var(--meta);display:block;margin-top:2px;line-height:1.35}
 .modo-btn.activo .modo-desc{color:color-mix(in srgb,#fff 78%,transparent)}
 @media(max-width:640px){nav.modos{grid-template-columns:repeat(2,1fr)}}

 .panel-intro{font-size:13.5px;color:var(--tinta2);margin-bottom:14px;max-width:66ch}
 .panel-intro b{color:var(--tinta)}

 form{display:flex;gap:9px;margin-bottom:10px;flex-wrap:wrap}
 input[type=text],textarea{flex:1;min-width:240px;padding:12px 14px;font-size:15px;
   font-family:inherit;background:var(--papel2);color:var(--tinta);
   border:1px solid var(--linea);border-radius:7px;resize:vertical}
 textarea{min-height:64px;line-height:1.5}
 input[type=text]:focus,textarea:focus{outline:2px solid var(--ocre);outline-offset:-1px}
 button{padding:12px 20px;font-size:14px;font-family:inherit;font-weight:600;
   background:var(--ocre);color:#fff;border:0;border-radius:7px;cursor:pointer;
   white-space:nowrap}
 button:disabled{opacity:.5;cursor:default}
 button.sec{background:transparent;color:var(--tinta2);border:1px solid var(--linea)}
 select{padding:11px 12px;font-size:13.5px;font-family:inherit;background:var(--papel2);
   color:var(--tinta);border:1px solid var(--linea);border-radius:7px}

 .opts{display:flex;gap:16px;align-items:center;font-size:13px;
   color:var(--tinta2);margin-bottom:14px;flex-wrap:wrap}
 .opts label{display:flex;gap:6px;align-items:center;cursor:pointer}

 .ejemplos{display:flex;flex-wrap:wrap;gap:6px;margin-bottom:18px}
 .ej{font-size:12px;padding:5px 11px;background:var(--papel2);
   border:1px solid var(--linea);border-radius:20px;cursor:pointer;color:var(--tinta2)}
 .ej:hover{border-color:var(--ocre);color:var(--ocre)}

 .plan{background:var(--papel2);border:1px solid var(--linea);border-left:2px solid var(--ocre);
   border-radius:0 6px 6px 0;padding:10px 14px;font-family:var(--mono);
   font-size:11.5px;color:var(--tinta2);margin-bottom:14px;overflow-x:auto}
 .plan b{color:var(--tinta)}
 h2{font-family:var(--serif);font-size:18px;font-weight:600;margin:24px 0 10px;
   display:flex;align-items:center;gap:9px}
 h2 .n{font-family:var(--mono);font-size:11px;color:var(--meta);font-weight:400}

 .resp{background:var(--papel2);border:1px solid var(--linea);border-radius:8px;
   padding:20px 22px;font-size:15px;line-height:1.72;box-shadow:var(--sombra)}
 .resp h3{font-family:var(--serif);font-size:16px;margin:16px 0 6px;font-weight:600}
 .resp h3:first-child{margin-top:0}
 .resp ul,.resp ol{margin:6px 0 10px;padding-left:22px}
 .resp li{margin-bottom:4px}
 .resp p{margin:0 0 10px}
 .resp .cita{background:var(--ocre-suave);color:var(--ocre);padding:0 4px;
   border-radius:3px;font-family:var(--mono);font-size:12px;font-weight:600}
 .resp .fuentes{margin-top:16px;padding-top:12px;border-top:1px solid var(--linea);
   font-size:12.5px;color:var(--tinta2)}
 .resp .cierre{margin-top:14px;padding:11px 14px;background:var(--ocre-suave);
   border-radius:6px;font-style:italic;color:var(--tinta)}

 /* --- debate: turnos --- */
 .turno{border-radius:8px;padding:15px 18px;margin-bottom:10px;box-shadow:var(--sombra)}
 .turno.tuyo{background:var(--azul-suave);border:1px solid color-mix(in srgb,var(--azul) 30%,transparent)}
 .turno.agente{background:var(--papel2);border:1px solid var(--linea)}
 .turno-quien{font-family:var(--mono);font-size:10px;text-transform:uppercase;
   letter-spacing:.08em;color:var(--meta);margin-bottom:6px;display:flex;align-items:center;gap:6px}
 .turno.tuyo .turno-quien{color:var(--azul)}
 .turno.agente .turno-quien{color:var(--ocre)}
 .turno-cuerpo{font-size:14.5px;line-height:1.68}
 .turno-cuerpo p{margin:0 0 9px}

 .frag{background:var(--papel2);border:1px solid var(--linea);border-radius:6px;
   padding:12px 14px;margin-bottom:8px}
 .frag-cab{display:flex;gap:9px;align-items:baseline;flex-wrap:wrap;margin-bottom:5px}
 .num{font-family:var(--mono);font-size:12px;font-weight:700;color:var(--ocre);flex:none}
 .doc{font-weight:600;font-size:13.5px}
 .loc{font-family:var(--mono);font-size:11px;color:var(--meta)}
 .pill{font-family:var(--mono);font-size:10px;padding:1.5px 6px;border-radius:3px;
   letter-spacing:.04em;text-transform:uppercase}
 .pill.lectura{background:var(--ocre-suave);color:var(--ocre)}
 .pill.clase{background:color-mix(in srgb,var(--azul) 16%,transparent);color:var(--azul)}
 .pill.rector,.pill.evaluacion,.pill.guion{background:var(--verde-suave);color:var(--verde)}
 .pill.ocr{background:color-mix(in srgb,var(--rojo) 15%,transparent);color:var(--rojo)}
 .cita-b{font-size:12px;color:var(--tinta2);font-style:italic;margin-bottom:6px}
 .ext{font-size:12.5px;color:var(--tinta2);max-height:0;overflow:hidden;
   transition:max-height .2s;border-top:1px solid transparent}
 .frag.open .ext{max-height:400px;overflow-y:auto;padding-top:9px;
   margin-top:7px;border-top:1px solid var(--linea)}
 .toggle{font-size:11px;color:var(--ocre);cursor:pointer;user-select:none;
   font-family:var(--mono)}
 details.evidencia{margin-top:8px}
 details.evidencia>summary{cursor:pointer;font-size:12.5px;color:var(--meta);
   font-family:var(--mono);padding:6px 0;list-style:none;display:flex;align-items:center;gap:6px}
 details.evidencia>summary::-webkit-details-marker{display:none}
 details.evidencia>summary::before{content:"▸";color:var(--ocre)}
 details.evidencia[open]>summary::before{content:"▾"}

 .aviso{background:color-mix(in srgb,var(--rojo) 8%,transparent);
   border-left:2px solid var(--rojo);padding:9px 13px;border-radius:0 4px 4px 0;
   font-size:13px;color:var(--tinta2);margin-bottom:8px}
 .ok{color:var(--verde)} .err{color:var(--rojo)}
 .cmp{display:grid;gap:8px;margin-top:8px}
 .cmp-row{display:grid;grid-template-columns:minmax(88px,auto) 1fr minmax(86px,auto);
   gap:11px;align-items:center;font-size:13px}
 .track{height:20px;background:color-mix(in srgb,var(--linea) 55%,transparent);
   border-radius:3px;overflow:hidden}
 .fill{height:100%;border-radius:3px}
 .val{font-family:var(--mono);font-size:12px;text-align:right;
   font-variant-numeric:tabular-nums;color:var(--tinta2)}
 .cargando{color:var(--meta);font-family:var(--mono);font-size:13px;padding:20px 0;
   display:flex;align-items:center;gap:9px}
 .punto{width:6px;height:6px;border-radius:50%;background:var(--ocre);
   animation:pulso 1.1s ease-in-out infinite}
 @keyframes pulso{0%,100%{opacity:.3}50%{opacity:1}}
 @media(prefers-reduced-motion:reduce){.punto{animation:none}}
 footer{margin-top:36px;padding-top:14px;border-top:1px solid var(--linea);
   font-family:var(--mono);font-size:10.5px;color:var(--meta)}
 @media(max-width:560px){.cmp-row{grid-template-columns:1fr;gap:2px}
   .val{text-align:left}}
</style></head><body>
<div class="wrap">
<header>
  <div>
    <div class="eyebrow">122005 · sección A · 2026-1 · prof. Juan Fonseca</div>
    <h1>Agente de Historia Crítica del Perú</h1>
    <div class="stats" id="stats">cargando…</div>
  </div>
  <div id="badge"></div>
</header>

<nav class="modos" id="modos"></nav>

<div class="panel-intro" id="intro"></div>

<form id="f"></form>

<div class="opts" id="opts">
  <label><input type="checkbox" id="gen"> Generar respuesta con IA <span id="gen-nota" style="color:var(--meta)"></span></label>
</div>

<div class="ejemplos" id="ejemplos"></div>
<div id="salida"></div>

<footer id="pie"></footer>
</div>

<script>
const MODOS = {
  preguntar: {
    icono: "?", nombre: "Preguntar", desc: "Consulta puntual con evidencia",
    intro: "Escribe cualquier pregunta sobre el curso. El agente responde <b>solo</b> con los materiales autorizados, cita cada afirmación y cierra devolviéndote una pregunta — no un resumen que te ahorre pensar.",
    placeholder: "¿Por qué colapsó la población andina en el siglo XVI?",
    boton: "Preguntar", multilinea: false,
    ejemplos: [
      "¿Cuándo es el examen parcial?",
      "¿Por qué colapsó la población andina en el siglo XVI?",
      "¿Qué dice Contreras sobre el centralismo?",
      "¿Qué significó la división norte patriota y sur realista?",
      "¿Qué se ve en la semana 13?",
    ],
  },
  resumen: {
    icono: "≡", nombre: "Resumir", desc: "Condensa un tema o una semana",
    intro: "Pide el resumen de una semana, una unidad o un conjunto de lecturas. Organiza por sub-tema, cita cada punto y <b>no oculta</b> los desacuerdos entre autores solo para que el resumen quede más corto.",
    placeholder: "Resume los temas y lecturas de la semana 2",
    boton: "Resumir", multilinea: false,
    ejemplos: [
      "Resume la semana 2: transiciones demográficas",
      "Resume qué cubre la unidad 2 del curso",
      "Resume las causas del centralismo peruano según Contreras",
      "Resume la semana 6 sobre cambio climático y desastres",
    ],
  },
  explicacion: {
    icono: "∵", nombre: "Explicar por qué", desc: "La cadena causal completa",
    intro: "Pide el <b>razonamiento</b>, no solo el dato: cómo se conectan las causas, en qué orden, y desde qué marco interpretativo lo explica cada autor. Más exigente que \"Preguntar\" — pensado para entender un proceso, no solo recordarlo.",
    placeholder: "¿Por qué el trabajo forzado colonial agravó el colapso demográfico?",
    boton: "Explicar", multilinea: false,
    ejemplos: [
      "¿Por qué el trabajo forzado colonial agravó el colapso demográfico?",
      "¿Por qué Lima concentró el poder frente al resto del país?",
      "¿Por qué se dividió el país entre norte patriota y sur realista?",
      "¿Por qué las haciendas azucareras originaron el aprismo?",
    ],
  },
  debate: {
    icono: "⇄", nombre: "Debatir", desc: "Defiende una postura, el agente la confronta",
    intro: "Escribe tu propia tesis o postura sobre un tema del curso. El agente la reconstruye, busca en la evidencia lo que la <b>sostiene</b> y lo que la <b>tensiona</b>, y te devuelve la pregunta más difícil que el material permita — no cede por cortesía ni gana por autoridad.",
    placeholder: "Yo creo que el colapso demográfico se explica solo por las epidemias, no por la explotación colonial",
    boton: "Debatir", multilinea: true,
    ejemplos: [
      "Creo que el colapso demográfico se explica solo por las epidemias, no por la explotación colonial",
      "El centralismo limeño fue inevitable dada la geografía del país",
      "La independencia del Perú fue más una fractura regional que un proyecto nacional unificado",
    ],
  },
};

const $ = s => document.querySelector(s);
const esc = s => s.replace(/[&<>"]/g, c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));
let API_OK = false;
let modoActual = "preguntar";
let historialDebate = [];   // [{quien:'tuyo'|'agente', texto}]

// --- construir navegacion ---
$("#modos").innerHTML = Object.entries(MODOS).map(([id,m])=>
  `<button class="modo-btn${id==='preguntar'?' activo':''}" data-modo="${id}">`
  + `<span class="modo-ico">${m.icono}</span>`
  + `<span class="modo-nom">${m.nombre}</span>`
  + `<span class="modo-desc">${m.desc}</span></button>`
).join("");

document.querySelectorAll(".modo-btn").forEach(b => b.onclick = () => cambiarModo(b.dataset.modo));

function cambiarModo(id){
  modoActual = id;
  document.querySelectorAll(".modo-btn").forEach(b=>b.classList.toggle("activo", b.dataset.modo===id));
  const m = MODOS[id];
  $("#intro").innerHTML = m.intro;
  $("#ejemplos").innerHTML = m.ejemplos.map(e=>`<span class="ej">${esc(e)}</span>`).join("");
  document.querySelectorAll(".ej").forEach(el=>el.onclick=()=>{
    if(m.multilinea){ $("#q").value = el.textContent; } else { $("#q").value = el.textContent; }
    $("#f").requestSubmit();
  });
  if(id === "debate"){
    $("#f").innerHTML = `<textarea id="q" placeholder="${esc(m.placeholder)}" autocomplete="off"></textarea>`
      + `<button type="submit" id="btn">${m.boton}</button>`;
    if(historialDebate.length){
      $("#salida").innerHTML = "";
      historialDebate.forEach(t => pintarTurno(t.quien, t.texto));
    }
  } else {
    $("#f").innerHTML = `<input type="text" id="q" placeholder="${esc(m.placeholder)}" autocomplete="off">`
      + `<button type="submit" id="btn">${m.boton}</button>`
      + (id==="preguntar" ? `<button type="button" class="sec" id="btn-cmp">Comparar costo</button>` : "");
    if(id !== "debate") $("#salida").innerHTML = "";
    if(id === "preguntar"){ $("#btn-cmp").onclick = compararCosto; }
  }
  $("#f").onsubmit = enviar;
}

fetch("/api/info").then(r=>r.json()).then(d=>{
  $("#stats").innerHTML =
    `<span>${d.documentos} documentos</span><span>${d.bloques.toLocaleString('es')} bloques</span>` +
    `<span>${d.tokens.toLocaleString('es')} tokens</span><span>${d.semanas.length} semanas</span>`;
  API_OK = d.api_disponible;
  $("#badge").innerHTML = d.api_disponible
    ? `<span class="badge on">◆ generación activa · ${d.proveedor} · ${d.modelo}</span>`
    : `<span class="badge off">◇ solo recuperación · sin clave configurada</span>`;
  $("#gen").disabled = !d.api_disponible;
  $("#gen").checked = d.api_disponible;
  $("#gen-nota").textContent = d.api_disponible ? "" : "(crea un archivo .env con tu clave)";
  $("#pie").textContent = `corpus local · la recuperación no sale de esta máquina`;
});

cambiarModo("preguntar");

// --- formatea markdown ligero: negritas, encabezados ###, listas, citas [n] ---
function formatearMD(texto){
  let partes = texto.split(/\n\s*\n/).map(p=>p.trim()).filter(Boolean);
  let html = "", enFuentes = false;
  for(const p of partes){
    const esFuentes = /^(\*\*)?FUENTES/i.test(p) || /^#+\s*FUENTES/i.test(p);
    if(esFuentes){ enFuentes = true; html += `<div class="fuentes">`; }
    let bloque = esc(p)
      .replace(/^#{1,3}\s*(.+)$/gm, "<h3>$1</h3>")
      .replace(/\*\*(.+?)\*\*/g, "<b>$1</b>")
      .replace(/\[(\d+)\]/g, '<span class="cita">[$1]</span>');
    if(/^[-*•]\s/m.test(bloque)){
      const items = bloque.split("\n").filter(l=>l.trim());
      bloque = "<ul>" + items.map(l=>`<li>${l.replace(/^[-*•]\s*/,"")}</li>`).join("") + "</ul>";
    } else if(!/^<h3>/.test(bloque)){
      bloque = `<p>${bloque.replace(/\n/g,"<br>")}</p>`;
    }
    html += bloque;
    if(esFuentes) html += `</div>`;
  }
  return html;
}

async function enviar(ev){
  ev.preventDefault();
  const q = $("#q").value.trim(); if(!q) return;
  $("#btn").disabled = true;

  if(modoActual === "debate"){
    pintarTurno("tuyo", q);
    historialDebate.push({quien:"tuyo", texto:q});
    $("#q").value = "";
  } else {
    $("#salida").innerHTML = tarjetaCargando();
  }

  try{
    const r = await fetch("/api/preguntar", {method:"POST",
      headers:{"Content-Type":"application/json"},
      body: JSON.stringify({pregunta:q, modo:modoActual, generar: $("#gen").checked})});
    render(await r.json());
  }catch(e){
    const msg = `<div class="aviso">Error de conexión: ${esc(String(e))}</div>`;
    if(modoActual === "debate") $("#salida").insertAdjacentHTML("beforeend", msg);
    else $("#salida").innerHTML = msg;
  }
  $("#btn").disabled = false;
}

function tarjetaCargando(texto){
  return `<div class="cargando"><span class="punto"></span> ${texto || "recuperando evidencia del curso…"}</div>`;
}

function pintarTurno(quien, texto, esHtml){
  const etiqueta = quien === "tuyo" ? "Tú" : "Agente";
  const cuerpo = esHtml ? texto : `<p>${esc(texto)}</p>`;
  $("#salida").insertAdjacentHTML("beforeend",
    `<div class="turno ${quien}"><div class="turno-quien">${etiqueta}</div>`
    + `<div class="turno-cuerpo">${cuerpo}</div></div>`);
  window.scrollTo({top: document.body.scrollHeight, behavior:"smooth"});
}

function render(d){
  if(d.error){
    const msg = `<div class="aviso">${esc(d.error)}</div>`;
    if(modoActual === "debate") $("#salida").insertAdjacentHTML("beforeend", msg);
    else $("#salida").innerHTML = msg;
    return;
  }

  const filtros = Object.keys(d.filtros||{}).length
    ? " · filtros " + Object.entries(d.filtros).map(([k,v])=>`${k}=${v}`).join(", ") : "";
  const planHtml = `<div class="plan">consulta <b>${d.tipo}</b> · presupuesto <b>${d.presupuesto.toLocaleString('es')}</b> tok`
     + ` · usados <b>${d.tokens_evidencia.toLocaleString('es')}</b> · <b>${d.paquetes.length}</b> fragmentos`
     + ` · ${d.ms_recuperacion} ms${filtros}</div>`;

  const avisos = (d.avisos||[]).map(a=>`<div class="aviso">${esc(a)}</div>`).join("")
    + (d.error_generacion ? `<div class="aviso">Generación: ${esc(d.error_generacion)}</div>` : "");

  const evidenciaHtml = fragmentosHtml(d.paquetes);

  if(modoActual === "debate"){
    $("#salida").querySelector(".cargando")?.closest(".turno")?.remove();
    if(d.respuesta){
      const cuerpo = formatearMD(d.respuesta) + `<details class="evidencia"><summary>ver evidencia y verificación (${d.paquetes.length} fragmentos)</summary>`
        + planHtml + avisos + verificacionHtml(d) + usoHtml(d) + evidenciaHtml + `</details>`;
      pintarTurno("agente", cuerpo, true);
      historialDebate.push({quien:"agente", texto:cuerpo, esHtml:true});
    } else {
      pintarTurno("agente", planHtml + avisos + evidenciaHtml, true);
    }
    return;
  }

  // modos no conversacionales: preguntar / resumen / explicacion
  let h = planHtml + avisos;
  if(d.respuesta){
    const etiquetaResp = {resumen:"Resumen", explicacion:"Explicación"}[d.modo] || "Respuesta";
    h += `<h2>${etiquetaResp}</h2><div class="resp">${formatearMD(d.respuesta)}</div>`;
    h += verificacionHtml(d) + usoHtml(d);
  }
  h += `<h2>Evidencia recuperada <span class="n">(${d.paquetes.length})</span></h2>`;
  h += d.paquetes.length ? evidenciaHtml
     : `<div class="aviso">Ninguna fuente autorizada del curso responde a esto.</div>`;

  $("#salida").innerHTML = h;
  activarToggles();
}

function verificacionHtml(d){
  if(!d.verificacion) return "";
  const v = d.verificacion;
  let s = `<div class="plan" style="margin-top:9px">verificación de citas: `;
  s += v.problemas.length
    ? `<span class="err">${v.problemas.map(esc).join(" · ")}</span>`
    : `<span class="ok">todas las citas existen y los párrafos tienen respaldo</span>`;
  s += v.citadas.length ? ` · usadas [${v.citadas.join("] [")}]</div>` : `</div>`;
  return s;
}

function usoHtml(d){
  if(!d.uso) return "";
  return `<div class="plan">tokens · entrada <b>${d.uso.entrada.toLocaleString('es')}</b>`
    + ` · salida <b>${d.uso.salida.toLocaleString('es')}</b>`
    + (d.uso.cache_lectura ? ` · caché leído <b>${d.uso.cache_lectura.toLocaleString('es')}</b>` : "")
    + ` · ${d.uso.ms} ms · ${esc(d.uso.proveedor)} · ${esc(d.uso.modelo)}</div>`;
}

function fragmentosHtml(paquetes){
  return (paquetes||[]).map(p=>{
    let s = `<div class="frag"><div class="frag-cab">`
       + `<span class="num">[${p.n}]</span><span class="doc">${esc(p.documento)}</span>`
       + `<span class="pill ${p.tipo}">${p.tipo}</span>`
       + (p.ocr?`<span class="pill ocr">ocr</span>`:``)
       + `<span class="loc">${esc(p.ubicacion)} · U${p.unidad||"–"}/S${p.semana||"–"} · ${p.tokens} tok</span>`
       + `</div>`;
    if(p.cita && p.cita !== p.documento) s += `<div class="cita-b">${esc(p.cita)}</div>`;
    s += `<span class="toggle">ver extracto ▾</span><div class="ext">${esc(p.extracto)}…</div></div>`;
    return s;
  }).join("");
}

function activarToggles(){
  document.querySelectorAll(".toggle").forEach(t=>t.onclick=()=>{
    const f = t.closest(".frag"); f.classList.toggle("open");
    t.textContent = f.classList.contains("open") ? "ocultar ▴" : "ver extracto ▾";
  });
}

async function compararCosto(){
  const q = $("#q").value.trim(); if(!q) return;
  $("#salida").innerHTML = tarjetaCargando("midiendo estrategias…");
  const r = await fetch("/api/comparar",{method:"POST",
    headers:{"Content-Type":"application/json"}, body:JSON.stringify({pregunta:q})});
  const d = await r.json();
  const max = d.completo || 1;
  const fila = (n,v,c) => v ? `<div class="cmp-row"><span>${n}</span>`
     + `<span class="track"><span class="fill" style="width:${Math.max(v/max*100,.4)}%;background:${c}"></span></span>`
     + `<span class="val">${v.toLocaleString('es')} tok</span></div>` : "";
  $("#salida").innerHTML = `<h2>Costo por estrategia</h2><div class="cmp">`
    + fila("Todo el curso", d.completo, "var(--tinta2)")
    + fila(d.semana?`Semana ${d.semana}`:"Sección", d.seccion, "var(--azul)")
    + fila("Recuperación", d.recuperacion, "var(--ocre)")
    + `</div><div class="plan" style="margin-top:14px">`
    + `contexto completo = <b>${d.documentos_completo}</b> documentos · `
    + `<b>${(d.completo/Math.max(d.recuperacion,1)).toFixed(0)}×</b> más entrada que recuperación`
    + `</div>`;
}
</script></body></html>"""


# ---------------------------------------------------------------- main

def ip_local():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80)); ip = s.getsockname()[0]; s.close()
        return ip
    except Exception:
        return "127.0.0.1"


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--puerto", type=int, default=5000)
    ap.add_argument("--red", action="store_true",
                    help="accesible desde otros equipos de la red local")
    a = ap.parse_args()

    if not os.path.exists(IDX_PATH):
        print("Falta corpus/indice.pkl — corre primero: python reconstruir_todo.py")
        sys.exit(1)

    cargar_indice()
    host = "0.0.0.0" if a.red else "127.0.0.1"
    prov, modelo = proveedor_activo()

    print("=" * 66)
    print("  Agente · Historia Crítica del Perú")
    print("=" * 66)
    print(f"  documentos : {len(IDX['docs'])}")
    print(f"  bloques    : {len(IDX['bloques'])}")
    if prov:
        print(f"  generación : activa · {prov} · {modelo}")
    else:
        print("  generación : inactiva — crea un archivo .env con tu clave")
        print("               (copia .env.ejemplo como .env)")
    print()
    print(f"  local      : http://127.0.0.1:{a.puerto}")
    if a.red:
        print(f"  en la red  : http://{ip_local()}:{a.puerto}")
        print("               (si no abre desde otro equipo, revisa el firewall de Windows)")
    else:
        print("               usa --red para permitir acceso desde otros equipos")
    print("=" * 66)

    app.run(host=host, port=a.puerto, debug=False, threaded=True)
