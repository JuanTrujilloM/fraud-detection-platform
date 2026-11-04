import { createRouter, createWebHistory } from 'vue-router';

import { resolverGuardia, type MetaRuta } from '@/app/guardia';
import rutasAuth from '@/features/auth/rutas';
import rutasComercio from '@/features/comercio/rutas';
import rutasConsola from '@/features/consola/rutas';
import rutasPortal from '@/features/portal/rutas';
import useAuthStore from '@/features/auth/store';

const router = createRouter({
  history: createWebHistory(),
  routes: [
    ...rutasAuth,
    ...rutasComercio,
    ...rutasPortal,
    ...rutasConsola,
    { path: '/:pathMatch(.*)*', redirect: '/login' },
  ],
});

router.beforeEach((to) => {
  const meta: MetaRuta = {};
  for (const registro of to.matched) Object.assign(meta, registro.meta);
  return resolverGuardia(to.path, meta, useAuthStore().usuario) ?? true;
});

router.afterEach((to) => {
  const titulo = to.meta.titulo as string | undefined;
  document.title = titulo ? `${titulo} · CoopAndina` : 'CoopAndina';
});

export default router;
