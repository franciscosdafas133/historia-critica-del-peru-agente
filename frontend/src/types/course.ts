/**
 * Modelo de dominio: curso, estructura académica y materiales.
 * Refleja la forma real de corpus/manifiesto.json (unidad -> semana -> documentos),
 * para que conectar el backend real más adelante no requiera remodelar tipos.
 */

export type MaterialType = 'clase' | 'lectura' | 'evaluacion' | 'guion' | 'rector'

export type TopicStatus = 'not_started' | 'in_progress' | 'understood' | 'needs_review'

export interface Material {
  id: string
  title: string
  type: MaterialType
  authors: string[]
  /** Ruta relativa de origen, solo para referencia visual (no se sirve el archivo en esta fase). */
  sourceFile: string
  pageCount: number
  tokens: number
  isScanned: boolean
}

export interface Topic {
  id: string
  title: string
  status: TopicStatus
  materialIds: string[]
}

export interface Week {
  id: string
  number: number
  dateRange: string
  theme: string
  topics: Topic[]
  materialIds: string[]
  isExamWeek: boolean
}

export interface Unit {
  id: string
  number: number
  title: string
  weeks: Week[]
}

export interface Course {
  id: string
  slug: string
  code: string
  name: string
  professor: string
  department: string
  credits: number
  period: string
  section: string
  totalMaterials: number
  units: Unit[]
}

export interface Student {
  id: string
  firstName: string
  fullName: string
}
