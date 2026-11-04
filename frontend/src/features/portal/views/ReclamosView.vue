<script setup lang="ts">
import { onMounted } from 'vue';

import { listarReclamos, type Reclamo } from '@/features/portal/services/portal';
import Insignia from '@/shared/components/Insignia.vue';
import Paginacion from '@/shared/components/Paginacion.vue';
import { usePaginado } from '@/shared/composables/usePaginado';
import { formatoFechaHora, formatoMoneda } from '@/shared/utils/formato';

const { items, pagina, totalPaginas, cargando, error, cargar } =
  usePaginado<Reclamo>(listarReclamos);

onMounted(() => cargar(1));
</script>

<template>
  <h1>Mis reclamos</h1>
  <p class="subtitulo">Las compras que reportaste como no reconocidas.</p>
  <p v-if="error" class="error" role="alert">{{ error }}</p>
  <div class="tabla-contenedor">
    <table v-if="items.length">
      <thead>
        <tr>
          <th>Radicado</th>
          <th>Compra</th>
          <th>Tarjeta</th>
          <th class="numero">Monto</th>
          <th>Descripción</th>
          <th>Estado</th>
          <th>Resuelto</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="r in items" :key="r.id">
          <td>{{ formatoFechaHora(r.fecha_radicacion) }}</td>
          <td>{{ r.comercio_nombre }}</td>
          <td>•••• {{ r.ultimos_4 }}</td>
          <td class="numero">{{ formatoMoneda(r.monto) }}</td>
          <td class="ancho">{{ r.descripcion }}</td>
          <td><Insignia :valor="r.estado" /></td>
          <td>{{ formatoFechaHora(r.fecha_resolucion) }}</td>
        </tr>
      </tbody>
    </table>
    <p v-else-if="cargando" class="vacio">Cargando…</p>
    <p v-else-if="!error" class="vacio">
      No has reportado compras. Puedes hacerlo desde los movimientos de una tarjeta.
    </p>
  </div>
  <Paginacion :pagina="pagina" :total-paginas="totalPaginas" :cargando="cargando" @ir="cargar" />
</template>
