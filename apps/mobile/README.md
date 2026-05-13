# Mobile App Placeholder

The current implementation keeps the source-of-truth rule engine in the Python
domain package. A future Expo React Native or browser client should consume the
stable JSON payload emitted by:

```bash
symptothermal interpret --json
```

That payload contains rule pack metadata, daily statuses, cycle confirmations,
warnings, and rule traces.
