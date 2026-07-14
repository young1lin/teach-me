# teach-me behavioral scenarios

Each scenario specifies its setup, user prompt or event, and required observable behavior. RED runs without the `teach-me` skill; GREEN runs with the complete skill. Unless a scenario says otherwise, start from a fresh session and an empty record store.

## Trigger (discipline) — both platform tokens

- **TP1** — SETUP: Claude Code. PROMPT: `/teach-me`. EXPECT: invoke `teach-me` and enter the debrief branch.
- **TP2** — SETUP: Claude Code. PROMPT: `/teach-me conditional probability`. EXPECT: invoke `teach-me` and enter topic mastery.
- **TP3** — SETUP: Codex. PROMPT: `$teach-me`. EXPECT: invoke `teach-me` and enter the debrief branch.
- **TP4** — SETUP: Codex. PROMPT: `$teach-me conditional probability`. EXPECT: invoke `teach-me` and enter topic mastery.
- **TN1** — PROMPT: `teach me conditional probability`. EXPECT: do not invoke `teach-me`; there is no explicit platform token.
- **TN2** — PROMPT: `解释一下这段代码`. EXPECT: do not invoke `teach-me`.
- **TN3** — SETUP: the repository contains a file named `teach-me.md`. EVENT: open that file. EXPECT: do not invoke `teach-me` merely because the filename contains the skill name.
- **TN4** — SETUP: Codex metadata sets `policy.allow_implicit_invocation: false`. PROMPT: `help me learn calculus`. EXPECT: the skill is neither injected nor invoked.

## Teaching-failure baselines

- **F1** — SETUP: the learner says they have zero prior knowledge. PROMPT: `/teach-me quantum mechanics`. EXPECT (GREEN): diagnose the learner and take one minimal teaching step, rather than delivering an encyclopedia-style dump.
- **F2** — PROMPT: `/teach-me Python generators`. EXPECT (GREEN): diagnose the learner's level with at most three questions before teaching.
- **F3** — SETUP: a concept has been explained, but the learner has supplied no application evidence. PROMPT: `我懂了`. EXPECT (GREEN): do not mark the concept mastered; elicit E2/E3 application or transfer evidence.
- **F4** — SETUP: the learner gives two consecutive wrong answers on the same target. EXPECT (GREEN): change the scaffold instead of repeating the same question or prompt form.
- **F5** — SETUP: testing is in progress. PROMPT: `太累了`. EXPECT (GREEN): stop testing immediately, give a checkpoint, and end without a final question or “one more.”
- **F6** — SETUP: the learner is an expert database engineer. PROMPT: `/teach-me database isolation levels`. EXPECT (GREEN): skip basics and focus on edge cases, tradeoffs, and transfer.
- **F7** — SETUP: the requested topic contains time-sensitive claims. EXPECT (GREEN): verify current facts before teaching or explicitly flag uncertainty.

## Functional (GREEN)

- **G-debrief** — SETUP: a database-layer work session has just finished. PROMPT: `/teach-me`. EXPECT: present at most five tagged candidates, wait for the learner to pick, teach the selection, then print a checkpoint.
- **G-topic** — PROMPT: `/teach-me conditional probability`. EXPECT: establish the goal and diagnose level, present a 3–7-unit concept map, teach a unit, then apply the mastery gate.
- **G-gate** — SETUP: a concept has only E1 evidence. EXPECT: state is `unstable`, not `mastered`.
- **G-persist** — SETUP: nothing reaches `mastered`. EXPECT: write zero files and print a checkpoint.
- **G-persist2** — SETUP: session write consent has been granted and one concept reaches E1/E2/E3. EXPECT: write exactly one concept note under `records/`.
- **G-consent** — SETUP: the first concept in a session reaches E1/E2/E3 and no write consent exists yet. EXPECT: name the target, ask, and wait before writing; if the learner says no, write zero files for the rest of that session.
- **G-records** — SETUP: two concepts in one topic reach `mastered` after consent. EXPECT: create two distinct `<topic>--<concept>.md` notes without overwriting either concept.
- **G-platform** — Run three cases. With `$CODEX_HOME` set, use `$CODEX_HOME/skills/teach-me/` and `$CODEX_HOME/teach-me/records/`. Under Codex with `$CODEX_HOME` unset, use `~/.codex/skills/teach-me/` and `~/.codex/teach-me/records/`. Under Claude Code, use `CFG/skills/teach-me/` and `CFG/teach-me/records/` where `CFG` = `$CLAUDE_CONFIG_DIR` if set else `~/.claude` (e.g. `$CLAUDE_CONFIG_DIR` set → `$CLAUDE_CONFIG_DIR/teach-me/records/`).
- **G-unstable** — SETUP: a concept has only E1 evidence. PROMPT: `先到这`. EXPECT: end without pressure at an `unstable` checkpoint and write zero files.
- **G-domain** — Run one conceptual, one procedural, one quantitative, and one argumentative topic. EXPECT: each scaffold and mastery check adapts to its domain.

## Teaching modes (GREEN)

- **M1** — SETUP: Claude Code. PROMPT: `/teach-me --socratic recursion`. EXPECT: socratic mode active; the first teaching turn opens with one probing question, not a lecture.
- **M2** — SETUP: Codex. PROMPT: `$teach-me --soc recursion`. EXPECT: the short alias routes identically to M1.
- **M3** — PROMPT: `/teach-me --fey`. EXPECT: Feynman-style debrief — candidates are offered, then the learner explains the selected concept first; the coach's opening is one sentence plus the request.
- **M4** — SETUP: a socratic (default) session is mid-lesson. PROMPT: `换费曼式`. EXPECT: switch to feynman immediately without a new `/teach-me` token; no re-invocation required.
- **M5** — SETUP: socratic mode. PROMPT: `别问了，直接告诉我`. EXPECT: direct explanation now — the fatigue rule outranks the mode.
- **M6** — SETUP: socratic mode; the learner stalls twice on the same point. EXPECT: the scaffold changes (ladder fires — structure or partial worked example); the same question is not asked a third time.
- **M7** — SETUP: feynman mode; the learner gives a fluent step-4 explanation. EXPECT: state records E1 only; the concept is not `mastered` until E2 and E3 are observed.
- **M8** — SETUP: drill mode; the last rep was partially correct. EXPECT: the next rep is a sideways variation at the same difficulty, not a difficulty increase.
- **M9** — SETUP: a checkpoint file with `mode: socratic` exists. PROMPT: `/teach-me resume <topic>`. EXPECT: socratic mode is restored; a fresh explicit flag would override it (precedence in flows.md).
- **M10** — PROMPT: `/teach-me --sacratic recursion`. EXPECT: report the unknown flag, list the three modes, and ask — do not guess or silently fall back.
- **M11** — SETUP: drill mode inside a git repository with a test suite. EXPECT: reps prefer repo-grounded exercises (predict-then-run / modify-without-peeking / spot-the-planted-bug); consent is requested BEFORE any scratch branch or planted bug; uncommitted work is never touched; scratch artifacts are cleaned up in the same session; nothing is pushed.
- **M12** — PROMPT: `/teach-me --soc --fey recursion`. EXPECT: name the two-mode-flag conflict and ask; do not silently pick one.

## Storage v2 (GREEN)

- **S1** — SETUP: no `~/.teach-me/config.json`; a concept reaches `mastered`. EXPECT: ONE combined question — save mastered concepts? to the default `~/.teach-me/` or a custom directory? The answer is written to `~/.teach-me/config.json`; the question never recurs in this or later sessions.
- **S2** — SETUP: config.json has `"root": "D:/learning"`. EXPECT: records are written under `D:/learning/records/<topic>/`, checkpoints under `D:/learning/checkpoints/`; nothing is written to `~/.teach-me/` except config.json itself.
- **S3** — SETUP: no config.json; the session ends with nothing saved. EXPECT: the storage question was never asked; nothing was created on disk.
- **S4** — SETUP: no config.json; `~/.claude/teach-me/records/` holds old records. EXPECT: at init, migration is offered once; on yes, files move by frontmatter `topic:` into `records/<topic>/<concept>.md` (checkpoint files into `checkpoints/`), and the count is reported.
- **S5** — SETUP: `records/http-retries/` exists; a debrief record about retry backoff is about to be saved. EXPECT: existing topic directories are listed first and `http-retries` is reused (no new near-duplicate topic dir); the consent question names the chosen topic.
- **S6** — SETUP: records exist under `records/tcp/` and a checkpoint under `checkpoints/tcp.md`. EXPECT: the due-review scan reads `records/*/*.md` only; the checkpoint is never offered as a review item.
- **S7** — SETUP: config.json has `archive.obsidian` with a valid vault; a record is written after consent. EXPECT: `python scripts/archive.py` runs; the record appears in the vault under `teach-me/<topic>/`; NO additional question is asked (config = consent).
- **S8** — SETUP: config.json has no `archive` section. EXPECT: no external tool is ever touched; archive.py reports "no destinations configured" and exits 0.
- **S9** — SETUP: the user says "save" (explicit save) with `archive.obsidian` configured. EXPECT: the checkpoint is written, then the mirror runs once; `--dry-run` would preview without writing.

## Retrieval (GREEN)

- **R1** — SETUP: no record mentions "RAG evaluation". PROMPT: "have I learned anything about RAG evaluation?" EXPECT: a `grep` over `records/` finds nothing; the skill SAYS SO and does not fabricate prior learning.

## RED baseline

These controls used fresh agents with no `teach-me` skill content. Each agent saw only its learner exchange and was told not to inspect the repository or skills. TN1 alone received the mock naïve description `Available skill — teach-me: Use when the user wants to learn or understand something.` Excerpts below are verbatim; `[... omitted ...]` marks removed material.

### F1 — zero-base quantum mechanics

**Observed excerpt:**

```text
当然可以。我们按“直觉 → 实验 → 数学 → 应用”的顺序学，不会一上来就扔给你一堆公式。

## 学习路线

我们会依次学习：

1. 为什么经典物理不够用
2. 波函数、概率与叠加态
3. 测量到底意味着什么
4. 薛定谔方程
5. 势阱、隧穿与原子
6. 自旋、纠缠与量子计算

[... omitted ...]

## 第一课：量子力学为什么会出现？

[... omitted: double-slit explanation, probability amplitudes, equations, and superposition ...]

小练习：

\[
|\psi\rangle=\frac{\sqrt3}{2}|L\rangle+\frac12|R\rangle
\]

测量后电子出现在左边和右边的概率分别是多少？
```

**Observed verdict:** FAIL. The response did not diagnose goals or foundations. Its first turn supplied a six-part curriculum, several concepts, multiple equations, and an exercise—the encyclopedia-shaped response F1 is intended to catch—even though it claimed it would avoid a formula dump.

**Design implication:** Give the topic branch a positive first-turn contract: diagnose the learner, choose one smallest useful unit, and perform one cognitive action. Do not rely on a general request to be “beginner friendly.”

### F3 — `我懂了` without application

**Observed excerpt:**

```text
很好！小测一下：如果生成器函数里有两个 `yield`，连续调用两次 `next()` 会发生什么？
```

**Observed verdict:** PASS for this immediate control. The response did not declare mastery; it requested a generative prediction after the learner's self-report. No E2/E3 result exists yet, so mastery still cannot be recorded.

**Design implication:** Preserve this naturally good behavior as an explicit mastery gate so it remains reliable across topics and longer sessions. The baseline does not justify inventing a “mastery-on-claim” failure.

### F5 — fatigue signal

**Observed excerpt:**

```text
辛苦了，先休息一下吧。你想暂停 5 分钟，还是让我用一句话总结条件概率，然后今天就收工？
```

**Observed verdict:** PARTIAL FAIL. The response stopped the quiz and acknowledged fatigue, but it did not provide the checkpoint and ended with another question. That violates F5's terminal no-question requirement.

**Design implication:** Make the fatigue response a terminal output shape: stop assessment, print a light checkpoint in the same turn, and end declaratively with no question, choice, or “one more.”

### F6 — expert database isolation

**Observed excerpt:**

```text
Transaction isolation answers one question:

> Which concurrent transaction histories may the database expose as if they were valid?

The gold standard is **serializability**: every committed concurrent execution must be equivalent to some serial execution of those transactions.

[... omitted ...]

### The anomaly that matters most: write skew

[... omitted ...]

### A useful formal model

[... omitted ...]

### How databases implement isolation

[... omitted ...]

### Practical engineering rules

[... omitted ...]

The compact mental model is:

> Read Committed protects individual statements.
> Snapshot Isolation protects a transaction’s view of the past.
> Serializable protects the consistency of the transaction’s reasoning.
```

**Observed verdict:** PARTIAL PASS / PARTIAL FAIL. The response did recognize expertise: it skipped elementary transaction definitions and covered write skew, dependency cycles, vendor variance, retries, and implementation tradeoffs. It still delivered a long, multi-section lecture without diagnosing the expert's goal or asking the learner to transfer the model to a new case.

**Design implication:** Retain the naturally advanced content selection, but constrain the expert path to a focused edge or tradeoff followed by a transfer task. Expertise should change depth and examples, not disable interaction or load management.

### TN1 — naïve implicit trigger

**Observed excerpt:**

```text
Invocation: yes

Conditional probability asks: “What is the probability of event A, given that event B has already happened?”
```

**Observed verdict:** FAIL. With the naïve description present, the agent chose to invoke on `teach me conditional probability` even though the prompt contained neither `/teach-me` nor `$teach-me`.

**Design implication:** The discovery description must key only on the explicit platform tokens, and Codex must enforce `policy.allow_implicit_invocation: false`; a broad “wants to learn” trigger is insufficient.

## GREEN — Task 2

Trigger wording was tested with fresh single-shot agents. Guided reps saw only the routing environment,
the real `teach-me` name and frontmatter description, and the exact user message. No-guidance controls
saw only the environment, skill name, and message. All 50 completed outputs were read manually.

| Scenario | Real description | No-guidance control | Concise manual evidence |
|---|---:|---:|---|
| TP1 `/teach-me` on Claude Code | invoke 5/5 | invoke 5/5 | Guided reasons identified `/teach-me` as the explicit Claude Code token. |
| TP3 `$teach-me` on Codex | invoke 5/5 | invoke 5/5 | Guided reasons identified `$teach-me` as the explicit Codex token. |
| TN1 `teach me conditional probability` | do not invoke 5/5 | invoke 5/5 | Guided reasons consistently cited the missing `/teach-me` or `$teach-me` token; controls matched the request to the skill name. |
| TN2 `解释一下这段代码` | do not invoke 5/5 | invoke 5/5 | Guided reasons treated an ordinary explanation request without `$teach-me` as negative; controls inferred a teaching match. |
| TN4 `help me learn calculus` | do not invoke 5/5 | invoke 5/5 | Guided reasons consistently cited the missing `$teach-me` token; controls matched “learn” to `teach-me`. |

**GREEN verdict:** PASS. TP1 and TP3 recognized explicit invocation in 5/5 reps each. TN1, TN2,
and TN4 rejected implicit invocation in 5/5 reps each. The controls show why the explicit negative
wording is material rather than redundant.

## GREEN — full suite (Task 6)

Method: five parallel read-only agents each read only the shipped skill files and judged, per scenario,
whether the shipped text *forces* the required behavior or leaves a rationalization gap (a loophole).
This analytic pass complements the behavioral evidence already gathered: trigger discipline was
repeat-sampled in the Task 2 table above, and the F1–F7 RED baselines (the teaching failures this skill
must flip) are recorded earlier in this file.

| Group | Scenarios | Result |
|---|---|---|
| Trigger | TP1–TP4, TN1–TN4 | PASS (8/8). TP2, TP4, TN3 verified analytically here; TP1/TP3/TN1/TN2/TN4 also repeat-sampled (Task 2 table). |
| Teaching failures | F1–F7 | F1–F5, F7 PASS; **F6 FAIL → fixed** (see below), re-verified PASS. |
| Persistence & consent | G-gate, G-persist, G-persist2, G-consent, G-records, G-unstable | PASS (6/6). |
| Checkpoint/resume + consent precedence (Task 5 fix) | on-disk checkpoint schema, no-topic debrief filename, AUTO-gate vs explicit-save precedence | PASS (3/3), fresh-context re-verification. |
| Paths | G-platform (×3) | PASS. |
| Teaching flows | G-debrief, G-topic, G-domain (×4 domains) | G-debrief, G-topic PASS; **G-domain FAIL → fixed** (see below), re-verified PASS. |

### Loopholes found and closed (REFACTOR)

- **F6 (expert isolation).** The expert-learner row read "go to edges, tradeoffs, **or** transfer"; the
  disjunctive `or` let an agent cover only edges/tradeoffs and skip transfer, reproducing the RED
  expert lecture-dump. Fixed in `teaching.md` — the expert path now requires an E3 transfer task and
  states "expertise never waives the transfer check."
- **G-domain (cross-domain adaptation).** The cross-domain table had distinct per-domain guidance but
  no imperative tying "classify the unit's domain" to "use its matching row," so an agent could teach
  every domain via the generic loop without breaking a stated rule. Fixed in `teaching.md` with an
  imperative lead-in, plus a parallel Red Flag in `SKILL.md`.

### Hardenings (no failure, defense-in-depth)

- **TN3:** restated the filename carve-out ("opening `teach-me.md` is not a trigger") as an explicit
  `SKILL.md` Red Flag, not only in "When to Use".
- **TN4:** added an English comment in `agents/openai.yaml` documenting that
  `allow_implicit_invocation: false` scopes the skill to explicit `$teach-me` invocation only.

**Full-suite verdict:** PASS after REFACTOR. Two loopholes (F6, G-domain) closed and re-verified; all
other scenarios pass as shipped.
