export type Rol = 'COMERCIO' | 'ASOCIADO' | 'ANALISTA' | 'ADMIN';

export interface Usuario {
  id: number;
  username: string;
  rol: Rol;
  nombre?: string;
  vende_en_linea?: boolean;
}

export interface RespuestaLogin {
  access: string;
  refresh: string;
  usuario: Usuario;
}
