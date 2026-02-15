import os
import json
import uuid
from datetime import datetime

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
LOG_FILE = os.path.join(BASE_DIR, "events.jsonl")


def collect_status(state, motor_on, motor_on2, counter, next_section_available, n1,
                   align_stopper, aligned, clamp):
    return {
        "state": state,
        "motor_on": motor_on,
        "motor_on2": motor_on2,
        "counter": counter,
        "next_section_available": next_section_available,
        "next_sensor": n1,
        "align_stopper": align_stopper,
        "aligned": aligned,
        "clamping": clamp
    }


def print_status(message, status):
    print(message)
    print(f"Current state: {status['state']}")
    print(f"Motor: {'ON' if status['motor_on'] else 'OFF'}")
    print(f"Motor_next_link: {'ON' if status['motor_on2'] else 'OFF'}")
    print(f"Counter: {status['counter']}")
    print(f"Next section: {'FREE' if status['next_section_available'] else 'BLOCKED'}")
    print(f"Alignator: {'STUCK OUT' if status['align_stopper'] else 'STUCK IN'}")
    print(f"Radiator aligned: {'YES' if status['aligned'] else 'NO'}")
    print(f"Clamped: {'YES' if status['clamping'] else 'NO'}")


def clear_log_file():
    open(LOG_FILE, "w", encoding="utf-8").close()


def reset_system():
    # state, counter, motor_on, motor_on2, n1, next_section_available, align_stopper, aligned, clamp
    return "WAIT_EMPTY", 0, False, False, False, True, False, False, False


def handle_tick(state, counter, motor_on, motor_on2, n1, next_section_available,
                align_stopper, aligned, clamp):
    """
    Always returns 11 values:
    state, counter, motor_on, motor_on2, n1, next_section_available,
    align_stopper, aligned, clamp, message, error_code
    """
    message = "Tick ignored (not moving)"
    error_code = None

    if state == "MOVE_TO_S2":
        motor_on = True
        counter += 1
        message = "Tick: moving to S2..."

        if counter >= 4:
            message = "ERROR: no S2 confirmation (timeout) -> auto reset"
            error_code = "E_S2_TIMEOUT"
            state, counter, motor_on, motor_on2, n1, next_section_available, align_stopper, aligned, clamp = reset_system()

    elif state == "PREP_TRANSFER":
        # motor_on2 already ON, align_stopper already OUT (set on 'next')
        message = "Tick: next section moving, start current motor -> TRANSFER"
        motor_on = True
        state = "TRANSFER"
        counter = 0

    elif state == "TRANSFER":
        counter += 1

        # N1 interrupt: we DO NOT finish instantly.
        # We enter ALIGNING for exactly 1 tick so radiator "hits stopper".
        if n1:
            message = "N1 confirmed: keep pushing for 1 tick to hit stopper (ALIGNING)"
            next_section_available = False   # next section occupied
            # In transfer, next motor is already ON. Keep it ON for the impact tick.
            motor_on = False                 # current motor stops once radiator reached next sensor
            motor_on2 = True                 # keep pushing into stopper for one more tick
            state = "ALIGNING"
            counter = 0
            n1 = False
        elif counter >= 4:
            message = "ERROR: no N1 confirmation (timeout) -> auto reset"
            error_code = "E_N1_TIMEOUT"
            state, counter, motor_on, motor_on2, n1, next_section_available, align_stopper, aligned, clamp = reset_system()
        else:
            message = "Transfer in progress: waiting for N1"

    elif state == "ALIGNING":
        # Exactly 1 tick: radiator hits stopper, then we stop next motor and retract stopper.
        counter += 1
        message = "ALIGNING: radiator hit stopper -> stop next motor, retract stopper, wait clamp"

        if counter >= 1:
            motor_on2 = False
            align_stopper = False
            state = "WAIT_CLAMP"
            counter = 0

    elif state == "WAIT_CLAMP":
        message = "Waiting clamp command (manual manipulator)"

    elif state == "CLAMPING":
        counter += 1
        message = "Clamping in progress..."

        if counter >= 2:
            aligned = True
            clamp = True
            # After clamp alignment, start discharge
            motor_on2 = True
            state = "DISCHARGE"
            counter = 0
            message = "Aligned by clamp -> DISCHARGE (next motor moves radiator away)"

    elif state == "DISCHARGE":
        counter += 1
        message = "Discharging radiator..."

        if counter >= 2:
            motor_on2 = False
            clamp = False
            aligned = False
            next_section_available = True
            state = "DONE"
            counter = 0
            message = "Radiator discharged. Simulation finished."

    elif state == "DONE":
        message = "DONE"

    return (state, counter, motor_on, motor_on2, n1, next_section_available,
            align_stopper, aligned, clamp, message, error_code)


def log_event(command, message, status, event_type=None, level="INFO", error_code=None,
              enabled=True, run_id=""):
    if not enabled:
        return

    event = {
        "run_id": run_id,
        "ts": datetime.now().isoformat(timespec="seconds"),
        "command": command,
        "event_type": event_type or command,
        "level": level,
        "error_code": error_code,
        "message": message,
        "state": status.get("state"),
        "status": status
    }

    try:
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(json.dumps(event, ensure_ascii=False) + "\n")
    except Exception as e:
        print(f"[LOG ERROR] {e}")


def main():
    run_id = uuid.uuid4().hex[:8]
    state, counter, motor_on, motor_on2, n1, next_section_available, align_stopper, aligned, clamp = reset_system()
    logging_enabled = True
    auto_clear_log_on_start = False

    if auto_clear_log_on_start:
        clear_log_file()

    print("LineCheck Simulator started")
    print("Commands: s1, s2, next, n1, tick, clamp, next_section_toggle, reset, clearlog, log, exit")

    should_exit = False

    while True:
        if state == "DONE":
            print("Simulation finished.")
            break

        message = ""
        error_code = None
        command = input("> ").strip().lower()

        if command == "exit":
            message = "Simulation stopped by user"
            should_exit = True

        elif command == "log":
            logging_enabled = not logging_enabled
            message = f"Logging = {logging_enabled}"

        elif command == "clearlog":
            clear_log_file()
            message = "Log cleared"

        elif command == "reset":
            state, counter, motor_on, motor_on2, n1, next_section_available, align_stopper, aligned, clamp = reset_system()
            message = "Manual reset: system returned to WAIT_EMPTY"

        elif command == "next_section_toggle":
            next_section_available = not next_section_available
            message = f"Next section toggled -> {'FREE' if next_section_available else 'BLOCKED'}"

        elif command == "s1":
            counter = 1
            motor_on = True
            motor_on2 = False
            n1 = False
            message = "S1 triggered (radiator detected at entry)"
            state = "MOVE_TO_S2"

        elif command == "s2":
            motor_on = False
            motor_on2 = False
            counter = 0
            message = "S2 triggered (radiator at end position)" if state != "WAIT_EMPTY" else "Manual load at S2"
            state = "AT_END"

        elif command == "next":
            if state == "AT_END":
                if next_section_available:
                    message = "Preparing transfer: next motor ON + align stopper OUT"
                    state = "PREP_TRANSFER"
                    motor_on2 = True
                    align_stopper = True
                else:
                    message = "Next section blocked"
                    motor_on2 = False
            else:
                message = "Cannot transfer: radiator is not at end position"

        elif command == "n1":
            n1 = True
            message = "N1 triggered (radiator detected on next section)"
            # interrupt-style: process immediately if in TRANSFER
            if state == "TRANSFER":
                (state, counter, motor_on, motor_on2, n1, next_section_available,
                 align_stopper, aligned, clamp, message, error_code) = handle_tick(
                    state, counter, motor_on, motor_on2, n1, next_section_available,
                    align_stopper, aligned, clamp
                )

        elif command == "clamp":
            if state == "WAIT_CLAMP":
                clamp = True
                state = "CLAMPING"
                counter = 0
                message = "Clamp command accepted: manipulator started"
            else:
                message = "Clamp not allowed in this state"

        elif command == "tick":
            (state, counter, motor_on, motor_on2, n1, next_section_available,
             align_stopper, aligned, clamp, message, error_code) = handle_tick(
                state, counter, motor_on, motor_on2, n1, next_section_available,
                align_stopper, aligned, clamp
            )

        else:
            message = "Unknown command"

        status = collect_status(state, motor_on, motor_on2, counter, next_section_available,
                                n1, align_stopper, aligned, clamp)
        print_status(message, status)

        event_type = "command"
        level = "INFO"
        if error_code:
            event_type = "timeout"
            level = "ERROR"
        elif command in ("s1", "s2", "n1"):
            event_type = "sensor"
        elif command in ("next", "tick"):
            event_type = "controller"
        elif command in ("reset", "clearlog", "log"):
            event_type = "maintenance"
        elif command == "clamp":
            event_type = "actuator"

        log_event(command, message, status, event_type=event_type, level=level,
                  error_code=error_code, enabled=logging_enabled, run_id=run_id)

        if should_exit:
            print("Simulation finished.")
            break


if __name__ == "__main__":
    main()