import { getProfile } from '../../api/profile'
import { requireRole } from '../../lib/guards'

export async function profileLoader() {
  await requireRole(['user'])
  return { profile: await getProfile() }
}
