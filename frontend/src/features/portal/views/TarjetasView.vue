<script setup lang="ts">
import { onMounted, ref } from 'vue';

import {
  bloquearTarjeta,
  desbloquearTarjeta,
  listarTarjetas,
  type Tarjeta,
} from '@/features/portal/services/portal';
import Insignia from '@/shared/components/Insignia.vue';
import { mensajeDeError } from '@/shared/utils/errores';
import { etiqueta, formatoMoneda, formatoVencimiento } from '@/shared/utils/formato';

const tarjetas = ref<Tarjeta[]>([]);
const cargando = ref(true);
const error = ref('');
const procesando = ref<number | null>(null);

async function cargar() {
  try {
    tarjetas.value = await listarTarjetas();
  } catch (e) {
    error.value = mensajeDeError(e, 'No se pudieron cargar tus tarjetas.');
  } finally {
    cargando.value = false;
  }
}

async function cambiarBloqueo(tarjeta: Tarjeta, accion: (id: number) => Promise<unknown>) {
  error.value = '';
  procesando.value = tarjeta.id;
  try {
    await accion(tarjeta.id);
    await cargar();
  } catch (e) {
    error.value = mensajeDeError(e);
  } finally {
    procesando.value = null;
  }
}

const porcentajeDisponible = (t: Tarjeta) =>
  t.cupo_total > 0 ? Math.round((t.cupo_disponible / t.cupo_total) * 100) : 0;

onMounted(cargar);
</script>

<template>
  <h1>Mis tarjetas</h1>
  <p class="subtitulo">Consulta tu cupo y bloquea una tarjeta si no la encuentras.</p>
  <p v-if="error" class="error" role="alert">{{ error }}</p>
  <p v-if="cargando" class="vacio">Cargando…</p>
  <p v-else-if="!tarjetas.length && !error" class="panel vacio">No tienes tarjetas registradas.</p>
  <div class="rejilla">
    <article v-for="t in tarjetas" :key="t.id" class="panel tarjeta">
      <header>
        <strong>{{ etiqueta(t.franquicia) }} •••• {{ t.ultimos_4 }}</strong>
        <Insignia :valor="t.estado" />
      </header>
      <p class="cupo">{{ formatoMoneda(t.cupo_disponible) }}</p>
      <p class="detalle">disponibles de {{ formatoMoneda(t.cupo_total) }}</p>
      <div
        class="barra"
        role="img"
        :aria-label="`${porcentajeDisponible(t)} % del cupo disponible`"
      >
        <div :style="{ width: `${porcentajeDisponible(t)}%` }" />
      </div>
      <p class="detalle">Vence {{ formatoVencimiento(t.fecha_vencimiento) }}</p>
      <div class="acciones">
        <RouterLink :to="`/portal/tarjetas/${t.id}`" class="enlace-boton">Movimientos</RouterLink>
        <button
          v-if="t.estado === 'ACTIVA'"
          type="button"
          class="peligro"
          :disabled="procesando === t.id"
          @click="cambiarBloqueo(t, bloquearTarjeta)"
        >
          Bloquear
        </button>
        <button
          v-else-if="t.puede_desbloquear"
          type="button"
          :disabled="procesando === t.id"
          @click="cambiarBloqueo(t, desbloquearTarjeta)"
        >
          Desbloquear
        </button>
      </div>
      <p v-if="t.estado === 'BLOQUEADA' && !t.puede_desbloquear" class="detalle aviso">
        La cooperativa bloqueó esta tarjeta. Comunícate con ella para levantar el bloqueo.
      </p>
    </article>
  </div>
</template>

<style scoped>
.rejilla {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(290px, 1fr));
  gap: 16px;
}

.tarjeta header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  margin-bottom: 14px;
}

.cupo {
  margin: 0;
  font-size: 1.5rem;
  font-weight: 700;
  font-variant-numeric: tabular-nums;
}

.detalle {
  margin: 0 0 10px;
  color: var(--texto-suave);
  font-size: 0.875rem;
}

.aviso {
  margin: 12px 0 0;
}

.barra {
  height: 6px;
  margin-bottom: 10px;
  overflow: hidden;
  border-radius: 3px;
  background: var(--neutro-suave);
}

.barra div {
  height: 100%;
  background: var(--marca);
}

.enlace-boton {
  padding: 9px 16px;
  border: 1px solid #b9bfb5;
  border-radius: 6px;
  color: var(--texto);
  font-weight: 600;
  text-decoration: none;
}

.enlace-boton:hover {
  background: var(--neutro-suave);
}
</style>
