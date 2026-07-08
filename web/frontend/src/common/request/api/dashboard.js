import request from '@/common/request/request.js'

export function getDashboardSummary() {
    return request.get('/api/dashboard/summary')
}
