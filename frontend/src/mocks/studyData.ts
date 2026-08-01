/**
 * Contenido conversacional y pedagógico simulado.
 *
 * A diferencia de courseData.ts (estructura real del curso), el contenido
 * de aquí —explicaciones, preguntas, retroalimentación— es demostrativo.
 * La interfaz lo marca explícitamente como simulación en el modal de fuente
 * y en las respuestas del tutor, tal como exige esta fase del proyecto.
 */
import type { DebateResponse, Evidence, PracticeQuestion, ReviewCard, UnderstandAnswer } from '@/types/study'

export const MOCK_EVIDENCE: Record<string, Evidence> = Object.fromEntries(
  (
    [
      {
        id: 'ev-1',
        referenceNumber: 1,
        materialTitle: 'Crisis demográfica del siglo XVI',
        authors: ['Contreras, C.'],
        materialType: 'lectura',
        location: 'pp. 7-9',
        excerpt:
          'La población andina se redujo drásticamente entre 1520 y 1620 debido a la conjunción de epidemias, guerra y desestructuración del sistema de trabajo colectivo…',
        supportLevel: 'direct',
      },
      {
        id: 'ev-2',
        referenceNumber: 2,
        materialTitle: 'Transiciones demográficas',
        authors: [],
        materialType: 'clase',
        location: 'diapositivas 5-8',
        excerpt:
          'La transición demográfica del Perú se explica en cuatro etapas: preindustrial, inicio de transición, transición plena y postransición…',
        supportLevel: 'context',
      },
      {
        id: 'ev-3',
        referenceNumber: 3,
        materialTitle: 'Orígenes de la explosión demográfica',
        authors: ['Contreras, C.'],
        materialType: 'lectura',
        location: 'pp. 12-14',
        excerpt:
          'Contreras sostiene que el crecimiento poblacional posterior a 1940 respondió principalmente a la caída de la mortalidad, no a un aumento de la natalidad…',
        supportLevel: 'interpretation',
      },
    ] satisfies Evidence[]
  ).map((e) => [e.id, e]),
)

export const MOCK_UNDERSTAND_ANSWER: UnderstandAnswer = {
  mainIdea:
    'La población andina colapsó entre los siglos XVI y XVII por la combinación de epidemias, violencia de la conquista y desarticulación del sistema de trabajo colectivo incaico.',
  explanation:
    'No fue un único factor: las epidemias de viruela y sarampión llegaron sin inmunidad previa en la población, mientras la guerra y el desplazamiento forzado de mano de obra hacia la minería rompieron las redes de subsistencia tradicionales. Estos factores se retroalimentaron —la crisis de subsistencia hizo a la población más vulnerable a las enfermedades, y la mortalidad epidémica dificultó sostener el trabajo agrícola.',
  example:
    'En algunas regiones andinas, censos coloniales tempranos registran caídas poblacionales de más del 80% en menos de un siglo, un ritmo de despoblación sin precedente en los registros disponibles para el periodo.',
  checkQuestion: '¿Qué evidencia usarías para argumentar que la epidemia, y no solo la violencia, fue el factor dominante?',
}

export const MOCK_PRACTICE_QUESTIONS: PracticeQuestion[] = [
  {
    id: 'pq-1',
    topicId: 't-transiciones-demograficas',
    prompt: '¿Cuál de las siguientes NO es una de las etapas clásicas de la transición demográfica descritas en clase?',
    options: [
      'Etapa preindustrial',
      'Inicio de la transición',
      'Transición plena',
      'Etapa de reconquista',
    ],
    correctAnswer: 'Etapa de reconquista',
    explanation:
      'La "etapa de reconquista" no forma parte del modelo de transición demográfica; es un concepto de historia política, no demográfica. Las cuatro etapas reales son: preindustrial, inicio de transición, transición plena y postransición.',
    evidenceIds: ['ev-2'],
  },
  {
    id: 'pq-2',
    topicId: 't-transiciones-demograficas',
    prompt: 'Según Contreras (1994), ¿qué explica principalmente el crecimiento poblacional posterior a 1940?',
    options: [
      'Un fuerte aumento de la natalidad',
      'La caída sostenida de la mortalidad',
      'La migración internacional',
      'Las políticas de colonización de la Amazonía',
    ],
    correctAnswer: 'La caída sostenida de la mortalidad',
    explanation:
      'Contreras argumenta que el crecimiento no se explica por un aumento de nacimientos, sino por la reducción de la mortalidad —principalmente infantil— gracias a mejoras sanitarias.',
    evidenceIds: ['ev-3'],
  },
]

export const MOCK_DEBATE_RESPONSE: DebateResponse = {
  restatedThesis:
    'Entiendo tu postura así: la epidemia fue el factor decisivo del colapso demográfico andino, y la violencia de la conquista fue secundaria frente a eso. ¿Es una reconstrucción justa de tu tesis?',
  supportingEvidence: [MOCK_EVIDENCE['ev-1']].filter((e): e is Evidence => Boolean(e)),
  tensioningEvidence: [MOCK_EVIDENCE['ev-3']].filter((e): e is Evidence => Boolean(e)),
  verdict:
    'Tu tesis tiene respaldo real: Contreras documenta la epidemia como factor central de la caída poblacional en el siglo XVI. Pero el material también advierte que aislar la epidemia de la desestructuración del trabajo colectivo simplifica una cadena causal que la fuente presenta como interdependiente, no secuencial.',
  closingQuestion:
    'Si la epidemia hubiera llegado sin la ruptura previa del sistema de trabajo colectivo, ¿el material permite sostener que la mortalidad habría sido igual de severa, o esa desestructuración es parte de la causa y no solo su consecuencia?',
}

export const MOCK_REVIEW_CARDS: ReviewCard[] = [
  {
    id: 'rc-1',
    topicId: 't-transiciones-demograficas',
    question: '¿Qué distingue a la etapa de "transición plena" de la "postransición"?',
    answer:
      'En transición plena la mortalidad ya cayó pero la natalidad se mantiene alta, generando fuerte crecimiento poblacional; en postransición ambas tasas son bajas y el crecimiento se estabiliza.',
    evidenceIds: ['ev-2'],
  },
  {
    id: 'rc-2',
    topicId: 't-intercambio-colonial',
    question: '¿Qué papel jugó la ausencia de inmunidad previa en el impacto de las epidemias coloniales?',
    answer:
      'La población andina no había tenido contacto previo con enfermedades como la viruela, por lo que carecía de inmunidad adquirida, lo que amplificó drásticamente la mortalidad frente a Europa, donde esas enfermedades eran endémicas.',
    evidenceIds: ['ev-1'],
  },
]
