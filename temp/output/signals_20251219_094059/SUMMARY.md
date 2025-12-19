# Signal helper exploration (proxy-based)

This folder contains raw upstream trends payloads plus computed, explainable spike/velocity signals.

## What this demonstrates
- We can compute lightweight 'regulator signals' without local ingestion.
- The value-add is ranking/flags on top of CFPB trends buckets (not changing the data).

## Files
- manifest.json: index of all scenarios
- *.raw.json: upstream responses
- *.computed.json: extracted time series + simple signals
