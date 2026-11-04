<script setup lang="ts">
import { ref } from 'vue';
import { useRouter } from 'vue-router';

import { rutaInicial } from '@/app/guardia';
import useAuthStore from '@/features/auth/store';
import { mensajeDeError } from '@/shared/utils/errores';

const auth = useAuthStore();
const router = useRouter();

const username = ref('');
const password = ref('');
const error = ref('');
const enviando = ref(false);

async function entrar() {
  error.value = '';
  enviando.value = true;
  try {
    const usuario = await auth.login(username.value.trim(), password.value);
    const inicio = rutaInicial(usuario.rol);
    if (inicio) {
      await router.push(inicio);
    } else {
      window.location.assign('/admin/');
    }
  } catch (e) {
    error.value = mensajeDeError(e, 'Usuario o contraseña incorrectos.');
  } finally {
    enviando.value = false;
  }
}
</script>

<template>
  <main class="login">
    <form class="panel" @submit.prevent="entrar">
      <p class="marca">CoopAndina</p>
      <h1>Iniciar sesión</h1>
      <p class="subtitulo">Comercios, asociados y analistas entran por aquí.</p>
      <p v-if="error" class="error" role="alert">{{ error }}</p>
      <div class="campo">
        <label for="usuario">Usuario</label>
        <input id="usuario" v-model="username" autocomplete="username" required />
      </div>
      <div class="campo">
        <label for="clave">Contraseña</label>
        <input
          id="clave"
          v-model="password"
          type="password"
          autocomplete="current-password"
          required
        />
      </div>
      <button type="submit" class="entrar" :disabled="enviando">
        {{ enviando ? 'Entrando…' : 'Entrar' }}
      </button>
    </form>
  </main>
</template>

<style scoped>
.login {
  display: grid;
  min-height: 100vh;
  padding: 16px;
  place-items: center;
}

form {
  width: min(400px, 100%);
  padding: 28px;
}

.marca {
  margin: 0 0 20px;
  color: var(--marca);
  font-weight: 700;
}

.entrar {
  width: 100%;
}
</style>
