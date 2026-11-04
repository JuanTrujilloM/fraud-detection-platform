<script setup lang="ts">
import { computed } from 'vue';

import { etiqueta } from '@/shared/utils/formato';

const props = defineProps<{ valor: string | null }>();

const TONOS: Record<string, string> = {
  APROBADA: 'ok',
  ACTIVA: 'ok',
  ACTIVO: 'ok',
  RESUELTO: 'ok',
  DESCARTADA: 'ok',
  RECHAZADA: 'mal',
  BLOQUEADA: 'mal',
  BLOQUEADO: 'mal',
  CONFIRMADA_FRAUDE: 'mal',
  PENDIENTE: 'aviso',
  RADICADO: 'aviso',
  EN_REVISION: 'aviso',
};

const tono = computed(() => (props.valor ? (TONOS[props.valor] ?? '') : ''));
</script>

<template>
  <span class="insignia" :class="tono">{{ etiqueta(valor) }}</span>
</template>
