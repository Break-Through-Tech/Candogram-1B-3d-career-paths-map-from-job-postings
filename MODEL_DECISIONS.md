# Modeling decisions

Add a dated entry when a new modeling problem leads to a consequential choice. Record the problem, the chosen approach, the rejected alternative, and what would change the choice. Keep implementation steps in [MODEL_PLAN.md](MODEL_PLAN.md).

## 2026-09-28 — Find the fewest job changes to a selected goal

- **Problem:** A user may click a goal outside their nearby-job suggestions and ask for several paths from their current position.
- **Decision:** Treat the clicked job ID as the endpoint. Search directed job moves with breadth-first or bidirectional breadth-first search to find the minimum number of job changes. Rank and diversify the paths that use that minimum. Do not set a fixed four-move limit.
- **Instead of:** Restricting search to browsing suggestions, using 3D distance as a move rule, or using weighted K-shortest paths when the first objective is the fewest moves.
- **Revisit when:** User research changes the primary objective from minimum moves to minimum effort, or measured search performance calls for another algorithm. Move quality still controls which directed edges the search may use.
