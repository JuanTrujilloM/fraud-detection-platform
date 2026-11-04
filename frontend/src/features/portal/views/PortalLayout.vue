<script setup lang="ts">
import ModuloLayout from '@/shared/components/ModuloLayout.vue';

const enlaces = [
  { a: '/portal/tarjetas', texto: 'Mis tarjetas' },
  { a: '/portal/reclamos', texto: 'Mis reclamos' },
  { a: '/portal/perfil', texto: 'Mis datos' },
];
</script>

<template>
  <ModuloLayout modulo="Portal del asociado" :enlaces="enlaces" />
</template>
