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

export async function fetchProducts(businessId: string, idToken: string): Promise<Product[]> {
  const response = await fetch(
    `/api/admin/products?business_id=${encodeURIComponent(businessId)}`,
    { headers: authHeaders(idToken) },
  )
  if (!response.ok) {
    throw new Error(`Error ${response.status} al cargar productos`)
  }
  return response.json()
}

export async function adjustStock(
  businessId: string,
  productId: string,
  quantity: number,
  idToken: string,
): Promise<void> {
  const response = await fetch(
    `/api/admin/products/${productId}/stock?business_id=${encodeURIComponent(businessId)}`,
    {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json', ...authHeaders(idToken) },
      body: JSON.stringify({ quantity }),
    },
  )
  if (!response.ok) {
    throw new Error(`Error ${response.status} al ajustar el stock`)
  }
}

export async function updateThreshold(
  businessId: string,
  productId: string,
  minStockThreshold: number,
  idToken: string,
): Promise<void> {
  const response = await fetch(
    `/api/admin/products/${productId}/threshold?business_id=${encodeURIComponent(businessId)}`,
    {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json', ...authHeaders(idToken) },
      body: JSON.stringify({ min_stock_threshold: minStockThreshold }),
    },
  )
  if (!response.ok) {
    throw new Error(`Error ${response.status} al actualizar el mínimo`)
  }
}