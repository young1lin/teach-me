# teach-me mode — drill (deliberate practice)

## Usage

```text
/teach-me --drill <topic>     Claude Code / Cursor / Antigravity
/teach-me --dri <topic>       short alias
$teach-me --drill <topic>     Codex / OpenCode
```

Mid-session: say "switch to drill" (any language works, e.g. "换刻意练习") — takes effect
immediately, no re-invocation needed.

## When to choose / when NOT

Choose when the learner can already do the thing shakily and needs reps: a known weak
sub-skill, speed or accuracy building, consolidation after base-loop teaching.
Do NOT choose for brand-new conceptual material — there is nothing to drill yet; let the
shared base loop teach it first.

## Turn protocol — the rep loop

Ericsson's three conditions govern every rep: work at the edge of ability, one specific
micro-goal per rep, immediate specific feedback.

1. **Target.** Pick the weakest sub-skill from observed evidence (session state, records,
   or one diagnostic attempt). Name the target and micro-goal out loud, e.g.
   "target: off-by-one bounds; goal: set both loop bounds correctly on the first try."
2. **One exercise.** Give one task at the edge of current ability — hard enough to miss,
   close enough to reach. One rep per turn. In a repository session, prefer repo-grounded
   reps (see teaching.md "Exercise substrate"): predict a test's output before running
   it, fix a planted bug on a scratch branch, or rewrite an agent-written function
   without peeking — consent and cleanup rules live there.
3. **Attempt + feedback.** The learner attempts; feedback uses teaching.md's feedback
   turn protocol (Verdict / Evidence / Repair / State / Next).
4. **Vary the next rep:**

| Last rep | Next rep |
|---|---|
| Clean | Difficulty up one notch, or a new variation dimension |
| Partial | Sideways variation at the same difficulty |
| Two stalls | Scaffold down via the ladder (partial worked example → retry a similar one) |

5. A transfer-flavored variation (changed context, same skill) supplies E3.

## Overrides (vs the shared base loop)

- The "minimal explanation" step collapses into feedback: teaching happens as repair
  between reps, not as up-front exposition.
- Progress is measured in reps against one named sub-skill, not in concept-map units.

## Never overrides

The E1/E2/E3 rubric, state machine, fatigue hard rules, scaffolding ladder,
one-main-action rule, source discipline, and the write-consent gates in `teaching.md` /
`state.md` apply unchanged. Fatigue matters double here — reps are tiring; any stop
signal ends the session immediately with a checkpoint, no "one more rep".

## Red flags

- Two exercises in one turn → STOP, one rep per turn.
- Raising difficulty after a partial → STOP, vary sideways instead.
- Drilling material the learner has never met → STOP, that is the base loop's opening job.
- Rep N+1 identical to rep N after a miss → STOP, vary or ladder down.
- "One more rep" after a fatigue signal → STOP, checkpoint now.
