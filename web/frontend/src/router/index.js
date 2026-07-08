import { createRouter, createWebHistory } from 'vue-router'

const routes = [
    {
        path: '/',
        redirect: '/dashboard',
    },
    {
        path: '/dashboard',
        name: 'Dashboard',
        component: () => import('../views/DashboardPage.vue'),
        meta: { title: '系统总览' },
    },
    {
        path: '/recognitions',
        name: 'Recognitions',
        component: () => import('../views/RecognitionsPage.vue'),
        meta: { title: '导览识别记录' },
    },
    {
        path: '/scenic-spots',
        name: 'ScenicSpots',
        component: () => import('../views/ScenicSpotsPage.vue'),
        meta: { title: '导览内容库管理' },
    },
    {
        path: '/qa-records',
        name: 'QARecords',
        component: () => import('../views/QARecordsPage.vue'),
        meta: { title: '智能问答记录' },
    },
    {
        path: '/devices',
        name: 'Devices',
        component: () => import('../views/DevicesPage.vue'),
        meta: { title: '设备管理' },
    },
]

const router = createRouter({
    history: createWebHistory(process.env.BASE_URL),
    routes,
})

// 本地演示不要求登录，移除路由守卫
router.afterEach((to) => {
    if (to.meta.title) {
        document.title = to.meta.title + ' - 智能导览眼镜'
    }
})

export default router
