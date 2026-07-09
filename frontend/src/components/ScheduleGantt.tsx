import { useEffect, useRef, useState } from 'react'
import {
  createScheduleBlock,
  deleteScheduleBlock,
  updateScheduleBlock,
  type EmployeeWeeklySchedule,
  type ScheduleBlock,
} from '../api/schedule'
import { Modal } from './Modal'

interface ScheduleGanttProps {
  data: EmployeeWeeklySchedule[]
  weekStart: string // YYYY-MM-DD, lunes de la semana mostrada
  idToken: string
  onPrevWeek: () => void
  onNextWeek: () => void
  onThisWeek: () => void
}

const DAY_NAMES = ['Lunes', 'Martes', 'Miércoles', 'Jueves', 'Viernes', 'Sábado', 'Domingo']
const MONTH_NAMES = [
  'enero', 'febrero', 'marzo', 'abril', 'mayo', 'junio',
  'julio', 'agosto', 'septiembre', 'octubre', 'noviembre', 'diciembre',
]

const START_HOUR = 6
const END_HOUR = 23
const TOTAL_MINUTES = (END_HOUR - START_HOUR) * 60
const SNAP_MINUTES = 15
const DEFAULT_HOURS = 8
const TEMP_PREFIX = 'temp-'

const EMPLOYEE_COLORS = [
  'bg-sky-500 border-sky-300',
  'bg-emerald-500 border-emerald-300',
  'bg-amber-500 border-amber-300',
  'bg-fuchsia-500 border-fuchsia-300',
  'bg-orange-500 border-orange-300',
  'bg-teal-500 border-teal-300',
  'bg-rose-500 border-rose-300',
  'bg-indigo-500 border-indigo-300',
]

function colorFor(employeeIndex: number): string {
  return EMPLOYEE_COLORS[employeeIndex % EMPLOYEE_COLORS.length]
}

// --- Utilidades de fecha (en local, sin líos de timezone con Date/UTC) ---

function parseISODate(s: string): Date {
  const [y, m, d] = s.split('-').map(Number)
  return new Date(y, m - 1, d)
}

function formatISODate(d: Date): string {
  const y = d.getFullYear()
  const m = String(d.getMonth() + 1).padStart(2, '0')
  const day = String(d.getDate()).padStart(2, '0')
  return `${y}-${m}-${day}`
}

function addDays(d: Date, n: number): Date {
  const copy = new Date(d)
  copy.setDate(copy.getDate() + n)
  return copy
}

function isSameDate(a: Date, b: Date): boolean {
  return formatISODate(a) === formatISODate(b)
}

function timeToMinutes(t: string): number {
  const [h, m] = t.split(':').map(Number)
  return h * 60 + m
}

function minutesToTime(totalMinutes: number): string {
  const clamped = Math.max(0, Math.min(24 * 60 - 1, Math.round(totalMinutes)))
  const h = Math.floor(clamped / 60)
  const m = clamped % 60
  return `${String(h).padStart(2, '0')}:${String(m).padStart(2, '0')}:00`
}

function formatShort(t: string): string {
  return t.slice(0, 5)
}

function snap(minutes: number): number {
  return Math.round(minutes / SNAP_MINUTES) * SNAP_MINUTES
}

function makeTempId(): string {
  return `${TEMP_PREFIX}${Date.now()}-${Math.random().toString(36).slice(2, 8)}`
}

type DragPayload =
  | { kind: 'new'; employeeId: string; employeeIndex: number; durationMinutes: number }
  | { kind: 'move'; employeeId: string; employeeIndex: number; block: ScheduleBlock }

interface HoursPopupState {
  employeeId: string
  employeeName: string
}

export function ScheduleGantt({ data, weekStart, idToken, onPrevWeek, onNextWeek, onThisWeek }: ScheduleGanttProps) {
  const weekStartDate = parseISODate(weekStart)
  const weekDates = Array.from({ length: 7 }, (_, i) => addDays(weekStartDate, i))
  const today = new Date()

  const [localData, setLocalData] = useState(data)
  const employeeIdsKey = data.map((e) => e.employee_id).sort().join(',')
  const prevWeekRef = useRef(weekStart)
  const prevEmployeeIdsKeyRef = useRef(employeeIdsKey)
  const pendingCancelledRef = useRef<Set<string>>(new Set())

  useEffect(() => {
    if (weekStart !== prevWeekRef.current) {
      // Semana distinta: los datos son de otro periodo por completo.
      prevWeekRef.current = weekStart
      prevEmployeeIdsKeyRef.current = employeeIdsKey
      setLocalData(data)
      return
    }
    if (employeeIdsKey === prevEmployeeIdsKeyRef.current) return
    // Misma semana, pero cambió el conjunto de empleados (uno nuevo creado
    // en otra pestaña) — fundimos sin pisar ediciones locales en curso.
    prevEmployeeIdsKeyRef.current = employeeIdsKey
    setLocalData((prev) => {
      const byId = new Map(prev.map((e) => [e.employee_id, e]))
      return data.map((fresh) => byId.get(fresh.employee_id) ?? fresh)
    })
  }, [weekStart, employeeIdsKey, data])

  const [templateHours, setTemplateHours] = useState<Record<string, number>>({})
  const [hoursPopup, setHoursPopup] = useState<HoursPopupState | null>(null)
  const [hoursInput, setHoursInput] = useState(String(DEFAULT_HOURS))
  const [dragOverDate, setDragOverDate] = useState<string | null>(null)
  const [error, setError] = useState('')
  const dragPayloadRef = useRef<DragPayload | null>(null)

  function getTemplateHours(employeeId: string): number {
    return templateHours[employeeId] ?? DEFAULT_HOURS
  }

  function updateEmployeeSchedule(employeeId: string, updater: (blocks: ScheduleBlock[]) => ScheduleBlock[]) {
    setLocalData((prev) =>
      prev.map((e) => (e.employee_id === employeeId ? { ...e, schedule: updater(e.schedule) } : e)),
    )
  }

  function handleCreate(employeeId: string, dateIso: string, startMinutes: number, durationMinutes: number) {
    const tempId = makeTempId()
    const newBlock: ScheduleBlock = {
      id: tempId,
      date: dateIso,
      start_time: minutesToTime(startMinutes),
      end_time: minutesToTime(startMinutes + durationMinutes),
    }
    updateEmployeeSchedule(employeeId, (blocks) => [...blocks, newBlock])

    createScheduleBlock(employeeId, dateIso, newBlock.start_time, newBlock.end_time, idToken)
      .then((created) => {
        if (pendingCancelledRef.current.has(tempId)) {
          pendingCancelledRef.current.delete(tempId)
          deleteScheduleBlock(employeeId, created.id, idToken).catch(() => {})
          return
        }
        updateEmployeeSchedule(employeeId, (blocks) =>
          blocks.map((b) => (b.id === tempId ? { ...b, id: created.id } : b)),
        )
      })
      .catch((err) => {
        setError(err instanceof Error ? err.message : 'Error al crear el turno')
        updateEmployeeSchedule(employeeId, (blocks) => blocks.filter((b) => b.id !== tempId))
      })
  }

  function handleMove(employeeId: string, block: ScheduleBlock, dateIso: string, startMinutes: number) {
    const duration = timeToMinutes(block.end_time) - timeToMinutes(block.start_time)
    const previous = block
    const updated: ScheduleBlock = {
      ...block,
      date: dateIso,
      start_time: minutesToTime(startMinutes),
      end_time: minutesToTime(startMinutes + duration),
    }

    updateEmployeeSchedule(employeeId, (blocks) => blocks.map((b) => (b.id === block.id ? updated : b)))

    if (block.id.startsWith(TEMP_PREFIX)) return

    updateScheduleBlock(employeeId, block.id, dateIso, updated.start_time, updated.end_time, idToken).catch((err) => {
      setError(err instanceof Error ? err.message : 'Error al mover el turno')
      updateEmployeeSchedule(employeeId, (blocks) => blocks.map((b) => (b.id === block.id ? previous : b)))
    })
  }

  function handleDelete(employeeId: string, blockId: string) {
    const employee = localData.find((e) => e.employee_id === employeeId)
    const removed = employee?.schedule.find((b) => b.id === blockId)

    updateEmployeeSchedule(employeeId, (blocks) => blocks.filter((b) => b.id !== blockId))

    if (blockId.startsWith(TEMP_PREFIX)) {
      pendingCancelledRef.current.add(blockId)
      return
    }

    deleteScheduleBlock(employeeId, blockId, idToken).catch((err) => {
      setError(err instanceof Error ? err.message : 'Error al borrar el turno')
      if (removed) {
        updateEmployeeSchedule(employeeId, (blocks) => [...blocks, removed])
      }
    })
  }

  function handleDrop(event: React.DragEvent<HTMLDivElement>, dateIso: string) {
    event.preventDefault()
    setDragOverDate(null)
    const payload = dragPayloadRef.current
    dragPayloadRef.current = null
    if (!payload) return

    const rect = event.currentTarget.getBoundingClientRect()
    const ratio = Math.max(0, Math.min(1, (event.clientX - rect.left) / rect.width))
    const startMinutes = snap(ratio * TOTAL_MINUTES) + START_HOUR * 60

    if (payload.kind === 'new') {
      handleCreate(payload.employeeId, dateIso, startMinutes - START_HOUR * 60, payload.durationMinutes)
    } else {
      handleMove(payload.employeeId, payload.block, dateIso, startMinutes - START_HOUR * 60)
    }
  }

  function openHoursPopup(employeeId: string, employeeName: string) {
    setHoursInput(String(getTemplateHours(employeeId)))
    setHoursPopup({ employeeId, employeeName })
  }

  function confirmHours() {
    if (!hoursPopup) return
    const hours = Math.min(16, Math.max(1, Number(hoursInput) || DEFAULT_HOURS))
    setTemplateHours((prev) => ({ ...prev, [hoursPopup.employeeId]: hours }))
    setHoursPopup(null)
  }

  const hourStepPct = 100 / (END_HOUR - START_HOUR)
  const halfStepPct = hourStepPct / 2
  const halfHourMarks = Array.from({ length: (END_HOUR - START_HOUR) * 2 + 1 }, (_, i) => {
    const hour = START_HOUR + Math.floor(i / 2)
    const isHalf = i % 2 === 1
    return { hour, isHalf, leftPct: i * halfStepPct }
  })
  const gridlineBackground = {
    backgroundImage: [
      `repeating-linear-gradient(to right, transparent, transparent calc(${halfStepPct}% - 1px), rgba(255,255,255,0.04) calc(${halfStepPct}% - 1px), rgba(255,255,255,0.04) ${halfStepPct}%)`,
      `repeating-linear-gradient(to right, transparent, transparent calc(${hourStepPct}% - 1px), rgba(255,255,255,0.10) calc(${hourStepPct}% - 1px), rgba(255,255,255,0.10) ${hourStepPct}%)`,
    ].join(', '),
  }

  const weekEndDate = weekDates[6]
  const rangeLabel =
    weekStartDate.getMonth() === weekEndDate.getMonth()
      ? `${weekStartDate.getDate()} – ${weekEndDate.getDate()} de ${MONTH_NAMES[weekStartDate.getMonth()]} de ${weekStartDate.getFullYear()}`
      : `${weekStartDate.getDate()} de ${MONTH_NAMES[weekStartDate.getMonth()]} – ${weekEndDate.getDate()} de ${MONTH_NAMES[weekEndDate.getMonth()]} de ${weekEndDate.getFullYear()}`

  return (
    <div>
      <div className="mb-3 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <button
            type="button"
            onClick={onPrevWeek}
            aria-label="Semana anterior"
            className="rounded-md border border-neutral-800 px-2 py-1 text-sm text-neutral-400 hover:bg-neutral-800"
          >
            ←
          </button>
          <button
            type="button"
            onClick={onNextWeek}
            aria-label="Semana siguiente"
            className="rounded-md border border-neutral-800 px-2 py-1 text-sm text-neutral-400 hover:bg-neutral-800"
          >
            →
          </button>
          <button
            type="button"
            onClick={onThisWeek}
            className="rounded-md border border-neutral-800 px-2 py-1 text-xs text-neutral-400 hover:bg-neutral-800"
          >
            Hoy
          </button>
        </div>
        <p className="text-sm font-medium text-neutral-300">{rangeLabel}</p>
      </div>

      {error && (
        <p className="mb-2 text-xs text-red-400">
          {error}{' '}
          <button type="button" onClick={() => setError('')} className="underline">
            cerrar
          </button>
        </p>
      )}

      <div className="rounded-lg border border-neutral-800 bg-neutral-950 p-3">
        <div className="mb-1 flex text-[10px] text-neutral-600">
          <div style={{ width: 88 }} />
          <div className="relative flex-1" style={{ height: 14 }}>
            {halfHourMarks.map(({ hour, isHalf, leftPct }) => (
              <span
                key={`${hour}-${isHalf}`}
                className={`absolute -translate-x-1/2 ${isHalf ? 'text-neutral-700' : ''}`}
                style={{ left: `${leftPct}%` }}
              >
                {isHalf ? ':30' : hour}
              </span>
            ))}
          </div>
        </div>

        <div className="flex flex-col gap-1.5">
          {weekDates.map((dateObj, dayIndex) => {
            const dateIso = formatISODate(dateObj)
            const employeesThisDay = localData.filter((e) => e.schedule.some((b) => b.date === dateIso))
            const laneHeight = 20
            const rowHeight = Math.max(34, employeesThisDay.length * laneHeight + 4)
            const isToday = isSameDate(dateObj, today)

            return (
              <div key={dateIso} className="flex items-center">
                <div
                  className={`shrink-0 pr-2 text-xs ${isToday ? 'text-neutral-100' : 'text-neutral-400'}`}
                  style={{ width: 88 }}
                >
                  {DAY_NAMES[dayIndex]} <span className="text-neutral-600">{dateObj.getDate()}</span>
                  {isToday && <span className="ml-1 inline-block h-1.5 w-1.5 rounded-full bg-sky-400" />}
                </div>
                <div
                  onDragOver={(event) => {
                    event.preventDefault()
                    setDragOverDate(dateIso)
                  }}
                  onDragLeave={() => setDragOverDate((prev) => (prev === dateIso ? null : prev))}
                  onDrop={(event) => handleDrop(event, dateIso)}
                  className={`relative flex-1 overflow-hidden rounded border transition-colors ${
                    dragOverDate === dateIso ? 'border-neutral-500 bg-neutral-900' : 'border-neutral-800'
                  } ${isToday ? 'ring-1 ring-sky-500/30' : ''}`}
                  style={{ height: rowHeight, ...gridlineBackground }}
                >
                  {localData.map((employee, employeeIndex) => {
                    const laneIndex = employeesThisDay.findIndex((e) => e.employee_id === employee.employee_id)
                    if (laneIndex === -1) return null
                    return employee.schedule
                      .filter((block) => block.date === dateIso)
                      .map((block) => {
                        const startMinutes = timeToMinutes(block.start_time) - START_HOUR * 60
                        const endMinutes = timeToMinutes(block.end_time) - START_HOUR * 60
                        const leftPct = Math.max(0, Math.min(100, (startMinutes / TOTAL_MINUTES) * 100))
                        const rightPct = Math.max(0, Math.min(100, (endMinutes / TOTAL_MINUTES) * 100))
                        const widthPct = Math.max(2, rightPct - leftPct)
                        const pending = block.id.startsWith(TEMP_PREFIX)
                        return (
                          <div
                            key={block.id}
                            draggable
                            onDragStart={(event) => {
                              event.dataTransfer.effectAllowed = 'move'
                              event.dataTransfer.setData('text/plain', block.id)
                              dragPayloadRef.current = {
                                kind: 'move',
                                employeeId: employee.employee_id,
                                employeeIndex,
                                block,
                              }
                            }}
                            title={`${employee.employee_name}: ${formatShort(block.start_time)}–${formatShort(block.end_time)}`}
                            className={`absolute flex cursor-grab items-center justify-between gap-1 overflow-hidden rounded border px-1.5 text-[10px] font-medium text-neutral-950 transition-[left,width] duration-100 active:cursor-grabbing ${colorFor(
                              employeeIndex,
                            )} ${pending ? 'opacity-70' : ''}`}
                            style={{
                              left: `${leftPct}%`,
                              width: `${widthPct}%`,
                              top: laneIndex * laneHeight + 2,
                              height: laneHeight - 4,
                            }}
                          >
                            <span className="truncate">
                              {employee.employee_name} {formatShort(block.start_time)}–{formatShort(block.end_time)}
                            </span>
                            <button
                              type="button"
                              onClick={() => handleDelete(employee.employee_id, block.id)}
                              className="shrink-0 leading-none text-neutral-950/70 hover:text-neutral-950"
                              aria-label={`Quitar este turno de ${employee.employee_name}`}
                            >
                              ✕
                            </button>
                          </div>
                        )
                      })
                  })}
                </div>
              </div>
            )
          })}
        </div>
      </div>

      <div className="mt-4">
        <p className="mb-2 text-xs font-medium text-neutral-500">
          Empleados — clic para fijar horas, arrastra para asignar turno
        </p>
        <div className="flex flex-wrap gap-2">
          {localData.map((employee, employeeIndex) => (
            <div
              key={employee.employee_id}
              draggable
              onDragStart={(event) => {
                event.dataTransfer.effectAllowed = 'copy'
                event.dataTransfer.setData('text/plain', employee.employee_id)
                dragPayloadRef.current = {
                  kind: 'new',
                  employeeId: employee.employee_id,
                  employeeIndex,
                  durationMinutes: getTemplateHours(employee.employee_id) * 60,
                }
              }}
              onClick={() => openHoursPopup(employee.employee_id, employee.employee_name)}
              className={`flex cursor-grab items-center gap-2 rounded-md border px-3 py-2 text-xs font-medium text-neutral-950 active:cursor-grabbing ${colorFor(
                employeeIndex,
              )}`}
            >
              <span>{employee.employee_name}</span>
              <span className="rounded bg-neutral-950/20 px-1.5 py-0.5 text-[10px]">
                {getTemplateHours(employee.employee_id)}h
              </span>
            </div>
          ))}
        </div>
      </div>

      <p className="mt-3 text-xs text-neutral-600">
        Arrastra el bloque de un empleado hacia el día y hora donde quieres que trabaje esta semana. Si necesita
        turno partido, arrástralo otra vez a otro hueco. La ✕ quita un turno ya colocado.
      </p>

      {hoursPopup && (
        <Modal title={`Horas de ${hoursPopup.employeeName}`} onClose={() => setHoursPopup(null)}>
          <div className="flex flex-col gap-3">
            <div>
              <label className="mb-1 block text-xs font-medium text-neutral-500">
                ¿Cuántas horas trabaja por turno?
              </label>
              <input
                type="number"
                min={1}
                max={16}
                autoFocus
                value={hoursInput}
                onChange={(event) => setHoursInput(event.target.value)}
                onKeyDown={(event) => {
                  if (event.key === 'Enter') confirmHours()
                }}
                className="w-full rounded-md border border-neutral-800 bg-neutral-950 px-3 py-2 text-sm text-neutral-100 outline-none focus:border-neutral-600"
              />
            </div>
            <p className="text-xs text-neutral-600">
              Esto define el tamaño del bloque que arrastres para {hoursPopup.employeeName} de aquí en adelante —
              no cambia los turnos que ya tiene colocados.
            </p>
            <div className="mt-1 flex justify-end gap-2">
              <button
                type="button"
                onClick={() => setHoursPopup(null)}
                className="rounded-md border border-neutral-800 px-3 py-2 text-sm text-neutral-400 hover:bg-neutral-800"
              >
                Cancelar
              </button>
              <button
                type="button"
                onClick={confirmHours}
                className="rounded-md bg-neutral-100 px-4 py-2 text-sm font-medium text-neutral-950 hover:bg-neutral-300"
              >
                Guardar
              </button>
            </div>
          </div>
        </Modal>
      )}
    </div>
  )
}
