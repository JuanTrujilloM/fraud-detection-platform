<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue';

import { autorizarCompra, type Decision } from '@/features/comercio/services/comercio';
import { calcularHuella } from '@/features/comercio/services/huella';
import ResultadoCompra from '@/features/comercio/views/ResultadoCompra.vue';
import { mensajeDeError } from '@/shared/utils/errores';

const formulario = reactive({ numero: '', vencimiento: '', cvv: '', monto: '' as number | '' });
const decision = ref<Decision | null>(null);
const montoCobrado = ref('');
const error = ref('');
const enviando = ref(false);

// Señales de contexto que recibe el modelo de fraude.
const tarjetaPegada = ref(false);
let inicioFormulario = 0;

function reiniciarContexto() {
  tarjetaPegada.value = false;
  inicioFormulario = performance.now();
}

onMounted(reiniciarContexto);

async function pagar() {
  error.value = '';
  decision.value = null;
  enviando.value = true;
  try {
    decision.value = await autorizarCompra({
      numero_tarjeta: formulario.numero.replace(/\s/g, ''),
      fecha_vencimiento: formulario.vencimiento,
      monto: String(formulario.monto),
      canal: 'EN_LINEA',
      modo_lectura: 'DIGITADA',
      cvv: formulario.cvv,
      huella_dispositivo: calcularHuella(),
      segundos_formulario: Math.round((performance.now() - inicioFormulario) / 100) / 10,
      tarjeta_pegada: tarjetaPegada.value,
    });
    montoCobrado.value = String(formulario.monto);
    Object.assign(formulario, { numero: '', vencimiento: '', cvv: '', monto: '' });
    reiniciarContexto();
  } catch (e) {
    error.value = mensajeDeError(e);
  } finally {
    enviando.value = false;
  }
}
</script>

<template>
  <h1>Tienda en línea</h1>
  <p class="subtitulo">Checkout simulado, como lo vería un cliente en la tienda del comercio.</p>
  <div class="dos-columnas">
    <form class="panel" autocomplete="off" @submit.prevent="pagar">
      <p v-if="error" class="error" role="alert">{{ error }}</p>
      <div class="campo">
        <label for="monto">Valor de la compra (COP)</label>
        <input id="monto" v-model="formulario.monto" type="number" min="1" step="1" required />
      </div>
      <div class="campo">
        <label for="numero">Número de tarjeta</label>
        <input
          id="numero"
          v-model="formulario.numero"
          inputmode="numeric"
          autocomplete="off"
          pattern="[\d ]{13,23}"
          title="Entre 13 y 19 dígitos"
          required
          @paste="tarjetaPegada = true"
        />
      </div>
      <div class="fila-campos">
        <div class="campo">
          <label for="vencimiento">Vencimiento</label>
          <input
            id="vencimiento"
            v-model="formulario.vencimiento"
            placeholder="MM/AA"
            autocomplete="off"
            pattern="(0[1-9]|1[0-2])/\d{2}"
            title="Formato MM/AA"
            required
          />
        </div>
        <div class="campo">
          <label for="cvv">CVV</label>
          <input
            id="cvv"
            v-model="formulario.cvv"
            type="password"
            inputmode="numeric"
            autocomplete="off"
            pattern="\d{3,4}"
            title="3 o 4 dígitos"
            required
          />
        </div>
      </div>
      <button type="submit" :disabled="enviando">{{ enviando ? 'Autorizando…' : 'Pagar' }}</button>
    </form>
    <ResultadoCompra :decision="decision" :monto="montoCobrado" />
  </div>
</template>
