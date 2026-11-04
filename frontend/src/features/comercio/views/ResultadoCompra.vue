<script setup lang="ts">
import type { Decision } from '@/features/comercio/services/comercio';
import { formatoMoneda, MOTIVOS } from '@/shared/utils/formato';

defineProps<{ decision: Decision | null; monto: string }>();
</script>

<template>
  <section class="panel resultado" :class="decision?.resultado" aria-live="polite">
    <template v-if="decision">
      <p class="titulo">{{ decision.resultado === 'APROBADA' ? 'Aprobada' : 'Rechazada' }}</p>
      <p class="monto">{{ formatoMoneda(monto) }}</p>
      <p v-if="decision.motivo_rechazo">
        {{ MOTIVOS[decision.motivo_rechazo] ?? decision.motivo_rechazo }}
      </p>
      <p v-if="decision.id_autorizacion" class="referencia">
        Autorización #{{ decision.id_autorizacion }}
      </p>
    </template>
    <p v-else class="espera">El resultado de la compra aparece aquí.</p>
  </section>
</template>

<style scoped>
.resultado p {
  margin: 0 0 4px;
}

.titulo {
  font-size: 1.25rem;
  font-weight: 700;
}

.monto {
  font-size: 1.75rem;
  font-variant-numeric: tabular-nums;
}

.APROBADA {
  border-color: var(--ok);
  background: var(--ok-suave);
  color: var(--ok);
}

.RECHAZADA {
  border-color: var(--mal);
  background: var(--mal-suave);
  color: var(--mal);
}

.referencia {
  font-size: 0.875rem;
}

.espera {
  color: var(--texto-suave);
}
</style>
