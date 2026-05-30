export const runtime = 'nodejs'
export const dynamic = 'force-dynamic'

const backendUrl = process.env.BACKEND_URL || process.env.NEXT_PUBLIC_BACKEND_URL || 'http://localhost:8000'

export async function GET() {
  const response = await fetch(`${backendUrl}/api/traces`, { cache: 'no-store' })
  const data = await response.text()

  return new Response(data, {
    status: response.status,
    headers: {
      'Content-Type': response.headers.get('content-type') || 'application/json',
      'Cache-Control': 'no-store',
    },
  })
}
