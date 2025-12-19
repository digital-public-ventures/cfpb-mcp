# Company spike pipeline (proxy-based)

This demonstrates a realistic Phase 4-style 'signal helper' that is actually a pipeline of upstream calls:
1) search (aggregations) -> top companies
2) trends per company -> time series
3) simple spike scoring -> ranked results

See 04_ranked_company_spikes.json for the main output.