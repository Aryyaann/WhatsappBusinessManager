import { useState } from 'react'
import type { Product } from '../api/products'
import { EditableNumber } from './EditableNumber'

type SortKey = 'name' | 'quantity' | 'sale_price'
type SortDir = 'asc' | 'desc'

function isLowStock(product: Product): boolean {
  return product.min_stock_threshold > 0 && product.quantity <= product.min_stock_threshold
}

function SortHeader({
  label,
  sortKey,
  activeKey,
  activeDir,
  onSort,
  align = 'left',
}: {
  label: string
  sortKey: SortKey
  activeKey: SortKey
  activeDir: SortDir
  onSort: (key: SortKey) => void
  align?: 'left' | 'right'
}) {
  const isActive = sortKey === activeKey
  return (
    <th className={`px-4 py-3 font-medium ${align === 'right' ? 'text-right' : 'text-left'}`}>
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

interface ProductsTableProps {
  products: Product[]
  onAdjustStock: (productId: string, quantity: number) => Promise<void>
  onUpdateThreshold: (productId: string, threshold: number) => Promise<void>
}

export function ProductsTable({ products, onAdjustStock, onUpdateThreshold }: ProductsTableProps) {
  const [sortKey, setSortKey] = useState<SortKey>('name')
  const [sortDir, setSortDir] = useState<SortDir>('asc')

  if (products.length === 0) {
    return (
      <div className="rounded-lg border border-neutral-800 bg-neutral-900 px-6 py-12 text-center">
        <p className="text-neutral-400">No hay productos que coincidan.</p>
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

  const sorted = [...products].sort((a, b) => {
    let result = 0
    if (sortKey === 'name') result = a.name.localeCompare(b.name)
    if (sortKey === 'quantity') result = a.quantity - b.quantity
    if (sortKey === 'sale_price') result = (a.sale_price ?? 0) - (b.sale_price ?? 0)
    return sortDir === 'asc' ? result : -result
  })

  return (
    <div className="overflow-hidden rounded-lg border border-neutral-800">
      <table className="w-full text-left text-sm">
        <thead>
          <tr className="border-b border-neutral-800 bg-neutral-900 text-neutral-400">
            <SortHeader label="Producto" sortKey="name" activeKey={sortKey} activeDir={sortDir} onSort={handleSort} />
            <th className="px-4 py-3 font-medium">SKU</th>
            <SortHeader label="Stock" sortKey="quantity" activeKey={sortKey} activeDir={sortDir} onSort={handleSort} />
            <th className="px-4 py-3 font-medium">Mínimo</th>
            <SortHeader
              label="Precio"
              sortKey="sale_price"
              activeKey={sortKey}
              activeDir={sortDir}
              onSort={handleSort}
              align="right"
            />
          </tr>
        </thead>
        <tbody className="divide-y divide-neutral-800">
          {sorted.map((product) => {
            const lowStock = isLowStock(product)
            return (
              <tr key={product.id} className="bg-neutral-950 hover:bg-neutral-900">
                <td className="px-4 py-3 text-neutral-100">{product.name}</td>
                <td className="px-4 py-3 text-neutral-500">{product.sku ?? '—'}</td>
                <td className="px-4 py-3">
                  <div className="flex items-center gap-2">
                    <span className={lowStock ? 'text-amber-400' : 'text-neutral-200'}>
                      <EditableNumber
                        value={product.quantity}
                        suffix={product.unit}
                        onSave={(newValue) => onAdjustStock(product.id, newValue)}
                      />
                    </span>
                    {lowStock && (
                      <span className="rounded-full border border-amber-400/30 bg-amber-400/10 px-2 py-0.5 text-xs text-amber-400">
                        Stock bajo
                      </span>
                    )}
                  </div>
                </td>
                <td className="px-4 py-3 text-neutral-400">
                  <EditableNumber
                    value={product.min_stock_threshold}
                    onSave={(newValue) => onUpdateThreshold(product.id, newValue)}
                  />
                </td>
                <td className="px-4 py-3 text-right text-neutral-200">
                  {product.sale_price !== null ? `${product.sale_price.toFixed(2)} €` : '—'}
                </td>
              </tr>
            )
          })}
        </tbody>
      </table>
    </div>
  )
}