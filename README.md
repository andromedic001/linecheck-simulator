# LineCheck Simulator

A Python console simulation of an industrial radiator transfer line.

This project models a real production scenario using a Finite State Machine (FSM),
tick-based controller logic, actuator timing, and structured logging.

The focus is on process modeling, deterministic state transitions,
and QA-style reasoning rather than production-ready UI.

---

## Context

The simulator represents a section of a production line where radiators:

1. Enter the section (S1 sensor)
2. Move to the end position (S2 sensor)
3. Transfer to the next section (if available)
4. Hit an alignment stopper
5. Get centered by a clamp manipulator
6. Are discharged downstream

The logic separates:

- Sensor events
- Mechanical delay
- Actuator behavior
- Time-based controller ticks

---

## Process Flow

### 1. Entry Phase
- `s1` → Radiator detected at entry  
- State: `MOVE_TO_S2`  
- Current section motor ON  

### 2. End Detection
- `s2` → Radiator at end position  
- State: `AT_END`  

### 3. Transfer Phase
- `next` → Prepare transfer  
- Next section motor ON  
- Alignment stopper automatically extends  
- State: `PREP_TRANSFER`  

- `tick` → Transition to `TRANSFER`  
- Current motor ON  

### 4. N1 Confirmation
- `n1` → Radiator detected on next section  
- Transition to `ALIGNING`  
- 1 tick delay simulates physical impact against stopper  

### 5. Stopper Alignment (1 Tick)
- Radiator hits stopper  
- Next motor turns OFF  
- Stopper retracts  
- State: `WAIT_CLAMP`  

### 6. Manual Clamp Phase
- `clamp` → Activate manipulator  
- State: `CLAMPING`  
- 2 ticks simulate centering process  

### 7. Discharge Phase
- After clamping:
  - Next motor ON  
  - Radiator moves downstream  
- 2 ticks simulate discharge  
- State: `DONE`  

---

## What Is Modeled

- Finite State Machine (FSM)
- Deterministic tick-based transitions
- Sensor interrupt logic (N1 handled immediately)
- Mechanical delay modeling (`ALIGNING` state)
- Manual actuator control (`CLAMPING`)
- Controlled discharge cycle
- Structured JSONL logging
- Timeout error handling:
  - `E_S2_TIMEOUT`
  - `E_N1_TIMEOUT`

---

## State Overview

WAIT_EMPTY
MOVE_TO_S2
AT_END
PREP_TRANSFER
TRANSFER
ALIGNING
WAIT_CLAMP
CLAMPING
DISCHARGE
DONE

Each state represents a physically meaningful stage of the process.

---

## Available Commands

s1 -> trigger entry sensor
s2 -> trigger end sensor
next -> allow transfer to next section
n1 -> trigger next section sensor
tick -> simulate controller time step
clamp -> activate clamp manipulator
next_section_toggle -> manually block/unblock next section
reset -> reset system
clearlog -> clear log file
log -> toggle logging on/off
exit -> stop simulation
---

## Logging

Events are written to `events.jsonl` in JSONL format.

Each event contains:

- timestamp
- run_id
- event_type
- level
- error_code (if any)
- full state snapshot

The logger is protected with `try/except` to ensure
that logging errors never crash the simulator.

---

## Project Goals

This project is built to:

- Practice FSM modeling
- Simulate real industrial timing logic
- Separate sensor events from mechanical delays
- Apply QA-style reasoning
- Improve deterministic system design thinking
- Build a foundation for future:
  - Automated tests
  - Monitoring
  - API layer (FastAPI)
  - Database integration

---

## How to Run

```bash
python main.py
```

Follow the process flow described above.

## Project Status
Active learning project.

The simulator now models a full mechanical cycle including:

- Stopper impact delay
- Manual clamping
- Timed discharge
- Deterministic completion

##Why This Matters
Real production systems are not just sensor triggers.

They include:

-Mechanical inertia
-Physical alignment delays
-Actuator timing
-Safety-oriented transitions

This simulator attempts to reflect that reality in code.

Author: Andrii Dehtiar
Project Type: Industrial Logic Simulation / QA Practice
