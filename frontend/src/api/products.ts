export interface Product {
  id: string
  name: string
  sku: string | null
  unit: string
  quantity: number
  min_stock_threshold: number
  sale_price: number | null
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