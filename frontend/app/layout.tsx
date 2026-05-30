import type { Metadata } from 'next'
import './globals.css'

export const metadata: Metadata = {
  title: 'AegisOps v2 - Self-Evolving Incident Commander',
  description: 'An autonomous AI operations agent that resolves enterprise incidents and gets measurably faster each time.',
}

export default function RootLayout({
  children,
}: {
  children: React.ReactNode
}) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  )
}
