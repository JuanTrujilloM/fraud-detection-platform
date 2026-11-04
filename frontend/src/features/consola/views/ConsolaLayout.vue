<script setup lang="ts">
import ModuloLayout from '@/shared/components/ModuloLayout.vue';

const enlaces = [
  { a: '/consola/alertas', texto: 'Alertas' },
  { a: '/consola/bloqueos', texto: 'Bloqueos' },
  { a: '/consola/reclamos', texto: 'Reclamos' },
];
</script>

<template>
  <ModuloLayout modulo="Consola de fraude" :enlaces="enlaces" />
</template>
