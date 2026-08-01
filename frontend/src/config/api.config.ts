/**
 * URL base del backend real. Si no está definida (VITE_API_URL ausente),
 * la app cae automáticamente a los servicios simulados — ver
 * src/services/studyService.ts, punto de sustitución al final del archivo.
 */
export const API_BASE_URL = import.meta.env.VITE_API_URL as string | undefined
