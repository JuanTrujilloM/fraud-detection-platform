import api, { type Pagina } from '@/shared/services/api';

export interface SolicitudCompra {
  numero_tarjeta: string;
  fecha_vencimiento: string;
  monto: string;
  canal: 'PRESENCIAL' | 'EN_LINEA';
  modo_lectura: 'CHIP' | 'BANDA' | 'DIGITADA';
  cvv?: string;
  huella_dispositivo?: string;
  segundos_formulario?: number;
  tarjeta_pegada?: boolean;
}

export interface Decision {
  id_autorizacion: number | null;
  resultado: 'APROBADA' | 'RECHAZADA';
  motivo_rechazo: string | null;
}

export interface AutorizacionComercio {
  id: number;
  ultimos_4: string;
  monto: number;
  canal: string;
  modo_lectura: string;
  resultado: string;
  motivo_rechazo: string | null;
  fecha_hora: string;
}

export const autorizarCompra = (solicitud: SolicitudCompra) =>
  api.post<Decision>('autorizaciones/', solicitud).then((r) => r.data);

export const listarHistorial = (page: number) =>
  api
    .get<Pagina<AutorizacionComercio>>('comercio/autorizaciones/', { params: { page } })
    .then((r) => r.data);
