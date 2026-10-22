import { createRouter, createWebHistory } from 'vue-router'
import { useAppStore } from '../stores/appStore'

const routes = [
  {
    path: '/login',
    name: 'login',
    component: () => import('../views/LoginView.vue'),
    meta: { public: true, title: '登录' }
  },
  {
    path: '/',
    component: () => import('../components/AppLayout.vue'),
    children: [
      { path: '', redirect: '/dashboard' },
      {
        path: 'dashboard',
        name: 'dashboard',
        component: () => import('../views/DashboardView.vue'),
        meta: { menu: 'dashboard', title: '工作台' }
      },
      {
        path: 'documents',
        name: 'documents',
        component: () => import('../views/DocumentsView.vue'),
        meta: { menu: 'documents', title: '单据管理' }
      },
      {
        path: 'documents/new',
        name: 'document-new',
        component: () => import('../views/DocumentNewView.vue'),
        meta: { menu: 'documents', title: '新建单据' }
      },
      {
        path: 'documents/:id',
        name: 'document-detail',
        component: () => import('../views/DocumentDetailView.vue'),
        meta: { menu: 'documents', title: '单据详情' }
      },
      {
        path: 'risks',
        name: 'risks',
        component: () => import('../views/RisksView.vue'),
        meta: { menu: 'risks', title: '风险分析' }
      },
      {
        path: 'approvals',
        name: 'approvals',
        component: () => import('../views/ApprovalsView.vue'),
        meta: { menu: 'approvals', title: '审批中心', roles: ['DEPT_MANAGER', 'FINANCE', 'ADMIN'] }
      },
      {
        path: 'reports',
        name: 'reports',
        component: () => import('../views/ReportCenterView.vue'),
        meta: { menu: 'reports', title: '报告中心' }
      },
      {
        path: 'reports/:docId',
        name: 'report-detail',
        component: () => import('../views/ReportView.vue'),
        meta: { menu: 'reports', title: '风险审核报告' }
      },
      {
        path: 'logs',
        name: 'logs',
        component: () => import('../views/AuditLogsView.vue'),
        meta: { menu: 'logs', title: '审计日志', roles: ['FINANCE', 'ADMIN'] }
      },
      {
        path: 'admin',
        name: 'admin',
        component: () => import('../views/AdminView.vue'),
        meta: { menu: 'admin', title: '系统管理', roles: ['ADMIN'] }
      }
    ]
  },
  { path: '/:pathMatch(.*)*', redirect: '/dashboard' }
]

const router = createRouter({
  history: createWebHistory(),
  routes,
  scrollBehavior: () => ({ top: 0 })
})

router.beforeEach((to) => {
  const store = useAppStore()
  if (!to.meta.public && !store.state.auth) {
    return { name: 'login', query: { redirect: to.fullPath } }
  }
  if (to.name === 'login' && store.state.auth) {
    return { name: 'dashboard' }
  }
  if (to.meta.roles && !to.meta.roles.includes(store.state.user?.role_code)) {
    return { name: 'dashboard' }
  }
  document.title = to.meta.title
    ? `${to.meta.title} · 财务风审平台`
    : '财务单据智能风险审核系统'
  return true
})

export default router
