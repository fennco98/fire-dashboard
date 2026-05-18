"""FIRE retirement account simulator.

Compares Traditional 401(k), Roth 401(k), Traditional IRA, and Roth IRA, plus
optional taxable brokerage and private stock, over a multi-year horizon.

All comparison accounts are fed the same pre-tax gross income devoted to
retirement — the tax timing (paid now for Roth, paid at withdrawal for
Traditional) is handled inside each function.

All functions are pure — no module state, safe to call repeatedly.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List


# ---------- Config ----------

@dataclass(frozen=True)
class SimConfig:
    """Inputs that drive a simulation run.

    All amounts are nominal dollars. Returns are nominal unless noted.
    """
    gross_devoted: float            # pre-tax $ devoted to retirement per year
    annual_growth_rate: float       # nominal annual return (e.g. 0.07)
    marginal_tax_now: float         # marginal income tax rate today
    marginal_tax_retirement: float  # assumed marginal tax rate at withdrawal
    capital_gains_rate: float       # long-term capital gains rate (e.g. 0.15)
    years: int                      # accumulation horizon

    # Current balances (year-0 state of each account)
    starting_trad_401k: float = 0.0
    starting_roth_401k: float = 0.0
    starting_trad_ira: float = 0.0
    starting_roth_ira: float = 0.0
    starting_hsa: float = 0.0

    # Taxable brokerage
    starting_taxable: float = 0.0
    taxable_annual: float = 0.0     # post-tax dollars added per year

    # Private stock / equity (no annual contributions — just growth)
    private_stock_value: float = 0.0
    private_stock_growth: float = 0.0  # user-supplied annual growth assumption

    # Account limits
    limit_401k: float = 23500.0
    limit_ira: float = 7000.0
    limit_hsa: float = 4300.0

    include_hsa: bool = False


@dataclass
class AccountResult:
    name: str
    annual_contribution: float      # employee dollars added per year
    pretax_balance: List[float]     # nominal account balance per year (length = years+1)
    effective_balance: List[float]  # what you keep after any withdrawal taxes


# ---------- Internals ----------

def _compound(annual: float, growth: float, years: int,
              starting: float = 0.0) -> List[float]:
    """End-of-year compounding; contributions land at year-end.

    Returns a list of length years+1 where index 0 is the opening balance.
    """
    path: List[float] = []
    bal = starting
    for _ in range(years + 1):
        path.append(bal)
        bal = bal * (1 + growth) + annual
    return path


# ---------- Account simulations ----------

def traditional_401k(cfg: SimConfig) -> AccountResult:
    """Pre-tax contribution, taxed as ordinary income at withdrawal."""
    contribution = min(cfg.gross_devoted, cfg.limit_401k)
    path = _compound(contribution, cfg.annual_growth_rate, cfg.years,
                     cfg.starting_trad_401k)
    effective = [b * (1 - cfg.marginal_tax_retirement) for b in path]
    return AccountResult(
        name="Traditional 401(k)",
        annual_contribution=contribution,
        pretax_balance=path,
        effective_balance=effective,
    )


def roth_401k(cfg: SimConfig) -> AccountResult:
    """Post-tax contribution; growth and withdrawals tax-free."""
    aftertax_available = cfg.gross_devoted * (1 - cfg.marginal_tax_now)
    contribution = min(aftertax_available, cfg.limit_401k)
    path = _compound(contribution, cfg.annual_growth_rate, cfg.years,
                     cfg.starting_roth_401k)
    return AccountResult(
        name="Roth 401(k)",
        annual_contribution=contribution,
        pretax_balance=path,
        effective_balance=list(path),
    )


def traditional_ira(cfg: SimConfig) -> AccountResult:
    """Deductible Traditional IRA: pre-tax contribution, taxed at withdrawal.

    Assumes deductibility (see caveats for income phase-out limits).
    """
    contribution = min(cfg.gross_devoted, cfg.limit_ira)
    path = _compound(contribution, cfg.annual_growth_rate, cfg.years,
                     cfg.starting_trad_ira)
    effective = [b * (1 - cfg.marginal_tax_retirement) for b in path]
    return AccountResult(
        name="Traditional IRA",
        annual_contribution=contribution,
        pretax_balance=path,
        effective_balance=effective,
    )


def roth_ira(cfg: SimConfig) -> AccountResult:
    """Post-tax contribution, tax-free growth and withdrawals."""
    aftertax_available = cfg.gross_devoted * (1 - cfg.marginal_tax_now)
    contribution = min(aftertax_available, cfg.limit_ira)
    path = _compound(contribution, cfg.annual_growth_rate, cfg.years,
                     cfg.starting_roth_ira)
    return AccountResult(
        name="Roth IRA",
        annual_contribution=contribution,
        pretax_balance=path,
        effective_balance=list(path),
    )


def hsa(cfg: SimConfig) -> AccountResult:
    """HSA for qualified medical: triple-tax-free. Requires HDHP."""
    contribution = min(cfg.gross_devoted, cfg.limit_hsa)
    path = _compound(contribution, cfg.annual_growth_rate, cfg.years,
                     cfg.starting_hsa)
    return AccountResult(
        name="HSA",
        annual_contribution=contribution,
        pretax_balance=path,
        effective_balance=list(path),
    )


def taxable_brokerage(cfg: SimConfig) -> AccountResult:
    """Post-tax contributions; long-term capital gains tax on growth at sale."""
    path = _compound(cfg.taxable_annual, cfg.annual_growth_rate, cfg.years,
                     cfg.starting_taxable)
    effective = []
    for year, bal in enumerate(path):
        cost_basis = cfg.starting_taxable + cfg.taxable_annual * year
        gains = max(bal - cost_basis, 0.0)
        effective.append(bal - gains * cfg.capital_gains_rate)
    return AccountResult(
        name="Taxable brokerage",
        annual_contribution=cfg.taxable_annual,
        pretax_balance=path,
        effective_balance=effective,
    )


def private_stock(cfg: SimConfig) -> AccountResult:
    """Privately held equity: grows at user-supplied rate, no new contributions.

    Effective balance applies LTCG on accrued gains, consistent with a
    liquidation event. The growth rate is the user's own assumption —
    treat it as a real (inflation-adjusted) or nominal rate as appropriate.
    """
    path = _compound(0.0, cfg.private_stock_growth, cfg.years,
                     cfg.private_stock_value)
    effective = []
    for bal in path:
        gains = max(bal - cfg.private_stock_value, 0.0)
        effective.append(bal - gains * cfg.capital_gains_rate)
    return AccountResult(
        name="Private stock",
        annual_contribution=0.0,
        pretax_balance=path,
        effective_balance=effective,
    )


# ---------- Public API ----------

ACCOUNT_NAMES = [
    "Traditional 401(k)",
    "Roth 401(k)",
    "Traditional IRA",
    "Roth IRA",
]

_ACCOUNT_FN = {
    "Traditional 401(k)": traditional_401k,
    "Roth 401(k)": roth_401k,
    "Traditional IRA": traditional_ira,
    "Roth IRA": roth_ira,
}


def run_comparison(cfg: SimConfig) -> List[AccountResult]:
    """All four tax-advantaged types — used for the comparison view.

    Starting balances from cfg are included so the projections reflect
    the user's actual situation rather than a clean-slate hypothetical.
    """
    return [fn(cfg) for fn in _ACCOUNT_FN.values()]


def run_portfolio(cfg: SimConfig, primary_account: str) -> List[AccountResult]:
    """The user's actual portfolio: one primary tax-advantaged account plus
    any taxable brokerage and private stock they have.

    Used for the progress bar and stacked area chart.
    """
    results: List[AccountResult] = [_ACCOUNT_FN[primary_account](cfg)]
    if cfg.include_hsa:
        results.append(hsa(cfg))
    if cfg.taxable_annual > 0 or cfg.starting_taxable > 0:
        results.append(taxable_brokerage(cfg))
    if cfg.private_stock_value > 0:
        results.append(private_stock(cfg))
    return results
