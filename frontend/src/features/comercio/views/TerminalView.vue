<script setup lang="ts">
import { reactive, ref } from 'vue';

import { autorizarCompra, type Decision } from '@/features/comercio/services/comercio';
import ResultadoCompra from '@/features/comercio/views/ResultadoCompra.vue';
import { mensajeDeError } from '@/shared/utils/errores';

const formulario = reactive({
  numero: '',
  vencimiento: '',
  monto: '' as number | '',
  modo: 'CHIP' as 'CHIP' | 'BANDA',
});
const decision = ref<Decision | null>(null);
const montoCobrado = ref('');
const error = ref('');
const enviando = ref(false);

async function cobrar() {
  error.value = '';
  decision.value = null;
  enviando.value = true;
  try {
    decision.value = await autorizarCompra({
      numero_tarjeta: formulario.numero.replace(/\s/g, ''),
      fecha_vencimiento: formulario.vencimiento,
      monto: String(formulario.monto),
      canal: 'PRESENCIAL',
      modo_lectura: formulario.modo,
    });
    montoCobrado.value = String(formulario.monto);
    // Los datos de la tarjeta no se quedan en pantalla.
    formulario.numero = '';
    formulario.vencimiento = '';
    formulario.monto = '';
  } catch (e) {
    error.value = mensajeDeError(e);
  } finally {
    enviando.value = false;
  }
}
</script>

<template>
  <h1>Terminal presencial</h1>
  <p class="subtitulo">Registra una compra con la tarjeta en la mano.</p>
  <div class="dos-columnas">
    <form class="panel" @submit.prevent="cobrar">
      <p v-if="error" class="error" role="alert">{{ error }}</p>
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
          <label for="monto">Monto (COP)</label>
          <input id="monto" v-model="formulario.monto" type="number" min="1" step="1" required />
        </div>
      </div>
      <fieldset class="campo">
        <legend class="etiqueta">Modo de lectura</legend>
        <div class="opciones">
          <label><input v-model="formulario.modo" type="radio" value="CHIP" /> Chip</label>
          <label><input v-model="formulario.modo" type="radio" value="BANDA" /> Banda</label>
        </div>
      </fieldset>
      <button type="submit" :disabled="enviando">{{ enviando ? 'Autorizando…' : 'Cobrar' }}</button>
    </form>
    <ResultadoCompra :decision="decision" :monto="montoCobrado" />
  </div>
</template>

<style scoped>
fieldset {
  padding: 0;
  border: 0;
}

.opciones {
  display: flex;
  gap: 20px;
  margin-top: 4px;
}

.opciones label {
  display: flex;
  align-items: center;
  gap: 6px;
  font-weight: 400;
}

.opciones input {
  width: auto;
}
</style>
