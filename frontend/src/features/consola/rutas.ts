import type { RouteRecordRaw } from 'vue-router';

const rutas: RouteRecordRaw[] = [
  {
    path: '/consola',
    component: () => import('@/features/consola/views/ConsolaLayout.vue'),
    meta: { rol: 'ANALISTA' },
    redirect: '/consola/alertas',
    children: [
      {
        path: 'alertas',
        component: () => import('@/features/consola/views/AlertasView.vue'),
        meta: { titulo: 'Alertas' },
      },
      {
        path: 'alertas/:id',
        component: () => import('@/features/consola/views/AlertaDetalleView.vue'),
        props: (ruta) => ({ id: Number(ruta.params.id) }),
        meta: { titulo: 'Detalle de alerta' },
      },
      {
        path: 'bloqueos',
        component: () => import('@/features/consola/views/BloqueosView.vue'),
        meta: { titulo: 'Bloqueos' },
      },
      {
        path: 'reclamos',
        component: () => import('@/features/consola/views/ReclamosView.vue'),
        meta: { titulo: 'Reclamos' },
      },
    ],
  },
];

export default rutas;
