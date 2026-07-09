import { useEffect, useMemo, useState, type FormEvent } from 'react'
import { useAuth } from 'react-oidc-context'
import { adjustStock, createProduct, fetchProducts, updateThreshold, type Product, type ProductInput } from './api/products'
import {
  fetchAppointments,
  updateAppointmentStatus,
  type Appointment,
  type AppointmentStatus,
} from './api/appointments'
import { fetchCurrentUser, ApiError, type CurrentUser } from './api/me'
import { createBusiness } from './api/onboarding'
import { ProductsTable } from './components/ProductsTable'
import { AppointmentsTable } from './components/AppointmentsTable'
import { Modal } from './components/Modal'
import { ProductForm } from './components/ProductForm'
import { AppointmentForm } from './components/AppointmentForm'

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

  const [activeTab, setActiveTab] = useState<Tab>('inventario')

  // --- Usuario autenticado. Ya no pedimos un business_id a mano: en
  // cuanto el backend confirma quién eres, ya sabe a qué negocio
  // perteneces (current_user.business_id), y los endpoints de abajo lo
  // derivan solos del token — nunca de algo que mande el navegador. ---
  const [currentUser, setCurrentUser] = useState<CurrentUser | null>(null)
  const [meStatus, setMeStatus] = useState<'idle' | 'loading' | 'error' | 'not_onboarded' | 'ready'>('idle')
  const [meError, setMeError] = useState('')

  // --- Formulario de alta de negocio (solo se usa si meStatus === 'not_onboarded') ---
  const [signupBusinessName, setSignupBusinessName] = useState('')
  const [signupOwnerName, setSignupOwnerName] = useState('')
  const [signupWhatsappNumber, setSignupWhatsappNumber] = useState('')
  const [signupSubmitting, setSignupSubmitting] = useState(false)
  const [signupError, setSignupError] = useState('')

  // --- Inventario ---
  const [products, setProducts] = useState<Product[]>([])
  const [productsStatus, setProductsStatus] = useState<'idle' | 'loading' | 'error' | 'ready'>('idle')
  const [productsError, setProductsError] = useState('')
  const [searchTerm, setSearchTerm] = useState('')
  const [showLowStockOnly, setShowLowStockOnly] = useState(false)
  const [showProductModal, setShowProductModal] = useState(false)
  const [showAppointmentModal, setShowAppointmentModal] = useState(false)

  // --- Citas ---
  const [appointments, setAppointments] = useState<Appointment[]>([])
  const [appointmentsStatus, setAppointmentsStatus] = useState<'idle' | 'loading' | 'error' | 'ready'>('idle')
  const [appointmentsError, setAppointmentsError] = useState('')
  const [statusFilter, setStatusFilter] = useState<AppointmentStatus | 'all'>('all')

  function loadProducts() {
    setProductsStatus('loading')
    setProductsError('')
    fetchProducts(idToken)
      .then((data) => {
        setProducts(data)
        setProductsStatus('ready')
      })
      .catch((error: Error) => {
        setProductsError(error.message)
        setProductsStatus('error')
      })
  }

  function loadAppointments() {
    setAppointmentsStatus('loading')
    setAppointmentsError('')
    fetchAppointments(idToken)
      .then((data) => {
        setAppointments(data)
        setAppointmentsStatus('ready')
      })
      .catch((error: Error) => {
        setAppointmentsError(error.message)
        setAppointmentsStatus('error')
      })
  }

  function checkCurrentUser() {
    setMeStatus('loading')
    setMeError('')
    fetchCurrentUser(idToken)
      .then((user) => {
        setCurrentUser(user)
        setMeStatus('ready')
      })
      .catch((error: unknown) => {
        if (error instanceof ApiError && error.status === 403) {
          // Token válido, pero sin User local enlazado todavía — este es
          // el caso normal de "negocio nuevo", no un fallo real.
          setMeStatus('not_onboarded')
          return
        }
        setMeError(error instanceof Error ? error.message : 'Error desconocido')
        setMeStatus('error')
      })
  }

  // Paso 1: confirmar con el backend quién es el usuario (y a qué negocio
  // pertenece). Solo si esto va bien tiene sentido pedir inventario/citas.
  useEffect(() => {
    if (!auth.isAuthenticated || !idToken) {
      setCurrentUser(null)
      setMeStatus('idle')
      return
    }
    checkCurrentUser()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [auth.isAuthenticated, idToken])

  async function handleSignup(event: FormEvent) {
    event.preventDefault()
    setSignupSubmitting(true)
    setSignupError('')
    try {
      await createBusiness(signupBusinessName, signupOwnerName, signupWhatsappNumber, idToken)
      checkCurrentUser()
    } catch (error) {
      setSignupError(error instanceof Error ? error.message : 'Error desconocido')
    } finally {
      setSignupSubmitting(false)
    }
  }

  // Paso 2: una vez confirmado el usuario, cargar sus datos.
  useEffect(() => {
    if (meStatus !== 'ready') return
    loadProducts()
    loadAppointments()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [meStatus])

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

  async function handleCreateProduct(input: ProductInput) {
    await createProduct(input, idToken)
    setShowProductModal(false)
    loadProducts()
  }

  async function handleAdjustStock(productId: string, quantity: number) {
    await adjustStock(productId, quantity, idToken)
    loadProducts()
  }

  async function handleUpdateThreshold(productId: string, threshold: number) {
    await updateThreshold(productId, threshold, idToken)
    loadProducts()
  }

  async function handleUpdateAppointmentStatus(appointmentId: string, status: AppointmentStatus) {
    await updateAppointmentStatus(appointmentId, status, idToken)
    loadAppointments()
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

  if (meStatus === 'loading' || meStatus === 'idle') {
    return (
      <div className="flex min-h-screen items-center justify-center bg-neutral-950 text-neutral-400">
        Verificando tu sesión…
      </div>
    )
  }

  if (meStatus === 'error') {
    return (
      <div className="flex min-h-screen flex-col items-center justify-center gap-3 bg-neutral-950 px-6 text-center">
        <p className="text-sm text-red-400">No se pudo verificar el usuario contra el backend: {meError}</p>
        <button
          type="button"
          onClick={() => signOutRedirect()}
          className="mt-2 rounded-md border border-neutral-800 px-3 py-1.5 text-xs text-neutral-400 hover:bg-neutral-900"
        >
          Cerrar sesión
        </button>
      </div>
    )
  }

  if (meStatus === 'not_onboarded') {
    return (
      <div className="flex min-h-screen flex-col items-center justify-center gap-4 bg-neutral-950 px-6 text-neutral-100">
        <div className="w-full max-w-sm">
          <h1 className="mb-1 text-xl font-semibold">Registra tu negocio</h1>
          <p className="mb-6 text-sm text-neutral-500">
            Es la primera vez que entras — vamos a crear tu negocio para que puedas acceder al panel.
          </p>
          <form onSubmit={handleSignup} className="flex flex-col gap-3">
            <div>
              <label className="mb-1 block text-xs font-medium text-neutral-500">Nombre del negocio</label>
              <input
                type="text"
                required
                value={signupBusinessName}
                onChange={(event) => setSignupBusinessName(event.target.value)}
                placeholder="ej. Peluquería Ana"
                className="w-full rounded-md border border-neutral-800 bg-neutral-900 px-3 py-2 text-sm text-neutral-100 placeholder-neutral-600 outline-none focus:border-neutral-600"
              />
            </div>
            <div>
              <label className="mb-1 block text-xs font-medium text-neutral-500">Tu nombre (dueño/a)</label>
              <input
                type="text"
                required
                value={signupOwnerName}
                onChange={(event) => setSignupOwnerName(event.target.value)}
                placeholder="ej. Ana García"
                className="w-full rounded-md border border-neutral-800 bg-neutral-900 px-3 py-2 text-sm text-neutral-100 placeholder-neutral-600 outline-none focus:border-neutral-600"
              />
            </div>
            <div>
              <label className="mb-1 block text-xs font-medium text-neutral-500">
                Número de WhatsApp del negocio
              </label>
              <input
                type="text"
                required
                value={signupWhatsappNumber}
                onChange={(event) => setSignupWhatsappNumber(event.target.value)}
                placeholder="+34600000000"
                className="w-full rounded-md border border-neutral-800 bg-neutral-900 px-3 py-2 text-sm text-neutral-100 placeholder-neutral-600 outline-none focus:border-neutral-600"
              />
            </div>
            {signupError && <p className="text-xs text-red-400">{signupError}</p>}
            <button
              type="submit"
              disabled={signupSubmitting}
              className="mt-2 rounded-md bg-neutral-100 px-4 py-2 text-sm font-medium text-neutral-950 hover:bg-neutral-300 disabled:opacity-50"
            >
              {signupSubmitting ? 'Creando…' : 'Crear negocio'}
            </button>
          </form>
          <button
            type="button"
            onClick={() => signOutRedirect()}
            className="mt-4 text-xs text-neutral-500 hover:text-neutral-300"
          >
            Cerrar sesión
          </button>
        </div>
      </div>
    )
  }

  // --- Panel (usuario autenticado y reconocido por el backend) ---

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
          </div>
          <button
            type="button"
            onClick={() => signOutRedirect()}
            className="rounded-md border border-neutral-800 px-3 py-1.5 text-xs text-neutral-400 hover:bg-neutral-900"
          >
            Cerrar sesión
          </button>
        </header>

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

        {activeTab === 'inventario' && (
          <>
            <div className="mb-4 flex justify-end">
              <button
                type="button"
                onClick={() => setShowProductModal(true)}
                className="rounded-md bg-neutral-100 px-3 py-1.5 text-sm font-medium text-neutral-950 hover:bg-neutral-300"
              >
                + Nuevo producto
              </button>
            </div>
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

        {activeTab === 'citas' && (
          <>
            <div className="mb-4 flex justify-end">
              <button
                type="button"
                onClick={() => setShowAppointmentModal(true)}
                className="rounded-md bg-neutral-100 px-3 py-1.5 text-sm font-medium text-neutral-950 hover:bg-neutral-300"
              >
                + Nueva cita
              </button>
            </div>
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

      {showProductModal && (
        <Modal title="Nuevo producto" onClose={() => setShowProductModal(false)}>
          <ProductForm onSubmit={handleCreateProduct} onCancel={() => setShowProductModal(false)} />
        </Modal>
      )}

      {showAppointmentModal && (
        <Modal title="Nueva cita" onClose={() => setShowAppointmentModal(false)}>
          <AppointmentForm
            idToken={idToken}
            onCreated={() => {
              setShowAppointmentModal(false)
              loadAppointments()
            }}
            onCancel={() => setShowAppointmentModal(false)}
          />
        </Modal>
      )}
    </div>
  )
}

export default App
