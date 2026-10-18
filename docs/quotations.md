# Quotations, pricing and the dashboard — detailed rules

The business rules behind AQS APP, as built (last updated 2026-10-17, pricing v2). CLAUDE.md links here;
the code is the final word: `backend/app/services/` (`pricing.py`, `options.py`,
`quotations.py`, `quotation_views.py`, `pdf.py`, `dashboard.py`).

## 1. Materials, labour and product templates (Admin → Materials / Labour rates / Products)

**Materials** are entered at the price they are **bought** at, in one of these units:

| Unit | For | Measured by (template basis) |
|---|---|---|
| per piece | handles, rollers, locks | fixed count |
| per kilo | jamb rubber, vinyl #1 | perimeter / width / height (kg per ft), area (kg per sq ft) or fixed (kg per piece) |
| per foot | tracks, trims | perimeter / width / height |
| per sq ft | glass | area |
| per **bar** | aluminium profiles (21-ft bars), 10 mm square bar (6-m bars) | a length (feet needed ÷ bar length), area (factor = bars per sq ft) or fixed (bars per piece) |

A bar material has a **bar length** (`stock_length` + `ft`/`m`); its price is for one whole bar and
templates always count **whole bars, rounded up**. **Labour rates** are per piece (e.g. per grill or
per window), per foot or per sq ft. An item's unit can't change while a template uses it. Products
are archived, never deleted; materials / labour rates can be archived, or deleted only when no
template uses them (409).

A product's **template** lines are each one material or labour rate, measured from the size typed
(in **feet / sq ft**, worked out from the exact inches):

```
quantity = measurement × factor × (1 + waste% / 100)      (4 dp)
           bars: whole bars, rounded up (32 ft of frame ÷ 21-ft bars = 1.5238 → 2 bars)
cost     = quantity × item price                          (2 dp, half-up)
```

### Options

Each line belongs to one of:

| Kind | What it is | When it is priced | Example |
|---|---|---|---|
| Always included | `option_id` NULL | always | frames, rollers, labour |
| **Choice** of a group | option with `group_id` | when that choice is picked — **exactly one per group** (first pre-selected on forms) | Glass type: 1/4 Bronze / Reflective; Glass sheet: 4 x 7 ft / 4 x 8 ft |
| **Add-on** | option without a group | only when ticked (unticked by default) | Open back (outer jamb) |

- Groups: `product_option_groups`; choices and add-ons: `product_options` (names unique per group;
  add-on names unique among add-ons). A choice may have no lines (e.g. "None", or a sheet size).
- Choices and add-ons also have a **rate per sq ft** (`rate_per_sqft`), used by per-sq-ft products.
- Offered to clients: an add-on with ≥ 1 line (or, on a per-sq-ft product, a rate > 0) and no
  archived items; a choice with no archived items. If **no** choice of a group can be offered, the
  product can't be quoted at all.
- **Size reduction** (`width_reduction_mm` / `height_reduction_mm`, 0–2000, add-ons): when chosen,
  the size typed is the **wall opening** — the add-on's own lines use it as is, every other line
  is measured that much smaller (e.g. the window inside an open back frame). Too small → 422.
- Admins edit all of this in the template editor; the price preview re-prices immediately when a
  choice or add-on changes.

## 2. Price of one item

Sizes are typed in **inches** (default) or cm. The server keeps whole **mm** (stored, checked
against the product's min/max) and prices from the **exact inches** (cm ÷ 2.54):
`area (sq ft) = width_in × height_in ÷ 144`, rounded to 2 dp.

Each product has a **pricing method**:

| Method | Price of one piece | Used for |
|---|---|---|
| **Per sq ft** (`per_sqft`) | area × (product's base rate + the rates of the chosen choices and add-ons). No markup. The template is only a **cost guide** (staff see its cost and the margin). | sliding windows (and doors) |
| **From materials** (`computed`) | Σ line costs × (1 + markup%) (Settings) | grills, anything built from parts |

```
amount = price per piece × quantity, rounded UP to the next `rounding_step` (Settings; default 100, 0 = off)
```

**Prices are final: VAT is included, never added.** Staff see the VAT inside each amount
(`amount × VAT% ÷ (100 + VAT%)`), the cost (Σ line costs × quantity) and the margin
(amount − cost). Money is `Decimal` / `NUMERIC(12,2)`, never float; half-up to centavos at each
step. Prices are computed on the server only — the client sends product, size, unit, quantity and
option ids. A per-sq-ft product with no rate at all is not offered (and refused with 422).

**Raise all rates** (Settings, staff): every product base rate and option rate × (1 + N%),
N from −50 to +100, rounded to centavos, Yes/No confirmation, one audit row
(`pricing.rates_raised`) listing each change. Quotations already made keep their prices; computed
products follow their material prices instead.

### Worked examples (also in `tests/test_pricing.py`)

- **Sliding window 48 × 48 in** = 16 sq ft; Glass type 1/4 Bronze ₱350/sq ft + Open back ₱40/sq ft
  → 16 × 390 = ₱6,240 → **₱6,300**. VAT inside: ₱675.
- **Grill 48 × 48 in**: 10 mm square bar ₱450 per 6-m bar, factor 0.2187 bars/sq ft (the line
  dialog's sample grill: 3.5 bars ÷ 16 sq ft, rounded down to 4 dp so the sample never gets an extra
  bar) → 3.4992 → **4 bars** = ₱1,800; labour ₱500 per grill; cost ₱2,300 × 1.20 = ₱2,760 →
  **₱2,800**. A 36 × 36 in grill (9 sq ft) → 1.9683 → 2 bars; 60 × 48 in (20 sq ft) → 5 bars.
- **Cost guide**: frame profile ₱1,850 per 21-ft bar, perimeter 16 ft × 2 runs = 32 ft → **2 bars**
  = ₱3,700.

### Before v2 (quotations made until 2026-10-16)

Their snapshots keep the old rules and are shown as they were: metric units (m², m), and
`unit price = cost × (1 + markup%)`, `total = net + VAT%` (VAT added on top), then rounding.
Migration 0009 converted the catalogue at the same cost: per m² → per sq ft (÷ 10.7639104),
per metre → per foot (× 0.3048).

## 3. Quotations

- **Items**: 1–20 per quotation (`quotation_items`), each with its own product, size (in/cm typed,
  stored in mm, priced in inches), quantity 1–100, choices and add-ons (max 10 option ids). An error names the item
  ("Item 2: width must be …").
- Each item's prices are frozen in `quotation_items.snapshot` (product, input, pricing breakdown,
  choices, options). The quotation's `snapshot` holds the client, plus business details frozen at
  approval. Snapshot version 6 (`SNAPSHOT_VERSION` in `services/quotations.py`; 6 = pricing v2:
  `pricing_method`, inches / sq ft, whole bars, rates, `vat_included`, `margin`).
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

- Web page and PDF: each item's product, description, choices ("Glass type: Reflective",
  "Glass sheet: 4 x 7 ft"), add-ons ("With: Open back"), size ("48 x 48 in", "16 sq ft"), quantity
  and **amount (VAT included)**; the total; the 50/50 split. Never rates, unit prices, costs,
  markup, margin or VAT — not even in the API response.
- The **PDF never lists materials/labour**. (The customer web page still shows an "Includes: …"
  list — open question in CLAUDE.md §11.)
- PDF design: app colours (Blue → Indigo gradient header and total banner), rounded cards,
  Helvetica (no ₱ glyph, so amounts read "PHP"). Ends with signature lines: **Prepared by**
  (Settings → owner name, default "Cleo David") and **Conforme** (client name + date). Drafts
  carry an `ESTIMATE · PENDING APPROVAL` watermark drawn on top of the content.
- Staff see the full per-item breakdown: method, area, rates, cost lines (bars needed → whole
  bars), markup, rounding, VAT included, cost and margin.

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
| 0009 | pricing v2: units piece/kg/ft/sqft/bar (m² and m prices converted), bar lengths, `products.pricing_method` + `rate_per_sqft`, `product_options.rate_per_sqft` |

`tests/test_migrations.py` round-trips a real quotation through 0007, and metric prices through
0009 (and back), to prove no data is lost.
