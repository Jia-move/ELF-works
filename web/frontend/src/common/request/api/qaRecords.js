import request from '@/common/request/request.js'

export function getQARecords(params = {}) {
    return request.get('/api/qa-records', { params })
}
