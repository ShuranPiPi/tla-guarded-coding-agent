---- MODULE CodingAgent_TTrace_1776711753 ----
EXTENDS Sequences, TLCExt, CodingAgent, Toolbox, Naturals, TLC

_expression ==
    LET CodingAgent_TEExpression == INSTANCE CodingAgent_TEExpression
    IN CodingAgent_TEExpression!expression
----

_trace ==
    LET CodingAgent_TETrace == INSTANCE CodingAgent_TETrace
    IN CodingAgent_TETrace!trace
----

_inv ==
    ~(
        TLCGet("level") = Len(_TETrace)
        /\
        retries = (0)
        /\
        codeOk = (TRUE)
        /\
        pc = ("Done")
        /\
        tested = (TRUE)
    )
----

_init ==
    /\ codeOk = _TETrace[1].codeOk
    /\ tested = _TETrace[1].tested
    /\ pc = _TETrace[1].pc
    /\ retries = _TETrace[1].retries
----

_next ==
    /\ \E i,j \in DOMAIN _TETrace:
        /\ \/ /\ j = i + 1
              /\ i = TLCGet("level")
        /\ codeOk  = _TETrace[i].codeOk
        /\ codeOk' = _TETrace[j].codeOk
        /\ tested  = _TETrace[i].tested
        /\ tested' = _TETrace[j].tested
        /\ pc  = _TETrace[i].pc
        /\ pc' = _TETrace[j].pc
        /\ retries  = _TETrace[i].retries
        /\ retries' = _TETrace[j].retries

\* Uncomment the ASSUME below to write the states of the error trace
\* to the given file in Json format. Note that you can pass any tuple
\* to `JsonSerialize`. For example, a sub-sequence of _TETrace.
    \* ASSUME
    \*     LET J == INSTANCE Json
    \*         IN J!JsonSerialize("CodingAgent_TTrace_1776711753.json", _TETrace)

=============================================================================

 Note that you can extract this module `CodingAgent_TEExpression`
  to a dedicated file to reuse `expression` (the module in the 
  dedicated `CodingAgent_TEExpression.tla` file takes precedence 
  over the module `CodingAgent_TEExpression` below).

---- MODULE CodingAgent_TEExpression ----
EXTENDS Sequences, TLCExt, CodingAgent, Toolbox, Naturals, TLC

expression == 
    [
        \* To hide variables of the `CodingAgent` spec from the error trace,
        \* remove the variables below.  The trace will be written in the order
        \* of the fields of this record.
        codeOk |-> codeOk
        ,tested |-> tested
        ,pc |-> pc
        ,retries |-> retries
        
        \* Put additional constant-, state-, and action-level expressions here:
        \* ,_stateNumber |-> _TEPosition
        \* ,_codeOkUnchanged |-> codeOk = codeOk'
        
        \* Format the `codeOk` variable as Json value.
        \* ,_codeOkJson |->
        \*     LET J == INSTANCE Json
        \*     IN J!ToJson(codeOk)
        
        \* Lastly, you may build expressions over arbitrary sets of states by
        \* leveraging the _TETrace operator.  For example, this is how to
        \* count the number of times a spec variable changed up to the current
        \* state in the trace.
        \* ,_codeOkModCount |->
        \*     LET F[s \in DOMAIN _TETrace] ==
        \*         IF s = 1 THEN 0
        \*         ELSE IF _TETrace[s].codeOk # _TETrace[s-1].codeOk
        \*             THEN 1 + F[s-1] ELSE F[s-1]
        \*     IN F[_TEPosition - 1]
    ]

=============================================================================



Parsing and semantic processing can take forever if the trace below is long.
 In this case, it is advised to uncomment the module below to deserialize the
 trace from a generated binary file.

\*
\*---- MODULE CodingAgent_TETrace ----
\*EXTENDS IOUtils, CodingAgent, TLC
\*
\*trace == IODeserialize("CodingAgent_TTrace_1776711753.bin", TRUE)
\*
\*=============================================================================
\*

---- MODULE CodingAgent_TETrace ----
EXTENDS CodingAgent, TLC

trace == 
    <<
    ([retries |-> 0,codeOk |-> FALSE,pc |-> "Init",tested |-> FALSE]),
    ([retries |-> 0,codeOk |-> FALSE,pc |-> "Generate",tested |-> FALSE]),
    ([retries |-> 0,codeOk |-> TRUE,pc |-> "Test",tested |-> FALSE]),
    ([retries |-> 0,codeOk |-> TRUE,pc |-> "Done",tested |-> TRUE])
    >>
----


=============================================================================

---- CONFIG CodingAgent_TTrace_1776711753 ----
CONSTANTS
    MaxRetries = 3

INVARIANT
    _inv

CHECK_DEADLOCK
    \* CHECK_DEADLOCK off because of PROPERTY or INVARIANT above.
    FALSE

INIT
    _init

NEXT
    _next

CONSTANT
    _TETrace <- _trace

ALIAS
    _expression
=============================================================================
\* Generated on Mon Apr 20 14:02:33 CDT 2026