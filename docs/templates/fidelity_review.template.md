---
target: TODOTarget
source_refs: [thm:TODO-key]
lean_declaration: TODO_lemma_name
verdict: PASS                 # must match formal_mapping.yaml
rubric:
  A_assumptions: match        # match | added | dropped | altered
  B_conclusion: identical     # identical | equivalent | weaker | stronger | different
  C_quantifiers: match        # match | changed
  D_variables: match          # match | swapped
  E_vacuity: non_vacuous      # non_vacuous | vacuous | cannot_tell
  F_direction: preserved      # preserved | weakened | strengthened
  G_units_form: match         # match | differs_provably | differs_unjustified
judge:                        # filled in only if an LLM judge was consulted
  model: null
  version: null
  temperature: null
  prompt_sha256: null
  de_anchored: null
  ran_utc: null
  saw: null
  did_not_see: null
mutation_results: null
human_approved: true          # the human-approval gate; must match formal_mapping.yaml
human_approver: "TODO name"
human_approved_utc: "TODO-ISO-8601"
---

# TODOTarget — fidelity review

## Source claim
TODO restate the source claim (cite the theorem_index key).

## Lean claim
TODO describe the Lean statement (`TODO_lemma_name`).

## Assumption comparison
TODO source hypotheses vs Lean hypotheses; note anything added/dropped/weakened.

## Conclusion comparison
TODO does the Lean conclusion match in strength and direction?

## Modelling choices
TODO any deliberate modelling decisions (scalings dropped, types chosen, scope narrowed).

## Potential mismatches
TODO the subtle ways this could be wrong, and why each is or is not a problem here.

## Human reviewer notes
TODO sign-off rationale.
