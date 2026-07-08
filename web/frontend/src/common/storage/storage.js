import {cache} from "./cache.js"

// 通用 localStorage 存取工具
// 当前演示无需 JWT 登录，保留基础缓存能力供未来扩展

export function getCacheValue(key, obj) {
    return null != cache(key) ? cache(key)[obj] : null
}

export function saveCacheValue(key, value) {
    try {
        cache(key, value)
    } catch (e) {
        console.error('保存缓存失败:', e)
    }
}

export function clearCacheValue(key) {
    try {
        localStorage.removeItem(key)
    } catch (e) {
        console.error(`清除缓存 ${key} 失败:`, e)
    }
}
