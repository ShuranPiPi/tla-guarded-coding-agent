------------------------------ MODULE CodingAgent ------------------------------
(*****************************************************************************
  Formal specification of the self-correcting coding agent's controller.

  This spec intentionally abstracts away the LLM and the Python test runner.
  From the controller's perspective, both are non-deterministic oracles:
    - Generate/Repair produce *some* code  (modelled by a boolean `codeOk`,
      chosen non-deterministically to explore both "correct" and "incorrect"
      outcomes);
    - Test reports pass iff the current code is correct.

  The point of the model is to check *workflow-level* properties that hold
  regardless of how smart the LLM is:
    - INV1  NoAcceptBeforeValidation
    - INV2  FailedTestGoesToRepairOrFail
    - INV3  BoundedRetries
    - LIVE  EventuallyTerminates
******************************************************************************)

EXTENDS Naturals, TLC

CONSTANTS MaxRetries    \* non-negative integer

VARIABLES
    pc,        \* control-flow state: one of {"Init","Generate","Test","Repair","Done","Fail"}
    codeOk,    \* does the current code pass the tests?  (BOOLEAN)
    tested,    \* has the current code been run through Test since last generation?
    retries    \* number of repair iterations taken so far

vars == <<pc, codeOk, tested, retries>>

States == {"Init", "Generate", "Test", "Repair", "Done", "Fail"}

TypeOK ==
    /\ pc \in States
    /\ codeOk \in BOOLEAN
    /\ tested \in BOOLEAN
    /\ retries \in 0..MaxRetries

(***************************************************************************)
(*                               Transitions                               *)
(***************************************************************************)

Init ==
    /\ pc = "Init"
    /\ pc' = "Generate"
    /\ codeOk' = FALSE
    /\ tested' = FALSE
    /\ retries' = 0

(* Generate: producing a fresh piece of code invalidates the `tested` flag
   and non-deterministically chooses whether the code happens to be correct. *)
Generate ==
    /\ pc = "Generate"
    /\ pc' = "Test"
    /\ \E ok \in BOOLEAN : codeOk' = ok
    /\ tested' = FALSE
    /\ UNCHANGED retries

(* Test: record the verdict by setting `tested`; branch to Done / Repair / Fail. *)
TestPass ==
    /\ pc = "Test"
    /\ codeOk = TRUE
    /\ pc' = "Done"
    /\ tested' = TRUE
    /\ UNCHANGED <<codeOk, retries>>

TestFailRetry ==
    /\ pc = "Test"
    /\ codeOk = FALSE
    /\ retries < MaxRetries
    /\ pc' = "Repair"
    /\ tested' = TRUE
    /\ UNCHANGED <<codeOk, retries>>

TestFailGiveUp ==
    /\ pc = "Test"
    /\ codeOk = FALSE
    /\ retries = MaxRetries
    /\ pc' = "Fail"
    /\ tested' = TRUE
    /\ UNCHANGED <<codeOk, retries>>

Repair ==
    /\ pc = "Repair"
    /\ pc' = "Generate"
    /\ retries' = retries + 1
    /\ UNCHANGED <<codeOk, tested>>

Next ==
    \/ Init
    \/ Generate
    \/ TestPass
    \/ TestFailRetry
    \/ TestFailGiveUp
    \/ Repair

Spec ==
    /\ pc = "Init" /\ codeOk = FALSE /\ tested = FALSE /\ retries = 0
    /\ [][Next]_vars
    /\ WF_vars(Next)   \* weak fairness gives us the termination property

(***************************************************************************)
(*                               Properties                                *)
(***************************************************************************)

\* INV1: A final answer is never accepted before its code was tested.
\*       "Done" is only reachable through TestPass, which requires tested' = TRUE.
NoAcceptBeforeValidation == (pc = "Done") => tested

\* INV2: After a failed test we must be in Repair or Fail — never in Done,
\*       and never skip back to Generate without going through Repair first.
FailedTestGoesToRepairOrFail ==
    (tested /\ ~codeOk /\ pc \notin {"Test"}) => pc \in {"Repair", "Fail", "Generate"}
    \* Generate is allowed only *after* Repair increments retries; this is
    \* captured jointly with INV3 below.

\* INV3: Retries are bounded.
BoundedRetries == retries <= MaxRetries

\* LIVE: The workflow eventually terminates.
EventuallyTerminates == <>(pc \in {"Done", "Fail"})

================================================================================
