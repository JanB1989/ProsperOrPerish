"""Named subsets of trade goods from resolved :class:`GoodsData` tables."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

import pandas as pd

if TYPE_CHECKING:
    from core.data.goods_data import GoodsData


@dataclass
class GoodsSubsets:
    """Read-only bundles of good slugs (index names) for analysis and notebooks.

    Standard ``method`` values match EU5 ``common/goods`` (mining, farming, hunting,
    gathering, forestry); modded goods with other methods appear only in
    :attr:`by_method`.

    :attr:`rgo` (alias :attr:`raw_material`) lists goods with ``category == raw_material``
    (RGO-style extraction goods in EU5 ``common/goods``; missing ``category`` is treated
    as ``raw_material`` per engine default).

    :attr:`with_food` uses the primary frame (merged or vanilla). :attr:`vanilla_food`
    always uses the parsed vanilla gospel table (``GoodsData.vanilla_df``) when built
    via :meth:`from_goods_data`.
    """

    all: tuple[str, ...]
    farming: tuple[str, ...]
    mining: tuple[str, ...]
    hunting: tuple[str, ...]
    gathering: tuple[str, ...]
    forestry: tuple[str, ...]
    rgo: tuple[str, ...]
    with_food: tuple[str, ...]
    vanilla_food: tuple[str, ...]
    by_method: dict[str, tuple[str, ...]]

    @property
    def raw_material(self) -> tuple[str, ...]:
        """Same slugs as :attr:`rgo` (EU5 ``category = raw_material``)."""
        return self.rgo

    @staticmethod
    def _slugs_with_positive_food(df: pd.DataFrame | None) -> tuple[str, ...]:
        """Good slugs with positive ``food`` from a resolved goods frame (vanilla gospel or modded)."""
        if df is None or df.empty or "food" not in df.columns:
            return ()
        idx = df.index.astype(str)
        food = pd.to_numeric(df["food"], errors="coerce").fillna(0.0)
        return tuple(sorted(idx[food > 0]))

    @classmethod
    def from_goods_data(
        cls, data: GoodsData, *, merged: bool = True
    ) -> GoodsSubsets:
        """Build subsets from ``modded_df`` (default) or ``vanilla_df``.

        :attr:`vanilla_food` always uses ``data.vanilla_df`` (parsed base EU5), not the merged table.
        """
        df = data.modded_df if merged else data.vanilla_df
        return cls.from_dataframe(df, vanilla_df=data.vanilla_df)

    @classmethod
    def from_dataframe(
        cls,
        df: pd.DataFrame,
        *,
        vanilla_df: pd.DataFrame | None = None,
    ) -> GoodsSubsets:
        """Build subsets from a goods frame indexed by good slug with ``method`` and ``food``.

        If ``vanilla_df`` is set (e.g. ``GoodsData.vanilla_df``), :attr:`vanilla_food` lists slugs
        with ``food > 0`` in that frame only; otherwise :attr:`vanilla_food` is empty.
        """
        vanilla_food = cls._slugs_with_positive_food(vanilla_df)

        if df.empty:
            return cls((), (), (), (), (), (), (), (), vanilla_food, {})

        idx = df.index.astype(str)
        all_names = tuple(sorted(idx))

        if "method" not in df.columns:
            raise ValueError("goods DataFrame must include a 'method' column")
        mcol = df["method"].astype(str)

        method_to_goods: dict[str, list[str]] = {}
        for name, m in zip(idx, mcol, strict=True):
            method_to_goods.setdefault(m, []).append(name)
        by_method = {
            m: tuple(sorted(names)) for m, names in sorted(method_to_goods.items())
        }

        def pick(method: str) -> tuple[str, ...]:
            return by_method.get(method, ())

        if "category" in df.columns:
            ccol = df["category"].fillna("raw_material").astype(str)
        else:
            ccol = pd.Series("raw_material", index=df.index, dtype=str)
        rgo = tuple(sorted(idx[ccol == "raw_material"]))

        if "food" in df.columns:
            food = pd.to_numeric(df["food"], errors="coerce").fillna(0.0)
            with_food = tuple(sorted(idx[food > 0]))
        else:
            with_food = ()

        return cls(
            all=all_names,
            farming=pick("farming"),
            mining=pick("mining"),
            hunting=pick("hunting"),
            gathering=pick("gathering"),
            forestry=pick("forestry"),
            rgo=rgo,
            with_food=with_food,
            vanilla_food=vanilla_food,
            by_method=by_method,
        )
