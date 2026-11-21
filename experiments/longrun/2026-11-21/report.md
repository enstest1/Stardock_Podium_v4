# Long-run canon stress test (2026-11-21)

Stub writer, 300 episodes, per-episode volume {'events': 22, 'beliefs': 74, 'promises': 11, 'state_changes': 4, 'relationships': 4} (matches the showcase). Latency is measured on this laptop's CPU.

| Ep | Ledger KB | Brief ms | Brief tokens | Omniscience ms | Char state ms | Index ms | Unpaid season/series | Ep-1 recall | Anchor | Ep-1 promise |
|---|---|---|---|---|---|---|---|---|---|---|
| 1 | 54 | 6.5 | 672 | 2.4 | 0.2 | 27.7 | 6 | 22/22 | True | open |
| 25 | 1384 | 72.7 | 970 | 38.7 | 0.8 | 96.3 | 125 | 22/22 | True | open |
| 50 | 2766 | 119.7 | 994 | 49.2 | 0.8 | 134.6 | 260 | 22/22 | True | open |
| 75 | 4152 | 347.6 | 1008 | 245.3 | 4.9 | 308.9 | 392 | 22/22 | True | open |
| 100 | 5531 | 211.2 | 1006 | 95.7 | 1.2 | 203.0 | 539 | 22/22 | True | open |
| 125 | 6920 | 236.0 | 1019 | 186.2 | 1.5 | 221.3 | 672 | 22/22 | True | open |
| 150 | 8312 | 373.5 | 1017 | 316.9 | 1.1 | 397.7 | 799 | 22/22 | True | paid |
| 175 | 9695 | 557.3 | 1013 | 423.6 | 3.1 | 664.8 | 949 | 22/22 | True | paid |
| 200 | 11081 | 723.2 | 1022 | 378.6 | 3.2 | 361.6 | 1089 | 22/22 | True | paid |
| 225 | 12468 | 759.5 | 1012 | 484.3 | 3.7 | 507.7 | 1224 | 22/22 | True | paid |
| 250 | 13858 | 912.3 | 1016 | 488.2 | 2.4 | 424.1 | 1356 | 22/22 | True | paid |
| 275 | 15241 | 1235.9 | 1014 | 601.6 | 3.4 | 775.8 | 1495 | 22/22 | True | paid |
| 300 | 16628 | 1157.5 | 1017 | 449.8 | 3.6 | 761.2 | 1639 | 22/22 | True | paid |
