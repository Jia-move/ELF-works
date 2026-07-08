import request from '@/common/request/request.js'

export function getRecognitions(params = {}) {
    return request.get('/api/recognitions', { params })
}
