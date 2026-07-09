import type { Employee } from '../api/employees'
import type { EmployeeWeeklySchedule } from '../api/schedule'
import { Modal } from './Modal'

interface EmployeeDetailModalProps {
  employee: Employee
  schedule: EmployeeWeeklySchedule | undefined
  weekStart: string // YYYY-MM-DD, lunes de la semana mostrada
  onClose: () => void
}

const DAY_NAMES = ['Lunes', 'Martes', 'Miércoles', 'Jueves', 'Viernes', 'Sábado', 'Domingo']

function parseISODate(s: string): Date {
  const [y, m, d] = s.split('-').map(Number)
  return new Date(y, m - 1, d)
}

function addDays(d: Date, n: number): Date {
  const copy = new Date(d)
  copy.setDate(copy.getDate() + n)
  return copy
}

function formatISODate(d: Date): string {
  const y = d.getFullYear()
  const m = String(d.getMonth() + 1).padStart(2, '0')
  const day = String(d.getDate()).padStart(2, '0')
  return `${y}-${m}-${day}`
}

function formatShort(t: string): string {
  return t.slice(0, 5)
}

export function EmployeeDetailModal({ employee, schedule, weekStart, onClose }: EmployeeDetailModalProps) {
  const weekStartDate = parseISODate(weekStart)
  const weekDates = Array.from({ length: 7 }, (_, i) => addDays(weekStartDate, i))

  const blocksByDay = weekDates.map((dateObj, i) => {
    const dateIso = formatISODate(dateObj)
    return {
      label: `${DAY_NAMES[i]} ${dateObj.getDate()}`,
      blocks: (schedule?.schedule ?? []).filter((b) => b.date === dateIso),
    }
  })
  const totalWeeklyMinutes = (schedule?.schedule ?? []).reduce((sum, b) => {
    const [sh, sm] = b.start_time.split(':').map(Number)
    const [eh, em] = b.end_time.split(':').map(Number)
    return sum + (eh * 60 + em - (sh * 60 + sm))
  }, 0)

  return (
    <Modal title={employee.name} onClose={onClose}>
      <div className="flex flex-col gap-4">
        <div>
          <p className="text-xs text-neutral-500">WhatsApp</p>
          <p className="text-sm text-neutral-100">{employee.whatsapp_number}</p>
        </div>

        <div>
          <div className="mb-2 flex items-center justify-between">
            <p className="text-xs text-neutral-500">Horario de esta semana</p>
            <p className="text-xs text-neutral-500">
              {Math.round((totalWeeklyMinutes / 60) * 10) / 10}h esta semana
            </p>
          </div>
          <div className="flex flex-col gap-1 rounded-md border border-neutral-800 bg-neutral-950 p-2">
            {blocksByDay.map(({ label, blocks }) => (
              <div key={label} className="flex items-start justify-between gap-2 text-xs">
                <span className="w-24 shrink-0 text-neutral-400">{label}</span>
                {blocks.length === 0 ? (
                  <span className="text-neutral-700">Libre</span>
                ) : (
                  <span className="text-right text-neutral-200">
                    {blocks.map((b) => `${formatShort(b.start_time)}–${formatShort(b.end_time)}`).join(' · ')}
                  </span>
                )}
              </div>
            ))}
          </div>
        </div>

        <div className="flex justify-end">
          <button
            type="button"
            onClick={onClose}
            className="rounded-md border border-neutral-800 px-3 py-2 text-sm text-neutral-400 hover:bg-neutral-800"
          >
            Cerrar
          </button>
        </div>
      </div>
    </Modal>
  )
}
