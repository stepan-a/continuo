"""The Solution object returned by a simulation.

A :class:`Solution` is a light, framework-free container for a solved
perfect-foresight path. It glues the per-segment results into one time
grid and offers direct array access; the optional pandas / xarray
conversions are imported lazily so those packages stay optional.

Each :class:`Segment` keeps its own realised slice plus the metadata of
the regime it belongs to — the active exogenous configuration
(``info_set``) and the terminal steady state used as the jump anchor — so
downstream code can label or compare regimes (e.g. the discontinuous jump
in a control at a surprise) without re-deriving the revelation structure.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

__all__ = ["Segment", "Solution"]


@dataclass(eq=False)
class Segment:
    """One realised segment of the path and the regime it was solved under."""

    start_time: float
    times: np.ndarray
    path: np.ndarray
    names: tuple[str, ...]
    info_set: dict[str, float]
    terminal_ss: dict[str, float]
    iterations: int

    def __getitem__(self, name: str) -> np.ndarray:
        return self.path[:, self.names.index(name)]


@dataclass(eq=False)
class Solution:
    """A solved path over ``[0, T]``, glued from one or more segments."""

    segments: tuple[Segment, ...]
    names: tuple[str, ...]
    diagnostics: dict = field(default_factory=dict)
    converged: bool = True
    t: np.ndarray = field(init=False)
    path: np.ndarray = field(init=False)

    def __post_init__(self) -> None:
        # Segments hold non-overlapping realised slices, so the full grid is
        # just their concatenation (each reveal time appears exactly once).
        if self.segments:
            self.t = np.concatenate([segment.times for segment in self.segments])
            self.path = np.concatenate([segment.path for segment in self.segments], axis=0)
        else:
            self.t = np.empty(0)
            self.path = np.empty((0, len(self.names)))

    def __getitem__(self, name: str) -> np.ndarray:
        """The path of one variable over the full grid."""
        return self.path[:, self.names.index(name)]

    def __getattr__(self, name: str) -> np.ndarray:
        # Attribute alias (sol.K) for variables, when there is no real
        # attribute of that name. __getattr__ only fires on missing lookups.
        try:
            names = object.__getattribute__(self, "names")
        except AttributeError:
            raise AttributeError(name) from None
        if name in names:
            return self[name]
        raise AttributeError(name)

    def to_dataframe(self):
        """Return the path as a time-indexed :class:`pandas.DataFrame`."""
        try:
            import pandas as pd
        except ImportError as exc:
            raise ImportError(
                "Solution.to_dataframe() requires pandas; "
                "install it with `pip install continuo[pandas]` (or `[all]`)."
            ) from exc

        return pd.DataFrame(self.path, index=pd.Index(self.t, name="t"), columns=list(self.names))

    def to_xarray(self):
        """Return the path as an :class:`xarray.Dataset` over the time coordinate."""
        try:
            import xarray as xr
        except ImportError as exc:
            raise ImportError(
                "Solution.to_xarray() requires xarray; "
                "install it with `pip install continuo[xarray]` (or `[all]`)."
            ) from exc

        data = {name: ("t", self[name]) for name in self.names}
        return xr.Dataset(data, coords={"t": self.t})
