const moneda = new Intl.NumberFormat('es-CO', {
  style: 'currency',
  currency: 'COP',
  maximumFractionDigits: 0,
});
const fechaHora = new Intl.DateTimeFormat('es-CO', { dateStyle: 'medium', timeStyle: 'short' });
const fechaCorta = new Intl.DateTimeFormat('es-CO', { month: '2-digit', year: '2-digit' });

export const formatoMoneda = (valor: number | string) => moneda.format(Number(valor));
export const formatoFechaHora = (valor: string | null) =>
  valor ? fechaHora.format(new Date(valor)) : '—';
export const formatoVencimiento = (valor: string) =>
  fechaCorta.format(new Date(`${valor}T12:00:00`));
export const formatoProbabilidad = (valor: number | null) =>
  valor === null ? '—' : `${Math.round(valor * 100)} %`;

export const MOTIVOS: Record<string, string> = {
  COMERCIO_BLOQUEADO: 'Comercio bloqueado',
  CANAL_NO_PERMITIDO: 'El comercio no vende en línea',
  TARJETA_INEXISTENTE: 'La tarjeta no existe',
  TARJETA_BLOQUEADA: 'Tarjeta bloqueada',
  TARJETA_CANCELADA: 'Tarjeta cancelada',
  DATOS_INVALIDOS: 'La fecha de vencimiento no coincide',
  TARJETA_VENCIDA: 'Tarjeta vencida',
  CVV_INVALIDO: 'CVV incorrecto',
  CUPO_INSUFICIENTE: 'Cupo insuficiente',
  RIESGO_ALTO: 'Riesgo alto de fraude',
};

export const ETIQUETAS: Record<string, string> = {
  ...MOTIVOS,
  ACTIVA: 'Activa',
  ACTIVO: 'Activo',
  BLOQUEADA: 'Bloqueada',
  BLOQUEADO: 'Bloqueado',
  CANCELADA: 'Cancelada',
  APROBADA: 'Aprobada',
  RECHAZADA: 'Rechazada',
  PENDIENTE: 'Pendiente',
  CONFIRMADA_FRAUDE: 'Fraude confirmado',
  DESCARTADA: 'Descartada',
  RADICADO: 'Radicado',
  EN_REVISION: 'En revisión',
  RESUELTO: 'Resuelto',
  PRESENCIAL: 'Presencial',
  EN_LINEA: 'En línea',
  CHIP: 'Chip',
  BANDA: 'Banda',
  DIGITADA: 'Digitada',
  TARJETA: 'Tarjeta',
  COMERCIO: 'Comercio',
  ASOCIADO: 'Asociado',
  ANALISTA: 'Analista',
  MODELO: 'Modelo',
  STREAMING: 'Streaming',
  RIESGO_ALTO_MODELO: 'Riesgo alto del modelo',
  PRUEBA_TARJETAS: 'Prueba de tarjetas',
  VISA: 'Visa',
  MASTERCARD: 'Mastercard',
};

export const etiqueta = (valor: string | null) => (valor ? (ETIQUETAS[valor] ?? valor) : '—');
