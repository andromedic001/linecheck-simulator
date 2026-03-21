# LineCheck Simulator

Console-based simulation of an industrial production line using finite state machines (FSM), inspired by real factory processes.

This project focuses on **automation logic, system flow, and state control**, similar to PLC-driven production lines.

---

## Purpose

* Practice industrial logic thinking (PLC-style)
* Simulate real production line behavior
* Build a technical portfolio project for automation / QA / engineering roles
* Understand system stability, edge cases, and recovery strategies

---

## Features

* Modular FSM architecture (Section A / Section B)
* Tick-based simulation (discrete time steps)
* Auto-run mode with configurable flow (max / normal / random)
* Real-time console HMI (status visualization)
* Event logging (JSONL format)
* Fault detection and recovery system
* Manual control commands for testing scenarios

---

## Architecture

project/
│
├── main.py          # entry point, CLI loop, threading
├── fsm.py           # finite state machines (Section A & B)
├── cascade.py       # flow / transfer logic between sections
├── qa.py            # validation, fault detection, recovery
├── helpers.py       # logging, UI, utilities
├── state.py         # system state definition
└── legacy/          # initial monolithic version

---

## System Logic (Tick Flow)

Each simulation step ("tick") runs in the following order:

1. Cascade logic determines if transfers are allowed
2. Section B FSM executes (downstream priority)
3. Section A FSM executes
4. QA layer validates system state
5. Statistics are updated

This structure mimics real industrial systems where downstream constraints affect upstream behavior.

---

## Simulated Sections

* **U (Upstream)** — part source
* **A (Transport section)** — movement + buffering
* **B (Station)** — alignment, clamping, discharge

---

## Fault Handling

The system includes:

* Warning → Error escalation logic
* Auto-recovery for recoverable faults
* Manual reset for critical failures
* State validation (QA layer)

Example fault types:

* Sensor timeouts
* Occupancy conflicts
* Invalid actuator states
* State/flag mismatches

---

## Commands

run — start automatic simulation
stop — stop auto mode
tick — single simulation step
stepauto — one auto step with feed logic

feed — add part to upstream
s2a — force part at A end

reset — reset system (safe conditions required)
recover — attempt auto recovery

flow max / normal / random — change feed behavior

clearlog — clear event log
clearcount — reset statistics

exit — terminate program

---

## Statistics

* Parts per tick
* Estimated throughput (1h / 8h)
* Real-time performance tracking

---

## Legacy Version

Initial monolithic implementation is stored in:

/legacy/linecheck_simulator_v1.py

---

## Future Improvements

* GUI / web interface
* Real sensor modeling
* Configuration system
* Better visualization of states
* Integration with real PLC concepts

---

## Notes

This project is not focused on UI or frameworks —
it is focused on **logic, system behavior, and automation thinking**.

---

## Author

Andrii Dehtiar
Industrial automation enthusiast / future PLC & QA engineer
