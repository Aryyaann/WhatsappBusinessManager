export interface BusinessSignupResult {
  business_id: string
  business_name: string
  owner_name: string
}

export async function createBusiness(
  businessName: string,
  ownerName: string,
  whatsappNumber: string,
  idToken: string,
): Promise<BusinessSignupResult> {
  const response = await fetch('/api/admin/businesses', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${idToken}` },
    body: JSON.stringify({
      business_name: businessName,
      owner_name: ownerName,
      whatsapp_number: whatsappNumber,
    }),
  })
  if (!response.ok) {
    let detail = `Error ${response.status}`
    try {
      const body = await response.json()
      if (body?.detail) detail = body.detail
    } catch {
      // El cuerpo no era JSON — nos quedamos con el código HTTP.
    }
    throw new Error(detail)
  }
  return response.json()
}