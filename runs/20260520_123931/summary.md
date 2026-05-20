# b_decide summary 20260520_123931

- approved: 1
- rejected: 12 (judge: 3, writer-budget: 9)

## Approved trades

- ALAB buy entry=256.0 stop=248.0 target=278.0 qty=19 conv=6

## Rejections (with reasons)

- CPAY (judge): single_position_cap_exceeded
- CVX (judge): single_position_cap_exceeded: stock too high-priced for current account size, cannot fit even minimum scaled position. Gate 2 expected_return_per_share = 0.5*(205.00-196.77) - 0.5*(196.77-193.50) = +$2.48 (POSITIVE, passes). Gate 3 quantity = floor($250 risk / $3.27 risk_per_share) = 76 shares. Gate 4: notional = 196.77 * 76 = $14,955 >> $3,750 (15% cap). Small-scaled path: M = floor($5,000 / $196.77) = 25 shares; risk_M = 25 * $3.27 = $81.75; risk_dollars_floor = 0.40 * $250 = $100. risk_M ($81.75) < floor ($100) — small-scaled path fails the 40%-of-risk-budget minimum. Even at extended 20% notional cap, a $196.77 stock with a tight $3.27 stop cannot use enough risk budget to be meaningful on a $25k account.
- LAMR (judge): single_position_cap_exceeded: stock too high-priced for current account size, cannot fit even minimum scaled position. Gate 3 quantity=floor(250/2.975)=84 at entry $150.375 → notional $12,631.50 exceeds 15% cap ($3,750). Small-scaled path: M=floor(5000/150.375)=33 shares → notional $4,962 fits 20% extended cap, but risk_M = 33 × 2.975 = $98.18 falls below 40%-of-risk-budget floor ($100). Single-share entry uses only ~39% of risk budget — fails small_scaled floor by $1.83. Direction consensus PASS, Gate 1 budget PASS, Gate 2 expected return PASS (+$1.575/share with combined_p_bull=0.5), but discrete-share constraint at $150 price point on a $25k account with $2.975 risk-per-share means no valid quantity satisfies both caps simultaneously.
- CPAY (writer-budget): single_position_cap_exceeded
- CVX (writer-budget): single_position_cap_exceeded: stock too high-priced for current account size, cannot fit even minimum scaled position. Gate 2 expected_return_per_share = 0.5*(205.00-196.77) - 0.5*(196.77-193.50) = +$2.48 (POSITIVE, passes). Gate 3 quantity = floor($250 risk / $3.27 risk_per_share) = 76 shares. Gate 4: notional = 196.77 * 76 = $14,955 >> $3,750 (15% cap). Small-scaled path: M = floor($5,000 / $196.77) = 25 shares; risk_M = 25 * $3.27 = $81.75; risk_dollars_floor = 0.40 * $250 = $100. risk_M ($81.75) < floor ($100) — small-scaled path fails the 40%-of-risk-budget minimum. Even at extended 20% notional cap, a $196.77 stock with a tight $3.27 stop cannot use enough risk budget to be meaningful on a $25k account.
- LAMR (writer-budget): single_position_cap_exceeded: stock too high-priced for current account size, cannot fit even minimum scaled position. Gate 3 quantity=floor(250/2.975)=84 at entry $150.375 → notional $12,631.50 exceeds 15% cap ($3,750). Small-scaled path: M=floor(5000/150.375)=33 shares → notional $4,962 fits 20% extended cap, but risk_M = 33 × 2.975 = $98.18 falls below 40%-of-risk-budget floor ($100). Single-share entry uses only ~39% of risk budget — fails small_scaled floor by $1.83. Direction consensus PASS, Gate 1 budget PASS, Gate 2 expected return PASS (+$1.575/share with combined_p_bull=0.5), but discrete-share constraint at $150 price point on a $25k account with $2.975 risk-per-share means no valid quantity satisfies both caps simultaneously.
- ARM (writer-budget): budget_check_failed: risk_budget_exceeded (trade_risk=$164.85 > available=$98.00)
- RVMD (writer-budget): budget_check_failed: risk_budget_exceeded (trade_risk=$132.00 > available=$98.00)
- ALL (writer-budget): budget_check_failed: risk_budget_exceeded (trade_risk=$111.32 > available=$98.00)
- BILI (writer-budget): budget_check_failed: risk_budget_exceeded (trade_risk=$249.40 > available=$98.00)
- CAI (writer-budget): budget_check_failed: risk_budget_exceeded (trade_risk=$177.45 > available=$98.00)
- HSAI (writer-budget): budget_check_failed: risk_budget_exceeded (trade_risk=$248.97 > available=$98.00)
