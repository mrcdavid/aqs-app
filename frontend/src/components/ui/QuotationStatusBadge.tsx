import type { QuotationStatus } from '../../api/quotations'

const STYLES: Record<QuotationStatus, { label: string; className: string }> = {
  pending: { label: 'Pending approval', className: 'bg-amber-50 text-amber-800' },
  approved: { label: 'Approved', className: 'bg-green-50 text-green-700' },
  rejected: { label: 'Rejected', className: 'bg-red-50 text-red-700' },
  cancelled: { label: 'Cancelled', className: 'bg-gray-100 text-gray-600' },
}

export function QuotationStatusBadge({ status }: { status: QuotationStatus }) {
  const { label, className } = STYLES[status]
  return (
    <span className={`whitespace-nowrap rounded-full px-2 py-0.5 text-xs font-medium ${className}`}>
      {label}
    </span>
  )
}
