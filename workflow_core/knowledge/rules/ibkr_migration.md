# Constraint: IBKR Migration Compatibility

1. **Provider Agnostic**: Do NOT couple schemas to `yfinance` limitations.
2. **Future Proofing**: Design for `Tick` data and `Order Books` (Level 2 data), even if yfinance doesn't provide it.
3. **Selection**: When choosing providers, present a Pros/Cons analysis and WAIT for explicit user decision.
