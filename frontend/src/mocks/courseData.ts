/**
 * Datos simulados del curso piloto.
 *
 * La estructura (unidades, semanas, temas, fechas, tipos y autores de
 * materiales) refleja los metadatos reales de corpus/manifiesto.json y
 * construir_corpus.py — no son datos inventados en su organización, aunque
 * el contenido conversacional del tutor (features/study) sí es simulado y
 * está claramente marcado como demostración en la interfaz.
 *
 * Cuando exista backend real, este archivo se reemplaza por llamadas HTTP
 * dentro de services/courseService.ts sin tocar los componentes.
 */
import type { Course, Material, Topic } from '@/types/course'

const material = (
  id: string,
  title: string,
  type: Material['type'],
  authors: string[],
  sourceFile: string,
  pageCount: number,
  tokens: number,
  isScanned = false,
): Material => ({ id, title, type, authors, sourceFile, pageCount, tokens, isScanned })

const topic = (id: string, title: string, materialIds: string[], status: Topic['status'] = 'not_started'): Topic => ({
  id,
  title,
  status,
  materialIds,
})

export const PILOT_COURSE: Course = {
  id: 'crs-122005',
  slug: 'historia-critica-del-peru',
  code: '122005',
  name: 'Historia Crítica del Perú',
  professor: 'Juan Fonseca',
  department: 'Humanidades',
  credits: 4,
  period: '2026-1',
  section: 'A',
  totalMaterials: 39,
  units: [
    {
      id: 'u1',
      number: 1,
      title: 'Demografía, territorio y medioambiente en el Perú',
      weeks: [
        {
          id: 'w1',
          number: 1,
          dateRange: '16–22 marzo',
          theme: 'Conceptos demográficos y principales indicadores',
          isExamWeek: false,
          materialIds: ['m-s1-clase1', 'm-s1-clase1a', 'm-s1-clase2', 'm-s1-amatleon', 'm-s1-aramburu', 'm-s1-moneda'],
          topics: [
            topic('t-poblacion-crecimiento', 'Población y crecimiento', ['m-s1-clase1', 'm-s1-amatleon'], 'understood'),
            topic('t-indicadores-demograficos', 'Indicadores demográficos', ['m-s1-clase2', 'm-s1-moneda'], 'in_progress'),
          ],
        },
        {
          id: 'w2',
          number: 2,
          dateRange: '23–29 marzo',
          theme: 'Transiciones demográficas y epidemiológicas',
          isExamWeek: false,
          materialIds: ['m-s2-clase1', 'm-s2-clase2', 'm-s2-aramburu-mendoza', 'm-s2-contreras94', 'm-s2-contreras20'],
          topics: [
            topic('t-transiciones-demograficas', 'Transiciones demográficas en el Perú', ['m-s2-clase1', 'm-s2-contreras20'], 'needs_review'),
            topic('t-intercambio-colonial', 'Intercambio colonial y enfermedades', ['m-s2-clase2', 'm-s2-contreras94'], 'not_started'),
          ],
        },
        {
          id: 'w3',
          number: 3,
          dateRange: '30 marzo–5 abril',
          theme: 'Geografía del Perú: Andes, cuencas, El Niño',
          isExamWeek: false,
          materialIds: ['m-s3-clase1', 'm-s3-caviedes', 'm-s3-torero'],
          topics: [
            topic('t-geografia-andina', 'Geografía andina y cuencas', ['m-s3-clase1'], 'not_started'),
            topic('t-fenomeno-nino', 'El fenómeno de El Niño', ['m-s3-caviedes'], 'not_started'),
          ],
        },
        {
          id: 'w4',
          number: 4,
          dateRange: '6–12 abril',
          theme: 'Organización del territorio; ciudades y redes urbanas',
          isExamWeek: false,
          materialIds: ['m-s4-clase1', 'm-s4-clase2', 'm-s4-contreras02', 'm-s4-marzal', 'm-s4-sobrevilla'],
          topics: [
            topic('t-centralismo', 'El centralismo peruano', ['m-s4-contreras02'], 'not_started'),
            topic('t-ciudades-intermedias', 'Ciudades intermedias y redes urbanas', ['m-s4-marzal'], 'not_started'),
          ],
        },
        {
          id: 'w5',
          number: 5,
          dateRange: '13–19 abril',
          theme: 'Esquema urbano-rural y redes urbanas',
          isExamWeek: false,
          materialIds: ['m-s5-clase1', 'm-s5-espinoza'],
          topics: [topic('t-reorganizacion-territorial', 'Reorganizar el Perú: ciudades intermedias', ['m-s5-espinoza'], 'not_started')],
        },
        {
          id: 'w6',
          number: 6,
          dateRange: '20–26 abril',
          theme: 'Cambio climático, desastres y políticas de desarrollo',
          isExamWeek: false,
          materialIds: ['m-s6-clase1', 'm-s6-clase2', 'm-s6-carey'],
          topics: [topic('t-glaciares-clima', 'Glaciares y cambio climático', ['m-s6-carey'], 'not_started')],
        },
        {
          id: 'w7',
          number: 7,
          dateRange: '27 abril–3 mayo',
          theme: 'El caso de la región Áncash',
          isExamWeek: false,
          materialIds: ['m-s7-clase1'],
          topics: [topic('t-ancash', 'Estudio de caso: Áncash', ['m-s7-clase1'], 'not_started')],
        },
        {
          id: 'w8',
          number: 8,
          dateRange: '4–10 mayo',
          theme: 'Exámenes parciales (5 de mayo)',
          isExamWeek: true,
          materialIds: [],
          topics: [],
        },
      ],
    },
    {
      id: 'u2',
      number: 2,
      title: 'Procesos socioeconómicos y recursos naturales en los espacios regionales',
      weeks: [
        {
          id: 'w9',
          number: 9,
          dateRange: '11–17 mayo',
          theme: 'La idea de nación; construcción del Estado nacional',
          isExamWeek: false,
          materialIds: ['m-s9-contreras-cueto', 'm-s9-contreras-nacion'],
          topics: [topic('t-idea-nacion', 'La idea de nación', ['m-s9-contreras-nacion'], 'not_started')],
        },
        {
          id: 'w10',
          number: 10,
          dateRange: '18–24 mayo',
          theme: 'Regiones y macrorregiones; la costa norte colonial',
          isExamWeek: false,
          materialIds: ['m-s10-aldana', 'm-s10-rivasplata'],
          topics: [topic('t-costa-norte', 'La costa norte colonial', ['m-s10-rivasplata'], 'not_started')],
        },
        {
          id: 'w11',
          number: 11,
          dateRange: '25–31 mayo',
          theme: 'Independencia: norte patriota y sur realista',
          isExamWeek: false,
          materialIds: ['m-s11-ophelan'],
          topics: [topic('t-norte-sur-independencia', 'Norte patriota y sur realista', ['m-s11-ophelan'], 'not_started')],
        },
        {
          id: 'w12',
          number: 12,
          dateRange: '1–7 junio',
          theme: 'Haciendas azucareras y APRA; sur andino prehispánico',
          isExamWeek: false,
          materialIds: ['m-s12-klaren'],
          topics: [topic('t-haciendas-apra', 'Haciendas azucareras y el APRA', ['m-s12-klaren'], 'not_started')],
        },
        {
          id: 'w13',
          number: 13,
          dateRange: '8–14 junio',
          theme: 'Sur andino colonial; Confederación Perú-Boliviana',
          isExamWeek: false,
          materialIds: ['m-s13-cahill'],
          topics: [topic('t-confederacion', 'Confederación Perú-Boliviana', ['m-s13-cahill'], 'not_started')],
        },
        {
          id: 'w14',
          number: 14,
          dateRange: '15–21 junio',
          theme: 'Arequipa siglo XIX; movimientos indígenas siglo XX',
          isExamWeek: false,
          materialIds: ['m-s14-renique'],
          topics: [topic('t-movimientos-indigenas', 'Movimientos indígenas del siglo XX', ['m-s14-renique'], 'not_started')],
        },
      ],
    },
  ],
}

export const MATERIALS: Record<string, Material> = Object.fromEntries(
  [
    material('m-s1-clase1', 'Conceptos demográficos', 'clase', [], 'Clase_S1_1_Conceptosdemográficos_2025_2.pdf', 18, 1697),
    material('m-s1-clase1a', 'Introducción a la Historia Crítica', 'clase', [], 'Clase_S1_1a_Historia_Crítica.pdf', 8, 258),
    material('m-s1-clase2', 'Indicadores demográficos', 'clase', [], 'Clase_S1_2_Indicadores_demográficos_2026_1.pdf', 18, 1409),
    material('m-s1-amatleon', 'El Perú nuestro de cada día', 'lectura', ['Amat y León, C.'], 'Amat_y_León_2012_Perúnuestrodecadadía.pdf', 19, 13218),
    material('m-s1-aramburu', 'Una población diferente (pp. 55-72)', 'lectura', ['Aramburú, C.'], 'Aramburú_2012_Poblacióndiferente_pags-55-72.pdf', 18, 12212),
    material('m-s1-moneda', 'Revista Moneda 190-07', 'lectura', ['BCRP'], 'moneda-190-07.pdf', 5, 6919),

    material('m-s2-clase1', 'Transiciones demográficas', 'clase', [], 'Clase_S2_1_Transiciones_demográficas_2026_1.pdf', 34, 5794),
    material('m-s2-clase2', 'Intercambios coloniales y enfermedades', 'clase', [], 'Clase_S2_2_Intercambios_coloniales_enfermedades_2026_1.pdf', 40, 5181),
    material('m-s2-aramburu-mendoza', 'El futuro de la población peruana', 'lectura', ['Aramburú, C.', 'Mendoza, W.'], 'Aramburú_Mendoza_2015_Futuro_población_peruana.pdf', 20, 13505),
    material('m-s2-contreras94', 'Orígenes de la explosión demográfica', 'lectura', ['Contreras, C.'], 'Contreras_1994_Orígenes_explosión_demográfica.pdf', 29, 32237),
    material('m-s2-contreras20', 'Crisis demográfica del siglo XVI', 'lectura', ['Contreras, C.'], 'Contreras_2020_Crisisdemográfica_sigloXVI.pdf', 19, 25810),

    material('m-s3-clase1', 'Pluralismo médico y transiciones epidemiológicas', 'clase', [], 'Clase_S3_1_Pluralismo_Médico_Transiciones_Epidemiológicas_2026_1.pdf', 28, 5729),
    material('m-s3-caviedes', 'Imprints of El Niño in World History', 'lectura', ['Caviedes, C.'], 'Cavieses_2001_Imprints_El_Niño.pdf', 44, 24522, true),
    material('m-s3-torero', 'Cómo enfrentar una geografía adversa', 'lectura', ['Torero, M.', 'Escobal, J.'], 'Torero_Escobal_2000_Como_enfrentar_una_geografia_adversa.pdf', 9, 6293),

    material('m-s4-clase1', 'Organización del territorio (I)', 'clase', [], 'Clase_Semana4_1_2026_1.pdf', 37, 4198),
    material('m-s4-clase2', 'Organización del territorio (II)', 'clase', [], 'Clase_Semana4_2_2026_1.pdf', 23, 2192),
    material('m-s4-contreras02', 'El centralismo peruano en su perspectiva histórica', 'lectura', ['Contreras, C.'], 'Contreras_2002_Centralismo_peruano.pdf', 35, 29579),
    material('m-s4-marzal', 'Ciudades intermedias', 'lectura', ['Marzal, V.', 'Ludeña, W.'], 'Marzal_Ludeña_2017_Ciudadesintermedias.pdf', 18, 8964),
    material('m-s4-sobrevilla', 'Disputa de jurisdicciones', 'lectura', ['Sobrevilla, N.'], 'Sobrevilla_2021_Disputa_jurisdicciones.pdf', 50, 38251, true),

    material('m-s5-clase1', 'Esquema urbano-rural', 'clase', [], 'Clase_Semana_5_1_2026_1_HCP.pdf', 28, 3112),
    material('m-s5-espinoza', 'Reorganizar el Perú: ciudades intermedias', 'lectura', ['Espinoza, A.', 'Fort, R.', 'Espinoza, M.'], 'Espinoza_Fort_Espinoza_2022_Reorganizar_el Perú.pdf', 33, 17112),

    material('m-s6-clase1', 'Cambio climático (I)', 'clase', [], 'Clase_Semana_6_1_HCP_2026_1.pptx', 41, 4727),
    material('m-s6-clase2', 'Cambio climático (II)', 'clase', [], 'Clase_Semana_6_2_HCP_2026_1.pptx', 24, 3635),
    material('m-s6-carey', 'Glaciares, cambio climático y desastres', 'lectura', ['Carey, M.'], 'Carey_2014_Glaciares_CambioClimático_caps_3_4.pdf', 50, 65189, true),

    material('m-s7-clase1', 'El caso de la región Áncash', 'clase', [], 'Clase_Semana_7_1_HCP_2026_1.pptx', 21, 4054),

    material('m-s9-contreras-cueto', 'Caminos, ciencia y Estado', 'lectura', ['Contreras, C.', 'Cueto, M.'], 'Contreras_Cueto_2008_Caminos_Ciencia_Estado.pdf', 21, 20040),
    material('m-s9-contreras-nacion', 'El concepto de nación', 'lectura', ['Contreras, C.'], 'Contreras_sf_Concepto_Nación.pdf', 12, 5374),

    material('m-s10-aldana', 'Regiones vivas y activas', 'lectura', ['Aldana, S.', 'Pereyra, N.'], 'Aldana_Pereyra_2022_Regiones vivas y activas.pdf', 68, 99330),
    material('m-s10-rivasplata', 'Cambio de paisajes en la costa norte', 'lectura', ['Rivasplata Varillas, P.'], 'RivasplataVarillas_2014_Cambio_paisajes_costa_norte.pdf', 33, 32121),

    material('m-s11-ophelan', 'El norte patriota y el sur realista', 'lectura', ["O'Phelan, S."], 'O_Phelan_2019_Norte_patriota_Sur_realista.pdf', 68, 36181, true),

    material('m-s12-klaren', 'Haciendas azucareras y orígenes del APRA', 'lectura', ['Klarén, P.'], 'Klarén_1976_Haciendas_Azucareras_Apra.pdf', 224, 146486),

    material('m-s13-cahill', 'Independencia, sociedad y fiscalidad', 'lectura', ['Cahill, D.'], 'Cahill_1993_Independencia_sociedad_fiscalidad.pdf', 33, 15882),

    material('m-s14-renique', 'La nación radical (cap. 4)', 'lectura', ['Rénique, J. L.'], 'Renique_2022_Nación_Radical_cap.4.pdf', 34, 21823),
  ].map((m) => [m.id, m]),
)
