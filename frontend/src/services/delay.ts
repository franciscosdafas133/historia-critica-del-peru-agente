/** Simula latencia de red breve para mostrar estados de carga sin volver la app lenta. */
export function delay(ms = 400): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms))
}
