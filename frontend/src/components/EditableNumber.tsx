import { useState } from 'react'

interface EditableNumberProps {
  value: number
  suffix?: string
  onSave: (newValue: number) => Promise<void>
}

export function EditableNumber({ value, suffix, onSave }: EditableNumberProps) {
  const [editing, setEditing] = useState(false)
  const [draft, setDraft] = useState(String(value))
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState('')

  if (!editing) {
    return (
      <button
        type="button"
        onClick={() => {
          setDraft(String(value))
          setEditing(true)
          setError('')
        }}
        className="rounded px-1 py-0.5 text-left hover:bg-neutral-800"
        title="Clic para editar"
      >
        {value}
        {suffix ? ` ${suffix}` : ''}
      </button>
    )
  }

  const handleSave = async () => {
    const parsed = Number(draft)
    if (Number.isNaN(parsed) || parsed < 0) {
      setError('Número inválido')
      return
    }
    setSaving(true)
    setError('')
    try {
      await onSave(parsed)
      setEditing(false)
    } catch (err) {
      setError((err as Error).message)
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="flex items-center gap-1">
      <input
        type="number"
        value={draft}
        onChange={(event) => setDraft(event.target.value)}
        onKeyDown={(event) => {
          if (event.key === 'Enter') handleSave()
          if (event.key === 'Escape') setEditing(false)
        }}
        autoFocus
        disabled={saving}
        className="w-20 rounded border border-neutral-700 bg-neutral-900 px-1.5 py-0.5 text-sm text-neutral-100 outline-none focus:border-neutral-500"
      />
      <button
        type="button"
        onClick={handleSave}
        disabled={saving}
        className="rounded bg-neutral-700 px-1.5 py-0.5 text-xs text-neutral-100 hover:bg-neutral-600 disabled:opacity-50"
      >
        {saving ? '…' : 'OK'}
      </button>
      <button
        type="button"
        onClick={() => setEditing(false)}
        disabled={saving}
        className="rounded px-1.5 py-0.5 text-xs text-neutral-500 hover:text-neutral-300"
      >
        Cancelar
      </button>
      {error && <span className="text-xs text-red-400">{error}</span>}
    </div>
  )
}