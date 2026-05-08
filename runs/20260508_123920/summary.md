# b_decide summary 20260508_123920

- approved: 1
- rejected: 11 (judge: 2, writer-budget: 9)

## Approved trades

- FSLY short entry=19.4 stop=20.3 target=16.5 qty=257 conv=7

## Rejections (with reasons)

- COST (judge): single_position_cap_exceeded
- NVDA (judge): single_position_cap_exceeded: stock too high-priced for current account size, cannot fit even minimum scaled position. Gate-3 quantity=71 (risk_dollars=$250 / risk_per_share=$3.50) yields notional=$15,194 (60.8% of $25k account), exceeding 15% standard cap of $3,750. Small-scaled path: extended_cap=$5,000 (20%) → M=floor(5000/214.00)=23 shares → risk_M=23 * 3.50=$80.50, which is only 32% of the $250 risk budget — below the 40% floor of $100 required. Both standard and small-scaled paths fail. Direction consensus PASSED (all 4 perspectives long). Expected return PASSED: combined_p_bull=(0.500+0.538)/2=0.519, combined_p_bear=0.481, entry=214.00 (mid of b_bull_a 213.50-214.50), target=min(222.00, 224.00)=222.00, stop=max(210.50, 210.00)=210.50, expected_return_per_share = 0.519*(222-214) - 0.481*(214-210.50) = +$2.47/share. Trade is mathematically positive but the $25k account cannot accommodate the $214 share price under capital concentration rules.
- COST (writer-budget): single_position_cap_exceeded
- NVDA (writer-budget): single_position_cap_exceeded: stock too high-priced for current account size, cannot fit even minimum scaled position. Gate-3 quantity=71 (risk_dollars=$250 / risk_per_share=$3.50) yields notional=$15,194 (60.8% of $25k account), exceeding 15% standard cap of $3,750. Small-scaled path: extended_cap=$5,000 (20%) → M=floor(5000/214.00)=23 shares → risk_M=23 * 3.50=$80.50, which is only 32% of the $250 risk budget — below the 40% floor of $100 required. Both standard and small-scaled paths fail. Direction consensus PASSED (all 4 perspectives long). Expected return PASSED: combined_p_bull=(0.500+0.538)/2=0.519, combined_p_bear=0.481, entry=214.00 (mid of b_bull_a 213.50-214.50), target=min(222.00, 224.00)=222.00, stop=max(210.50, 210.00)=210.50, expected_return_per_share = 0.519*(222-214) - 0.481*(214-210.50) = +$2.47/share. Trade is mathematically positive but the $25k account cannot accommodate the $214 share price under capital concentration rules.
- BROS (writer-budget): budget_check_failed: risk_budget_exceeded (trade_risk=$159.03 > available=$18.70)
- CRWD (writer-budget): budget_check_failed: risk_budget_exceeded (trade_risk=$114.75 > available=$18.70)
- GLW (writer-budget): budget_check_failed: risk_budget_exceeded (trade_risk=$198.25 > available=$18.70)
- GPGI (writer-budget): budget_check_failed: risk_budget_exceeded (trade_risk=$166.84 > available=$18.70)
- HWM (writer-budget): budget_check_failed: risk_budget_exceeded (trade_risk=$148.50 > available=$18.70)
- ROK (writer-budget): budget_check_failed: risk_budget_exceeded (trade_risk=$150.00 > available=$18.70)
- BIIB (writer-budget): budget_check_failed: risk_budget_exceeded (trade_risk=$101.40 > available=$18.70)
