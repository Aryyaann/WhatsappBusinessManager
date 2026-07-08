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

function authHeaders(idToken: string): HeadersInit {
  return { Authorization: `Bearer ${idToken}` }
}

export async function fetchAppointments(idToken: string): Promise<Appointment[]> {
  const response = await fetch('/api/admin/appointments', { headers: authHeaders(idToken) })
  if (!response.ok) {
    throw new Error(`Error ${response.status} al cargar las citas`)
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