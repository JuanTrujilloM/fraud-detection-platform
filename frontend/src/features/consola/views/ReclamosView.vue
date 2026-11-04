<script setup lang="ts">
import { onMounted, ref } from 'vue';

import { cambiarEstadoReclamo, listarReclamosTodos } from '@/features/consola/services/consola';
import type { Reclamo } from '@/features/portal/services/portal';
import Insignia from '@/shared/components/Insignia.vue';
import Paginacion from '@/shared/components/Paginacion.vue';
import { usePaginado } from '@/shared/composables/usePaginado';
import { mensajeDeError } from '@/shared/utils/errores';
import { formatoFechaHora, formatoMoneda } from '@/shared/utils/formato';

const filtroEstado = ref('');
const { items, pagina, totalPaginas, cargando, error, cargar } = usePaginado<Reclamo>((p) =>
  listarReclamosTodos(filtroEstado.value, p),
);
const errorAccion = ref('');
const procesando = ref<number | null>(null);

async function cambiar(reclamo: Reclamo, estado: string) {
  errorAccion.value = '';
  procesando.value = reclamo.id;
  try {
    Object.assign(reclamo, await cambiarEstadoReclamo(reclamo.id, estado));
  } catch (e) {
    errorAccion.value = mensajeDeError(e);
  } finally {
    procesando.value = null;
  }
}

onMounted(() => cargar(1));
</script>

<template>
  <h1>Reclamos</h1>
  <p class="subtitulo">Compras que los asociados reportaron como no reconocidas.</p>
  <div class="campo filtro">
    <label for="estado">Estado</label>
    <select id="estado" v-model="filtroEstado" @change="cargar(1)">
      <option value="">Todos</option>
      <option value="RADICADO">Radicado</option>
      <option value="EN_REVISION">En revisión</option>
      <option value="RESUELTO">Resuelto</option>
    </select>
  </div>
  <p v-if="errorAccion || error" class="error" role="alert">{{ errorAccion || error }}</p>
  <div class="tabla-contenedor">
    <table v-if="items.length">
      <thead>
        <tr>
          <th>Radicado</th>
          <th>Asociado</th>
          <th>Compra</th>
          <th class="numero">Monto</th>
          <th>Descripción</th>
          <th>Estado</th>
          <th><span class="solo-lector">Acciones</span></th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="r in items" :key="r.id">
          <td>{{ formatoFechaHora(r.fecha_radicacion) }}</td>
          <td>{{ r.asociado_nombre }}</td>
          <td>{{ r.comercio_nombre }} · •••• {{ r.ultimos_4 }}</td>
          <td class="numero">{{ formatoMoneda(r.monto) }}</td>
          <td class="ancho">{{ r.descripcion }}</td>
          <td><Insignia :valor="r.estado" /></td>
          <td>
            <div v-if="r.estado !== 'RESUELTO'" class="acciones">
              <button
                v-if="r.estado === 'RADICADO'"
                type="button"
                class="secundario"
                :disabled="procesando === r.id"
                @click="cambiar(r, 'EN_REVISION')"
              >
                Revisar
              </button>
              <button
                type="button"
                class="secundario"
                :disabled="procesando === r.id"
                @click="cambiar(r, 'RESUELTO')"
              >
                Resolver
              </button>
            </div>
            <span v-else>{{ formatoFechaHora(r.fecha_resolucion) }}</span>
          </td>
        </tr>
      </tbody>
    </table>
    <p v-else-if="cargando" class="vacio">Cargando…</p>
    <p v-else-if="!error" class="vacio">No hay reclamos con este estado.</p>
  </div>
  <Paginacion :pagina="pagina" :total-paginas="totalPaginas" :cargando="cargando" @ir="cargar" />
</template>

<style scoped>
.filtro {
  max-width: 220px;
}

td button {
  padding: 4px 10px;
  font-size: 0.875rem;
}

.acciones {
  flex-wrap: nowrap;
}

.solo-lector {
  position: absolute;
  width: 1px;
  height: 1px;
  overflow: hidden;
  clip-path: inset(50%);
}
</style>
