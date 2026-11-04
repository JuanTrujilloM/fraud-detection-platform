<script setup lang="ts">
import { onMounted, reactive } from 'vue';

import { listarAlertas, type Alerta } from '@/features/consola/services/consola';
import Paginacion from '@/shared/components/Paginacion.vue';
import { usePaginado } from '@/shared/composables/usePaginado';
import { etiqueta, formatoFechaHora, formatoProbabilidad } from '@/shared/utils/formato';

const filtros = reactive({ tipo: '', desde: '', hasta: '' });

const { items, total, pagina, totalPaginas, cargando, error, cargar } = usePaginado<Alerta>((p) =>
  listarAlertas(
    {
      ...(filtros.tipo && { tipo: filtros.tipo }),
      ...(filtros.desde && { desde: filtros.desde }),
      ...(filtros.hasta && { hasta: filtros.hasta }),
    },
    p,
  ),
);

onMounted(() => cargar(1));
</script>

<template>
  <h1>Alertas pendientes</h1>
  <p class="subtitulo">
    {{ total }} {{ total === 1 ? 'alerta espera' : 'alertas esperan' }} revisión.
  </p>

  <form class="panel filtros" @submit.prevent="cargar(1)">
    <div class="campo">
      <label for="tipo">Tipo</label>
      <select id="tipo" v-model="filtros.tipo">
        <option value="">Todos</option>
        <option value="RIESGO_ALTO_MODELO">Riesgo alto del modelo</option>
        <option value="PRUEBA_TARJETAS">Prueba de tarjetas</option>
      </select>
    </div>
    <div class="campo">
      <label for="desde">Desde</label>
      <input id="desde" v-model="filtros.desde" type="date" />
    </div>
    <div class="campo">
      <label for="hasta">Hasta</label>
      <input id="hasta" v-model="filtros.hasta" type="date" />
    </div>
    <button type="submit" class="secundario">Filtrar</button>
  </form>

  <p v-if="error" class="error" role="alert">{{ error }}</p>
  <div class="tabla-contenedor">
    <table v-if="items.length">
      <thead>
        <tr>
          <th>Alerta</th>
          <th>Creada</th>
          <th>Tipo</th>
          <th>Tarjeta</th>
          <th>Comercio</th>
          <th class="numero">Probabilidad</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="a in items" :key="a.id">
          <td>
            <RouterLink :to="`/consola/alertas/${a.id}`">#{{ a.id }}</RouterLink>
          </td>
          <td>{{ formatoFechaHora(a.fecha_creacion) }}</td>
          <td>{{ etiqueta(a.tipo) }}</td>
          <td>{{ a.tarjeta_ultimos_4 ? `•••• ${a.tarjeta_ultimos_4}` : '—' }}</td>
          <td>{{ a.comercio_nombre ?? '—' }}</td>
          <td class="numero">{{ formatoProbabilidad(a.probabilidad_fraude) }}</td>
        </tr>
      </tbody>
    </table>
    <p v-else-if="cargando" class="vacio">Cargando…</p>
    <p v-else-if="!error" class="vacio">No hay alertas pendientes con estos filtros.</p>
  </div>
  <Paginacion :pagina="pagina" :total-paginas="totalPaginas" :cargando="cargando" @ir="cargar" />
</template>

<style scoped>
.filtros {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(160px, 1fr));
  align-items: end;
  gap: 12px;
  margin-bottom: 20px;
  padding: 16px;
}

.filtros .campo {
  margin: 0;
}
</style>
