# Nexo Académico — Frontend

Interfaz de estudio del agente universitario para el curso **Historia
Crítica del Perú** (prof. Juan Fonseca). Explícitamente no un chatbot: mesa
de estudio digital con navegación por temas, seis modos de estudio
interactivos y un panel de evidencias citadas.

**Conexión a backend real:** si se define `VITE_API_URL`, la app usa
`httpStudyService` y conversa de verdad con el backend Flask (recuperación +
Gemini) — ver `.env.example`. Sin esa variable, cae automáticamente a
servicios 100% simulados (`src/mocks/`), útil para desarrollar la interfaz
sin depender de la API. `courseService` (estructura de unidades/semanas/
temas) sigue siendo simulado en ambos casos — es metadata de navegación, no
contenido generado por el tutor. El progreso del estudiante (última
actividad, resultados de evaluación, tarjetas repasadas) se persiste solo en
`localStorage` del navegador.

## Requisitos

- Node.js 18+ y npm
- Para conectar al backend real: el servidor Flask corriendo (ver README de
  la raíz del proyecto) y una API key de Gemini/Anthropic configurada ahí

## Instalación y ejecución

```bash
cd frontend
npm install
cp .env.example .env.local   # opcional: apunta a un backend real
npm run dev
```

La app queda disponible en **http://localhost:5173/**.

Otros comandos:

```bash
npm run build      # build de producción a dist/
npx tsc --noEmit   # chequeo de tipos estricto sin emitir archivos
```

## Rutas principales

| Ruta | Descripción |
|---|---|
| `/` | Dashboard personalizado: curso activo, progreso, próxima actividad, temas débiles, actividad reciente |
| `/cursos/historia-critica-del-peru` | Vista general del curso: unidades, semanas, temas con estado, materiales recientes |
| `/cursos/historia-critica-del-peru/estudiar` | Sala de estudio (layout de 3 columnas): navegación de temas, selector de modo, conversación, panel de evidencias |
| `/historial`, `/progreso`, `/ajustes` | Pantallas complementarias (algunas secciones marcadas "Próximamente" cuando aún no están desarrolladas) |

## Modos de estudio (todos interactivos, no maquetas estáticas)

- **Entender** — pregunta libre; con backend real, respuesta narrativa citada del tutor (modo `preguntar`)
- **Resolver** — intento del estudiante + retroalimentación citada, sin entregar la respuesta (modo `resolver`)
- **Practicar** — preguntas de opción múltiple con corrección y explicación citada (modo `practicar`)
- **Evaluarme** — microevaluación de 3 preguntas generadas (modo `evaluar`), guarda resultados en `localStorage`
- **Repasar** — tarjetas tipo flashcard generadas por tema (modo `repasar`)
- **Debatir** — el estudiante plantea una tesis, el tutor la confronta con evidencia a favor y en contra (modo `debate`)

## Panel de evidencias

Cada respuesta muestra evidencias con número de referencia, título, autor,
página/diapositiva, extracto, tipo de material y nivel de respaldo (directo,
contextual, interpretativo). El modal de vista previa de fuente incluye el
aviso: *"Vista previa del prototipo. La apertura del documento original se
conectará en la fase backend."* Los estados de confianza son siempre
cualitativos — no se inventan porcentajes.

## Estructura del código

```
src/
  app/            rutas y páginas
  components/     primitivos de UI accesibles (Button, Modal, Drawer, etc.)
  config/         configuración centralizada (nombre del producto, claves de localStorage)
  features/       componentes de dominio (dashboard, curso, estudio, evidencias)
  hooks/          useTheme, useMediaQuery
  mocks/          datos simulados de curso, materiales y estudio
  services/       capa de servicios (CourseService, StudyService, progressService)
                  con implementaciones mock, preparada para reemplazarse por
                  llamadas HTTP reales sin tocar los componentes
  types/          tipos TypeScript del dominio (curso, estudio)
```

## Estado de verificación

- `npx tsc --noEmit` y `npm run build`: sin errores
- Los 8 modos del backend (`preguntar`, `resumen`, `explicacion`, `debate`, `resolver`, `practicar`, `evaluar`, `repasar`) probados vía HTTP real contra `servidor.py`
- CORS verificado: origen del frontend permitido, orígenes no autorizados sin header de acceso
- Verificación visual automatizada por navegador headless no se pudo completar en este entorno — se recomienda abrir `http://localhost:5173/` en un navegador real para la revisión visual final
