export interface Product {
  id: string
  name: string
  sku: string | null
  unit: string
  quantity: number
  min_stock_threshold: number
  sale_price: number | null
}

export async function fetchProducts(businessId: string): Promise<Product[]> {
  const response = await fetch(
    `/api/admin/products?business_id=${encodeURIComponent(businessId)}`,
  )
  if (!response.ok) {
    throw new Error(`Error ${response.status} al cargar productos`)
  }
  return response.json()
}