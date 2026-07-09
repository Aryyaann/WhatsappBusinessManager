export interface ScheduleBlock {
  id: string
  date: string // YYYY-MM-DD
  start_time: string
  end_time: string
}

export interface EmployeeWeeklySchedule {
  employee_id: string
  employee_name: string
  schedule: ScheduleBlock[]
}

function authHeaders(idToken: string): HeadersInit {
  return { Authorization: `Bearer ${idToken}` }
}

export async function fetchWeeklySchedule(weekStart: string, idToken: string): Promise<EmployeeWeeklySchedule[]> {
  const response = await fetch(
    `/api/admin/employees/schedule?week_start=${encodeURIComponent(weekStart)}`,
    { headers: authHeaders(idToken) },
  )
  if (!response.ok) {
    throw new Error(`Error ${response.status} al cargar el horario semanal`)
  }
  return response.json()
}

export async function createScheduleBlock(
  employeeId: string,
  date: string,
  startTime: string,
  endTime: string,
  idToken: string,
): Promise<ScheduleBlock> {
  const response = await fetch(`/api/admin/employees/${employeeId}/schedule`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', ...authHeaders(idToken) },
    body: JSON.stringify({ date, start_time: startTime, end_time: endTime }),
  })
  if (!response.ok) {
    throw new Error(`Error ${response.status} al crear el bloque de horario`)
  }
  return response.json()
}

export async function updateScheduleBlock(
  employeeId: string,
  blockId: string,
  date: string,
  startTime: string,
  endTime: string,
  idToken: string,
): Promise<ScheduleBlock> {
  const response = await fetch(`/api/admin/employees/${employeeId}/schedule/${blockId}`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json', ...authHeaders(idToken) },
    body: JSON.stringify({ date, start_time: startTime, end_time: endTime }),
  })
  if (!response.ok) {
    throw new Error(`Error ${response.status} al mover el bloque de horario`)
  }
  return response.json()
}

export async function deleteScheduleBlock(employeeId: string, blockId: string, idToken: string): Promise<void> {
  const response = await fetch(`/api/admin/employees/${employeeId}/schedule/${blockId}`, {
    method: 'DELETE',
    headers: authHeaders(idToken),
  })
  if (!response.ok) {
    throw new Error(`Error ${response.status} al borrar el bloque de horario`)
  }
}