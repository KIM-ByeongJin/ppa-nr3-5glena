# Event Log Construction Strategy

This document summarizes how raw ns-3 / 5G-LENA traces are converted into event logs for later predictive process analytics (PPA).

## 1. Data Preparation
Raw trace files are loaded first.

To keep the data focused on UE-level downlink behavior, the following records are removed:
- system broadcast messages such as `MIB` and `SIB1`
- records with public or non-UE-specific RNTI values such as `65535` and `0`
- uplink control and channel-quality related messages such as `UL_DCI`, `UL_UCI`, `SRS`, and `CQI`

This step reduces noise and keeps the pipeline centered on downlink packet delivery.

## 2. Sub-case Identification
Each downlink packet is treated as an individual process instance.

To do this:
- packets in `NrDlPdcpTxStats` are sorted by time for each RNTI
- a sequential `Virtual_SN` is assigned from 1 to N
- `Case_ID` is created by combining `RNTI` and `Virtual_SN` (for example, `11_1`, `11_2`, `2_1`)

This allows multiple packets from the same UE to be handled as separate sub-cases.

## 3. Cross-layer Mapping
Each packet-level case is then tracked across PDCP and RLC logs.

The receive time in `NrDlPdcpRxStats` and the delay recorded in `NrDlRxRlcStats` are used to estimate the corresponding transmission time. Based on this mapping, each `Case_ID` can be connected to its PDCP and RLC transmit/receive events.

## 4. Activity Timeline
For each `Case_ID`, a small sequence of activities is constructed in time order.

### Common prefix events
These events are copied to all packet-level sub-cases of the same RNTI:
- `Admission_Request`
- `Admission_Accept`

### Packet-specific events
These events are mapped dynamically for each packet:
- `DL_Resource_Allocation`
- `DL_PDCP_Enqueue`
- `DL_RLC_Tx`
- `DL_RLC_Rx`

## 5. Final Outcome
Each packet case is labeled with its final outcome.

- `DL_Data_Received`: inserted when the packet successfully reaches UE PDCP reception
- `DL_Data_Failed`: inserted when the packet is transmitted but does not reach the expected lower-layer or final reception point within a timeout window

This provides a unified failure handling rule for different traffic types.

## 6. Features for PPA
Additional features are attached to support later predictive modeling.

Main features include:
- `Time_since_Admission`
- `Time_since_Last_Activity`
- `Packet_Size`

The final outcome is labeled as:
- `1 (Violation)` if the packet fails or exceeds the configured SLA threshold
- `0 (Success)` if the packet is successfully delivered within the threshold

## Notes
This pipeline is designed for event log generation, not for final model training itself.

The resulting event log is intended to be used later for:
- SLA violation prediction
- prefix-based outcome prediction
- comparison with baseline ML models