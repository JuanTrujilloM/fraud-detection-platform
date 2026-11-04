import axios from 'axios';

/** Primer mensaje legible de una respuesta de error de DRF. */
export function mensajeDeError(error: unknown, porDefecto = 'No se pudo completar la operación.') {
  if (!axios.isAxiosError(error) || !error.response) {
    return axios.isAxiosError(error) ? 'No hay conexión con el servidor.' : porDefecto;
  }
  const datos = error.response.data as unknown;
  if (error.response.status >= 500 || typeof datos !== 'object' || datos === null) {
    return porDefecto;
  }
  const { detail, ...campos } = datos as Record<string, unknown>;
  if (error.response.status === 401) return porDefecto;
  if (typeof detail === 'string') return detail;
  for (const valor of Object.values(campos)) {
    if (Array.isArray(valor) && typeof valor[0] === 'string') return valor[0];
    if (typeof valor === 'string') return valor;
  }
  return porDefecto;
}
