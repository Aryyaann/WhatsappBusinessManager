import { useEffect, useMemo, useState } from 'react'
import { adjustStock, fetchProducts, updateThreshold, type Product } from './api/products'
import { ProductsTable } from './components/ProductsTable'

const STORAGE_KEY = 'wbm.businessId'

function App() {
  const [businessId, setBusinessId] = useState(() => localStorage.getItem(STORAGE_KEY) ?? '')
  const [products, setProducts] = useState<Product[]>([])
  const [status, setStatus] = useState<'idle' | 'loading' | 'error' | 'ready'>('idle')
  const [errorMessage, setErrorMessage] = useState('')
  const [searchTerm, setSearchTerm] = useState('')
  const [showLowStockOnly, setShowLowStockOnly] = useState(false)

  function loadProducts(id: string) {
    setStatus('loading')
    setErrorMessage('')
    fetchProducts(id)
      .then((data) => {
        setProducts(data)
        setStatus('ready')
      })
      .catch((error: Error) => {
        setErrorMessage(error.message)
        setStatus('error')
      })
  }

  useEffect(() => {
    if (!businessId) {
      setStatus('idle')
      return
    }
    localStorage.setItem(STORAGE_KEY, businessId)
    loadProducts(businessId)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [businessId])

  const filteredProducts = useMemo(() => {
    return products.filter((product) => {
      const matchesSearch = product.name.toLowerCase().includes(searchTerm.toLowerCase())
      const matchesLowStock =
        !showLowStockOnly ||
        (product.min_stock_threshold > 0 && product.quantity <= product.min_stock_threshold)
      return matchesSearch && matchesLowStock
    })
  }, [products, searchTerm, showLowStockOnly])

  async function handleAdjustStock(productId: string, quantity: number) {
    await adjustStock(businessId, productId, quantity)
    loadProducts(businessId)
  }

  async function handleUpdateThreshold(productId: string, threshold: number) {
    await updateThreshold(businessId, productId, threshold)
    loadProducts(businessId)
  }

  return (
    <div className="min-h-screen bg-neutral-950 px-6 py-10 text-neutral-100">
      <div className="mx-auto max-w-4xl">
        <header className="mb-8">
          <h1 className="text-xl font-semibold tracking-tight">Inventario</h1>
          <p className="mt-1 text-sm text-neutral-500">
            Panel de administración — WhatsApp Business Manager
          </p>
        </header>

        <div className="mb-6">
          <label htmlFor="business-id" className="mb-1 block text-xs font-medium text-neutral-500">
            ID de negocio (temporal — todavía no hay login)
          </label>
          <input
            id="business-id"
            type="text"
            value={businessId}
            onChange={(event) => setBusinessId(event.target.value.trim())}
            placeholder="ej. d62a4701-f49a-4f90-8503-9d59346f91e5"
            className="w-full max-w-md rounded-md border border-neutral-800 bg-neutral-900 px-3 py-2 text-sm text-neutral-100 placeholder-neutral-600 outline-none focus:border-neutral-600"
          />
        </div>

        {status === 'idle' && (
          <p className="text-sm text-neutral-500">Introduce un ID de negocio para ver su inventario.</p>
        )}
        {status === 'loading' && products.length === 0 && (
          <p className="text-sm text-neutral-500">Cargando productos…</p>
        )}
        {status === 'error' && (
          <p className="text-sm text-red-400">No se pudo cargar el inventario: {errorMessage}</p>
        )}

        {products.length > 0 && status !== 'error' && (
          <>
            <div className="mb-4 flex flex-wrap items-center gap-3">
              <input
                type="text"
                value={searchTerm}
                onChange={(event) => setSearchTerm(event.target.value)}
                placeholder="Buscar producto…"
                className="w-full max-w-xs rounded-md border border-neutral-800 bg-neutral-900 px-3 py-1.5 text-sm text-neutral-100 placeholder-neutral-600 outline-none focus:border-neutral-600"
              />
              <label className="flex items-center gap-2 text-sm text-neutral-400">
                <input
                  type="checkbox"
                  checked={showLowStockOnly}
                  onChange={(event) => setShowLowStockOnly(event.target.checked)}
                  className="h-4 w-4 rounded border-neutral-700 bg-neutral-900"
                />
                Solo stock bajo
              </label>
              <span className="text-xs text-neutral-600">
                {filteredProducts.length} de {products.length} productos
              </span>
            </div>

            <ProductsTable
              products={filteredProducts}
              onAdjustStock={handleAdjustStock}
              onUpdateThreshold={handleUpdateThreshold}
            />
          </>
        )}
        {status === 'ready' && products.length === 0 && (
          <p className="text-sm text-neutral-500">Este negocio no tiene productos activos todavía.</p>
        )}
      </div>
    </div>
  )
}

export default App