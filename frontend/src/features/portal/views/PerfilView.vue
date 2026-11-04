<script setup lang="ts">
import { onMounted, ref } from 'vue';

import { actualizarPerfil, obtenerPerfil, type Perfil } from '@/features/portal/services/portal';
import { mensajeDeError } from '@/shared/utils/errores';

const perfil = ref<Perfil | null>(null);
const celular = ref('');
const email = ref('');
const error = ref('');
const exito = ref('');
const guardando = ref(false);

function aplicar(datos: Perfil) {
  perfil.value = datos;
  celular.value = datos.celular;
  email.value = datos.email;
}

async function guardar() {
  error.value = '';
  exito.value = '';
  guardando.value = true;
  try {
    aplicar(await actualizarPerfil({ celular: celular.value, email: email.value }));
    exito.value = 'Guardamos tus datos.';
  } catch (e) {
    error.value = mensajeDeError(e);
  } finally {
    guardando.value = false;
  }
}

onMounted(async () => {
  try {
    aplicar(await obtenerPerfil());
  } catch (e) {
    error.value = mensajeDeError(e, 'No se pudieron cargar tus datos.');
  }
});
</script>

<template>
  <h1>Mis datos</h1>
  <p class="subtitulo">Puedes cambiar tu celular y tu correo.</p>
  <p v-if="error" class="error" role="alert">{{ error }}</p>
  <div v-if="perfil" class="dos-columnas">
    <form class="panel" @submit.prevent="guardar">
      <p v-if="exito" class="exito" role="status">{{ exito }}</p>
      <div class="campo">
        <label for="celular">Celular</label>
        <input id="celular" v-model="celular" type="tel" autocomplete="tel" required />
      </div>
      <div class="campo">
        <label for="correo">Correo</label>
        <input id="correo" v-model="email" type="email" autocomplete="email" required />
      </div>
      <button type="submit" :disabled="guardando">
        {{ guardando ? 'Guardando…' : 'Guardar' }}
      </button>
    </form>
    <section class="panel">
      <h2>Datos de afiliación</h2>
      <dl class="datos">
        <dt>Nombre</dt>
        <dd>{{ perfil.nombres }} {{ perfil.apellidos }}</dd>
        <dt>Documento</dt>
        <dd>{{ perfil.tipo_documento }} {{ perfil.numero_documento }}</dd>
        <dt>Ciudad</dt>
        <dd>{{ perfil.ciudad }}</dd>
      </dl>
    </section>
  </div>
</template>
