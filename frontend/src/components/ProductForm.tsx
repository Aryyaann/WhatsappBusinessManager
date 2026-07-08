import { useState, type FormEvent } from 'react'
import { UNIT_OPTIONS, type ProductInput, type Unit } from '../api/products'

const UNIT_LABELS: Record<Unit, string> = {
  unidad: 'Unidad',
  caja: 'Caja',
  kg: 'Kilogramo',
  litro: 'Litro',
  ml: 'Mililitro',
  gramo: 'Gramo',
}

interface ProductFormProps {
  onSubmit: (input: ProductInput) => Promise<void>
  onCancel: () => void
}

const inputClass =
  'w-full rounded-md border border-neutral-800 bg-neutral-950 px-3 py-2 text-sm text-neutral-100 placeholder-neutral-600 outline-none focus:border-neutral-600'
const labelClass = 'mb-1 block text-xs font-medium text-neutral-500'

export function ProductForm({ onSubmit, onCancel }: ProductFormProps) {
  const [name, setName] = useState('')
  const [sku, setSku] = useState('')
  const [category, setCategory] = useState('')
  const [unit, setUnit] = useState<Unit>('unidad')
  const [salePrice, setSalePrice] = useState('')
  const [minStockThreshold, setMinStockThreshold] = useState('0')
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState('')

  async function handleSubmit(event: FormEvent) {
    event.preventDefault()
    setSubmitting(true)
    setError('')
    try {
      await onSubmit({
        name: name.trim(),
        sku: sku.trim() || undefined,
        category: category.trim() || undefined,
        unit,
        sale_price: salePrice ? Number(salePrice) : undefined,
        min_stock_threshold: Number(minStockThreshold) || 0,
      })
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
          placeholder="ej. Tinte Rubio 100ml"
          className={inputClass}
        />
      </div>

      <div className="grid grid-cols-2 gap-3">
        <div>
          <label className={labelClass}>SKU (opcional)</label>
          <input
            type="text"
            value={sku}
            onChange={(event) => setSku(event.target.value)}
            placeholder="ej. TIN-RUB-100"
            className={inputClass}
          />
        </div>
        <div>
          <label className={labelClass}>Categoría (opcional)</label>
          <input
            type="text"
            value={category}
            onChange={(event) => setCategory(event.target.value)}
            placeholder="ej. Tintes"
            className={inputClass}
          />
        </div>
      </div>

      <div className="grid grid-cols-2 gap-3">
        <div>
          <label className={labelClass}>Unidad</label>
          <select value={unit} onChange={(event) => setUnit(event.target.value as Unit)} className={inputClass}>
            {UNIT_OPTIONS.map((option) => (
              <option key={option} value={option}>
                {UNIT_LABELS[option]}
              </option>
            ))}
          </select>
        </div>
        <div>
          <label className={labelClass}>Precio de venta (opcional)</label>
          <input
            type="number"
            min="0"
            step="0.01"
            value={salePrice}
            onChange={(event) => setSalePrice(event.target.value)}
            placeholder="0.00"
            className={inputClass}
          />
        </div>
      </div>

      <div>
        <label className={labelClass}>Umbral mínimo de stock</label>
        <input
          type="number"
          min="0"
          value={minStockThreshold}
          onChange={(event) => setMinStockThreshold(event.target.value)}
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
          {submitting ? 'Creando…' : 'Crear producto'}
        </button>
      </div>
    </form>
  )
}
