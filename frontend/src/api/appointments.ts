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

export async function fetchAppointments(businessId: string): Promise<Appointment[]> {
  const response = await fetch(
    `/api/admin/appointments?business_id=${encodeURIComponent(businessId)}`,
  )
  if (!response.ok) {
    throw new Error(`Error ${response.status} al cargar las citas`)
  }
  return response.json()
}

export async function updateAppointmentStatus(
  businessId: string,
  appointmentId: string,
  status: AppointmentStatus,
): Promise<void> {
  const response = await fetch(
    `/api/admin/appointments/${appointmentId}/status?business_id=${encodeURIComponent(businessId)}`,
    {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ status }),
    },
  )
  if (!response.ok) {
    throw new Error(`Error ${response.status} al actualizar el estado`)
  }
}