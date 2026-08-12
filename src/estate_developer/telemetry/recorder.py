
"""
V2.14.2 Deferred transaction recorder.

Important timing model:

    observation[t]
        ↓
    action[t]
        ↓
    environment processes action
        ↓
    observation[t+1]

Therefore SELL revenue cannot be known from observation[t]
alone. We keep a pending transaction and resolve it when
the next observation reveals the resulting cash balance.
"""

from __future__ import annotations

from estate_developer.telemetry.events import (
    EventType,
    FarmEvent,
)


class EventRecorder:

    def __init__(self) -> None:

        self.events = []

        self.previous_money = None

        # Orders issued on the previous turn whose financial
        # result becomes visible in the current observation.
        self.pending_sales = []

        self.pending_seed_spend = 0.0

    # ========================================================
    # HELPERS
    # ========================================================

    @staticmethod
    def _farmer_position(obs):

        p = obs["farms"][0]["farmer"]

        return (
            int(p[0]),
            int(p[1]),
        )

    @staticmethod
    def _tile_at(
        obs,
        x: int,
        y: int,
    ):

        tiles = obs["farms"][0]["tiles"]

        if y < 0 or y >= len(tiles):
            return None

        if x < 0 or x >= len(tiles[y]):
            return None

        return tiles[y][x]

    @classmethod
    def _crop_at_farmer(
        cls,
        obs,
    ):

        x, y = cls._farmer_position(obs)

        tile = cls._tile_at(
            obs,
            x,
            y,
        )

        if (
            isinstance(tile, dict)
            and tile.get("kind") == "PLANT"
        ):
            return tile.get("crop")

        return None

    @staticmethod
    def _seed_cost(
        crop: str,
        quantity: int,
    ) -> float:

        from estate_developer.economics.crops import (
            CROP_PROFILES,
        )

        profile = CROP_PROFILES.get(crop)

        if profile is None:
            return 0.0

        return (
            float(profile.seed_cost)
            * quantity
        )

    # ========================================================
    # RESOLVE FINANCIAL RESULT OF PREVIOUS ACTION
    # ========================================================

    def _resolve_previous_transaction(
        self,
        obs,
    ) -> None:

        current_money = float(
            obs["farms"][0]["money"]
        )

        if self.previous_money is None:
            return

        money_delta = (
            current_money
            - self.previous_money
        )

        # ----------------------------------------------------
        # If the previous action contained SELL:
        #
        # realized sale revenue =
        #     cash delta
        #     + seed spend from same action
        #
        # because seed purchases reduce cash in the same turn.
        # ----------------------------------------------------

        if self.pending_sales:

            total_sale_revenue = (
                money_delta
                + self.pending_seed_spend
            )

            # Current V2.12 action generation produces at most
            # one SELL per crop cycle. If multiple sales ever
            # appear on the same action, split proportionally
            # by quantity rather than silently misattributing.
            total_quantity = sum(
                sale["quantity"]
                for sale in self.pending_sales
            )

            for sale in self.pending_sales:

                quantity = sale["quantity"]

                if total_quantity > 0:

                    share = (
                        quantity
                        / total_quantity
                    )

                else:
                    share = 0.0

                gross_revenue = (
                    total_sale_revenue
                    * share
                )

                avg_price = (
                    gross_revenue / quantity
                    if quantity > 0
                    else 0.0
                )

                self.events.append(
                    FarmEvent(
                        step=sale["step"],
                        day=sale["day"],
                        hour=sale["hour"],
                        event_type=EventType.SELL,
                        crop=sale["crop"],
                        quantity=quantity,
                        unit_price=avg_price,
                        gross_revenue=gross_revenue,
                        market_inventory_before=(
                            sale[
                                "market_inventory_before"
                            ]
                        ),
                        market_inventory_after=(
                            sale[
                                "market_inventory_after"
                            ]
                        ),
                        details=(
                            "revenue resolved from "
                            "next observation cash delta"
                        ),
                    )
                )

        self.pending_sales = []

        self.pending_seed_spend = 0.0

    # ========================================================
    # RECORD CURRENT ACTION
    # ========================================================

    def record_action(
        self,
        obs: dict,
        action: dict,
    ) -> None:

        # First resolve the financial result of the previous
        # action using the current observation.
        self._resolve_previous_transaction(
            obs
        )

        step = int(obs["step"])
        day = int(obs["day"])
        hour = int(obs["hour"])

        farmer = action.get(
            "farmer",
            [],
        )

        market = action.get(
            "market",
            [],
        )

        current_money = float(
            obs["farms"][0]["money"]
        )

        current_seed_spend = 0.0

        current_sales = []

        # ====================================================
        # FARMER ACTIONS
        # ====================================================

        if farmer:

            op = farmer[0]

            if op == "PLANT":

                crop = (
                    farmer[1]
                    if len(farmer) > 1
                    else None
                )

                self.events.append(
                    FarmEvent(
                        step=step,
                        day=day,
                        hour=hour,
                        event_type=EventType.PLANT,
                        crop=crop,
                        quantity=1,
                        position=self._farmer_position(
                            obs
                        ),
                    )
                )

            elif op == "WATER":

                crop = self._crop_at_farmer(
                    obs
                )

                self.events.append(
                    FarmEvent(
                        step=step,
                        day=day,
                        hour=hour,
                        event_type=EventType.WATER,
                        crop=crop,
                        quantity=1,
                        position=self._farmer_position(
                            obs
                        ),
                    )
                )

            elif op == "HARVEST":

                crop = self._crop_at_farmer(
                    obs
                )

                self.events.append(
                    FarmEvent(
                        step=step,
                        day=day,
                        hour=hour,
                        event_type=EventType.HARVEST,
                        crop=crop,
                        quantity=1,
                        position=self._farmer_position(
                            obs
                        ),
                    )
                )

            elif op == "PLACE":

                crop = (
                    farmer[1]
                    if len(farmer) > 1
                    else None
                )

                quantity = (
                    int(farmer[2])
                    if len(farmer) > 2
                    else 0
                )

                self.events.append(
                    FarmEvent(
                        step=step,
                        day=day,
                        hour=hour,
                        event_type=EventType.PLACE,
                        crop=crop,
                        quantity=quantity,
                        position=self._farmer_position(
                            obs
                        ),
                    )
                )

        # ====================================================
        # MARKET ACTIONS
        # ====================================================

        for order in market:

            if not order:
                continue

            op = order[0]

            # ------------------------------------------------
            # BUY_SEED
            # ------------------------------------------------

            if op == "BUY_SEED":

                crop = (
                    order[1]
                    if len(order) > 1
                    else None
                )

                quantity = (
                    int(order[2])
                    if len(order) > 2
                    else 0
                )

                spend = self._seed_cost(
                    crop,
                    quantity,
                )

                current_seed_spend += spend

                self.events.append(
                    FarmEvent(
                        step=step,
                        day=day,
                        hour=hour,
                        event_type=EventType.BUY_SEED,
                        crop=crop,
                        quantity=quantity,
                    )
                )

            # ------------------------------------------------
            # BUY_PRODUCT
            # ------------------------------------------------

            elif op == "BUY_PRODUCT":

                crop = (
                    order[1]
                    if len(order) > 1
                    else None
                )

                quantity = (
                    int(order[2])
                    if len(order) > 2
                    else 0
                )

                self.events.append(
                    FarmEvent(
                        step=step,
                        day=day,
                        hour=hour,
                        event_type=EventType.BUY_PRODUCT,
                        crop=crop,
                        quantity=quantity,
                    )
                )

            # ------------------------------------------------
            # SELL
            # ------------------------------------------------

            elif op == "SELL":

                crop = (
                    order[1]
                    if len(order) > 1
                    else None
                )

                quantity = (
                    int(order[2])
                    if len(order) > 2
                    else 0
                )

                market_inventory = int(
                    obs["market"]["inventory"].get(
                        crop,
                        0,
                    )
                )

                current_sales.append({
                    "step": step,
                    "day": day,
                    "hour": hour,
                    "crop": crop,
                    "quantity": quantity,
                    "market_inventory_before": (
                        market_inventory
                    ),
                    "market_inventory_after": (
                        market_inventory
                        + quantity
                    ),
                })

        # ----------------------------------------------------
        # Defer transaction resolution until next observation.
        # ----------------------------------------------------

        self.pending_sales = current_sales

        self.pending_seed_spend = (
            current_seed_spend
        )

        # ----------------------------------------------------
        # Raw money-change event for observability.
        # ----------------------------------------------------

        if self.previous_money is not None:

            delta = (
                current_money
                - self.previous_money
            )

            if abs(delta) > 1e-9:

                self.events.append(
                    FarmEvent(
                        step=step,
                        day=day,
                        hour=hour,
                        event_type=EventType.MONEY_CHANGE,
                        money_delta=delta,
                    )
                )

        self.previous_money = current_money

    # ========================================================
    # FLUSH
    # ========================================================

    def finalize(
        self,
        final_obs: dict | None = None,
    ) -> None:
        """
        Resolve the final pending transaction.

        If final_obs is supplied, its money value is used.
        """

        if final_obs is not None:

            self._resolve_previous_transaction(
                final_obs
            )

    # ========================================================
    # ACCESS
    # ========================================================

    def get_events(self):

        return list(
            self.events
        )

    def clear(self):

        self.events.clear()

        self.previous_money = None

        self.pending_sales = []

        self.pending_seed_spend = 0.0
