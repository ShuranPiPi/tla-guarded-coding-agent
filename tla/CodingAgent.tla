------------------------------ MODULE CodingAgent ------------------------------
(*****************************************************************************
  Controller model for the TLC-spec-guarded coding agent.

  The model abstracts LLM output and Python test outcomes as nondeterministic
  booleans. It verifies workflow-level guarantees:
    - Python code generation cannot start before a TLC-checked spec succeeds.
    - Done requires both a verified spec and passing code tests.
    - Spec and code retry budgets are bounded.
    - The workflow eventually reaches Done, CodeFail, or SpecFail.
******************************************************************************)

EXTENDS Naturals, TLC

CONSTANTS
    MaxSpecRetries,
    MaxCodeRetries

VARIABLES
    pc,
    specOk,
    codeOk,
    specChecked,
    testsDerived,
    codeChecked,
    specRetries,
    codeRetries

vars == <<pc, specOk, codeOk, specChecked, testsDerived, codeChecked,
          specRetries, codeRetries>>

States == {
    "Init", "GenerateSpec", "CheckSpec", "RepairSpec", "DeriveTests",
    "GenerateCode", "TestCode", "RepairCode",
    "Done", "CodeFail", "SpecFail"
}

Terminal == {"Done", "CodeFail", "SpecFail"}
CodeStates == {"GenerateCode", "TestCode", "RepairCode", "Done", "CodeFail"}

TypeOK ==
    /\ pc \in States
    /\ specOk \in BOOLEAN
    /\ codeOk \in BOOLEAN
    /\ specChecked \in BOOLEAN
    /\ testsDerived \in BOOLEAN
    /\ codeChecked \in BOOLEAN
    /\ specRetries \in 0..MaxSpecRetries
    /\ codeRetries \in 0..MaxCodeRetries

Init ==
    /\ pc = "Init"
    /\ pc' = "GenerateSpec"
    /\ specOk' = FALSE
    /\ codeOk' = FALSE
    /\ specChecked' = FALSE
    /\ testsDerived' = FALSE
    /\ codeChecked' = FALSE
    /\ specRetries' = 0
    /\ codeRetries' = 0

GenerateSpec ==
    /\ pc = "GenerateSpec"
    /\ pc' = "CheckSpec"
    /\ \E ok \in BOOLEAN : specOk' = ok
    /\ specChecked' = FALSE
    /\ UNCHANGED <<codeOk, testsDerived, codeChecked, specRetries, codeRetries>>

CheckSpecPass ==
    /\ pc = "CheckSpec"
    /\ specOk
    /\ pc' = "DeriveTests"
    /\ specChecked' = TRUE
    /\ UNCHANGED <<specOk, codeOk, testsDerived, codeChecked, specRetries, codeRetries>>

CheckSpecFailRetry ==
    /\ pc = "CheckSpec"
    /\ ~specOk
    /\ specRetries < MaxSpecRetries
    /\ pc' = "RepairSpec"
    /\ specChecked' = TRUE
    /\ UNCHANGED <<specOk, codeOk, testsDerived, codeChecked, specRetries, codeRetries>>

CheckSpecFailGiveUp ==
    /\ pc = "CheckSpec"
    /\ ~specOk
    /\ specRetries = MaxSpecRetries
    /\ pc' = "SpecFail"
    /\ specChecked' = TRUE
    /\ UNCHANGED <<specOk, codeOk, testsDerived, codeChecked, specRetries, codeRetries>>

RepairSpec ==
    /\ pc = "RepairSpec"
    /\ pc' = "CheckSpec"
    /\ specRetries' = specRetries + 1
    /\ \E ok \in BOOLEAN : specOk' = ok
    /\ specChecked' = FALSE
    /\ UNCHANGED <<codeOk, testsDerived, codeChecked, codeRetries>>

DeriveTests ==
    /\ pc = "DeriveTests"
    /\ specChecked
    /\ specOk
    /\ pc' = "GenerateCode"
    /\ testsDerived' = TRUE
    /\ UNCHANGED <<specOk, codeOk, specChecked, codeChecked, specRetries, codeRetries>>

GenerateCode ==
    /\ pc = "GenerateCode"
    /\ testsDerived
    /\ pc' = "TestCode"
    /\ \E ok \in BOOLEAN : codeOk' = ok
    /\ codeChecked' = FALSE
    /\ UNCHANGED <<specOk, specChecked, testsDerived, specRetries, codeRetries>>

TestCodePass ==
    /\ pc = "TestCode"
    /\ codeOk
    /\ pc' = "Done"
    /\ codeChecked' = TRUE
    /\ UNCHANGED <<specOk, codeOk, specChecked, testsDerived, specRetries, codeRetries>>

TestCodeFailRetry ==
    /\ pc = "TestCode"
    /\ ~codeOk
    /\ codeRetries < MaxCodeRetries
    /\ pc' = "RepairCode"
    /\ codeChecked' = TRUE
    /\ UNCHANGED <<specOk, codeOk, specChecked, testsDerived, specRetries, codeRetries>>

TestCodeFailGiveUp ==
    /\ pc = "TestCode"
    /\ ~codeOk
    /\ codeRetries = MaxCodeRetries
    /\ pc' = "CodeFail"
    /\ codeChecked' = TRUE
    /\ UNCHANGED <<specOk, codeOk, specChecked, testsDerived, specRetries, codeRetries>>

RepairCode ==
    /\ pc = "RepairCode"
    /\ pc' = "TestCode"
    /\ codeRetries' = codeRetries + 1
    /\ \E ok \in BOOLEAN : codeOk' = ok
    /\ codeChecked' = FALSE
    /\ UNCHANGED <<specOk, specChecked, testsDerived, specRetries>>

Next ==
    \/ Init
    \/ GenerateSpec
    \/ CheckSpecPass
    \/ CheckSpecFailRetry
    \/ CheckSpecFailGiveUp
    \/ RepairSpec
    \/ DeriveTests
    \/ GenerateCode
    \/ TestCodePass
    \/ TestCodeFailRetry
    \/ TestCodeFailGiveUp
    \/ RepairCode

Spec ==
    /\ pc = "Init"
    /\ specOk = FALSE
    /\ codeOk = FALSE
    /\ specChecked = FALSE
    /\ testsDerived = FALSE
    /\ codeChecked = FALSE
    /\ specRetries = 0
    /\ codeRetries = 0
    /\ [][Next]_vars
    /\ WF_vars(Next)

SpecCheckedBeforeCode ==
    pc \in CodeStates => specChecked /\ specOk /\ testsDerived

NoDoneWithoutVerifiedSpec ==
    pc = "Done" => specChecked /\ specOk /\ testsDerived /\ codeChecked /\ codeOk

SpecFailOnlyAfterBudget ==
    pc = "SpecFail" => specChecked /\ ~specOk /\ specRetries = MaxSpecRetries

CodeFailPreservesSpecSuccess ==
    pc = "CodeFail" => specChecked /\ specOk /\ testsDerived /\ codeChecked

BoundedRetries ==
    /\ specRetries <= MaxSpecRetries
    /\ codeRetries <= MaxCodeRetries

EventuallyTerminates ==
    <>(pc \in Terminal)

================================================================================
