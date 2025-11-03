import type { Metadata } from 'next'

export const metadata: Metadata = {
  title: 'Amazon PPC Dashboard',
  description: 'Amazon PPC Optimization Dashboard',
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
