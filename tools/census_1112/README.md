# Census scripts of 2026-11-12 (kept from the session scratchpad)

Diagnostics behind the figures in docs/cpu-moonshots-20-1112.md (the moonshot agent's: insn_class_census.py,
callers_of.py, cat_samples.py, insn_ops.py, busy_callers.py, insn_cards.py) and docs/calling-convention-plan.md /
docs/handoff/batch_cc2 (vec_abi_census.py: vector argument / result registers; abi_after_call_census.py: volatile reads
after calls; saved_use_census.py: incoming saved registers used; cc3_2_census.py / cc3_2b_census.py: garbage argument
registers; ctx_where.py: where the ctx accesses sit; profdiff.py: per-function sample diff of two profiles; hotins.py:
the hottest instructions of one function). They were written as one-off scratch tools: paths are absolute and inputs
are console profiles + the same build's map / ELF. Run with plain python from the repository root.
