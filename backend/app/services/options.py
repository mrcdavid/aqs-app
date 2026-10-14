"""Product options: add-ons (tick or not) and choose-one groups (e.g. Glass type).

Rules shared by the customer catalogue, quotations and the admin price preview:
  - An add-on is offered when it has at least one line and none of its items is archived.
  - A choice is offered when none of its items is archived (it may have no lines, e.g. "None").
  - A group with choices needs exactly one of them; if none can be offered, the product can't be
    quoted at all (the window would be missing its glass).
  - Chosen options with a size reduction (e.g. an open back frame) make every *other* line be
    measured smaller; their own lines use the size typed (the wall opening).
"""

import uuid
from collections import defaultdict
from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Any

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import LaborRate, Material, ProductComponent, ProductOption, ProductOptionGroup
from app.services.catalog import to_component_input
from app.services.pricing import ComponentInput

OPTION_NOT_AVAILABLE = HTTPException(
    status.HTTP_422_UNPROCESSABLE_CONTENT, "This option is not available"
)

Lines = list[tuple[ProductComponent, Material | LaborRate]]


async def load_groups(db: AsyncSession, product_id: uuid.UUID) -> list[ProductOptionGroup]:
    """A product's choose-one groups, in display order."""
    return list(
        await db.scalars(
            select(ProductOptionGroup)
            .where(ProductOptionGroup.product_id == product_id)
            .order_by(ProductOptionGroup.sort_order, ProductOptionGroup.name)
        )
    )


@dataclass
class Offer:
    """What can be chosen for one product."""

    add_ons: list[ProductOption] = field(default_factory=list)
    groups: list[tuple[ProductOptionGroup, list[ProductOption]]] = field(default_factory=list)
    complete: bool = True  # False: a group has choices but none can be offered


def offer(
    components: Lines, groups: Sequence[ProductOptionGroup], options: Sequence[ProductOption]
) -> Offer:
    items_by_option: dict[uuid.UUID, list[Material | LaborRate]] = defaultdict(list)
    for component, item in components:
        if component.option_id is not None:
            items_by_option[component.option_id].append(item)

    def usable(option: ProductOption) -> bool:
        items = items_by_option[option.id]
        has_lines = bool(items) or option.group_id is not None
        return has_lines and all(item.is_active for item in items)

    result = Offer(add_ons=[o for o in options if o.group_id is None and usable(o)])
    for group in groups:
        choices = [o for o in options if o.group_id == group.id]
        if not choices:
            continue  # an empty group asks nothing
        offered = [o for o in choices if usable(o)]
        if offered:
            result.groups.append((group, offered))
        else:
            result.complete = False
    return result


@dataclass(frozen=True)
class Picked:
    """The options chosen for one quotation, in display order."""

    choices: list[tuple[ProductOptionGroup, ProductOption]]
    add_ons: list[ProductOption]

    @property
    def options(self) -> list[ProductOption]:
        return [o for _, o in self.choices] + self.add_ons

    def snapshot(self) -> dict[str, Any]:
        return {
            "choices": [
                {"group": g.name, "name": o.name, "description": o.description}
                for g, o in self.choices
            ],
            "options": [{"name": o.name, "description": o.description} for o in self.add_ons],
        }


def pick(
    groups: Sequence[ProductOptionGroup],
    options: Sequence[ProductOption],
    option_ids: Sequence[uuid.UUID],
) -> Picked:
    """Check the chosen ids belong to this product and that each group has exactly one choice."""
    by_id = {o.id: o for o in options}
    if any(option_id not in by_id for option_id in option_ids):
        raise OPTION_NOT_AVAILABLE
    chosen = [by_id[option_id] for option_id in option_ids]

    choices: list[tuple[ProductOptionGroup, ProductOption]] = []
    for group in groups:
        in_group = [o for o in chosen if o.group_id == group.id]
        if not any(o.group_id == group.id for o in options):
            continue
        if len(in_group) != 1:
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_CONTENT, f"Choose one option for {group.name}"
            )
        choices.append((group, in_group[0]))
    add_ons = sorted(
        (o for o in chosen if o.group_id is None), key=lambda o: (o.sort_order, o.name)
    )
    return Picked(choices=choices, add_ons=add_ons)


def priced_lines(components: Lines, picked: Picked) -> list[ComponentInput]:
    """Always-included lines plus the chosen options' lines, each measured at the right size."""
    chosen = {o.id: o for o in picked.options}
    total_w = sum(o.width_reduction_mm for o in chosen.values())
    total_h = sum(o.height_reduction_mm for o in chosen.values())
    result = []
    for component, item in components:
        own = chosen.get(component.option_id) if component.option_id else None
        if component.option_id is not None and own is None:
            continue  # an option that wasn't chosen
        result.append(
            to_component_input(
                component,
                item,
                own.name if own else "",
                width_reduction_mm=total_w - (own.width_reduction_mm if own else 0),
                height_reduction_mm=total_h - (own.height_reduction_mm if own else 0),
            )
        )
    return result
