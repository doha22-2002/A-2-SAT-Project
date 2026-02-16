| Graph | n | m | Expected | Result | Correct | Degeneracy | Clauses | Fallback |
|---|---|---|---|---|---|---|---|---|
| C4 | 4 | 4 | True | True | Yes | 2 | 8 | No |
| C6 | 6 | 6 | True | True | Yes | 2 | 12 | No |
| C7 | 7 | 7 | False | False | Yes | 2 | 14 | No |
| C9 | 9 | 9 | False | False | Yes | 2 | 18 | No |
| C5 | 5 | 5 | False | False | Yes | 2 | 10 | No |
| Path P4 | 4 | 3 | True | True | Yes | 1 | 4 | No |
| Star n=6 | 6 | 5 | True | True | Yes | 1 | 20 | No |
| Triangle K3 | 3 | 3 | True | True | Yes | 2 | 0 | No |
| Clique K6 | 6 | 15 | True | True | Yes | 5 | 0 | No |
| Bipartite K3,3 | 6 | 9 | True | True | Yes | 3 | 36 | No |
| Bipartite K4,4 | 8 | 16 | True | True | Yes | 4 | 96 | No |
| House | 5 | 6 | True | True | Yes | 2 | 12 | No |
| Disconnected mix | 8 | 6 | True | True | Yes | 2 | 4 | No |
| Large sparse | 50 | 29 | ? | True | N/A | 2 | 16 | No |
| Medium dense | 10 | 36 | ? | True | N/A | 7 | 28 | No |
| Realistic sparse | 12 | 18 | ? | False | N/A | 2 | 74 | No |
| Temporal small pathlike | 3 | 2 | True | True | Yes | N/A | 4 | N/A |
| Temporal hard K6 aug | 6 | 15 | False | False | Yes | N/A | 84 | N/A |
