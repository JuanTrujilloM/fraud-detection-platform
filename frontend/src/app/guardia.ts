import type { Rol, Usuario } from '@/features/auth/tipos';

export const INICIO_POR_ROL: Record<Exclude<Rol, 'ADMIN'>, string> = {
  COMERCIO: '/comercio/terminal',
  ASOCIADO: '/portal/tarjetas',
  ANALISTA: '/consola/alertas',
};

/** Ruta inicial del rol. El administrador no tiene pantallas en Vue: usa el admin de Django. */
export function rutaInicial(rol: Rol): string | null {
  return rol === 'ADMIN' ? null : INICIO_POR_ROL[rol];
}

export interface MetaRuta {
  rol?: Rol;
  soloVentaEnLinea?: boolean;
}

/** Decide a dónde redirigir. `null` significa que puede entrar. */
export function resolverGuardia(
  destino: string,
  meta: MetaRuta,
  usuario: Usuario | null,
): string | null {
  if (destino === '/login') {
    const inicio = usuario && rutaInicial(usuario.rol);
    return inicio ?? null;
  }
  if (!usuario) return '/login';
  if (meta.rol && meta.rol !== usuario.rol) return rutaInicial(usuario.rol) ?? '/login';
  if (meta.soloVentaEnLinea && !usuario.vende_en_linea) return '/comercio/terminal';
  return null;
}
