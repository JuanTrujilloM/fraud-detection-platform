import api, { type Pagina } from '@/shared/services/api';

export interface Tarjeta {
  id: number;
  ultimos_4: string;
  franquicia: string;
  fecha_vencimiento: string;
  cupo_total: number;
  cupo_disponible: number;
  estado: string;
  puede_desbloquear: boolean;
}

export interface Movimiento {
  id: number;
  comercio_nombre: string;
  categoria: string;
  monto: number;
  canal: string;
  resultado: string;
  motivo_rechazo: string | null;
  fecha_hora: string;
  reclamado: boolean;
}

export interface Reclamo {
  id: number;
  autorizacion: number;
  asociado_nombre: string;
  comercio_nombre: string;
  monto: number;
  fecha_compra: string;
  ultimos_4: string;
  descripcion: string;
  estado: string;
  fecha_radicacion: string;
  fecha_resolucion: string | null;
}

export interface Perfil {
  tipo_documento: string;
  numero_documento: string;
  nombres: string;
  apellidos: string;
  ciudad: string;
  celular: string;
  email: string;
}

export const listarTarjetas = () => api.get<Tarjeta[]>('asociado/tarjetas/').then((r) => r.data);

export const listarMovimientos = (tarjetaId: number, page: number) =>
  api
    .get<Pagina<Movimiento>>(`asociado/tarjetas/${tarjetaId}/autorizaciones/`, {
      params: { page },
    })
    .then((r) => r.data);

export const bloquearTarjeta = (id: number) => api.post(`asociado/tarjetas/${id}/bloquear/`, {});

export const desbloquearTarjeta = (id: number) => api.post(`asociado/tarjetas/${id}/desbloquear/`);

export const radicarReclamo = (autorizacion: number, descripcion: string) =>
  api.post<Reclamo>('asociado/reclamos/', { autorizacion, descripcion }).then((r) => r.data);

export const listarReclamos = (page: number) =>
  api.get<Pagina<Reclamo>>('asociado/reclamos/', { params: { page } }).then((r) => r.data);

export const obtenerPerfil = () => api.get<Perfil>('asociado/perfil/').then((r) => r.data);

export const actualizarPerfil = (cambios: Pick<Perfil, 'celular' | 'email'>) =>
  api.patch<Perfil>('asociado/perfil/', cambios).then((r) => r.data);
