These modifications are required to preserve UE-level identifiers in low-level simulator traces, which are later transformed into event logs for predictive process analytics.

## Modified Source Files

This section describes the source-level modifications applied to the original 5G-LENA code in order to obtain more informative PHY control traces for later trace merging and event log generation.

### 1. `nr-phy-rx-trace.cc`

#### Problem
In the original implementation, the `TxedGnbPhyCtrlMsgsTrace` output records the RNTI field as `0` for all messages generated after simulation.

This makes it difficult to determine which UE a given trace record is associated with, and therefore reduces the usefulness of the trace when reconstructing UE-level communication events.

#### Cause
The issue comes from the original callback path used to generate the trace. At the call site, the `rnti` argument is passed as `0`, so the written trace file also stores `0` even when the message is logically related to a specific UE.

#### Modification
The code was modified so that the actual RNTI value is explicitly written into the trace whenever it can be derived from the transmitted control message.

This allows the generated trace to preserve UE-level identity information instead of leaving all entries as `0`.

#### Why this matters
For this project, trace records must later be merged and transformed into event logs. If the RNTI value is always `0`, it becomes difficult to identify which UE session a control-plane event belongs to.

By correcting the RNTI field, the trace becomes more suitable for process-oriented event reconstruction and downstream SLA violation analysis.

#### Caution
- The RNTI values of MIB, SIB1, and RAR messages are expected to remain `0`, because these messages are not unicast to a specific UE. In these cases, keeping `0` is the correct behavior.
- A single `DL_DCI` message may contain scheduling information for multiple UEs. It should therefore be checked whether 5G-LENA internally generates a separate `NrDlDciMessage` object for each UE before assuming a one-to-one mapping between `DL_DCI` and UE identity.

### 2. `nr-ue-phy.cc`

#### Problem
In the original implementation, the `TxedUePhyCtrlMsgsTrace` output also records the RNTI field as `0` for all generated messages.

As a result, it becomes difficult to determine which UE generated each PHY control trace entry.

#### Modification
The code was modified so that `DL_CQI` and `DL_HARQ` related control message traces explicitly include the UE RNTI.

#### Why this matters
This change makes the generated UE PHY control traces easier to interpret by clearly showing which UE each trace record belongs to.

This is important for later trace merging and for constructing event logs that preserve per-UE process context.

## Notes
These modifications were introduced to improve trace interpretability and trace-to-event-log conversion. The objective is not to change the communication protocol itself, but to make simulator output more suitable for downstream process mining and predictive analysis.