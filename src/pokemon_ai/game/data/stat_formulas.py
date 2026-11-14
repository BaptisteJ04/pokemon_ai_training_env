"""Gen 1 stat formulas (same integer rounding as the game)."""

from __future__ import annotations

MAX_STAT = 999

# Stat stage multipliers as (numerator, denominator), from stage -6 to +6.
STAGE_RATIOS = (
    (25, 100), (28, 100), (33, 100), (40, 100), (50, 100), (66, 100), (1, 1),
    (15, 10), (2, 1), (25, 10), (3, 1), (35, 10), (4, 1),
)  # fmt: skip


def stat_exp_bonus(stat_exp: int) -> int:
    """Smallest root b such that b*b >= stat_exp (capped at 255), divided by 4."""
    root = 0
    while root * root < stat_exp and root < 255:
        root += 1
    return root // 4


def calc_stat(base: int, dv: int, stat_exp: int, level: int, is_hp: bool = False) -> int:
    """Stat from base stat, DV, stat experience and level (HP adds level + 10, others add 5)."""
    value = ((base + dv) * 2 + stat_exp_bonus(stat_exp)) * level // 100
    return value + (level + 10 if is_hp else 5)


def stage_stat(unmodified: int, stage: int) -> int:
    """Stat after a stage change from -6 to +6, kept between 1 and 999."""
    numerator, denominator = STAGE_RATIOS[stage + 6]
    return max(1, min(MAX_STAT, unmodified * numerator // denominator))
