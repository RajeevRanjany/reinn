# ADR-003: Point-in-time selection is an invariant, not a feature

**Status:** accepted

**Context.** WINDFOR republishes ~8 times a day. Grading the newest forecast before delivery
grades a forecast the buyer never had at decision time, and understates risk.

**Decision.** Every selection takes a cutoff and may only see vintages with
`publish_time ≤ cutoff`; if none qualifies the value is missing (never fall forward). The rule is
implemented once in pandas (`core/selection.py`) and once in SQL (`DuckDBRepository`), and tests
assert that both agree. A Hypothesis property test asserts no selected vintage is ever published
after its cutoff.

**Consequences.** Slightly more complex queries; in exchange, accuracy numbers mean what a
desk thinks they mean. Bands in Decision Mode are also out-of-sample (leave-one-day-out) for the
same reason.
