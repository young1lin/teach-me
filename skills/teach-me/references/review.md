# teach-me review flow (Branch C)

Spaced-repetition retention checks for concepts already demonstrated in an earlier session.
Explicitly invoked only, via `/teach-me review` (`$teach-me review`). Never auto-started.

## Procedure

1. Get the due list deterministically: `python scripts/store.py due --limit 5` (the script is
   under this skill's directory — resolve its path there, don't assume the current working
   directory). Each line is `topic<TAB>concept<TAB>state<TAB>box<TAB>days_overdue<TAB>path`.
   Only **empty output from a command that exited successfully** means nothing is due → tell the
   user nothing is due and stop. If the command errors instead (non-zero exit, a traceback, or
   "No such file or directory"), it did **not** report an empty due list — surface the problem
   and fix it (e.g. re-run with the correct script path); never tell the user nothing is due on
   the strength of a command that failed.
2. For each due concept, in the order printed (prerequisites come first), open its record and
   ask its stored **"Review question (self-test prompt)"** as a retrieval check. One question
   per turn. Obey every fatigue hard rule in `teaching.md` — stop immediately on any stop or
   fatigue signal, checkpoint, and do not add "one more".
3. Grade the answer with the normal feedback verdict:
   - `correct` → `python scripts/store.py review --topic T --concept C --result pass`
     (promotes the Leitner box, marks `retained`).
   - `partial` / `not yet` → `python scripts/store.py review --topic T --concept C --result fail`
     (resets to box 1, marks `stale`), then ask "review this now?" — yes runs the normal
     teaching loop on the concept; no moves to the next due item.
4. If a failed concept lists `deps` that are themselves `stale` or overdue, offer to check the
   prerequisite first: "this may be because prerequisite Y is shaky — review Y?"
5. Stop when the batch (5) is exhausted, the due list is empty, or a fatigue signal arrives.
   Always end with the standard copyable checkpoint.

## Invariants

- Batch cap: at most 5 due concepts per review session unless the user asks for more.
- Never compute due dates or box transitions by hand — `store.py` owns all schedule math.
- Review changes retention state only; it never fabricates prior learning. Only a **successful**
  `due` that returns nothing means nothing is due — say so; a `due` command that errored is a
  problem to surface and fix, never grounds to report "nothing due".
