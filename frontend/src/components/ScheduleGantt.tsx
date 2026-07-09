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
  idToken: string
}

const DAY_LABELS = ['Lunes', 'Martes', 'Miércoles', 'Jueves', 'Viernes', 'Sábado', 'Domingo']

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

export function ScheduleGantt({ data, idToken }: ScheduleGanttProps) {
  // Estado local: fuente de verdad de lo que se ve en pantalla. Se
  // actualiza al instante en cada interacción (optimista) y la llamada a
  // la API va detrás, sin bloquear ni recargar la vista. Si la API falla,
  // deshacemos el cambio local y avisamos.
  const [localData, setLocalData] = useState(data)
  const employeeIdsKey = data.map((e) => e.employee_id).sort().join(',')
  const prevKeyRef = useRef(employeeIdsKey)
  const pendingCancelledRef = useRef<Set<string>>(new Set())

  useEffect(() => {
    // Solo re-sincronizamos con el servidor cuando cambia el CONJUNTO de
    // empleados (uno nuevo creado en otra pestaña, por ejemplo) — nunca
    // por un cambio de horario, que ya gestionamos nosotros localmente.
    // Así evitamos pisar ediciones locales en curso con datos viejos.
    if (employeeIdsKey === prevKeyRef.current) return
    prevKeyRef.current = employeeIdsKey
    setLocalData((prev) => {
      const byId = new Map(prev.map((e) => [e.employee_id, e]))
      return data.map((fresh) => byId.get(fresh.employee_id) ?? fresh)
    })
  }, [employeeIdsKey, data])

  const [templateHours, setTemplateHours] = useState<Record<string, number>>({})
  const [hoursPopup, setHoursPopup] = useState<HoursPopupState | null>(null)
  const [hoursInput, setHoursInput] = useState(String(DEFAULT_HOURS))
  const [dragOverDay, setDragOverDay] = useState<number | null>(null)
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

  function handleCreate(employeeId: string, dayOfWeek: number, startMinutes: number, durationMinutes: number) {
    const tempId = makeTempId()
    const newBlock: ScheduleBlock = {
      id: tempId,
      day_of_week: dayOfWeek,
      start_time: minutesToTime(startMinutes),
      end_time: minutesToTime(startMinutes + durationMinutes),
    }
    // 1) UI al instante.
    updateEmployeeSchedule(employeeId, (blocks) => [...blocks, newBlock])

    // 2) Persistir en segundo plano, sin bloquear ni recargar nada.
    createScheduleBlock(employeeId, dayOfWeek, newBlock.start_time, newBlock.end_time, idToken)
      .then((created) => {
        if (pendingCancelledRef.current.has(tempId)) {
          // Se borró localmente antes de que el servidor respondiera —
          // borramos también en el servidor y no lo volvemos a mostrar.
          pendingCancelledRef.current.delete(tempId)
          deleteScheduleBlock(employeeId, created.id, idToken).catch(() => {})
          return
        }
        // Sustituimos el id temporal por el real, conservando la posición
        // actual (por si el usuario ya lo movió mientras se guardaba).
        updateEmployeeSchedule(employeeId, (blocks) =>
          blocks.map((b) => (b.id === tempId ? { ...b, id: created.id } : b)),
        )
      })
      .catch((err) => {
        setError(err instanceof Error ? err.message : 'Error al crear el turno')
        updateEmployeeSchedule(employeeId, (blocks) => blocks.filter((b) => b.id !== tempId))
      })
  }

  function handleMove(employeeId: string, block: ScheduleBlock, dayOfWeek: number, startMinutes: number) {
    const duration = timeToMinutes(block.end_time) - timeToMinutes(block.start_time)
    const previous = block
    const updated: ScheduleBlock = {
      ...block,
      day_of_week: dayOfWeek,
      start_time: minutesToTime(startMinutes),
      end_time: minutesToTime(startMinutes + duration),
    }

    updateEmployeeSchedule(employeeId, (blocks) => blocks.map((b) => (b.id === block.id ? updated : b)))

    if (block.id.startsWith(TEMP_PREFIX)) return // aún creándose; ya tiene la posición nueva, se persistirá sola

    updateScheduleBlock(employeeId, block.id, dayOfWeek, updated.start_time, updated.end_time, idToken).catch(
      (err) => {
        setError(err instanceof Error ? err.message : 'Error al mover el turno')
        updateEmployeeSchedule(employeeId, (blocks) => blocks.map((b) => (b.id === block.id ? previous : b)))
      },
    )
  }

  function handleDelete(employeeId: string, blockId: string) {
    const employee = localData.find((e) => e.employee_id === employeeId)
    const removed = employee?.schedule.find((b) => b.id === blockId)

    updateEmployeeSchedule(employeeId, (blocks) => blocks.filter((b) => b.id !== blockId))

    if (blockId.startsWith(TEMP_PREFIX)) {
      // Todavía no existe en el servidor — lo marcamos para borrarlo en
      // cuanto termine de crearse.
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

  function handleDrop(event: React.DragEvent<HTMLDivElement>, dayOfWeek: number) {
    event.preventDefault()
    setDragOverDay(null)
    const payload = dragPayloadRef.current
    dragPayloadRef.current = null
    if (!payload) return

    const rect = event.currentTarget.getBoundingClientRect()
    const ratio = Math.max(0, Math.min(1, (event.clientX - rect.left) / rect.width))
    // Ya no recortamos el inicio en función de la duración — un bloque
    // puede soltarse en cualquier punto de la ventana visible aunque su
    // final se salga de ella (se recorta solo visualmente al pintarlo).
    // Antes esto impedía soltar bloques largos pasadas ciertas horas.
    const startMinutes = snap(ratio * TOTAL_MINUTES) + START_HOUR * 60

    if (payload.kind === 'new') {
      handleCreate(payload.employeeId, dayOfWeek, startMinutes - START_HOUR * 60, payload.durationMinutes)
    } else {
      handleMove(payload.employeeId, payload.block, dayOfWeek, startMinutes - START_HOUR * 60)
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
  // Marcas cada 30 min para el eje: la hora en punto se ve más marcada
  // (número normal), la media hora más tenue (":30" pequeño).
  const halfHourMarks = Array.from({ length: (END_HOUR - START_HOUR) * 2 + 1 }, (_, i) => {
    const totalHalfHours = i
    const hour = START_HOUR + Math.floor(totalHalfHours / 2)
    const isHalf = totalHalfHours % 2 === 1
    return { hour, isHalf, leftPct: totalHalfHours * halfStepPct }
  })
  const gridlineBackground = {
    backgroundImage: [
      `repeating-linear-gradient(to right, transparent, transparent calc(${halfStepPct}% - 1px), rgba(255,255,255,0.04) calc(${halfStepPct}% - 1px), rgba(255,255,255,0.04) ${halfStepPct}%)`,
      `repeating-linear-gradient(to right, transparent, transparent calc(${hourStepPct}% - 1px), rgba(255,255,255,0.10) calc(${hourStepPct}% - 1px), rgba(255,255,255,0.10) ${hourStepPct}%)`,
    ].join(', '),
  }

  return (
    <div>
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
          {DAY_LABELS.map((dayLabel, dayOfWeek) => {
            const employeesThisDay = localData.filter((e) => e.schedule.some((b) => b.day_of_week === dayOfWeek))
            const laneHeight = 20
            const rowHeight = Math.max(34, employeesThisDay.length * laneHeight + 4)

            return (
              <div key={dayLabel} className="flex items-center">
                <div className="shrink-0 pr-2 text-xs text-neutral-400" style={{ width: 88 }}>
                  {dayLabel}
                </div>
                <div
                  onDragOver={(event) => {
                    event.preventDefault()
                    setDragOverDay(dayOfWeek)
                  }}
                  onDragLeave={() => setDragOverDay((prev) => (prev === dayOfWeek ? null : prev))}
                  onDrop={(event) => handleDrop(event, dayOfWeek)}
                  className={`relative flex-1 overflow-hidden rounded border transition-colors ${
                    dragOverDay === dayOfWeek ? 'border-neutral-500 bg-neutral-900' : 'border-neutral-800'
                  }`}
                  style={{ height: rowHeight, ...gridlineBackground }}
                >
                  {localData.map((employee, employeeIndex) => {
                    const laneIndex = employeesThisDay.findIndex((e) => e.employee_id === employee.employee_id)
                    if (laneIndex === -1) return null
                    return employee.schedule
                      .filter((block) => block.day_of_week === dayOfWeek)
                      .map((block) => {
                        const startMinutes = timeToMinutes(block.start_time) - START_HOUR * 60
                        const endMinutes = timeToMinutes(block.end_time) - START_HOUR * 60
                        // Recortamos a la ventana visible (6:00-23:00): un
                        // horario que empiece o acabe fuera de esa franja
                        // se ve cortado en el borde en vez de escaparse
                        // del todo con un porcentaje negativo o gigante.
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
        Arrastra el bloque de un empleado hacia el día y hora donde quieres que trabaje. Si necesita turno partido,
        arrástralo otra vez a otro hueco. La ✕ quita un turno ya colocado.
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
