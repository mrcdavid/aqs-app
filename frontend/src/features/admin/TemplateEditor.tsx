import { zodResolver } from '@hookform/resolvers/zod'
import { AlertTriangle, Boxes, HardHat, Layers, ListChecks, PackagePlus, Pencil, Plus, Save, Trash2, X } from 'lucide-react'
import { useState, type ReactNode } from 'react'
import { useForm, useWatch } from 'react-hook-form'

import {
  adminApi,
  type Basis,
  type Component,
  type LaborRate,
  type Material,
  type PriceUnit,
  type ProductDetail,
  type ProductOption,
  type ProductOptionGroup,
} from '../../api/admin'
import { Badge } from '../../components/ui/Badge'
import { Button, ButtonLink, IconButton } from '../../components/ui/Button'
import { Card, EmptyState, ErrorBanner } from '../../components/ui/Card'
import { Field, inputClass } from '../../components/ui/Field'
import { Modal } from '../../components/ui/Modal'
import { messageOf } from '../../lib/errors'
import { barLabel, BASES_FOR_UNIT, BASIS_LABEL, formatMoney, trimDecimal, UNIT_LABEL } from '../../lib/format'
import { confirmAction, toast } from '../../stores/feedback'
import {
  componentSchema,
  optionGroupSchema,
  optionSchema,
  type ComponentForm,
  type OptionForm,
  type OptionGroupForm,
} from './schemas'
import { useCurrency } from './useCurrency'

interface Props {
  product: ProductDetail
  materials: Material[]
  laborRates: LaborRate[]
  onChanged: () => void
}

/** null = closed; line null = adding a new line to `optionId` ('' = always included). */
type LineEditing = { line: Component | null; optionId: string } | null
/** null = closed; option null = adding one: a choice of `groupId`, or an add-on (groupId null). */
type OptionEditing = { option: ProductOption | null; groupId: string | null } | null
/** null = closed; 'new' = adding a group; otherwise renaming that group. */
type GroupEditing = ProductOptionGroup | 'new' | null

/** "per sq ft", or "per 21 ft bar" for bars. */
function unitLabel(unit: PriceUnit, length?: string | null, lengthUnit?: string | null): string {
  return unit === 'bar' ? `per ${barLabel(length, lengthUnit)}` : UNIT_LABEL[unit]
}

export function TemplateEditor({ product, materials, laborRates, onChanged }: Props) {
  const currency = useCurrency()
  const [editing, setEditing] = useState<LineEditing>(null)
  const [editingOption, setEditingOption] = useState<OptionEditing>(null)
  const [editingGroup, setEditingGroup] = useState<GroupEditing>(null)
  const [busyId, setBusyId] = useState<string | null>(null)
  const hasItems = materials.some((m) => m.is_active) || laborRates.some((r) => r.is_active)
  const editingId = editing?.line?.id ?? null
  const baseLines = product.components.filter((c) => c.option_id === null)
  const linesOf = (o: ProductOption) => product.components.filter((c) => c.option_id === o.id)
  const addOns = product.options.filter((o) => o.group_id === null)
  const choicesOf = (g: ProductOptionGroup) => product.options.filter((o) => o.group_id === g.id)
  const hasOptions = product.options.length > 0 || product.option_groups.length > 0
  const perSqft = product.pricing_method === 'per_sqft'
  const rateBadge = (o: ProductOption) =>
    perSqft && Number(o.rate_per_sqft) > 0 ? (
      <Badge tone="success">+{formatMoney(o.rate_per_sqft, currency)} / sq ft</Badge>
    ) : null

  async function remove(c: Component) {
    const ok = await confirmAction({
      title: `Remove ${c.item_code}?`,
      message: `“${c.label || c.item_name}” will no longer be part of this product's price. The material or labour rate itself is not deleted.`,
      confirmLabel: 'Remove line',
      tone: 'danger',
    })
    if (!ok) return
    setBusyId(c.id)
    try {
      await adminApi.removeComponent(product.id, c.id)
      toast.success(`${c.item_code} removed from the template.`)
      onChanged()
    } catch (err) {
      toast.error(messageOf(err))
    } finally {
      setBusyId(null)
    }
  }

  async function removeOption(o: ProductOption) {
    const count = linesOf(o).length
    const what = o.group_id ? 'choice' : 'add-on'
    const ok = await confirmAction({
      title: `Delete the ${what} “${o.name}”?`,
      message: `${count === 1 ? 'Its 1 line is' : `Its ${count} lines are`} removed from this template. Quotations already made keep their prices.`,
      confirmLabel: `Delete ${what}`,
      tone: 'danger',
    })
    if (!ok) return
    setBusyId(o.id)
    try {
      await adminApi.removeOption(product.id, o.id)
      toast.success(`${o.group_id ? 'Choice' : 'Add-on'} “${o.name}” deleted.`)
      onChanged()
    } catch (err) {
      toast.error(messageOf(err))
    } finally {
      setBusyId(null)
    }
  }

  async function removeGroup(g: ProductOptionGroup) {
    const count = choicesOf(g).length
    const ok = await confirmAction({
      title: `Delete the group “${g.name}”?`,
      message: `${count === 1 ? 'Its 1 choice is' : `Its ${count} choices are`} removed from this template, with their lines. Quotations already made keep their prices.`,
      confirmLabel: 'Delete group',
      tone: 'danger',
    })
    if (!ok) return
    setBusyId(g.id)
    try {
      await adminApi.removeOptionGroup(product.id, g.id)
      toast.success(`Group “${g.name}” deleted.`)
      onChanged()
    } catch (err) {
      toast.error(messageOf(err))
    } finally {
      setBusyId(null)
    }
  }

  const lineActions = (c: Component) => (
    <div className="flex justify-end gap-1">
      <IconButton icon={Pencil} tone="brand" label={`Edit line ${c.item_code}`} onClick={() => setEditing({ line: c, optionId: c.option_id ?? '' })} />
      <IconButton icon={Trash2} tone="danger" label={`Remove line ${c.item_code}`} loading={busyId === c.id} onClick={() => remove(c)} />
    </div>
  )

  const itemCell = (c: Component) => (
    <div className="min-w-0">
      <div className="flex flex-wrap items-center gap-1.5">
        <span className="font-mono text-xs text-muted">{c.item_code}</span>
        <Badge tone={c.kind === 'labor' ? 'brand' : 'neutral'} icon={c.kind === 'labor' ? HardHat : Boxes}>
          {c.kind === 'labor' ? 'Labour' : 'Material'}
        </Badge>
        {!c.item_active && (
          <Badge tone="warning" icon={AlertTriangle}>
            Archived
          </Badge>
        )}
      </div>
      <p className="font-medium">{c.label || c.item_name}</p>
    </div>
  )

  const lineList = (lines: Component[]) => (
    <>
      <ul className="space-y-3 md:hidden">
        {lines.map((c) => (
          <li key={c.id} className={`rounded-xl border p-3 ${editingId === c.id ? 'border-transparent ring-2 ring-ring' : 'border-line'}`}>
            {itemCell(c)}
            <p className="mt-2 text-sm text-muted">
              {BASIS_LABEL[c.basis]} × {trimDecimal(c.factor)} · waste {trimDecimal(c.waste_percent)}%
            </p>
            <div className="mt-1 flex items-center justify-between">
              <span className="text-sm tabular-nums">
                {formatMoney(c.item_price, currency)}{' '}
                <span className="text-muted">{unitLabel(c.item_unit, c.item_stock_length, c.item_stock_length_unit)}</span>
              </span>
              {lineActions(c)}
            </div>
          </li>
        ))}
      </ul>
      <div className="hidden overflow-x-auto md:block">
        <table className="w-full text-left text-sm">
          <thead className="text-xs tracking-wide text-muted uppercase">
            <tr className="border-b border-line">
              <th className="py-3 pr-4 font-medium">Item</th>
              <th className="py-3 pr-4 font-medium">Measured by</th>
              <th className="py-3 pr-4 text-right font-medium">Factor</th>
              <th className="py-3 pr-4 text-right font-medium">Waste</th>
              <th className="py-3 pr-4 text-right font-medium">Price</th>
              <th className="py-3 text-right font-medium">Actions</th>
            </tr>
          </thead>
          <tbody>
            {lines.map((c) => (
              <tr
                key={c.id}
                className={`border-b border-line last:border-0 ${
                  editingId === c.id ? 'bg-brand-soft outline-2 -outline-offset-2 outline-ring' : 'hover:bg-surface-2/60'
                }`}
              >
                <td className="py-2.5 pr-4">{itemCell(c)}</td>
                <td className="py-2.5 pr-4">{BASIS_LABEL[c.basis]}</td>
                <td className="py-2.5 pr-4 text-right tabular-nums">{trimDecimal(c.factor)}</td>
                <td className="py-2.5 pr-4 text-right tabular-nums">{trimDecimal(c.waste_percent)}%</td>
                <td className="py-2.5 pr-4 text-right tabular-nums whitespace-nowrap">
                  {formatMoney(c.item_price, currency)}{' '}
                  <span className="text-muted">{unitLabel(c.item_unit, c.item_stock_length, c.item_stock_length_unit)}</span>
                </td>
                <td className="py-1.5">{lineActions(c)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </>
  )

  return (
    <Card
      title={perSqft ? 'Rates and cost guide' : 'Price template'}
      icon={Layers}
      actions={
        hasItems && (
          <div className="flex flex-wrap gap-2">
            <Button size="sm" variant="secondary" icon={ListChecks} onClick={() => setEditingGroup('new')}>
              Add a choice group
            </Button>
            <Button size="sm" variant="secondary" icon={PackagePlus} onClick={() => setEditingOption({ option: null, groupId: null })}>
              Add an add-on
            </Button>
            <Button size="sm" icon={Plus} onClick={() => setEditing({ line: null, optionId: '' })}>
              Add line
            </Button>
          </div>
        )
      }
    >
      {perSqft && (
        <p className="mb-4 rounded-xl border border-brand/30 bg-brand-soft p-3 text-sm text-ink">
          <strong>Sold per sq ft.</strong> The price is <strong>area × (base rate {formatMoney(product.rate_per_sqft, currency)}
          {' '}+ the rates of the chosen glass type and add-ons)</strong>, VAT included. The lines below are only a{' '}
          <strong>cost guide</strong>: the preview shows what one piece costs you and your margin. A choice group with
          no rates (e.g. Glass sheet: 4 × 7 ft) is just recorded on the quotation.
        </p>
      )}
      <p className="mb-4 rounded-xl bg-surface-2 p-3 text-sm text-muted">
        Each line costs <strong className="text-ink">measurement × factor × (1 + waste %) × price</strong>, measured in feet
        and sq ft. Bars are counted whole, rounded up: e.g. 32 ft of frame in 21-ft bars → 2 bars. Example: two tracks along
        the width → <em>Width</em>, factor <em>2</em>. <strong className="text-ink">Choice groups</strong> ask one question
        with one answer (e.g. Glass type: 1/4 Bronze or Reflective); only the chosen answer is priced.{' '}
        <strong className="text-ink">Add-ons</strong> are optional extras (e.g. an open back frame), priced only when ticked.
      </p>

      {!hasItems && (
        <div className="mb-4 rounded-xl border border-warning/30 bg-warning-soft p-4 text-sm text-warning">
          <p className="flex items-center gap-2 font-medium">
            <AlertTriangle className="size-4" aria-hidden /> No materials or labour rates yet
          </p>
          <p className="mt-1">Add them first, then come back to build this template.</p>
          <div className="mt-3 flex flex-wrap gap-2">
            <ButtonLink to="/admin/materials" size="sm" variant="secondary" icon={Boxes}>
              Go to Materials
            </ButtonLink>
            <ButtonLink to="/admin/labor-rates" size="sm" variant="secondary" icon={HardHat}>
              Go to Labour rates
            </ButtonLink>
          </div>
        </div>
      )}

      <div className="space-y-6">
        <Section title="Always included" text={hasOptions ? 'Priced on every quotation.' : undefined}>
          {baseLines.length === 0
            ? hasItems && (
                <EmptyState
                  icon={Layers}
                  title="This template is empty"
                  text="Add the materials and labour that make up one piece of this product."
                  action={
                    <Button icon={Plus} onClick={() => setEditing({ line: null, optionId: '' })}>
                      Add first line
                    </Button>
                  }
                />
              )
            : lineList(baseLines)}
        </Section>

        {product.option_groups.map((g) => {
          const choices = choicesOf(g)
          return (
            <Section
              key={g.id}
              title={g.name}
              badge={
                <Badge tone="brand" icon={ListChecks}>
                  Choose one
                </Badge>
              }
              text="Customers pick exactly one choice; the first is selected for them."
              actions={
                <>
                  <Button size="sm" variant="secondary" icon={Plus} onClick={() => setEditingOption({ option: null, groupId: g.id })}>
                    Add a choice
                  </Button>
                  <IconButton icon={Pencil} tone="brand" label={`Rename group ${g.name}`} onClick={() => setEditingGroup(g)} />
                  <IconButton icon={Trash2} tone="danger" label={`Delete group ${g.name}`} loading={busyId === g.id} onClick={() => removeGroup(g)} />
                </>
              }
            >
              {choices.length === 0 ? (
                <p className="rounded-xl border border-dashed border-line p-4 text-sm text-muted">
                  No choices yet. Add at least two, e.g. “Ordinary” and “Reflective”.
                </p>
              ) : (
                <div className="space-y-4 border-l-2 border-brand/30 pl-4">
                  {choices.map((o) => {
                    const lines = linesOf(o)
                    return (
                      <Section
                        key={o.id}
                        title={o.name}
                        badge={rateBadge(o)}
                        text={o.description || undefined}
                        actions={
                          <>
                            <Button size="sm" variant="secondary" icon={Plus} disabled={!hasItems} onClick={() => setEditing({ line: null, optionId: o.id })}>
                              Add line
                            </Button>
                            <IconButton icon={Pencil} tone="brand" label={`Edit choice ${o.name}`} onClick={() => setEditingOption({ option: o, groupId: g.id })} />
                            <IconButton icon={Trash2} tone="danger" label={`Delete choice ${o.name}`} loading={busyId === o.id} onClick={() => removeOption(o)} />
                          </>
                        }
                      >
                        {lines.length === 0 ? (
                          <p className="text-sm text-muted">
                            {perSqft
                              ? 'No cost lines. Its rate (if any) is added to the price per sq ft.'
                              : 'No lines: choosing this adds nothing (fine for a “None” choice).'}
                          </p>
                        ) : (
                          lineList(lines)
                        )}
                      </Section>
                    )
                  })}
                </div>
              )}
            </Section>
          )
        })}

        {addOns.map((o) => {
          const lines = linesOf(o)
          const shrinks = o.width_reduction_mm > 0 || o.height_reduction_mm > 0
          return (
            <Section
              key={o.id}
              title={o.name}
              badge={
                <>
                  <Badge tone="brand" icon={PackagePlus}>
                    Optional add-on
                  </Badge>
                  {rateBadge(o)}
                </>
              }
              text={
                [
                  o.description,
                  shrinks &&
                    `When ticked, the size typed is the wall opening and the window is measured ${o.width_reduction_mm} mm narrower and ${o.height_reduction_mm} mm shorter.`,
                ]
                  .filter(Boolean)
                  .join(' ') || undefined
              }
              actions={
                <>
                  <Button size="sm" variant="secondary" icon={Plus} disabled={!hasItems} onClick={() => setEditing({ line: null, optionId: o.id })}>
                    Add line
                  </Button>
                  <IconButton icon={Pencil} tone="brand" label={`Edit add-on ${o.name}`} onClick={() => setEditingOption({ option: o, groupId: null })} />
                  <IconButton icon={Trash2} tone="danger" label={`Delete add-on ${o.name}`} loading={busyId === o.id} onClick={() => removeOption(o)} />
                </>
              }
            >
              {lines.length === 0 ? (
                <p className="rounded-xl border border-dashed border-line p-4 text-sm text-muted">
                  {perSqft
                    ? Number(o.rate_per_sqft) > 0
                      ? 'No cost lines. Its rate is added to the price per sq ft when ticked.'
                      : "No rate or lines yet. Customers won't see this add-on until it has a rate per sq ft or a line."
                    : "No lines yet. Customers won't see this add-on until it has at least one line."}
                </p>
              ) : (
                lineList(lines)
              )}
            </Section>
          )
        })}
      </div>

      <LineModal
        editing={editing}
        product={product}
        materials={materials}
        laborRates={laborRates}
        onClose={() => setEditing(null)}
        onSaved={() => {
          setEditing(null)
          onChanged()
        }}
      />
      <OptionModal
        editing={editingOption}
        product={product}
        onClose={() => setEditingOption(null)}
        onSaved={() => {
          setEditingOption(null)
          onChanged()
        }}
      />
      <GroupModal
        editing={editingGroup}
        product={product}
        onClose={() => setEditingGroup(null)}
        onSaved={() => {
          setEditingGroup(null)
          onChanged()
        }}
      />
    </Card>
  )
}

function Section({
  title,
  badge,
  text,
  actions,
  children,
}: {
  title: string
  badge?: ReactNode
  text?: string
  actions?: ReactNode
  children: ReactNode
}) {
  return (
    <section className="space-y-3">
      <div className="flex flex-wrap items-start justify-between gap-2 border-b border-line pb-2">
        <div className="min-w-0">
          <h3 className="flex flex-wrap items-center gap-2 font-semibold">
            {title}
            {badge}
          </h3>
          {text && <p className="text-sm text-muted">{text}</p>}
        </div>
        {actions && <div className="flex items-center gap-1">{actions}</div>}
      </div>
      {children}
    </section>
  )
}

function OptionModal({
  editing,
  product,
  onClose,
  onSaved,
}: {
  editing: OptionEditing
  product: ProductDetail
  onClose: () => void
  onSaved: () => void
}) {
  const option = editing?.option ?? null
  const group = product.option_groups.find((g) => g.id === editing?.groupId)
  const what = group ? 'choice' : 'add-on'
  return (
    <Modal
      open={editing !== null}
      onClose={onClose}
      icon={option ? Pencil : group ? Plus : PackagePlus}
      title={option ? `Edit ${what} “${option.name}”` : group ? `Add a choice to “${group.name}”` : 'Add an add-on'}
      description={
        option
          ? `Part of ${product.name}.`
          : group
            ? `e.g. “Reflective”. After saving, add its lines (e.g. the reflective glass, measured by area).`
            : `An optional extra for ${product.name}, e.g. “Open back (outer jamb)”. After saving, add its lines.`
      }
      footer={
        <>
          <Button variant="secondary" icon={X} onClick={onClose}>
            Cancel
          </Button>
          <Button type="submit" form="option-form" icon={option ? Save : Plus}>
            {option ? `Save ${what}` : `Add ${what}`}
          </Button>
        </>
      }
    >
      {editing !== null && (
        <OptionFormBody
          option={option}
          isChoice={!!group}
          perSqft={product.pricing_method === 'per_sqft'}
          onSubmit={async (values) => {
            const body = optionSchema.parse(values)
            if (option) {
              await adminApi.updateOption(product.id, option.id, body)
              toast.success(`${group ? 'Choice' : 'Add-on'} saved.`)
            } else {
              const siblings = product.options.filter((o) => o.group_id === (group?.id ?? null)).length
              await adminApi.addOption(product.id, { ...body, group_id: group?.id ?? null, sort_order: siblings })
              toast.success(`${group ? 'Choice' : 'Add-on'} “${body.name}” added. Now add its lines.`)
            }
            onSaved()
          }}
        />
      )}
    </Modal>
  )
}

function OptionFormBody({
  option,
  isChoice,
  perSqft,
  onSubmit,
}: {
  option: ProductOption | null
  isChoice: boolean
  perSqft: boolean
  onSubmit: (values: OptionForm) => Promise<void>
}) {
  const [error, setError] = useState<string | null>(null)
  const currency = useCurrency()
  const { register, handleSubmit, formState } = useForm<OptionForm>({
    resolver: zodResolver(optionSchema),
    defaultValues: {
      name: option?.name ?? '',
      description: option?.description ?? '',
      width_reduction_mm: option?.width_reduction_mm ?? 0,
      height_reduction_mm: option?.height_reduction_mm ?? 0,
      rate_per_sqft: option ? trimDecimal(option.rate_per_sqft) : '0',
    },
  })
  const { errors, isSubmitting } = formState

  return (
    <form
      id="option-form"
      noValidate
      className="space-y-4"
      onSubmit={handleSubmit(async (values) => {
        setError(null)
        try {
          await onSubmit(values)
        } catch (err) {
          setError(messageOf(err))
        }
      })}
    >
      <ErrorBanner message={error} />
      <fieldset disabled={isSubmitting} className="grid gap-4 sm:grid-cols-2">
        <Field label="Name" htmlFor="o-name" required hint="Shown to customers when quoting" error={errors.name?.message} className="sm:col-span-2">
          <input
            id="o-name"
            data-autofocus
            placeholder={isChoice ? 'e.g. Reflective' : 'e.g. Open back (outer jamb)'}
            className={inputClass}
            aria-invalid={!!errors.name}
            {...register('name')}
          />
        </Field>
        <Field label="Description (optional)" htmlFor="o-desc" hint="A short explanation for customers" error={errors.description?.message} className="sm:col-span-2">
          <input id="o-desc" className={inputClass} {...register('description')} />
        </Field>
        {perSqft && (
          <Field
            label={`Rate per sq ft (${currency})`}
            htmlFor="o-rate"
            required
            hint={
              isChoice
                ? 'Added to the base rate when chosen, e.g. 1/4 Bronze 350. 0 = just recorded (e.g. a sheet size).'
                : 'Added to the rate when ticked, e.g. open back 40. Customers never see rates.'
            }
            error={errors.rate_per_sqft?.message}
            className="sm:col-span-2"
          >
            <input id="o-rate" inputMode="decimal" className={`${inputClass} tabular-nums sm:w-48`} aria-invalid={!!errors.rate_per_sqft} {...register('rate_per_sqft')} />
          </Field>
        )}
        {!isChoice && (
          <>
            <p className="rounded-xl bg-surface-2 p-3 text-sm text-muted sm:col-span-2">
              <strong className="text-ink">Frame around the window, like an open back?</strong> Then the size typed is the
              wall opening: this add-on&apos;s lines use it as is, and the rest of the window is measured smaller by the
              amounts below. Leave 0 for an add-on that doesn&apos;t change the size.
            </p>
            <Field label="Window narrower by (mm)" htmlFor="o-wr" required error={errors.width_reduction_mm?.message}>
              <input
                id="o-wr"
                type="number"
                min={0}
                max={2000}
                inputMode="numeric"
                className={`${inputClass} tabular-nums`}
                {...register('width_reduction_mm', { valueAsNumber: true })}
              />
            </Field>
            <Field label="Window shorter by (mm)" htmlFor="o-hr" required error={errors.height_reduction_mm?.message}>
              <input
                id="o-hr"
                type="number"
                min={0}
                max={2000}
                inputMode="numeric"
                className={`${inputClass} tabular-nums`}
                {...register('height_reduction_mm', { valueAsNumber: true })}
              />
            </Field>
          </>
        )}
      </fieldset>
    </form>
  )
}

function GroupModal({
  editing,
  product,
  onClose,
  onSaved,
}: {
  editing: GroupEditing
  product: ProductDetail
  onClose: () => void
  onSaved: () => void
}) {
  const group = editing && editing !== 'new' ? editing : null
  return (
    <Modal
      open={editing !== null}
      onClose={onClose}
      icon={group ? Pencil : ListChecks}
      title={group ? `Rename “${group.name}”` : 'Add a choice group'}
      description={
        group
          ? `Part of ${product.name}.`
          : `A question with one answer, e.g. “Glass type”. After saving, add its choices (e.g. Ordinary, Reflective).`
      }
      footer={
        <>
          <Button variant="secondary" icon={X} onClick={onClose}>
            Cancel
          </Button>
          <Button type="submit" form="group-form" icon={group ? Save : Plus}>
            {group ? 'Save group' : 'Add group'}
          </Button>
        </>
      }
    >
      {editing !== null && (
        <GroupFormBody
          group={group}
          onSubmit={async (values) => {
            const body = optionGroupSchema.parse(values)
            if (group) {
              await adminApi.updateOptionGroup(product.id, group.id, body)
              toast.success('Group saved.')
            } else {
              await adminApi.addOptionGroup(product.id, { ...body, sort_order: product.option_groups.length })
              toast.success(`Group “${body.name}” added. Now add its choices.`)
            }
            onSaved()
          }}
        />
      )}
    </Modal>
  )
}

function GroupFormBody({ group, onSubmit }: { group: ProductOptionGroup | null; onSubmit: (values: OptionGroupForm) => Promise<void> }) {
  const [error, setError] = useState<string | null>(null)
  const { register, handleSubmit, formState } = useForm<OptionGroupForm>({
    resolver: zodResolver(optionGroupSchema),
    defaultValues: { name: group?.name ?? '' },
  })
  const { errors, isSubmitting } = formState

  return (
    <form
      id="group-form"
      noValidate
      className="space-y-4"
      onSubmit={handleSubmit(async (values) => {
        setError(null)
        try {
          await onSubmit(values)
        } catch (err) {
          setError(messageOf(err))
        }
      })}
    >
      <ErrorBanner message={error} />
      <fieldset disabled={isSubmitting}>
        <Field label="Question" htmlFor="g-name" required hint="Shown to customers above the choices" error={errors.name?.message}>
          <input id="g-name" data-autofocus placeholder="e.g. Glass type" className={inputClass} aria-invalid={!!errors.name} {...register('name')} />
        </Field>
      </fieldset>
    </form>
  )
}

function LineModal({
  editing,
  product,
  materials,
  laborRates,
  onClose,
  onSaved,
}: Omit<Props, 'onChanged'> & { editing: LineEditing; onClose: () => void; onSaved: () => void }) {
  const [saving, setSaving] = useState(false)
  const line = editing?.line ?? null
  return (
    <Modal
      open={editing !== null}
      onClose={onClose}
      icon={line ? Pencil : Plus}
      title={line ? `Edit line ${line.item_code}` : 'Add a line'}
      description={line ? `${line.item_name} — the item can't be changed; remove the line and add a new one instead.` : `Part of ${product.name}.`}
      footer={
        <>
          <Button variant="secondary" icon={X} onClick={onClose}>
            Cancel
          </Button>
          <Button type="submit" form="line-form" icon={line ? Save : Plus} loading={saving}>
            {line ? 'Save line' : 'Add line'}
          </Button>
        </>
      }
    >
      {editing !== null && (
        <LineForm
          line={line}
          optionId={editing.optionId}
          groups={product.option_groups}
          options={product.options}
          materials={materials}
          laborRates={laborRates}
          onSubmit={async (values) => {
            const { item, option_id, ...rest } = componentSchema.parse(values)
            const option = option_id || null
            setSaving(true)
            try {
              if (line) {
                await adminApi.updateComponent(product.id, line.id, { ...rest, option_id: option })
              } else {
                const [kind, id] = item.split(':')
                await adminApi.addComponent(product.id, {
                  ...rest,
                  option_id: option,
                  [kind === 'material' ? 'material_id' : 'labor_rate_id']: id,
                  sort_order: product.components.length,
                })
              }
            } finally {
              setSaving(false)
            }
            toast.success(line ? 'Line saved.' : 'Line added.')
            onSaved()
          }}
        />
      )}
    </Modal>
  )
}

function LineForm({
  line,
  optionId,
  groups,
  options,
  materials,
  laborRates,
  onSubmit,
}: {
  line: Component | null
  /** '' = always included */
  optionId: string
  groups: ProductOptionGroup[]
  options: ProductOption[]
  materials: Material[]
  laborRates: LaborRate[]
  onSubmit: (values: ComponentForm) => Promise<void>
}) {
  const [error, setError] = useState<string | null>(null)
  const { register, handleSubmit, setValue, control, formState } = useForm<ComponentForm>({
    resolver: zodResolver(componentSchema),
    defaultValues: line
      ? {
          item: line.material_id ? `material:${line.material_id}` : `labor:${line.labor_rate_id}`,
          basis: line.basis,
          factor: trimDecimal(line.factor),
          waste_percent: trimDecimal(line.waste_percent),
          label: line.label,
          option_id: optionId,
        }
      : { item: '', basis: 'area', factor: '1', waste_percent: '0', label: '', option_id: optionId },
  })
  const { errors, isSubmitting } = formState

  // The chosen item's pricing unit decides which measurements make sense.
  const units = new Map<string, PriceUnit>([
    ...materials.map((m) => [`material:${m.id}`, m.unit] as const),
    ...laborRates.map((r) => [`labor:${r.id}`, r.unit] as const),
  ])
  const selectedUnit = units.get(useWatch({ control, name: 'item' }))
  const basis = useWatch({ control, name: 'basis' })
  const allowedBases: Basis[] = selectedUnit ? BASES_FOR_UNIT[selectedUnit] : []
  const factorHint =
    selectedUnit === 'bar'
      ? basis === 'area'
        ? 'Bars per sq ft of design, e.g. 3.5 bars for a 48 × 48 grill (16 sq ft) → 0.2188'
        : basis === 'fixed'
          ? 'Bars per piece'
          : 'How many runs, e.g. 2 (frame and panel); feet needed ÷ bar length, rounded up'
      : selectedUnit === 'kg'
        ? basis === 'fixed'
          ? 'Kilos per piece'
          : `Kilos per ${basis === 'area' ? 'sq ft' : 'foot'}, e.g. 0.05`
        : 'How many (e.g. 2 tracks)'

  const itemField = register('item', {
    onChange: (e: React.ChangeEvent<HTMLSelectElement>) => {
      const unit = units.get(e.target.value)
      if (unit) setValue('basis', BASES_FOR_UNIT[unit][0])
    },
  })

  return (
    <form
      id="line-form"
      noValidate
      className="space-y-4"
      onSubmit={handleSubmit(async (values) => {
        setError(null)
        try {
          await onSubmit(values)
        } catch (err) {
          setError(messageOf(err))
        }
      })}
    >
      <ErrorBanner message={error} />
      <fieldset disabled={isSubmitting} className="grid gap-4 sm:grid-cols-2">
        <Field label="Material or labour" htmlFor="c-item" required error={errors.item?.message} className="sm:col-span-2">
          <select id="c-item" className={inputClass} disabled={!!line} aria-invalid={!!errors.item} {...itemField}>
            <option value="">Choose…</option>
            <optgroup label="Materials">
              {materials
                .filter((m) => m.is_active || line?.material_id === m.id)
                .map((m) => (
                  <option key={m.id} value={`material:${m.id}`}>
                    {m.code} – {m.name} ({unitLabel(m.unit, m.stock_length, m.stock_length_unit)})
                  </option>
                ))}
            </optgroup>
            <optgroup label="Labour">
              {laborRates
                .filter((r) => r.is_active || line?.labor_rate_id === r.id)
                .map((r) => (
                  <option key={r.id} value={`labor:${r.id}`}>
                    {r.code} – {r.name} ({UNIT_LABEL[r.unit]})
                  </option>
                ))}
            </optgroup>
          </select>
        </Field>
        {options.length > 0 && (
          <Field label="Part of" htmlFor="c-option" required hint="Choice and add-on lines are only priced when chosen" className="sm:col-span-2">
            <select id="c-option" className={inputClass} {...register('option_id')}>
              <option value="">Always included</option>
              {groups.map((g) => (
                <optgroup key={g.id} label={g.name}>
                  {options
                    .filter((o) => o.group_id === g.id)
                    .map((o) => (
                      <option key={o.id} value={o.id}>
                        {g.name}: {o.name}
                      </option>
                    ))}
                </optgroup>
              ))}
              {options.some((o) => o.group_id === null) && (
                <optgroup label="Add-ons">
                  {options
                    .filter((o) => o.group_id === null)
                    .map((o) => (
                      <option key={o.id} value={o.id}>
                        Add-on: {o.name}
                      </option>
                    ))}
                </optgroup>
              )}
            </select>
          </Field>
        )}
        <Field
          label="Measured by"
          htmlFor="c-basis"
          required
          hint={selectedUnit ? undefined : 'Choose a material or labour first'}
          error={errors.basis?.message}
          className="sm:col-span-2"
        >
          <select id="c-basis" className={inputClass} disabled={!selectedUnit} {...register('basis')}>
            {allowedBases.map((b) => (
              <option key={b} value={b}>
                {BASIS_LABEL[b]}
              </option>
            ))}
          </select>
        </Field>
        <Field label="Factor" htmlFor="c-factor" required hint={factorHint} error={errors.factor?.message}>
          <input id="c-factor" data-autofocus={line ? true : undefined} inputMode="decimal" className={`${inputClass} tabular-nums`} {...register('factor')} />
        </Field>
        <Field label="Waste (%)" htmlFor="c-waste" required hint="Extra for cutting loss" error={errors.waste_percent?.message}>
          <input id="c-waste" inputMode="decimal" className={`${inputClass} tabular-nums`} {...register('waste_percent')} />
        </Field>
        <Field
          label="Label (optional)"
          htmlFor="c-label"
          hint="Shown on the quotation instead of the item name, e.g. “Top and bottom track”"
          error={errors.label?.message}
          className="sm:col-span-2"
        >
          <input id="c-label" className={inputClass} {...register('label')} />
        </Field>
      </fieldset>
    </form>
  )
}
