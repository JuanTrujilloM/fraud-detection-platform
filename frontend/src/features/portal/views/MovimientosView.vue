<script setup lang="ts">
import { onMounted, ref } from 'vue';

import {
  listarMovimientos,
  radicarReclamo,
  type Movimiento,
} from '@/features/portal/services/portal';
import Insignia from '@/shared/components/Insignia.vue';
import Paginacion from '@/shared/components/Paginacion.vue';
import { usePaginado } from '@/shared/composables/usePaginado';
import { mensajeDeError } from '@/shared/utils/errores';
import { etiqueta, formatoFechaHora, formatoMoneda, MOTIVOS } from '@/shared/utils/formato';

const props = defineProps<{ id: number }>();

const { items, pagina, totalPaginas, cargando, error, cargar } = usePaginado<Movimiento>((p) =>
  listarMovimientos(props.id, p),
);

const reportando = ref<Movimiento | null>(null);
const descripcion = ref('');
const errorReclamo = ref('');
const confirmacion = ref('');
const enviando = ref(false);

function abrirReporte(movimiento: Movimiento) {
  reportando.value = movimiento;
  descripcion.value = '';
  errorReclamo.value = '';
  confirmacion.value = '';
}

async function enviarReporte() {
  if (!reportando.value) return;
  errorReclamo.value = '';
  enviando.value = true;
  try {
    const reclamo = await radicarReclamo(reportando.value.id, descripcion.value);
    reportando.value.reclamado = true;
    reportando.value = null;
    confirmacion.value = `Radicamos tu reclamo #${reclamo.id}. Puedes seguirlo en Mis reclamos.`;
  } catch (e) {
    errorReclamo.value = mensajeDeError(e);
  } finally {
    enviando.value = false;
  }
}

onMounted(() => cargar(1));
</script>

<template>
  <p class="volver"><RouterLink to="/portal/tarjetas">← Mis tarjetas</RouterLink></p>
  <h1>Movimientos</h1>
  <p class="subtitulo">Si no reconoces una compra, repórtala.</p>
  <p v-if="error" class="error" role="alert">{{ error }}</p>
  <p v-if="confirmacion" class="exito" role="status">{{ confirmacion }}</p>

  <form v-if="reportando" class="panel reporte" @submit.prevent="enviarReporte">
    <h2>
      Reportar compra en {{ reportando.comercio_nombre }} por
      {{ formatoMoneda(reportando.monto) }}
    </h2>
    <p v-if="errorReclamo" class="error" role="alert">{{ errorReclamo }}</p>
    <div class="campo">
      <label for="descripcion">¿Qué pasó?</label>
      <textarea id="descripcion" v-model="descripcion" rows="3" maxlength="2000" required />
    </div>
    <div class="acciones">
      <button type="submit" :disabled="enviando">Radicar reclamo</button>
      <button type="button" class="secundario" @click="reportando = null">Cancelar</button>
    </div>
  </form>

  <div class="tabla-contenedor">
    <table v-if="items.length">
      <thead>
        <tr>
          <th>Fecha</th>
          <th>Comercio</th>
          <th>Canal</th>
          <th class="numero">Monto</th>
          <th>Resultado</th>
          <th>Motivo</th>
          <th><span class="solo-lector">Acción</span></th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="m in items" :key="m.id">
          <td>{{ formatoFechaHora(m.fecha_hora) }}</td>
          <td>{{ m.comercio_nombre }}</td>
          <td>{{ etiqueta(m.canal) }}</td>
          <td class="numero">{{ formatoMoneda(m.monto) }}</td>
          <td><Insignia :valor="m.resultado" /></td>
          <td>{{ m.motivo_rechazo ? MOTIVOS[m.motivo_rechazo] : '—' }}</td>
          <td>
            <span v-if="m.reclamado" class="insignia aviso">Reportada</span>
            <button v-else type="button" class="secundario" @click="abrirReporte(m)">
              No la reconozco
            </button>
          </td>
        </tr>
      </tbody>
    </table>
    <p v-else-if="cargando" class="vacio">Cargando…</p>
    <p v-else-if="!error" class="vacio">Esta tarjeta todavía no tiene movimientos.</p>
  </div>
  <Paginacion :pagina="pagina" :total-paginas="totalPaginas" :cargando="cargando" @ir="cargar" />
</template>

<style scoped>
.volver {
  margin: 0 0 12px;
}

.reporte {
  margin-bottom: 20px;
}

td button {
  padding: 4px 10px;
  font-size: 0.875rem;
}

.solo-lector {
  position: absolute;
  width: 1px;
  height: 1px;
  overflow: hidden;
  clip-path: inset(50%);
}
</style>
