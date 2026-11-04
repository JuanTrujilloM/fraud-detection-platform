import type { RouteRecordRaw } from 'vue-router';

const rutas: RouteRecordRaw[] = [
  {
    path: '/comercio',
    component: () => import('@/features/comercio/views/ComercioLayout.vue'),
    meta: { rol: 'COMERCIO' },
    redirect: '/comercio/terminal',
    children: [
      {
        path: 'terminal',
        component: () => import('@/features/comercio/views/TerminalView.vue'),
        meta: { titulo: 'Terminal presencial' },
      },
      {
        path: 'tienda',
        component: () => import('@/features/comercio/views/TiendaView.vue'),
        meta: { titulo: 'Tienda en línea', soloVentaEnLinea: true },
      },
      {
        path: 'historial',
        component: () => import('@/features/comercio/views/HistorialView.vue'),
        meta: { titulo: 'Historial' },
      },
    ],
  },
];

export default rutas;
