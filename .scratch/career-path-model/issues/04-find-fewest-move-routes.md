# 04 — Find fewest-move routes to a goal

**What to build:** A user supplies a profile and selects a destination job. The model finds several distinct routes from relevant starting jobs to that exact goal using the fewest job changes allowed by its move policy.

**Blocked by:** 01 — Recommend jobs from a profile; 02 — Resolve a selected or searched goal; 03 — Score a directed job move.

**Status:** ready-for-agent

- [ ] Route search can consider moves outside saved browsing suggestions and never repeats a job within one route.
- [ ] Returned routes use the minimum number of job changes for that request, with no fixed four-move limit.
- [ ] Equal-length routes are ranked and deduplicated by move quality and profile fit; unreachable goals produce an explicit no-route result.
