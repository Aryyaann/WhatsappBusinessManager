import { useEffect, useState } from 'react'
import { fetchProducts, type Product } from './api/products'
import { ProductsTable } from './components/ProductsTable'

const STORAGE_KEY = 'wbm.businessId'

function App() {
  const [businessId, setBusinessId] = useState(() => localStorage.getItem(STORAGE_KEY) ?? '')
  const [products, setProducts] = useState<Product[]>([])
  const [status, setStatus] = useState<'idle' | 'loading' | 'error' | 'ready'>('idle')
  const [errorMessage, setErrorMessage] = useState('')

  useEffect(() => {
    if (!businessId) {
      setStatus('idle')
      return
    }
    localStorage.setItem(STORAGE_KEY, businessId)
    setStatus('loading')
    setErrorMessage('')

    fetchProducts(businessId)
      .then((data) => {
        setProducts(data)
        setStatus('ready')
      })
      .catch((error: Error) => {
        setErrorMessage(error.message)
        setStatus('error')
      })
  }, [businessId])

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
        {status === 'loading' && <p className="text-sm text-neutral-500">Cargando productos…</p>}
        {status === 'error' && (
          <p className="text-sm text-red-400">No se pudo cargar el inventario: {errorMessage}</p>
        )}
        {status === 'ready' && <ProductsTable products={products} />}
      </div>
    </div>
  )
}

export default App