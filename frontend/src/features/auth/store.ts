import axios from 'axios';
import { defineStore } from 'pinia';

import type { RespuestaLogin, Usuario } from '@/features/auth/tipos';

const CLAVE = 'coopandina.sesion';

interface Sesion {
  access: string | null;
  refresh: string | null;
  usuario: Usuario | null;
}

function leerSesion(): Sesion {
  try {
    const guardada = localStorage.getItem(CLAVE);
    if (guardada) return JSON.parse(guardada) as Sesion;
  } catch {
    // Almacenamiento bloqueado o dañado: se empieza sin sesión.
  }
  return { access: null, refresh: null, usuario: null };
}

function guardarSesion(sesion: Sesion): void {
  try {
    localStorage.setItem(CLAVE, JSON.stringify(sesion));
  } catch {
    // Sin almacenamiento la sesión dura lo que dure la pestaña.
  }
}

const useAuthStore = defineStore('auth', {
  state: (): Sesion => leerSesion(),
  actions: {
    async login(username: string, password: string): Promise<Usuario> {
      // Sin el cliente con interceptores: un 401 aquí es una credencial mala, no un token vencido.
      const { data } = await axios.post<RespuestaLogin>('/api/auth/login/', { username, password });
      this.access = data.access;
      this.refresh = data.refresh;
      this.usuario = data.usuario;
      guardarSesion(this.$state);
      return data.usuario;
    },
    async renovar(): Promise<string> {
      const { data } = await axios.post<{ access: string }>('/api/auth/refresh/', {
        refresh: this.refresh,
      });
      this.access = data.access;
      guardarSesion(this.$state);
      return data.access;
    },
    salir(): void {
      this.access = null;
      this.refresh = null;
      this.usuario = null;
      try {
        localStorage.removeItem(CLAVE);
      } catch {
        // Nada que limpiar.
      }
    },
  },
});

export default useAuthStore;
