# Ranking evaluation

Catalog: 33,670 products · 32 rule-labelled queries (`eval/queries.json`) · k = 10 · embedding model: sentence-transformers/all-MiniLM-L6-v2

Labels are silver-standard regex rules on product name and price, written independently of the
engine's intent patterns. They check that results are the right kind of product within budget.

| System | precision@10 | ndcg@10 | mrr | hit_rate | over_budget_results | p50_ms | p95_ms |
|---|---|---|---|---|---|---|---|
| dense-only | 0.875 | 0.953 | 0.954 | 1.000 | 8 | 51 | 71 |
| lexical | 0.881 | 0.941 | 0.896 | 1.000 | 0 | 21 | 93 |
| hybrid | 0.969 | 0.996 | 1.000 | 1.000 | 0 | 41 | 107 |

## Per-query precision@10

| Query | Profile | dense-only | lexical | hybrid |
|---|---|---|---|---|
| laptop for AI under 90k | ai_student | 0.9 | 1.0 | 1.0 |
| gaming laptop | gaming | 0.9 | 0.9 | 1.0 |
| wireless earbuds under 2000 | general | 0.5 | 0.4 | 1.0 |
| noise cancelling headphones | general | 0.9 | 0.9 | 0.9 |
| bluetooth speaker | general | 1.0 | 1.0 | 1.0 |
| 43 inch smart tv | general | 1.0 | 1.0 | 1.0 |
| smartphone under 15000 | general | 0.4 | 1.0 | 0.9 |
| gaming mouse | gaming | 1.0 | 1.0 | 1.0 |
| mechanical keyboard | general | 0.9 | 1.0 | 1.0 |
| running shoes for men | general | 0.8 | 0.8 | 1.0 |
| women sandals | general | 1.0 | 0.7 | 1.0 |
| cotton kurti under 800 | general | 1.0 | 1.0 | 1.0 |
| men's formal shirt | general | 1.0 | 1.0 | 1.0 |
| polo t-shirt | general | 1.0 | 0.9 | 1.0 |
| saree for wedding | general | 1.0 | 1.0 | 1.0 |
| pressure cooker 5 litre | general | 0.9 | 0.7 | 1.0 |
| mixer grinder | general | 0.7 | 0.7 | 1.0 |
| 1.5 ton split ac | general | 0.9 | 1.0 | 1.0 |
| double door refrigerator | general | 1.0 | 1.0 | 1.0 |
| front load washing machine | general | 0.9 | 0.9 | 1.0 |
| smartwatch with calling | general | 1.0 | 1.0 | 1.0 |
| power bank 20000mah | general | 1.0 | 1.0 | 1.0 |
| trimmer for men | general | 1.0 | 0.9 | 0.9 |
| school backpack | student | 1.0 | 1.0 | 1.0 |
| yoga mat | general | 1.0 | 1.0 | 1.0 |
| dslr camera | general | 0.6 | 1.0 | 1.0 |
| wifi router | general | 0.8 | 1.0 | 1.0 |
| something to keep my tea hot | general | 0.2 | 0.5 | 0.5 |
| shoes for jogging | general | 0.9 | 0.5 | 1.0 |
| earphones for the gym | general | 0.8 | 1.0 | 1.0 |
| gift for a coffee lover | general | 1.0 | 0.4 | 0.8 |
| watch for men under 2000 | general | 1.0 | 1.0 | 1.0 |
