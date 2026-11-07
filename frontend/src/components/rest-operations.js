export const restOperations = {
  GET: 'Xem (GET)', POST: 'Tạo mới (POST)', PUT: 'Cập nhật toàn bộ (PUT)',
  PATCH: 'Cập nhật một phần (PATCH)', DELETE: 'Xóa (DELETE)', OTHER: 'Khác',
}

export function restOperation(value, actionCode = '') {
  if (Object.hasOwn(restOperations, value)) return value
  if (value === 'SELECT') return 'GET'
  if (value === 'INSERT') return 'POST'
  if (value === 'UPDATE') return actionCode.endsWith('.save') ? 'PUT' : 'PATCH'
  return 'OTHER'
}

export function restOperationLabel(value, actionCode) {
  return restOperations[restOperation(value, actionCode)]
}
