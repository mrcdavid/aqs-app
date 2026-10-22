// Product actions shared by the product list and the product page.

import { adminApi, type Product } from '../../api/admin'
import { messageOf } from '../../lib/errors'
import { confirmAction, toast } from '../../stores/feedback'
import type { ProductForm } from './schemas'

/** A product's details as the edit dialog expects them. */
export function productFormValues(p: Product): ProductForm {
  return {
    code: p.code,
    name: p.name,
    category: p.category,
    description: p.description,
    min_width_mm: p.min_width_mm,
    max_width_mm: p.max_width_mm,
    min_height_mm: p.min_height_mm,
    max_height_mm: p.max_height_mm,
    pricing_method: p.pricing_method,
    rate_per_sqft: p.rate_per_sqft,
  }
}

/** Ask Yes / No, then delete. Resolves true when the product was deleted. */
export async function deleteProduct(p: Pick<Product, 'id' | 'code' | 'name'>): Promise<boolean> {
  const ok = await confirmAction({
    title: `Delete ${p.code}?`,
    message: `“${p.name}” and its price template (lines, choices and add-ons) will be deleted. If it was already quoted, it is hidden instead, so its quotations and their PDFs still show it. This can't be undone — to stop offering it for now, archive it instead.`,
    confirmLabel: 'Yes, delete it',
    cancelLabel: 'No',
    tone: 'danger',
  })
  if (!ok) return false
  try {
    const { kept_for_quotations: kept } = await adminApi.deleteProduct(p.id)
    toast.success(kept ? `${p.code} deleted. Its quotations still show it.` : `${p.code} deleted.`)
    return true
  } catch (err) {
    toast.error(messageOf(err))
    return false
  }
}
