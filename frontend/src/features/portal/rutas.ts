import type { RouteRecordRaw } from 'vue-router';

const rutas: RouteRecordRaw[] = [
  {
    path: '/portal',
    component: () => import('@/features/portal/views/PortalLayout.vue'),
    meta: { rol: 'ASOCIADO' },
    redirect: '/portal/tarjetas',
    children: [
      {
        path: 'tarjetas',
        component: () => import('@/features/portal/views/TarjetasView.vue'),
        meta: { titulo: 'Mis tarjetas' },
      },
      {
        path: 'tarjetas/:id',
        component: () => import('@/features/portal/views/MovimientosView.vue'),
        props: (ruta) => ({ id: Number(ruta.params.id) }),
        meta: { titulo: 'Movimientos' },
      },
      {
        path: 'reclamos',
        component: () => import('@/features/portal/views/ReclamosView.vue'),
        meta: { titulo: 'Mis reclamos' },
      },
      {
        path: 'perfil',
        component: () => import('@/features/portal/views/PerfilView.vue'),
        meta: { titulo: 'Mis datos' },
      },
    ],
  },
];

export default rutas;
