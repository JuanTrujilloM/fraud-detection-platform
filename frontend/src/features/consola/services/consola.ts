import type { Reclamo } from '@/features/portal/services/portal';
import api, { type Pagina } from '@/shared/services/api';

export interface Alerta {
  id: number;
  tipo: string;
  autorizacion: number | null;
  tarjeta: number | null;
  tarjeta_ultimos_4: string | null;
  tarjeta_estado: string | null;
  comercio: number | null;
  comercio_nombre: string | null;
  comercio_estado: string | null;
  probabilidad_fraude: number | null;
  descripcion: string;
  estado: string;
  fecha_creacion: string;
  fecha_resolucion: string | null;
}

export interface AutorizacionAnalista {
  id: number;
  tarjeta: number;
  ultimos_4: string;
  comercio: number;
  comercio_nombre: string;
  monto: number;
  canal: string;
  modo_lectura: string;
  resultado: string;
  motivo_rechazo: string | null;
  probabilidad_fraude: number | null;
  ip: string | null;
  fecha_hora: string;
}

export interface AlertaDetalle extends Alerta {
  ultimas_autorizaciones: AutorizacionAnalista[];
}

export interface Bloqueo {
  id: number;
  tipo: 'TARJETA' | 'COMERCIO';
  tarjeta: number | null;
  comercio: number | null;
  objetivo: string;
  origen: string;
  motivo: string;
  fecha_inicio: string;
  fecha_fin: string | null;
}

export interface FiltrosAlertas {
  tipo?: string;
  desde?: string;
  hasta?: string;
}

export interface NuevoBloqueo {
  tipo: 'TARJETA' | 'COMERCIO';
  tarjeta?: number;
  comercio?: number;
  motivo: string;
}

export const listarAlertas = (filtros: FiltrosAlertas, page: number) =>
  api.get<Pagina<Alerta>>('alertas/', { params: { ...filtros, page } }).then((r) => r.data);

export const obtenerAlerta = (id: number) =>
  api.get<AlertaDetalle>(`alertas/${id}/`).then((r) => r.data);

export const resolverAlerta = (id: number, estado: 'CONFIRMADA_FRAUDE' | 'DESCARTADA') =>
  api.post<Alerta>(`alertas/${id}/resolver/`, { estado }).then((r) => r.data);

export const listarBloqueosVigentes = (page: number) =>
  api.get<Pagina<Bloqueo>>('bloqueos/', { params: { vigentes: true, page } }).then((r) => r.data);

export const crearBloqueo = (bloqueo: NuevoBloqueo) =>
  api.post<Bloqueo>('bloqueos/', bloqueo).then((r) => r.data);

export const levantarBloqueo = (id: number) =>
  api.post<Bloqueo>(`bloqueos/${id}/levantar/`).then((r) => r.data);

export const listarReclamosTodos = (estado: string, page: number) =>
  api
    .get<Pagina<Reclamo>>('reclamos/', { params: { page, ...(estado ? { estado } : {}) } })
    .then((r) => r.data);

export const cambiarEstadoReclamo = (id: number, estado: string) =>
  api.patch<Reclamo>(`reclamos/${id}/`, { estado }).then((r) => r.data);
