"""FIRE retirement account simulator.

Portfolio view: gross income devoted to retirement is auto-allocated across
accounts in tax-efficiency order —
  1. Traditional 401(k) (pre-tax, reduces taxable income today)
  2. HSA if enabled (triple-tax-free)
  3. Roth IRA (tax-free growth; funded from remaining after-tax dollars)
  4. Taxable brokerage (overflow)

Comparison view: all four tax-advantaged account types are projected
independently from the same gross input for side-by-side evaluation.

All functions are pure — no module state, safe to call repeatedly.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Tuple


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
    starting_taxable: float = 0.0

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
    annual_contribution: float      # dollars added per year (post-tax for Roth/taxable)
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


# ---------- Allocation ----------

def allocate(cfg: SimConfig) -> Dict[str, float]:
    """Distribute gross_devoted across accounts in tax-efficiency order.

    Returns a dict of annual contribution amounts:
      trad_401k  — pre-tax dollars going into the 401(k)
      hsa        — pre-tax dollars going into the HSA (0 if not enabled)
      roth_ira   — post-tax dollars going into the Roth IRA
      taxable    — post-tax dollars going to the taxable brokerage (overflow)
    """
    remaining_gross = cfg.gross_devoted

    # 1. Traditional 401(k): pre-tax, capped at employee limit
    trad_401k = min(remaining_gross, cfg.limit_401k)
    remaining_gross -= trad_401k

    # 2. HSA: pre-tax, triple-tax-free (only if enabled)
    hsa_contrib = 0.0
    if cfg.include_hsa:
        hsa_contrib = min(remaining_gross, cfg.limit_hsa)
        remaining_gross -= hsa_contrib

    # 3. Roth IRA: funded from remaining pre-tax budget converted to after-tax
    after_tax_remaining = remaining_gross * (1 - cfg.marginal_tax_now)
    roth_ira = min(after_tax_remaining, cfg.limit_ira)
    after_tax_remaining -= roth_ira

    # 4. Taxable brokerage: whatever after-tax dollars are left
    taxable = after_tax_remaining

    return {
        "trad_401k": trad_401k,
        "hsa": hsa_contrib,
        "roth_ira": roth_ira,
        "taxable": taxable,
    }


# ---------- Individual account simulations ----------

def traditional_401k(cfg: SimConfig, annual_override: float | None = None) -> AccountResult:
    """Pre-tax contribution, taxed as ordinary income at withdrawal."""
    contribution = annual_override if annual_override is not None else min(cfg.gross_devoted, cfg.limit_401k)
    path = _compound(contribution, cfg.annual_growth_rate, cfg.years, cfg.starting_trad_401k)
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
    path = _compound(contribution, cfg.annual_growth_rate, cfg.years, cfg.starting_roth_401k)
    return AccountResult(
        name="Roth 401(k)",
        annual_contribution=contribution,
        pretax_balance=path,
        effective_balance=list(path),
    )


def traditional_ira(cfg: SimConfig) -> AccountResult:
    """Deductible Traditional IRA: pre-tax contribution, taxed at withdrawal."""
    contribution = min(cfg.gross_devoted, cfg.limit_ira)
    path = _compound(contribution, cfg.annual_growth_rate, cfg.years, cfg.starting_trad_ira)
    effective = [b * (1 - cfg.marginal_tax_retirement) for b in path]
    return AccountResult(
        name="Traditional IRA",
        annual_contribution=contribution,
        pretax_balance=path,
        effective_balance=effective,
    )


def roth_ira(cfg: SimConfig, annual_override: float | None = None) -> AccountResult:
    """Post-tax contribution, tax-free growth and withdrawals."""
    if annual_override is not None:
        contribution = annual_override
    else:
        aftertax_available = cfg.gross_devoted * (1 - cfg.marginal_tax_now)
        contribution = min(aftertax_available, cfg.limit_ira)
    path = _compound(contribution, cfg.annual_growth_rate, cfg.years, cfg.starting_roth_ira)
    return AccountResult(
        name="Roth IRA",
        annual_contribution=contribution,
        pretax_balance=path,
        effective_balance=list(path),
    )


def hsa(cfg: SimConfig, annual_override: float | None = None) -> AccountResult:
    """HSA for qualified medical expenses: triple-tax-free. Requires HDHP."""
    contribution = annual_override if annual_override is not None else min(cfg.gross_devoted, cfg.limit_hsa)
    path = _compound(contribution, cfg.annual_growth_rate, cfg.years, cfg.starting_hsa)
    return AccountResult(
        name="HSA",
        annual_contribution=contribution,
        pretax_balance=path,
        effective_balance=list(path),
    )


def taxable_brokerage(cfg: SimConfig, annual_override: float | None = None) -> AccountResult:
    """Post-tax contributions; LTCG applied to all gains at withdrawal."""
    annual = annual_override if annual_override is not None else 0.0
    path = _compound(annual, cfg.annual_growth_rate, cfg.years, cfg.starting_taxable)
    effective = []
    for year, bal in enumerate(path):
        cost_basis = cfg.starting_taxable + annual * year
        gains = max(bal - cost_basis, 0.0)
        effective.append(bal - gains * cfg.capital_gains_rate)
    return AccountResult(
        name="Taxable brokerage",
        annual_contribution=annual,
        pretax_balance=path,
        effective_balance=effective,
    )


def private_stock(cfg: SimConfig) -> AccountResult:
    """Privately held equity: grows at user-supplied rate, no new contributions.

    Effective balance applies LTCG on accrued gains at a future liquidity event.
    """
    path = _compound(0.0, cfg.private_stock_growth, cfg.years, cfg.private_stock_value)
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

def run_portfolio_auto(cfg: SimConfig) -> Tuple[List[AccountResult], Dict[str, float]]:
    """Auto-allocate gross_devoted in tax-efficiency order and return portfolio results.

    Returns (results, allocation) where allocation is the dict from allocate().
    """
    alloc = allocate(cfg)
    results: List[AccountResult] = []

    # Traditional 401(k)
    if alloc["trad_401k"] > 0 or cfg.starting_trad_401k > 0:
        results.append(traditional_401k(cfg, annual_override=alloc["trad_401k"]))

    # HSA
    if cfg.include_hsa and (alloc["hsa"] > 0 or cfg.starting_hsa > 0):
        results.append(hsa(cfg, annual_override=alloc["hsa"]))

    # Roth IRA
    if alloc["roth_ira"] > 0 or cfg.starting_roth_ira > 0:
        results.append(roth_ira(cfg, annual_override=alloc["roth_ira"]))

    # Taxable brokerage (overflow)
    if alloc["taxable"] > 0 or cfg.starting_taxable > 0:
        results.append(taxable_brokerage(cfg, annual_override=alloc["taxable"]))

    # Private stock
    if cfg.private_stock_value > 0:
        results.append(private_stock(cfg))

    return results, alloc


_COMPARISON_FNS = {
    "Traditional 401(k)": traditional_401k,
    "Roth 401(k)": roth_401k,
    "Traditional IRA": traditional_ira,
    "Roth IRA": roth_ira,
}


def run_comparison(cfg: SimConfig) -> List[AccountResult]:
    """Project all four tax-advantaged types independently for side-by-side comparison.

    Each account receives the full gross_devoted as if it were the only account,
    for a fair apples-to-apples view. Starting balances are included so projections
    reflect the user's actual situation.
    """
    return [fn(cfg) for fn in _COMPARISON_FNS.values()]
