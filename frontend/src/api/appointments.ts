export type AppointmentStatus = 'pending' | 'confirmed' | 'cancelled' | 'completed' | 'no_show'

export interface Appointment {
  id: string
  customer_name: string | null
  customer_phone: string
  employee_name: string | null
  service_name: string | null
  start_at: string
  end_at: string
  status: AppointmentStatus
  notes: string | null
}

export interface ServiceOption {
  id: string
  name: string
  duration_minutes: number
  price: number | null
}

export interface AppointmentInput {
  employee_id: string
  service_id: string
  start_at: string
  customer_name?: string
  customer_phone: string
  notes?: string
}

function authHeaders(idToken: string): HeadersInit {
  return { Authorization: `Bearer ${idToken}` }
}

async function readErrorDetail(response: Response, fallback: string): Promise<string> {
  try {
    const body = await response.json()
    if (body?.detail) return body.detail
  } catch {
    // El cuerpo no era JSON — nos quedamos con el mensaje genérico.
  }
  return fallback
}

export async function fetchAppointments(idToken: string): Promise<Appointment[]> {
  const response = await fetch('/api/admin/appointments', { headers: authHeaders(idToken) })
  if (!response.ok) {
    throw new Error(`Error ${response.status} al cargar las citas`)
  }
  return response.json()
}

export async function fetchServices(idToken: string): Promise<ServiceOption[]> {
  const response = await fetch('/api/admin/services', { headers: authHeaders(idToken) })
  if (!response.ok) {
    throw new Error(`Error ${response.status} al cargar servicios`)
  }
  return response.json()
}

export async function createAppointment(input: AppointmentInput, idToken: string): Promise<Appointment> {
  const response = await fetch('/api/admin/appointments', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', ...authHeaders(idToken) },
    body: JSON.stringify(input),
  })
  if (!response.ok) {
    throw new Error(await readErrorDetail(response, `Error ${response.status} al crear la cita`))
  }
  return response.json()
}

export async function updateAppointmentStatus(
  appointmentId: string,
  status: AppointmentStatus,
  idToken: string,
): Promise<void> {
  const response = await fetch(`/api/admin/appointments/${appointmentId}/status`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json', ...authHeaders(idToken) },
    body: JSON.stringify({ status }),
  })
  if (!response.ok) {
    throw new Error(`Error ${response.status} al actualizar el estado`)
  }
}