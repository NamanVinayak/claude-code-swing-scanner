# b_decide summary 20260505_213533

- approved: 3
- rejected: 1

## Approved trades

- (none)

## Rejections (with reasons)

- NBIS: fire_cap_3_exceeded
- TSM: budget_check_failed: risk_budget_exceeded (trade_risk=$126.00 > available=$125.00); single_position_cap_exceeded (notional=$4860.00 > cap=$3750.00)
- ALL: budget_check_failed: single_position_cap_exceeded (notional=$4490.00 > cap=$3750.00)
- COST: budget_check_failed: single_position_cap_exceeded (notional=$4065.00 > cap=$3750.00)

## Notes

- Scheduled fire `decide_power` ran late at 14:37 PT (scheduled 11:30 PT); markets already closed.
- Stage 2 watchlist sourced from morning premarket run 20260505_053944 (TSM, ALL, COST, NBIS — all long breakouts).
- All 4 judges approved long trades in adversarial debate, but defensive `trade_passes_budget_checks` rejected them on `single_position_cap_exceeded` (15% strict cap vs judge's 20% small_scaled exception). Same blocker hit the 7 AM b_decide_open run.
- NBIS dropped earlier by fire_cap_3_exceeded (4 approvals → 3-trade hard cap, conviction tied at 6).
- Architectural mismatch: judge prompts allow extended (20%) notional cap on small_scaled positions, but `budget_calculator.trade_passes_budget_checks` enforces only the 15% standard cap — needs reconciliation before this account size can take swing positions on stocks priced > ~$200.
