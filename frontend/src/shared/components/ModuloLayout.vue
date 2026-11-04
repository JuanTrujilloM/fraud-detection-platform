<script setup lang="ts">
import { useRouter } from 'vue-router';

import useAuthStore from '@/features/auth/store';

export interface EnlaceNav {
  a: string;
  texto: string;
}

defineProps<{ modulo: string; enlaces: EnlaceNav[] }>();

const auth = useAuthStore();
const router = useRouter();

async function salir() {
  auth.salir();
  await router.push('/login');
}
</script>

<template>
  <header class="barra">
    <div class="interno">
      <div class="identidad">
        <strong>CoopAndina</strong>
        <span>{{ modulo }}</span>
      </div>
      <nav aria-label="Secciones">
        <RouterLink v-for="enlace in enlaces" :key="enlace.a" :to="enlace.a">
          {{ enlace.texto }}
        </RouterLink>
      </nav>
      <div class="sesion">
        <span class="nombre">{{ auth.usuario?.nombre ?? auth.usuario?.username }}</span>
        <button type="button" class="salir" @click="salir">Salir</button>
      </div>
    </div>
  </header>
  <main class="contenido">
    <RouterView />
  </main>
</template>

<style scoped>
.barra {
  background: var(--marca-oscura);
  color: #fff;
}

.interno {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 8px 28px;
  max-width: 1120px;
  margin: 0 auto;
  padding: 10px 16px;
}

.identidad {
  display: flex;
  align-items: baseline;
  gap: 10px;
}

.identidad span {
  color: #b9d4c7;
  font-size: 0.875rem;
}

nav {
  display: flex;
  flex-wrap: wrap;
  flex: 1;
  gap: 4px;
}

nav a {
  padding: 6px 12px;
  border-radius: 6px;
  color: #dcebe3;
  text-decoration: none;
}

nav a:hover {
  background: rgb(255 255 255 / 10%);
}

nav a.router-link-active {
  background: rgb(255 255 255 / 16%);
  color: #fff;
  font-weight: 600;
}

nav a:focus-visible,
.salir:focus-visible {
  outline-color: #fff;
}

@media (max-width: 860px) {
  .interno {
    justify-content: space-between;
  }

  nav {
    order: 3;
    flex-basis: 100%;
  }
}

.sesion {
  display: flex;
  align-items: center;
  gap: 12px;
}

.nombre {
  color: #dcebe3;
  font-size: 0.875rem;
}

.salir {
  padding: 5px 12px;
  border-color: rgb(255 255 255 / 40%);
  background: transparent;
}

.salir:hover:not(:disabled) {
  background: rgb(255 255 255 / 12%);
}

.contenido {
  max-width: 1120px;
  margin: 0 auto;
  padding: 28px 16px 48px;
}
</style>
