<script setup lang="ts">
import { onMounted } from 'vue';

import { listarHistorial, type AutorizacionComercio } from '@/features/comercio/services/comercio';
import Insignia from '@/shared/components/Insignia.vue';
import Paginacion from '@/shared/components/Paginacion.vue';
import { usePaginado } from '@/shared/composables/usePaginado';
import { etiqueta, formatoFechaHora, formatoMoneda, MOTIVOS } from '@/shared/utils/formato';

const { items, pagina, totalPaginas, cargando, error, cargar } =
  usePaginado<AutorizacionComercio>(listarHistorial);

onMounted(() => cargar(1));
</script>

<template>
  <h1>Historial</h1>
  <p class="subtitulo">Autorizaciones de tu comercio, de la más reciente a la más antigua.</p>
  <p v-if="error" class="error" role="alert">{{ error }}</p>
  <div class="tabla-contenedor">
    <table v-if="items.length">
      <thead>
        <tr>
          <th>Fecha</th>
          <th>Tarjeta</th>
          <th>Canal</th>
          <th>Lectura</th>
          <th class="numero">Monto</th>
          <th>Resultado</th>
          <th>Motivo</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="a in items" :key="a.id">
          <td>{{ formatoFechaHora(a.fecha_hora) }}</td>
          <td>•••• {{ a.ultimos_4 }}</td>
          <td>{{ etiqueta(a.canal) }}</td>
          <td>{{ etiqueta(a.modo_lectura) }}</td>
          <td class="numero">{{ formatoMoneda(a.monto) }}</td>
          <td><Insignia :valor="a.resultado" /></td>
          <td>{{ a.motivo_rechazo ? MOTIVOS[a.motivo_rechazo] : '—' }}</td>
        </tr>
      </tbody>
    </table>
    <p v-else-if="!cargando && !error" class="vacio">Todavía no hay autorizaciones.</p>
    <p v-else-if="cargando" class="vacio">Cargando…</p>
  </div>
  <Paginacion :pagina="pagina" :total-paginas="totalPaginas" :cargando="cargando" @ir="cargar" />
</template>
