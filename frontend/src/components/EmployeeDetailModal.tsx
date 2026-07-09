import type { Employee } from '../api/employees'
import type { EmployeeWeeklySchedule } from '../api/schedule'
import { Modal } from './Modal'

interface EmployeeDetailModalProps {
  employee: Employee
  schedule: EmployeeWeeklySchedule | undefined
  onClose: () => void
}

const DAY_LABELS = ['Lunes', 'Martes', 'Miércoles', 'Jueves', 'Viernes', 'Sábado', 'Domingo']

function formatShort(t: string): string {
  return t.slice(0, 5)
}

export function EmployeeDetailModal({ employee, schedule, onClose }: EmployeeDetailModalProps) {
  const blocksByDay = DAY_LABELS.map((label, dayOfWeek) => ({
    label,
    blocks: (schedule?.schedule ?? []).filter((b) => b.day_of_week === dayOfWeek),
  }))
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
            <p className="text-xs text-neutral-500">Horario semanal</p>
            <p className="text-xs text-neutral-500">
              {Math.round((totalWeeklyMinutes / 60) * 10) / 10}h / semana
            </p>
          </div>
          <div className="flex flex-col gap-1 rounded-md border border-neutral-800 bg-neutral-950 p-2">
            {blocksByDay.map(({ label, blocks }) => (
              <div key={label} className="flex items-start justify-between gap-2 text-xs">
                <span className="w-20 shrink-0 text-neutral-400">{label}</span>
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
