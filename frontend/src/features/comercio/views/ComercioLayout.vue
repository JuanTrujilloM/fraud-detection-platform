<script setup lang="ts">
import { computed } from 'vue';

import useAuthStore from '@/features/auth/store';
import ModuloLayout from '@/shared/components/ModuloLayout.vue';

const auth = useAuthStore();
const enlaces = computed(() => [
  { a: '/comercio/terminal', texto: 'Terminal' },
  ...(auth.usuario?.vende_en_linea ? [{ a: '/comercio/tienda', texto: 'Tienda en línea' }] : []),
  { a: '/comercio/historial', texto: 'Historial' },
]);
</script>

<template>
  <ModuloLayout modulo="Terminal de pago" :enlaces="enlaces" />
</template>
