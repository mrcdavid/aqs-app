# Quotations, pricing and the dashboard — detailed rules

The business rules behind AQS APP, as built (last updated 2026-10-16). CLAUDE.md links here;
the code is the final word: `backend/app/services/` (`pricing.py`, `options.py`,
`quotations.py`, `quotation_views.py`, `pdf.py`, `dashboard.py`).

## 1. Product templates (Admin → Products)

A product's price comes from its **template**: lines that are each one material or one labour
rate, measured from the opening the client types:

```
quantity = measurement × factor × (1 + waste% / 100)      (4 dp)
cost     = quantity × item price                          (2 dp, half-up)
```

Measurements (`basis`): **area** (m², item priced per m²), **perimeter / width / height**
(m, priced per metre), **fixed** (count, priced per piece). An item's unit can't change while a
template uses it. Products are archived, never deleted. Materials / labour rates can be
archived, or deleted only when no template uses them (409).

### Options

Each line belongs to one of:

| Kind | What it is | When it is priced | Example |
|---|---|---|---|
| Always included | `option_id` NULL | always | frames, rollers, labour |
| **Choice** of a group | option with `group_id` | when that choice is picked — **exactly one per group** (first pre-selected on forms) | Glass type: Ordinary / Reflective |
| **Add-on** | option without a group | only when ticked (unticked by default) | Open back (outer jamb) |

- Groups: `product_option_groups`; choices and add-ons: `product_options` (names unique per group;
  add-on names unique among add-ons). A choice may have no lines (e.g. "None").
- Offered to clients: an add-on with ≥ 1 line and no archived items; a choice with no archived
  items. If **no** choice of a group can be offered, the product can't be quoted at all.
- **Size reduction** (`width_reduction_mm` / `height_reduction_mm`, 0–2000, add-ons): when chosen,
  the size typed is the **wall opening** — the add-on's own lines use it as is, every other line
  is measured that much smaller (e.g. the window inside an open back frame). Too small → 422.
- Admins edit all of this in the template editor; the price preview re-prices immediately when a
  choice or add-on changes.

## 2. Price of one item

```
unit_subtotal = Σ line costs                 (cost of one piece)
unit_price    = unit_subtotal × (1 + markup%)       net = unit_price × quantity
vat           = net × VAT%                          total = net + VAT
amount        = total rounded UP to the next `rounding_step` (Settings; default 100, 0 = off)
```

Money is `Decimal` / `NUMERIC(12,2)`, never float; half-up to centavos at each step. Prices are
computed on the server only — the client sends product, size, unit, quantity and option ids.

## 3. Quotations

- **Items**: 1–20 per quotation (`quotation_items`), each with its own product, size (cm/in typed,
  stored in mm), quantity 1–100, choices and add-ons (max 10 option ids). An error names the item
  ("Item 2: width must be …").
- Each item's prices are frozen in `quotation_items.snapshot` (product, input, pricing breakdown,
  choices, options). The quotation's `snapshot` holds the client, plus business details frozen at
  approval. Snapshot version 5 (`SNAPSHOT_VERSION` in `services/quotations.py`).
- `quotations.total` = Σ item amounts. On approval an admin may type a different **final amount**;
  the difference shows as an **Adjustment** (customer page and PDF: Subtotal → Adjustment → Total).
- **Payment terms**: 50% downpayment, 50% upon completion and installation (always add up).
- **Who it's for**: a signed-in customer (`user_id`), or a **walk-in client** typed in by staff
  (`user_id` NULL, `created_by` = staff). Walk-in quotes never appear in any customer account.

### Statuses and who can do what

| Action | Who | Rules |
|---|---|---|
| Create | customer (own profile) / staff (walk-in client) | starts `pending`; 10 requests/min per IP; customers max 20 pending |
| Approve | admin, super admin | pending only; assigns `AQS-<year>-<6 digits>` (PHT, per year), valid N days (Settings), stores the final PDF once; optional final amount; Yes/No confirmation |
| Reject | admin, super admin | pending only; note required (customer sees it); Yes/No confirmation |
| Cancel | the customer (own) or admin / super admin | pending only; staff may add a reason; Yes/No confirmation |
| Delete | **super admin only** | any status; **soft delete** (`deleted_at`, `deleted_by`): hidden from every list, page, PDF link, the dashboard and the pending limit; kept in the DB and audited |

Every state change writes an `audit_log` row.

## 4. What the client sees

- Web page and PDF: each item's product, description, choices ("Glass type: Reflective"),
  add-ons ("With: Open back"), size, quantity and **amount (VAT included)**; the total; the 50/50
  split. Never unit prices, costs, markup or VAT — not even in the API response.
- The **PDF never lists materials/labour**. (The customer web page still shows an "Includes: …"
  list — open question in CLAUDE.md §11.)
- PDF design: app colours (Blue → Indigo gradient header and total banner), rounded cards,
  Helvetica (no ₱ glyph, so amounts read "PHP"). Ends with signature lines: **Prepared by**
  (Settings → owner name, default "Cleo David") and **Conforme** (client name + date). Drafts
  carry an `ESTIMATE · PENDING APPROVAL` watermark drawn on top of the content.
- Staff see the full per-item cost breakdown (lines, measured size, markup, VAT, rounding).

## 5. Dashboard (`/admin`)

Counts **approved quotations only**, by the PHT date they were *requested* (max 366-day range):
approved value, average quotation, approved per day, by province and by product (ranked by
approved value; a quotation counts once per product, valued by that product's item amounts),
largest approved projects. Exceptions: approval rate = approved ÷ (approved + rejected); "Waiting
for review" = all pending now. Deleted quotations never count.

## 6. Input rules (backend `schemas/common.py`, frontend `lib/schemas.ts`)

- Mobile numbers: PH only, `09XXXXXXXXX` / `+639XXXXXXXXX`; spaces, dashes, dots and brackets are
  accepted and removed. Landlines and foreign numbers are rejected.
- Names (customer, walk-in client, owner): letters plus spaces and `. , ' -`; cities/provinces
  also `( )`. Emails: optional for walk-in clients but must be valid when given.
- Required fields show a red `*` (`<Field required>` / `<RequiredMark>`).

## 7. Migrations

| Rev | What |
|---|---|
| 0001–0003 | auth, catalogue, quotations |
| 0004 | walk-in clients (`user_id` nullable, `created_by`), `rounding_step`, `owner_name` |
| 0005 | add-ons (`product_options`, `product_components.option_id`) |
| 0006 | choice groups (`product_option_groups`), size reductions |
| 0007 | several items per quotation (`quotation_items`; old quotes became one-item quotes) |
| 0008 | soft delete of quotations (`deleted_at`, `deleted_by`) |

`tests/test_migrations.py` round-trips a real quotation through 0007 to prove no data is lost.
