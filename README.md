# linecheck-simulator
A small Python console simulator of a production line section (S1/S2 sensors + next section availability). Goal: model states and validate expected behavior (QA mindset).

## Context

This simulator is based on a real production line scenario.
Radiators are detected by sensors (S1, S2) and transferred to the next section
if it is available.

## What is simulated

- Finite State Machine (FSM)
- States: WAIT_EMPTY, MOVE_TO_S2, AT_END, TRANSFER, ERROR
- S1: sensor at the beginning of the section
- S2: sensor at the end of the section (manual loading possible)
- Motor on/off logic
- Transfer to the next section
- Timeout simulation via "tick"
- Automatic reset on error conditions

## Goal

Model normal flow and detect error situations
(missing confirmation, blocked transfer, lost part).

## Project status

Work in progress.  
This is a learning project focused on logic, state transitions,
and QA-style reasoning rather than production-ready code.

## Why

This simulator is based on a real production line scenario
and is used to practice reasoning about system behavior,
error handling, and safety-critical logic.

## How to run

```bash
python main.py
```
Available commands:
- s1 — trigger entry sensor
- s2 — trigger end sensor / manual load
- next — allow transfer to next section
- tick — simulate time passing
- reset — reset system to initial state
- exit — stop simulation

