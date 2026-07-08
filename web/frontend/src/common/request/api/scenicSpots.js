import request from '@/common/request/request.js'

export function getScenicSpots() {
    return request.get('/api/scenic-spots')
}

export function createScenicSpot(data) {
    return request.post('/api/scenic-spots', data)
}

export function updateScenicSpot(id, data) {
    return request.put(`/api/scenic-spots/${id}`, data)
}

export function deleteScenicSpot(id) {
    return request.delete(`/api/scenic-spots/${id}`)
}
