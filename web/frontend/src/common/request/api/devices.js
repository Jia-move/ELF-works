import request from '@/common/request/request.js'

export function getDevices() {
    return request.get('/api/devices')
}
