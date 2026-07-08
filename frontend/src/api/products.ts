export interface Product {
  id: string
  name: string
  sku: string | null
  unit: string
  quantity: number
  min_stock_threshold: number
  sale_price: number | null
}

export const UNIT_OPTIONS = ['unidad', 'caja', 'kg', 'litro', 'ml', 'gramo'] as const
export type Unit = (typeof UNIT_OPTIONS)[number]

export interface ProductInput {
  name: string
  description?: string
  sku?: string
  category?: string
  unit: Unit
  sale_price?: number
  min_stock_threshold: number
}

function authHeaders(idToken: string): HeadersInit {
  return { Authorization: `Bearer ${idToken}` }
}

export async function fetchProducts(idToken: string): Promise<Product[]> {
  const response = await fetch('/api/admin/products', { headers: authHeaders(idToken) })
  if (!response.ok) {
    throw new Error(`Error ${response.status} al cargar productos`)
  }
  return response.json()
}

export async function createProduct(input: ProductInput, idToken: string): Promise<Product> {
  const response = await fetch('/api/admin/products', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', ...authHeaders(idToken) },
    body: JSON.stringify(input),
  })
  if (!response.ok) {
    let detail = `Error ${response.status} al crear el producto`
    try {
      const body = await response.json()
      if (body?.detail) detail = body.detail
    } catch {
      // El cuerpo no era JSON — nos quedamos con el mensaje genérico.
    }
    throw new Error(detail)
  }
  return response.json()
}

export async function adjustStock(productId: string, quantity: number, idToken: string): Promise<void> {
  const response = await fetch(`/api/admin/products/${productId}/stock`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json', ...authHeaders(idToken) },
    body: JSON.stringify({ quantity }),
  })
  if (!response.ok) {
    throw new Error(`Error ${response.status} al ajustar el stock`)
  }
}

export async function updateThreshold(
  productId: string,
  minStockThreshold: number,
  idToken: string,
): Promise<void> {
  const response = await fetch(`/api/admin/products/${productId}/threshold`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json', ...authHeaders(idToken) },
    body: JSON.stringify({ min_stock_threshold: minStockThreshold }),
  })
  if (!response.ok) {
    throw new Error(`Error ${response.status} al actualizar el mínimo`)
  }
}