import { useState } from 'react'
import { confirmAppointment, type Appointment } from '../api/appointments'
import type { Employee } from '../api/employees'

interface PendingAppointmentsPanelProps {
  appointments: Appointment[]
  employees: Employee[]
  idToken: string
  onConfirmed: () => void
}

function formatDateTime(iso: string): string {
  const date = new Date(iso)
  return date.toLocaleString('es-ES', {
    day: '2-digit',
    month: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  })
}

function PendingAppointmentRow({
  appointment,
  employees,
  idToken,
  onConfirmed,
}: {
  appointment: Appointment
  employees: Employee[]
  idToken: string
  onConfirmed: () => void
}) {
  const currentEmployee = employees.find((e) => e.name === appointment.employee_name)
  const [selectedEmployeeId, setSelectedEmployeeId] = useState(currentEmployee?.id ?? '')
  const [submitting, setSubmitting] = useState(false)
  const [feedback, setFeedback] = useState<{ ok: boolean; text: string } | null>(null)

  async function handleConfirm() {
    setSubmitting(true)
    setFeedback(null)
    try {
      const result = await confirmAppointment(appointment.id, selectedEmployeeId || null, idToken)
      setFeedback({
        ok: true,
        text: result.whatsapp_sent
          ? `Confirmada con ${result.employee_name} — WhatsApp enviado al cliente.`
          : `Confirmada con ${result.employee_name} — no se pudo avisar por WhatsApp (${result.whatsapp_error}).`,
      })
      onConfirmed()
    } catch (err) {
      setFeedback({ ok: false, text: err instanceof Error ? err.message : 'Error desconocido' })
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <div className="rounded-md border border-amber-400/30 bg-amber-400/5 p-3">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <p className="text-sm text-neutral-100">
            {appointment.service_name ?? 'Servicio'} — {appointment.customer_name ?? appointment.customer_phone}
          </p>
          <p className="text-xs text-neutral-500">
            {formatDateTime(appointment.start_at)} · {appointment.customer_phone}
          </p>
          {appointment.notes && <p className="mt-1 text-xs text-amber-400/80">{appointment.notes}</p>}
        </div>

        <div className="flex items-center gap-2">
          <select
            value={selectedEmployeeId}
            onChange={(event) => setSelectedEmployeeId(event.target.value)}
            className="rounded-md border border-neutral-800 bg-neutral-950 px-2 py-1.5 text-xs text-neutral-100 outline-none focus:border-neutral-600"
          >
            <option value="">Sin asignar</option>
            {employees.map((employee) => (
              <option key={employee.id} value={employee.id}>
                {employee.name}
              </option>
            ))}
          </select>
          <button
            type="button"
            onClick={handleConfirm}
            disabled={submitting || !selectedEmployeeId}
            className="rounded-md bg-neutral-100 px-3 py-1.5 text-xs font-medium text-neutral-950 hover:bg-neutral-300 disabled:opacity-50"
          >
            {submitting ? 'Confirmando…' : 'Confirmar'}
          </button>
        </div>
      </div>

      {feedback && (
        <p className={`mt-2 text-xs ${feedback.ok ? 'text-emerald-400' : 'text-red-400'}`}>{feedback.text}</p>
      )}
    </div>
  )
}

export function PendingAppointmentsPanel({
  appointments,
  employees,
  idToken,
  onConfirmed,
}: PendingAppointmentsPanelProps) {
  const pending = appointments.filter((a) => a.status === 'pending')

  if (pending.length === 0) return null

  return (
    <div className="mb-6">
      <h2 className="mb-2 flex items-center gap-2 text-sm font-medium text-neutral-200">
        Citas pendientes de confirmar
        <span className="rounded-full bg-amber-400/20 px-2 py-0.5 text-xs text-amber-400">{pending.length}</span>
      </h2>
      <div className="flex flex-col gap-2">
        {pending.map((appointment) => (
          <PendingAppointmentRow
            key={appointment.id}
            appointment={appointment}
            employees={employees}
            idToken={idToken}
            onConfirmed={onConfirmed}
          />
        ))}
      </div>
    </div>
  )
}
