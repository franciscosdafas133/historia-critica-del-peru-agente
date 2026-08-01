/**
 * Mapeo compartido entre el mock y el backend real: convierte los paquetes
 * de evidencia que devuelve /api/preguntar en el tipo Evidence del frontend,
 * y calcula el estado de confianza cualitativo a partir de esa evidencia.
 */
import type { Evidence, ConfidenceState } from '@/types/study'
import type { MaterialType } from '@/types/course'

export function confidenceFrom(evidence: Evidence[]): ConfidenceState {
  const hasInterpretation = evidence.some((e) => e.supportLevel === 'interpretation')
  const directCount = evidence.filter((e) => e.supportLevel === 'direct').length
  return {
    level: evidence.length === 0 ? 'insufficient' : directCount > 0 ? 'strong' : 'partial',
    supportingCount: evidence.length,
    hasInterpretation,
  }
}

/** Forma real de cada elemento de `paquetes` en la respuesta de /api/preguntar
 * (ver servidor.py, api_preguntar()). */
export interface BackendPaquete {
  n: number
  documento: string
  cita: string
  ubicacion: string
  archivo: string
  tipo: string
  autoridad: string
  unidad: number | null
  semana: number | null
  tokens: number
  score: number
  cobertura: number | null
  ocr: boolean
  extracto: string
}

/** El backend no distingue "direct"/"context"/"interpretation" explícitamente
 * (esa distinción la hace el LLM en prosa, no como campo). Se aproxima con la
 * cobertura léxica del paquete: cobertura alta sugiere respaldo directo al
 * tema preguntado; el resto se trata como contexto complementario. Es una
 * heurística del cliente, no algo que el modelo decida. */
function supportLevelFrom(paquete: BackendPaquete): Evidence['supportLevel'] {
  if (paquete.cobertura !== null && paquete.cobertura > 0.6) return 'direct'
  return 'context'
}

/** El backend agrupa autores dentro de `cita` (referencia bibliográfica
 * completa) en vez de un array separado. Se extrae heurísticamente el
 * fragmento antes del primer paréntesis de año, si existe. */
function authorsFrom(cita: string): string[] {
  const match = cita.match(/^([^(]+)\(\d{4}/)
  if (!match) return []
  return [match[1].trim().replace(/,\s*$/, '')]
}

export function evidenceFromPaquetes(paquetes: BackendPaquete[]): Evidence[] {
  return paquetes.map((p) => ({
    id: String(p.n),
    referenceNumber: p.n,
    materialTitle: p.documento,
    authors: authorsFrom(p.cita),
    materialType: p.tipo as MaterialType,
    location: p.ubicacion,
    excerpt: p.extracto,
    supportLevel: supportLevelFrom(p),
  }))
}
