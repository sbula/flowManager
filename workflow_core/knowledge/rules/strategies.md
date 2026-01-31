# Protocol: Strategy Implementation (Traditional & ML)

1. **Standardization**: Strategies must implement the `strategies.base.Strategy` interface.
2. **Bundles**: "Trained Models" are artifacts. They must be versioned and loaded via the `Manifest` system.
3. **Verification**: strategies must be verifiable in isolation using `scripts/verify_strategy.py`.
