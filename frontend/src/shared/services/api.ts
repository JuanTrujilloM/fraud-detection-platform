import axios, { type AxiosError, type InternalAxiosRequestConfig } from 'axios';

import router from '@/app/router';
import useAuthStore from '@/features/auth/store';

interface PeticionReintentable extends InternalAxiosRequestConfig {
  reintentada?: boolean;
}

const api = axios.create({ baseURL: '/api/' });

api.interceptors.request.use((config) => {
  const { access } = useAuthStore();
  if (access) config.headers.Authorization = `Bearer ${access}`;
  return config;
});

// Una sola renovación a la vez, aunque varias peticiones reciban 401 al mismo tiempo.
let renovacion: Promise<string> | null = null;

api.interceptors.response.use(undefined, async (error: AxiosError) => {
  const peticion = error.config as PeticionReintentable | undefined;
  if (error.response?.status !== 401 || !peticion || peticion.reintentada) throw error;

  const auth = useAuthStore();
  try {
    renovacion ??= auth.renovar().finally(() => {
      renovacion = null;
    });
    await renovacion;
  } catch {
    auth.salir();
    await router.push('/login');
    throw error;
  }
  peticion.reintentada = true;
  return api(peticion);
});

export interface Pagina<T> {
  count: number;
  next: string | null;
  previous: string | null;
  results: T[];
}

export default api;
