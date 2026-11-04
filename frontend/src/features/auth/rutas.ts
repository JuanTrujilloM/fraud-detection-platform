import type { RouteRecordRaw } from 'vue-router';

const rutas: RouteRecordRaw[] = [
  { path: '/', redirect: '/login' },
  {
    path: '/login',
    component: () => import('@/features/auth/views/LoginView.vue'),
    meta: { titulo: 'Iniciar sesión' },
  },
];

export default rutas;
