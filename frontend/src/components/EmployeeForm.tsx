import { useState, type FormEvent } from 'react'
import { createEmployee, type EmployeeInput } from '../api/employees'

interface EmployeeFormProps {
  idToken: string
  onCreated: () => void
  onCancel: () => void
}

const inputClass =
  'w-full rounded-md border border-neutral-800 bg-neutral-950 px-3 py-2 text-sm text-neutral-100 placeholder-neutral-600 outline-none focus:border-neutral-600'
const labelClass = 'mb-1 block text-xs font-medium text-neutral-500'

export function EmployeeForm({ idToken, onCreated, onCancel }: EmployeeFormProps) {
  const [name, setName] = useState('')
  const [whatsappNumber, setWhatsappNumber] = useState('')
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState('')

  async function handleSubmit(event: FormEvent) {
    event.preventDefault()
    setSubmitting(true)
    setError('')
    try {
      const input: EmployeeInput = { name: name.trim(), whatsapp_number: whatsappNumber.trim() }
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

      <p className="text-xs text-neutral-600">
        El horario se planifica después, semana a semana, desde el Gantt de abajo.
      </p>

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
