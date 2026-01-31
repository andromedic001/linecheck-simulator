# linecheck-simulator
A small Python console simulator of a production line section (S1/S2 sensors + next section availability). Goal: model states and validate expected behavior (QA mindset).

## Context

This simulator is based on a real production line scenario.
Radiators are detected by sensors (S1, S2) and transferred to the next section
if it is available.

## What is simulated

- S1: sensor at the beginning of the section
- S2: sensor at the end of the section (manual loading possible)
- Next section availability (free / blocked)

## Goal

Model normal flow and detect error situations
(missing confirmation, blocked transfer, lost part).
