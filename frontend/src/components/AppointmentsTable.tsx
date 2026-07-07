import { useState } from 'react'
import type { Appointment, AppointmentStatus } from '../api/appointments'

type SortKey = 'start_at' | 'customer_name' | 'employee_name'
type SortDir = 'asc' | 'desc'

const STATUS_OPTIONS: AppointmentStatus[] = [
  'pending',
  'confirmed',
  'cancelled',
  'completed',
  'no_show',
]

const STATUS_LABELS: Record<AppointmentStatus, string> = {
  pending: 'Pendiente',
  confirmed: 'Confirmada',
  cancelled: 'Cancelada',
  completed: 'Completada',
  no_show: 'No presentado',
}

const STATUS_STYLES: Record<AppointmentStatus, string> = {
  pending: 'border-amber-400/30 bg-amber-400/10 text-amber-400',
  confirmed: 'border-emerald-400/30 bg-emerald-400/10 text-emerald-400',
  cancelled: 'border-red-400/30 bg-red-400/10 text-red-400',
  completed: 'border-neutral-500/30 bg-neutral-500/10 text-neutral-400',
  no_show: 'border-orange-400/30 bg-orange-400/10 text-orange-400',
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

function StatusEditor({
  status,
  onSave,
}: {
  status: AppointmentStatus
  onSave: (newStatus: AppointmentStatus) => Promise<void>
}) {
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState('')

  return (
    <div className="flex items-center gap-1">
      <select
        value={status}
        disabled={saving}
        onChange={async (event) => {
          const newStatus = event.target.value as AppointmentStatus
          setSaving(true)
          setError('')
          try {
            await onSave(newStatus)
          } catch (err) {
            setError((err as Error).message)
          } finally {
            setSaving(false)
          }
        }}
        className={`rounded-full border px-2 py-0.5 text-xs outline-none ${STATUS_STYLES[status]}`}
      >
        {STATUS_OPTIONS.map((option) => (
          <option key={option} value={option} className="bg-neutral-900 text-neutral-100">
            {STATUS_LABELS[option]}
          </option>
        ))}
      </select>
      {error && <span className="text-xs text-red-400">{error}</span>}
    </div>
  )
}

function SortHeader({
  label,
  sortKey,
  activeKey,
  activeDir,
  onSort,
}: {
  label: string
  sortKey: SortKey
  activeKey: SortKey
  activeDir: SortDir
  onSort: (key: SortKey) => void
}) {
  const isActive = sortKey === activeKey
  return (
    <th className="px-4 py-3 text-left font-medium">
      <button
        type="button"
        onClick={() => onSort(sortKey)}
        className="inline-flex items-center gap-1 hover:text-neutral-200"
      >
        {label}
        {isActive && <span className="text-neutral-500">{activeDir === 'asc' ? '↑' : '↓'}</span>}
      </button>
    </th>
  )
}

interface AppointmentsTableProps {
  appointments: Appointment[]
  onUpdateStatus: (appointmentId: string, status: AppointmentStatus) => Promise<void>
}

export function AppointmentsTable({ appointments, onUpdateStatus }: AppointmentsTableProps) {
  const [sortKey, setSortKey] = useState<SortKey>('start_at')
  const [sortDir, setSortDir] = useState<SortDir>('asc')

  if (appointments.length === 0) {
    return (
      <div className="rounded-lg border border-neutral-800 bg-neutral-900 px-6 py-12 text-center">
        <p className="text-neutral-400">No hay citas que coincidan.</p>
      </div>
    )
  }

  function handleSort(key: SortKey) {
    if (key === sortKey) {
      setSortDir(sortDir === 'asc' ? 'desc' : 'asc')
    } else {
      setSortKey(key)
      setSortDir('asc')
    }
  }

  const sorted = [...appointments].sort((a, b) => {
    let result = 0
    if (sortKey === 'start_at') result = a.start_at.localeCompare(b.start_at)
    if (sortKey === 'customer_name') result = (a.customer_name ?? '').localeCompare(b.customer_name ?? '')
    if (sortKey === 'employee_name') result = (a.employee_name ?? '').localeCompare(b.employee_name ?? '')
    return sortDir === 'asc' ? result : -result
  })

  return (
    <div className="overflow-hidden rounded-lg border border-neutral-800">
      <table className="w-full text-left text-sm">
        <thead>
          <tr className="border-b border-neutral-800 bg-neutral-900 text-neutral-400">
            <SortHeader label="Fecha y hora" sortKey="start_at" activeKey={sortKey} activeDir={sortDir} onSort={handleSort} />
            <SortHeader label="Cliente" sortKey="customer_name" activeKey={sortKey} activeDir={sortDir} onSort={handleSort} />
            <th className="px-4 py-3 font-medium">Teléfono</th>
            <SortHeader label="Empleado" sortKey="employee_name" activeKey={sortKey} activeDir={sortDir} onSort={handleSort} />
            <th className="px-4 py-3 font-medium">Servicio</th>
            <th className="px-4 py-3 font-medium">Estado</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-neutral-800">
          {sorted.map((appointment) => (
            <tr key={appointment.id} className="bg-neutral-950 hover:bg-neutral-900">
              <td className="px-4 py-3 text-neutral-100">
                {formatDateTime(appointment.start_at)} – {formatDateTime(appointment.end_at).split(', ')[1]}
              </td>
              <td className="px-4 py-3 text-neutral-100">{appointment.customer_name ?? '—'}</td>
              <td className="px-4 py-3 text-neutral-500">{appointment.customer_phone}</td>
              <td className="px-4 py-3 text-neutral-400">{appointment.employee_name ?? '—'}</td>
              <td className="px-4 py-3 text-neutral-400">{appointment.service_name ?? '—'}</td>
              <td className="px-4 py-3">
                <StatusEditor
                  status={appointment.status}
                  onSave={(newStatus) => onUpdateStatus(appointment.id, newStatus)}
                />
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
