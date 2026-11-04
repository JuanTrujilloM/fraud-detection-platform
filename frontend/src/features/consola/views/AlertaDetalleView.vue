<script setup lang="ts">
import { computed, onMounted, ref } from 'vue';

import {
  crearBloqueo,
  obtenerAlerta,
  resolverAlerta,
  type AlertaDetalle,
  type NuevoBloqueo,
} from '@/features/consola/services/consola';
import Insignia from '@/shared/components/Insignia.vue';
import { mensajeDeError } from '@/shared/utils/errores';
import {
  etiqueta,
  formatoFechaHora,
  formatoMoneda,
  formatoProbabilidad,
  MOTIVOS,
} from '@/shared/utils/formato';

const props = defineProps<{ id: number }>();

const alerta = ref<AlertaDetalle | null>(null);
const error = ref('');
const exito = ref('');
const procesando = ref(false);
const motivoBloqueo = ref('');

const pendiente = computed(() => alerta.value?.estado === 'PENDIENTE');
const puedeBloquearTarjeta = computed(() => alerta.value?.tarjeta_estado === 'ACTIVA');
const puedeBloquearComercio = computed(() => alerta.value?.comercio_estado === 'ACTIVO');

async function cargar() {
  try {
    alerta.value = await obtenerAlerta(props.id);
  } catch (e) {
    error.value = mensajeDeError(e, 'No se pudo cargar la alerta.');
  }
}

async function ejecutar(accion: () => Promise<unknown>, mensaje: string) {
  error.value = '';
  exito.value = '';
  procesando.value = true;
  try {
    await accion();
    exito.value = mensaje;
    await cargar();
  } catch (e) {
    error.value = mensajeDeError(e);
  } finally {
    procesando.value = false;
  }
}

const resolver = (estado: 'CONFIRMADA_FRAUDE' | 'DESCARTADA') =>
  ejecutar(
    () => resolverAlerta(props.id, estado),
    estado === 'DESCARTADA' ? 'Alerta descartada.' : 'Fraude confirmado.',
  );

async function bloquear(tipo: NuevoBloqueo['tipo']) {
  const datos: NuevoBloqueo = { tipo, motivo: motivoBloqueo.value.trim() };
  if (tipo === 'TARJETA') datos.tarjeta = alerta.value?.tarjeta ?? undefined;
  else datos.comercio = alerta.value?.comercio ?? undefined;
  await ejecutar(
    () => crearBloqueo(datos),
    tipo === 'TARJETA' ? 'Tarjeta bloqueada.' : 'Comercio bloqueado.',
  );
  if (!error.value) motivoBloqueo.value = '';
}

onMounted(cargar);
</script>

<template>
  <p class="volver"><RouterLink to="/consola/alertas">← Alertas</RouterLink></p>
  <p v-if="error" class="error" role="alert">{{ error }}</p>
  <p v-if="exito" class="exito" role="status">{{ exito }}</p>

  <div v-if="alerta" class="pila">
    <div>
      <h1>Alerta #{{ alerta.id }} <Insignia :valor="alerta.estado" /></h1>
      <p class="subtitulo">{{ alerta.descripcion }}</p>
    </div>

    <div class="dos-columnas">
      <section class="panel">
        <h2>Datos</h2>
        <dl class="datos">
          <dt>Tipo</dt>
          <dd>{{ etiqueta(alerta.tipo) }}</dd>
          <dt>Probabilidad</dt>
          <dd>{{ formatoProbabilidad(alerta.probabilidad_fraude) }}</dd>
          <dt>Creada</dt>
          <dd>{{ formatoFechaHora(alerta.fecha_creacion) }}</dd>
          <template v-if="alerta.tarjeta">
            <dt>Tarjeta</dt>
            <dd>•••• {{ alerta.tarjeta_ultimos_4 }} <Insignia :valor="alerta.tarjeta_estado" /></dd>
          </template>
          <template v-if="alerta.comercio">
            <dt>Comercio</dt>
            <dd>{{ alerta.comercio_nombre }} <Insignia :valor="alerta.comercio_estado" /></dd>
          </template>
          <template v-if="alerta.fecha_resolucion">
            <dt>Resuelta</dt>
            <dd>{{ formatoFechaHora(alerta.fecha_resolucion) }}</dd>
          </template>
        </dl>
      </section>

      <section class="panel">
        <template v-if="pendiente">
          <h2>Resolver</h2>
          <div class="acciones resolver">
            <button
              type="button"
              class="peligro"
              :disabled="procesando"
              @click="resolver('CONFIRMADA_FRAUDE')"
            >
              Confirmar fraude
            </button>
            <button
              type="button"
              class="secundario"
              :disabled="procesando"
              @click="resolver('DESCARTADA')"
            >
              Descartar
            </button>
          </div>
        </template>
        <h2>Bloquear</h2>
        <template v-if="puedeBloquearTarjeta || puedeBloquearComercio">
          <div class="campo">
            <label for="motivo">Motivo del bloqueo</label>
            <input id="motivo" v-model="motivoBloqueo" maxlength="255" />
          </div>
          <div class="acciones">
            <button
              v-if="puedeBloquearTarjeta"
              type="button"
              class="secundario"
              :disabled="procesando || !motivoBloqueo.trim()"
              @click="bloquear('TARJETA')"
            >
              Bloquear tarjeta
            </button>
            <button
              v-if="puedeBloquearComercio"
              type="button"
              class="secundario"
              :disabled="procesando || !motivoBloqueo.trim()"
              @click="bloquear('COMERCIO')"
            >
              Bloquear comercio
            </button>
          </div>
        </template>
        <p v-else class="sin-bloqueo">
          Ya están bloqueados. Puedes levantarlos desde
          <RouterLink to="/consola/bloqueos">Bloqueos</RouterLink>.
        </p>
      </section>
    </div>

    <section>
      <h2>Últimas autorizaciones de {{ alerta.tarjeta ? 'la tarjeta' : 'el comercio' }}</h2>
      <div class="tabla-contenedor">
        <table v-if="alerta.ultimas_autorizaciones.length">
          <thead>
            <tr>
              <th>Fecha</th>
              <th>Tarjeta</th>
              <th>Comercio</th>
              <th>Canal</th>
              <th class="numero">Monto</th>
              <th class="numero">Probabilidad</th>
              <th>Resultado</th>
              <th>Motivo</th>
              <th>IP</th>
            </tr>
          </thead>
          <tbody>
            <tr
              v-for="a in alerta.ultimas_autorizaciones"
              :key="a.id"
              :class="{ actual: a.id === alerta.autorizacion }"
            >
              <td>{{ formatoFechaHora(a.fecha_hora) }}</td>
              <td>•••• {{ a.ultimos_4 }}</td>
              <td>{{ a.comercio_nombre }}</td>
              <td>{{ etiqueta(a.canal) }}</td>
              <td class="numero">{{ formatoMoneda(a.monto) }}</td>
              <td class="numero">{{ formatoProbabilidad(a.probabilidad_fraude) }}</td>
              <td><Insignia :valor="a.resultado" /></td>
              <td>{{ a.motivo_rechazo ? MOTIVOS[a.motivo_rechazo] : '—' }}</td>
              <td>{{ a.ip ?? '—' }}</td>
            </tr>
          </tbody>
        </table>
        <p v-else class="vacio">Sin autorizaciones.</p>
      </div>
    </section>
  </div>
</template>

<style scoped>
.volver {
  margin: 0 0 12px;
}

h1 .insignia {
  vertical-align: middle;
}

.subtitulo {
  margin-bottom: 0;
}

.resolver {
  margin-bottom: 20px;
}

.sin-bloqueo {
  margin: 0;
  color: var(--texto-suave);
}

tr.actual td {
  background: var(--aviso-suave);
}
</style>
