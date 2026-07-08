export interface CurrentUser {
  id: string
  name: string
  role: 'owner' | 'employee'
  business_id: string
}

export class ApiError extends Error {
  status: number

  constructor(message: string, status: number) {
    super(message)
    this.status = status
  }
}

export async function fetchCurrentUser(idToken: string): Promise<CurrentUser> {
  const response = await fetch('/api/admin/me', {
    headers: { Authorization: `Bearer ${idToken}` },
  })
  if (!response.ok) {
    // Intentamos leer el "detail" que manda FastAPI en el cuerpo del error
    // (ej. "Token inválido: ..."), en vez de solo el código HTTP — así el
    // aviso en pantalla dice el motivo real sin tener que ir a mirar los
    // logs de uvicorn. Guardamos también el status: un 403 significa
    // "token válido pero sin negocio enlazado todavía" (mostramos alta de
    // negocio), mientras que un 401 es un fallo real de autenticación.
    let detail = `Error ${response.status}`
    try {
      const body = await response.json()
      if (body?.detail) detail = body.detail
    } catch {
      // El cuerpo no era JSON — nos quedamos con el código HTTP.
    }
    throw new ApiError(detail, response.status)
  }
  return response.json()
}