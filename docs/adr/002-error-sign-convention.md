# ADR-002: Error sign = forecast − actual

**Status:** accepted

**Context.** Both sign conventions are common. The users are buyers; the costly direction is
too little wind (they under-bought and settle the gap in imbalance).

**Decision.** `e = forecast − actual`. Positive = over-forecast = buyer short. Headroom is the
upper (q90) tail of e. The convention is stated in every API response (`meta.error_sign`) and
next to every error chart.

**Consequences.** "Big positive number = risk" reads naturally on the desk. The actual band is
`[F − q90, F − q10]`, which tests pin down.
