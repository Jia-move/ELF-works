import * as I from '@/common/interactive.js'
import * as ReqConfig from '@/common/request/request-config.js'
import axios from 'axios'

// 创建 axios 实例
export const request = axios.create({
    baseURL: ReqConfig.BASE_URL,
    timeout: 10000,
    headers: {
        'Content-Type': 'application/json'
    }
})

// 当前演示不要求登录，不添加 JWT 拦截器

// 添加响应拦截器
request.interceptors.response.use(
    (response) => {
        const res = response.data
        if (res.status === 'success' && res.code === 200) {
            return res
        }
        // 其他情况展示错误信息
        const msg = res.message || '请求失败'
        I.showToast(msg, 'error')
        return Promise.reject(res)
    },
    (error) => {
        if (error.response) {
            const { status, data } = error.response
            const msg = (data && data.message) ? data.message : '服务器错误'
            I.showToast(`[${status}] ${msg}`, 'error')
        } else if (error.request) {
            I.showToast('网络请求超时，请检查网络连接', 'error')
        } else {
            I.showToast(`请求配置错误: ${error.message}`, 'error')
        }
        return Promise.reject(error)
    }
)

export default request
