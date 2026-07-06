import type { Product } from '../api/products'

function isLowStock(product: Product): boolean {
  return product.min_stock_threshold > 0 && product.quantity <= product.min_stock_threshold
}

export function ProductsTable({ products }: { products: Product[] }) {
  if (products.length === 0) {
    return (
      <div className="rounded-lg border border-neutral-800 bg-neutral-900 px-6 py-12 text-center">
        <p className="text-neutral-400">No hay productos activos para este negocio todavía.</p>
      </div>
    )
  }

  return (
    <div className="overflow-hidden rounded-lg border border-neutral-800">
      <table className="w-full text-left text-sm">
        <thead>
          <tr className="border-b border-neutral-800 bg-neutral-900 text-neutral-400">
            <th className="px-4 py-3 font-medium">Producto</th>
            <th className="px-4 py-3 font-medium">SKU</th>
            <th className="px-4 py-3 font-medium">Stock</th>
            <th className="px-4 py-3 font-medium">Mínimo</th>
            <th className="px-4 py-3 font-medium text-right">Precio</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-neutral-800">
          {products.map((product) => {
            const lowStock = isLowStock(product)
            return (
              <tr key={product.id} className="bg-neutral-950 hover:bg-neutral-900">
                <td className="px-4 py-3 text-neutral-100">{product.name}</td>
                <td className="px-4 py-3 text-neutral-500">{product.sku ?? '—'}</td>
                <td className="px-4 py-3">
                  <span className={lowStock ? 'font-medium text-amber-400' : 'text-neutral-200'}>
                    {product.quantity} {product.unit}
                  </span>
                  {lowStock && (
                    <span className="ml-2 rounded-full border border-amber-400/30 bg-amber-400/10 px-2 py-0.5 text-xs text-amber-400">
                      Stock bajo
                    </span>
                  )}
                </td>
                <td className="px-4 py-3 text-neutral-500">{product.min_stock_threshold}</td>
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