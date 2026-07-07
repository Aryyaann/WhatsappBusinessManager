import { useEffect, useMemo, useState } from 'react'
import { useAuth } from 'react-oidc-context'
import { adjustStock, fetchProducts, updateThreshold, type Product } from './api/products'
import {
  fetchAppointments,
  updateAppointmentStatus,
  type Appointment,
  type AppointmentStatus,
} from './api/appointments'
import { fetchCurrentUser, type CurrentUser } from './api/me'
import { ProductsTable } from './components/ProductsTable'
import { AppointmentsTable } from './components/AppointmentsTable'

const STORAGE_KEY = 'wbm.businessId'

type Tab = 'inventario' | 'citas'

function signOutRedirect() {
  const clientId = import.meta.env.VITE_COGNITO_CLIENT_ID
  const cognitoDomain = import.meta.env.VITE_COGNITO_DOMAIN
  const logoutUri = import.meta.env.VITE_COGNITO_REDIRECT_URI
  window.location.href = `${cognitoDomain}/logout?client_id=${clientId}&logout_uri=${encodeURIComponent(logoutUri)}`
}

function App() {
  const auth = useAuth()
  const idToken = auth.user?.id_token ?? ''

  const [businessId, setBusinessId] = useState(() => localStorage.getItem(STORAGE_KEY) ?? '')
  const [activeTab, setActiveTab] = useState<Tab>('inventario')

  // --- Usuario autenticado (confirma de punta a punta que el backend
  // reconoce el token de Cognito, no solo que el login "parece" ir bien) ---
  const [currentUser, setCurrentUser] = useState<CurrentUser | null>(null)
  const [meError, setMeError] = useState('')

  // --- Inventario ---
  const [products, setProducts] = useState<Product[]>([])
  const [productsStatus, setProductsStatus] = useState<'idle' | 'loading' | 'error' | 'ready'>('idle')
  const [productsError, setProductsError] = useState('')
  const [searchTerm, setSearchTerm] = useState('')
  const [showLowStockOnly, setShowLowStockOnly] = useState(false)

  // --- Citas ---
  const [appointments, setAppointments] = useState<Appointment[]>([])
  const [appointmentsStatus, setAppointmentsStatus] = useState<'idle' | 'loading' | 'error' | 'ready'>('idle')
  const [appointmentsError, setAppointmentsError] = useState('')
  const [statusFilter, setStatusFilter] = useState<AppointmentStatus | 'all'>('all')

  function loadProducts(id: string) {
    setProductsStatus('loading')
    setProductsError('')
    fetchProducts(id, idToken)
      .then((data) => {
        setProducts(data)
        setProductsStatus('ready')
      })
      .catch((error: Error) => {
        setProductsError(error.message)
        setProductsStatus('error')
      })
  }

  function loadAppointments(id: string) {
    setAppointmentsStatus('loading')
    setAppointmentsError('')
    fetchAppointments(id, idToken)
      .then((data) => {
        setAppointments(data)
        setAppointmentsStatus('ready')
      })
      .catch((error: Error) => {
        setAppointmentsError(error.message)
        setAppointmentsStatus('error')
      })
  }

  // Al autenticarse, confirmamos con el backend quién es el usuario real.
  useEffect(() => {
    if (!auth.isAuthenticated || !idToken) {
      setCurrentUser(null)
      return
    }
    setMeError('')
    fetchCurrentUser(idToken)
      .then(setCurrentUser)
      .catch((error: Error) => setMeError(error.message))
  }, [auth.isAuthenticated, idToken])

  useEffect(() => {
    if (!businessId || !idToken) {
      setProductsStatus('idle')
      setAppointmentsStatus('idle')
      return
    }
    localStorage.setItem(STORAGE_KEY, businessId)
    loadProducts(businessId)
    loadAppointments(businessId)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [businessId, idToken])

  const filteredProducts = useMemo(() => {
    return products.filter((product) => {
      const matchesSearch = product.name.toLowerCase().includes(searchTerm.toLowerCase())
      const matchesLowStock =
        !showLowStockOnly ||
        (product.min_stock_threshold > 0 && product.quantity <= product.min_stock_threshold)
      return matchesSearch && matchesLowStock
    })
  }, [products, searchTerm, showLowStockOnly])

  const filteredAppointments = useMemo(() => {
    if (statusFilter === 'all') return appointments
    return appointments.filter((appointment) => appointment.status === statusFilter)
  }, [appointments, statusFilter])

  async function handleAdjustStock(productId: string, quantity: number) {
    await adjustStock(businessId, productId, quantity, idToken)
    loadProducts(businessId)
  }

  async function handleUpdateThreshold(productId: string, threshold: number) {
    await updateThreshold(businessId, productId, threshold, idToken)
    loadProducts(businessId)
  }

  async function handleUpdateAppointmentStatus(appointmentId: string, status: AppointmentStatus) {
    await updateAppointmentStatus(businessId, appointmentId, status, idToken)
    loadAppointments(businessId)
  }

  // --- Pantallas de estado de autenticación ---

  if (auth.isLoading) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-neutral-950 text-neutral-400">
        Cargando…
      </div>
    )
  }

  if (auth.error) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-neutral-950 px-6 text-center text-red-400">
        Error de autenticación: {auth.error.message}
      </div>
    )
  }

  if (!auth.isAuthenticated) {
    return (
      <div className="flex min-h-screen flex-col items-center justify-center gap-4 bg-neutral-950 text-neutral-100">
        <h1 className="text-xl font-semibold">WhatsApp Business Manager</h1>
        <p className="text-sm text-neutral-500">Inicia sesión para acceder al panel de administración.</p>
        <button
          type="button"
          onClick={() => auth.signinRedirect()}
          className="rounded-md bg-neutral-100 px-4 py-2 text-sm font-medium text-neutral-950 hover:bg-neutral-300"
        >
          Iniciar sesión
        </button>
      </div>
    )
  }

  // --- Panel (usuario autenticado) ---

  return (
    <div className="min-h-screen bg-neutral-950 px-6 py-10 text-neutral-100">
      <div className="mx-auto max-w-4xl">
        <header className="mb-8 flex items-start justify-between">
          <div>
            <h1 className="text-xl font-semibold tracking-tight">
              {activeTab === 'inventario' ? 'Inventario' : 'Citas'}
            </h1>
            <p className="mt-1 text-sm text-neutral-500">
              Panel de administración — WhatsApp Business Manager
            </p>
            {currentUser && (
              <p className="mt-1 text-xs text-neutral-600">
                Sesión iniciada como <span className="text-neutral-400">{currentUser.name}</span> (
                {currentUser.role === 'owner' ? 'dueño' : 'empleado'})
              </p>
            )}
            {meError && (
              <div className="mt-2 rounded-md border border-amber-400/30 bg-amber-400/10 px-3 py-2 text-xs text-amber-300">
                <p>No se pudo verificar el usuario contra el backend: {meError}</p>
                {auth.user?.profile?.sub && (
                  <p className="mt-1">
                    Tu <code className="text-amber-200">sub</code> de Cognito es:{' '}
                    <code className="select-all text-amber-200">{auth.user.profile.sub}</code>
                    {' '}— pásaselo al script <code className="text-amber-200">link_cognito_user.py</code> para enlazar tu usuario.
                  </p>
                )}
              </div>
            )}
          </div>
          <button
            type="button"
            onClick={() => signOutRedirect()}
            className="rounded-md border border-neutral-800 px-3 py-1.5 text-xs text-neutral-400 hover:bg-neutral-900"
          >
            Cerrar sesión
          </button>
        </header>

        <div className="mb-6">
          <label htmlFor="business-id" className="mb-1 block text-xs font-medium text-neutral-500">
            ID de negocio (temporal — todavía no hay multi-tenancy automático)
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

        <div className="mb-6 flex gap-1 border-b border-neutral-800">
          <button
            type="button"
            onClick={() => setActiveTab('inventario')}
            className={`px-3 py-2 text-sm font-medium ${
              activeTab === 'inventario'
                ? 'border-b-2 border-neutral-100 text-neutral-100'
                : 'text-neutral-500 hover:text-neutral-300'
            }`}
          >
            Inventario
          </button>
          <button
            type="button"
            onClick={() => setActiveTab('citas')}
            className={`px-3 py-2 text-sm font-medium ${
              activeTab === 'citas'
                ? 'border-b-2 border-neutral-100 text-neutral-100'
                : 'text-neutral-500 hover:text-neutral-300'
            }`}
          >
            Citas
          </button>
        </div>

        {!businessId && (
          <p className="text-sm text-neutral-500">Introduce un ID de negocio para empezar.</p>
        )}

        {businessId && activeTab === 'inventario' && (
          <>
            {productsStatus === 'loading' && products.length === 0 && (
              <p className="text-sm text-neutral-500">Cargando productos…</p>
            )}
            {productsStatus === 'error' && (
              <p className="text-sm text-red-400">No se pudo cargar el inventario: {productsError}</p>
            )}
            {products.length > 0 && productsStatus !== 'error' && (
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
            {productsStatus === 'ready' && products.length === 0 && (
              <p className="text-sm text-neutral-500">Este negocio no tiene productos activos todavía.</p>
            )}
          </>
        )}

        {businessId && activeTab === 'citas' && (
          <>
            {appointmentsStatus === 'loading' && appointments.length === 0 && (
              <p className="text-sm text-neutral-500">Cargando citas…</p>
            )}
            {appointmentsStatus === 'error' && (
              <p className="text-sm text-red-400">No se pudieron cargar las citas: {appointmentsError}</p>
            )}
            {appointments.length > 0 && appointmentsStatus !== 'error' && (
              <>
                <div className="mb-4 flex flex-wrap items-center gap-3">
                  <select
                    value={statusFilter}
                    onChange={(event) => setStatusFilter(event.target.value as AppointmentStatus | 'all')}
                    className="rounded-md border border-neutral-800 bg-neutral-900 px-3 py-1.5 text-sm text-neutral-100 outline-none focus:border-neutral-600"
                  >
                    <option value="all">Todos los estados</option>
                    <option value="pending">Pendiente</option>
                    <option value="confirmed">Confirmada</option>
                    <option value="cancelled">Cancelada</option>
                    <option value="completed">Completada</option>
                    <option value="no_show">No presentado</option>
                  </select>
                  <span className="text-xs text-neutral-600">
                    {filteredAppointments.length} de {appointments.length} citas
                  </span>
                </div>

                <AppointmentsTable
                  appointments={filteredAppointments}
                  onUpdateStatus={handleUpdateAppointmentStatus}
                />
              </>
            )}
            {appointmentsStatus === 'ready' && appointments.length === 0 && (
              <p className="text-sm text-neutral-500">Este negocio no tiene citas todavía.</p>
            )}
          </>
        )}
      </div>
    </div>
  )
}

export default App