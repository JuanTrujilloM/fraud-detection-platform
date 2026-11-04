<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue';

import {
  crearBloqueo,
  levantarBloqueo,
  listarBloqueosVigentes,
  type Bloqueo,
  type NuevoBloqueo,
} from '@/features/consola/services/consola';
import Paginacion from '@/shared/components/Paginacion.vue';
import { usePaginado } from '@/shared/composables/usePaginado';
import { mensajeDeError } from '@/shared/utils/errores';
import { etiqueta, formatoFechaHora } from '@/shared/utils/formato';

const { items, pagina, totalPaginas, cargando, error, cargar } =
  usePaginado<Bloqueo>(listarBloqueosVigentes);

const formulario = reactive<{ tipo: NuevoBloqueo['tipo']; id: number | null; motivo: string }>({
  tipo: 'TARJETA',
  id: null,
  motivo: '',
});
const errorAccion = ref('');
const exito = ref('');
const procesando = ref(false);

async function ejecutar(accion: () => Promise<unknown>, mensaje: string) {
  errorAccion.value = '';
  exito.value = '';
  procesando.value = true;
  try {
    await accion();
    exito.value = mensaje;
    await cargar(1);
    return true;
  } catch (e) {
    errorAccion.value = mensajeDeError(e);
    return false;
  } finally {
    procesando.value = false;
  }
}

async function bloquear() {
  const datos: NuevoBloqueo = { tipo: formulario.tipo, motivo: formulario.motivo.trim() };
  if (formulario.tipo === 'TARJETA') datos.tarjeta = formulario.id ?? undefined;
  else datos.comercio = formulario.id ?? undefined;
  const hecho = await ejecutar(() => crearBloqueo(datos), 'Bloqueo aplicado.');
  if (hecho) {
    formulario.id = null;
    formulario.motivo = '';
  }
}

const levantar = (bloqueo: Bloqueo) =>
  ejecutar(() => levantarBloqueo(bloqueo.id), `Bloqueo de ${bloqueo.objetivo} levantado.`);

onMounted(() => cargar(1));
</script>

<template>
  <h1>Bloqueos</h1>
  <p class="subtitulo">Bloquea tarjetas y comercios, y levanta los bloqueos vigentes.</p>
  <p v-if="errorAccion || error" class="error" role="alert">{{ errorAccion || error }}</p>
  <p v-if="exito" class="exito" role="status">{{ exito }}</p>

  <form class="panel nuevo" @submit.prevent="bloquear">
    <div class="campo">
      <label for="tipo">Tipo</label>
      <select id="tipo" v-model="formulario.tipo">
        <option value="TARJETA">Tarjeta</option>
        <option value="COMERCIO">Comercio</option>
      </select>
    </div>
    <div class="campo">
      <label for="objetivo"
        >ID {{ formulario.tipo === 'TARJETA' ? 'de la tarjeta' : 'del comercio' }}</label
      >
      <input id="objetivo" v-model.number="formulario.id" type="number" min="1" required />
    </div>
    <div class="campo motivo">
      <label for="motivo">Motivo</label>
      <input id="motivo" v-model="formulario.motivo" maxlength="255" required />
    </div>
    <button type="submit" class="peligro" :disabled="procesando">Bloquear</button>
  </form>

  <h2>Vigentes</h2>
  <div class="tabla-contenedor">
    <table v-if="items.length">
      <thead>
        <tr>
          <th>Objetivo</th>
          <th>Tipo</th>
          <th>Origen</th>
          <th>Motivo</th>
          <th>Desde</th>
          <th><span class="solo-lector">Acción</span></th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="b in items" :key="b.id">
          <td>{{ b.objetivo }}</td>
          <td>{{ etiqueta(b.tipo) }}</td>
          <td>{{ etiqueta(b.origen) }}</td>
          <td class="ancho">{{ b.motivo }}</td>
          <td>{{ formatoFechaHora(b.fecha_inicio) }}</td>
          <td>
            <button type="button" class="secundario" :disabled="procesando" @click="levantar(b)">
              Levantar
            </button>
          </td>
        </tr>
      </tbody>
    </table>
    <p v-else-if="cargando" class="vacio">Cargando…</p>
    <p v-else-if="!error" class="vacio">No hay bloqueos vigentes.</p>
  </div>
  <Paginacion :pagina="pagina" :total-paginas="totalPaginas" :cargando="cargando" @ir="cargar" />
</template>

<style scoped>
.nuevo {
  display: grid;
  grid-template-columns: 140px 160px minmax(0, 1fr) auto;
  align-items: end;
  gap: 12px;
  margin-bottom: 28px;
}

.nuevo .campo {
  margin: 0;
}

@media (max-width: 760px) {
  .nuevo {
    grid-template-columns: minmax(0, 1fr);
  }
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
