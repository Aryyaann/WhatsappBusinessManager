export interface Employee {
  id: string
  name: string
  whatsapp_number: string
}

export interface EmployeeInput {
  name: string
  whatsapp_number: string
}

function authHeaders(idToken: string): HeadersInit {
  return { Authorization: `Bearer ${idToken}` }
}

async function readErrorDetail(response: Response, fallback: string): Promise<string> {
  try {
    const body = await response.json()
    if (body?.detail) return body.detail
  } catch {
    // El cuerpo no era JSON — nos quedamos con el mensaje genérico.
  }
  return fallback
}

export async function fetchEmployees(idToken: string): Promise<Employee[]> {
  const response = await fetch('/api/admin/employees', { headers: authHeaders(idToken) })
  if (!response.ok) {
    throw new Error(`Error ${response.status} al cargar empleados`)
  }
  return response.json()
}

export async function createEmployee(input: EmployeeInput, idToken: string): Promise<Employee> {
  const response = await fetch('/api/admin/employees', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', ...authHeaders(idToken) },
    body: JSON.stringify(input),
  })
  if (!response.ok) {
    throw new Error(await readErrorDetail(response, `Error ${response.status} al crear el empleado`))
  }
  return response.json()
}