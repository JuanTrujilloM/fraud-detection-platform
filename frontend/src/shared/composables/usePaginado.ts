import { computed, ref } from 'vue';

import type { Pagina } from '@/shared/services/api';
import { mensajeDeError } from '@/shared/utils/errores';

const TAMANO_PAGINA = 20;

export function usePaginado<T>(consultar: (pagina: number) => Promise<Pagina<T>>) {
  const items = ref<T[]>([]);
  const total = ref(0);
  const pagina = ref(1);
  const cargando = ref(true);
  const error = ref('');
  const totalPaginas = computed(() => Math.max(1, Math.ceil(total.value / TAMANO_PAGINA)));

  async function cargar(destino = pagina.value) {
    cargando.value = true;
    error.value = '';
    try {
      const datos = await consultar(destino);
      items.value = datos.results as typeof items.value;
      total.value = datos.count;
      pagina.value = destino;
    } catch (e) {
      error.value = mensajeDeError(e, 'No se pudo cargar la información.');
    } finally {
      cargando.value = false;
    }
  }

  return { items, total, pagina, totalPaginas, cargando, error, cargar };
}
