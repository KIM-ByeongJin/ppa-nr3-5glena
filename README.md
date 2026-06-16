# PPA-Oriented Event Log Generation for 5G-LENA / ns-3

## Overview
This project transforms UE-gNB communication traces in a cellular network simulation into event logs.
The generated event logs are intended for predictive process analytics (PPA) to detect SLA violations of different traffic classes in advance.

## Current Scope
- Completed: trace-to-event-log transformation
- Planned: PPA model development using the generated event log
- Planned: performance comparison with baseline ML models

## Environment
- Ubuntu 26.04
- ns-3.47
- 5g-lena-v4.2.y
- g++
- Python
- pandas

## Repository Structure
```text
ns-3.47/
├── patched-modules/
├── scratch/
scripts/
data-samples/
```

- `ns-3.47/patched-modules/`: modified 5G-LENA source files
- `ns-3.47/scratch/`: simulation code
- `scripts/`: trace merging and event log generation scripts
- `data-samples/`: sample merged trace and event log files

## Simulation Setup
- Number of UEs: 10
- Traffic types: 5 ULL flows and 5 BE flows

## How to Run

### 1. Clone ns-3
```bash
mkdir -p ~/workspace
cd ~/workspace
git clone -b ns-3.47 https://gitlab.com/nsnam/ns-3-dev.git ns-3.47
cd ns-3.47
```

### 2. Clone 5G-LENA
```bash
cd contrib
git clone https://gitlab.com/cttc-lena/nr.git
cd nr
git checkout 5g-lena-v4.2.y
cd ../..
```

### 3. Replace modified files
Replace the following files with the modified versions provided in this repository:
- `contrib/nr/helper/nr-phy-rx-trace.cc`
- `contrib/nr/helper/nr-phy-rx-trace.h`
- `contrib/nr/model/nr-ue-phy.cc`
- `contrib/nr/model/nr-ue-phy.h`

### 4. Configure and build
```bash
./ns3 configure --enable-examples --enable-tests
./ns3 build
```

### 5. Run simulation
Copy `cttc-nr-demo.cc` into the `scratch/` directory and run:
```bash
./ns3 run scratch/cttc-nr-demo
```

### 6. Generate event log
A concise description of how raw ns-3 / 5G-LENA traces are cleaned, merged, and transformed into event logs is available here:

- [Event Log Construction Strategy](docs/event_log_construction.md)

## Output Files
| File | Description |
|------|-------------|
| `merged_traces.csv` | Merged trace output |
| `PPM_Event_Log.csv` | Final event log |

## Modified Files
- `nr-ue-phy.cc`: modified RNTI logging behavior in `UlCtrl()`
- `nr-phy-rx-trace.cc`: modified PHY control trace logging to record actual RNTI from DCI messages

## Notes
- This repository currently focuses on event log generation.
- PPA model training is not yet included.
- Generated trace `.txt` and `.csv` files are excluded from version control.
- For details on source-level modifications, see [docs/source_code_modifications.md](docs/source_code_modifications.md).
