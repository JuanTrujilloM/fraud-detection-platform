<script setup lang="ts">
defineProps<{ pagina: number; totalPaginas: number; cargando?: boolean }>();
defineEmits<{ ir: [pagina: number] }>();
</script>

<template>
  <nav v-if="totalPaginas > 1" class="paginacion" aria-label="Paginación">
    <button
      type="button"
      class="secundario"
      :disabled="pagina <= 1 || cargando"
      @click="$emit('ir', pagina - 1)"
    >
      Anterior
    </button>
    <span>Página {{ pagina }} de {{ totalPaginas }}</span>
    <button
      type="button"
      class="secundario"
      :disabled="pagina >= totalPaginas || cargando"
      @click="$emit('ir', pagina + 1)"
    >
      Siguiente
    </button>
  </nav>
</template>

<style scoped>
.paginacion {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 14px;
  margin-top: 16px;
  color: var(--texto-suave);
}
</style>
