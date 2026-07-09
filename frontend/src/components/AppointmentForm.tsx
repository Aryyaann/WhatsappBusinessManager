import { useEffect, useState, type FormEvent } from 'react'
import {
  createAppointment,
  fetchEmployees,
  fetchServices,
  type AppointmentInput,
  type Employee,
  type ServiceOption,
} from '../api/appointments'

interface AppointmentFormProps {
  idToken: string
  onCreated: () => void
  onCancel: () => void
}

const inputClass =
  'w-full rounded-md border border-neutral-800 bg-neutral-950 px-3 py-2 text-sm text-neutral-100 placeholder-neutral-600 outline-none focus:border-neutral-600'
const labelClass = 'mb-1 block text-xs font-medium text-neutral-500'

export function AppointmentForm({ idToken, onCreated, onCancel }: AppointmentFormProps) {
  const [employees, setEmployees] = useState<Employee[]>([])
  const [services, setServices] = useState<ServiceOption[]>([])
  const [loadingOptions, setLoadingOptions] = useState(true)
  const [optionsError, setOptionsError] = useState('')

  const [employeeId, setEmployeeId] = useState('')
  const [serviceId, setServiceId] = useState('')
  const [date, setDate] = useState('')
  const [time, setTime] = useState('')
  const [customerName, setCustomerName] = useState('')
  const [customerPhone, setCustomerPhone] = useState('')
  const [notes, setNotes] = useState('')
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState('')

  useEffect(() => {
    Promise.all([fetchEmployees(idToken), fetchServices(idToken)])
      .then(([employeesData, servicesData]) => {
        setEmployees(employeesData)
        setServices(servicesData)
        if (employeesData.length > 0) setEmployeeId(employeesData[0].id)
        if (servicesData.length > 0) setServiceId(servicesData[0].id)
        setLoadingOptions(false)
      })
      .catch((err: Error) => {
        setOptionsError(err.message)
        setLoadingOptions(false)
      })
  }, [idToken])

  async function handleSubmit(event: FormEvent) {
    event.preventDefault()
    setSubmitting(true)
    setError('')
    try {
      const input: AppointmentInput = {
        employee_id: employeeId,
        service_id: serviceId,
        // Hora "de pared" sin zona horaria — igual que construye el
        // sistema las citas creadas por WhatsApp, para que ambos canales
        // comparen huecos de forma consistente.
        start_at: `${date}T${time}:00`,
        customer_name: customerName.trim() || undefined,
        customer_phone: customerPhone.trim(),
        notes: notes.trim() || undefined,
      }
      await createAppointment(input, idToken)
      onCreated()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Error desconocido')
      setSubmitting(false)
    }
  }

  if (loadingOptions) {
    return <p className="text-sm text-neutral-500">Cargando empleados y servicios…</p>
  }

  if (optionsError) {
    return <p className="text-sm text-red-400">No se pudo cargar el formulario: {optionsError}</p>
  }

  if (employees.length === 0 || services.length === 0) {
    return (
      <p className="text-sm text-neutral-500">
        Hace falta al menos un empleado y un servicio activos antes de poder crear una cita.
      </p>
    )
  }

  return (
    <form onSubmit={handleSubmit} className="flex flex-col gap-3">
      <div>
        <label className={labelClass}>Empleado</label>
        <select value={employeeId} onChange={(event) => setEmployeeId(event.target.value)} className={inputClass}>
          {employees.map((employee) => (
            <option key={employee.id} value={employee.id}>
              {employee.name}
            </option>
          ))}
        </select>
      </div>

      <div>
        <label className={labelClass}>Servicio</label>
        <select value={serviceId} onChange={(event) => setServiceId(event.target.value)} className={inputClass}>
          {services.map((service) => (
            <option key={service.id} value={service.id}>
              {service.name} ({service.duration_minutes} min)
            </option>
          ))}
        </select>
      </div>

      <div className="grid grid-cols-2 gap-3">
        <div>
          <label className={labelClass}>Fecha</label>
          <input
            type="date"
            required
            value={date}
            onChange={(event) => setDate(event.target.value)}
            className={inputClass}
          />
        </div>
        <div>
          <label className={labelClass}>Hora</label>
          <input
            type="time"
            required
            value={time}
            onChange={(event) => setTime(event.target.value)}
            className={inputClass}
          />
        </div>
      </div>

      <div>
        <label className={labelClass}>Nombre del cliente (opcional)</label>
        <input
          type="text"
          value={customerName}
          onChange={(event) => setCustomerName(event.target.value)}
          placeholder="ej. Marcos García"
          className={inputClass}
        />
      </div>

      <div>
        <label className={labelClass}>Teléfono del cliente</label>
        <input
          type="text"
          required
          value={customerPhone}
          onChange={(event) => setCustomerPhone(event.target.value)}
          placeholder="+34600000000"
          className={inputClass}
        />
      </div>

      <div>
        <label className={labelClass}>Notas (opcional)</label>
        <input
          type="text"
          value={notes}
          onChange={(event) => setNotes(event.target.value)}
          placeholder="ej. Primera visita"
          className={inputClass}
        />
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
          {submitting ? 'Creando…' : 'Crear cita'}
        </button>
      </div>
    </form>
  )
}
