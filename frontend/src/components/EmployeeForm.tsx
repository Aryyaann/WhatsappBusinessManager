import { useState, type FormEvent } from 'react'
import { createEmployee, type EmployeeInput, type ScheduleSlotInput } from '../api/employees'

interface EmployeeFormProps {
  idToken: string
  onCreated: () => void
  onCancel: () => void
}

const inputClass =
  'w-full rounded-md border border-neutral-800 bg-neutral-950 px-3 py-2 text-sm text-neutral-100 placeholder-neutral-600 outline-none focus:border-neutral-600'
const labelClass = 'mb-1 block text-xs font-medium text-neutral-500'

const DAYS = [
  { value: 0, label: 'Lunes' },
  { value: 1, label: 'Martes' },
  { value: 2, label: 'Miércoles' },
  { value: 3, label: 'Jueves' },
  { value: 4, label: 'Viernes' },
  { value: 5, label: 'Sábado' },
  { value: 6, label: 'Domingo' },
]

interface DayState {
  enabled: boolean
  start: string
  end: string
}

function defaultDayState(): DayState {
  return { enabled: false, start: '09:00', end: '18:00' }
}

export function EmployeeForm({ idToken, onCreated, onCancel }: EmployeeFormProps) {
  const [name, setName] = useState('')
  const [whatsappNumber, setWhatsappNumber] = useState('')
  const [days, setDays] = useState<Record<number, DayState>>(() =>
    Object.fromEntries(DAYS.map((day) => [day.value, defaultDayState()])),
  )
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState('')

  function updateDay(dayValue: number, patch: Partial<DayState>) {
    setDays((prev) => ({ ...prev, [dayValue]: { ...prev[dayValue], ...patch } }))
  }

  async function handleSubmit(event: FormEvent) {
    event.preventDefault()
    setSubmitting(true)
    setError('')

    const schedule: ScheduleSlotInput[] = DAYS.filter((day) => days[day.value].enabled).map((day) => ({
      day_of_week: day.value,
      start_time: `${days[day.value].start}:00`,
      end_time: `${days[day.value].end}:00`,
    }))

    try {
      const input: EmployeeInput = {
        name: name.trim(),
        whatsapp_number: whatsappNumber.trim(),
        schedule,
      }
      await createEmployee(input, idToken)
      onCreated()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Error desconocido')
      setSubmitting(false)
    }
  }

  return (
    <form onSubmit={handleSubmit} className="flex flex-col gap-3">
      <div>
        <label className={labelClass}>Nombre</label>
        <input
          type="text"
          required
          autoFocus
          value={name}
          onChange={(event) => setName(event.target.value)}
          placeholder="ej. Ana García"
          className={inputClass}
        />
      </div>

      <div>
        <label className={labelClass}>Número de WhatsApp</label>
        <input
          type="text"
          required
          value={whatsappNumber}
          onChange={(event) => setWhatsappNumber(event.target.value)}
          placeholder="+34600000000"
          className={inputClass}
        />
      </div>

      <div>
        <label className={labelClass}>Horario semanal (opcional — sin horario no podrá recibir citas)</label>
        <div className="flex flex-col gap-2 rounded-md border border-neutral-800 bg-neutral-950 p-3">
          {DAYS.map((day) => {
            const dayState = days[day.value]
            return (
              <div key={day.value} className="flex items-center gap-2">
                <label className="flex w-24 shrink-0 items-center gap-2 text-sm text-neutral-300">
                  <input
                    type="checkbox"
                    checked={dayState.enabled}
                    onChange={(event) => updateDay(day.value, { enabled: event.target.checked })}
                    className="h-4 w-4 rounded border-neutral-700 bg-neutral-900"
                  />
                  {day.label}
                </label>
                <input
                  type="time"
                  disabled={!dayState.enabled}
                  value={dayState.start}
                  onChange={(event) => updateDay(day.value, { start: event.target.value })}
                  className={`${inputClass} disabled:opacity-40`}
                />
                <span className="text-neutral-600">–</span>
                <input
                  type="time"
                  disabled={!dayState.enabled}
                  value={dayState.end}
                  onChange={(event) => updateDay(day.value, { end: event.target.value })}
                  className={`${inputClass} disabled:opacity-40`}
                />
              </div>
            )
          })}
        </div>
      </div>

      {error && <p className="text-xs text-red-400">{error}</p>}

      <div className="mt-2 flex justify-end gap-2">
        <button
          type="button"
          onClick={onCancel}
          className="rounded-md border border-neutral-800 px-3 py-2 text-sm text-neutral-400 hover:bg-neutral-800"
        >
          Cancelar
        </button>
        <button
          type="submit"
          disabled={submitting}
          className="rounded-md bg-neutral-100 px-4 py-2 text-sm font-medium text-neutral-950 hover:bg-neutral-300 disabled:opacity-50"
        >
          {submitting ? 'Creando…' : 'Crear empleado'}
        </button>
      </div>
    </form>
  )
}
