import os
import json
import uuid
from datetime import datetime

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
LOG_FILE = os.path.join(BASE_DIR, "events.jsonl")


# ---------- state ----------
def reset_system() -> dict:
    # Single source of truth: whole system state in one dict
    return {
        "state": "WAIT_EMPTY",
        "counter": 0,
        "entry_present": False,
        "at_end_present": False,
        "next_free":True,
        "station_clear": True,
        "motor_on": False,
        "motor_on2": False,
        "completed_count": 0,
        "n1": False,
        "align_stopper": False,
        "aligned": False,     # meaning: aligned by stopper (longitudinal)
        "clamp": False,       # meaning: clamping process active
        "clamped": False, # meaning: clamp finished / holding
        "error_code": None,
        "error_msg": "",
    }


# ---------- helpers ----------
def print_status(message: str, st: dict) -> None:
    print(message)
    #print(f"At entry: {'YES' if st['entry_present'] else 'NO'}")
    #print(f"At end position: {'YES' if st['at_end_present'] else 'NO'}")
    #print(f"Station clear: {'YES' if st['station_clear'] else 'NO'}")
    #print(f"Next section: {'FREE' if st['next_free'] else 'BLOCKED'}")
    print(f"Current state: {st['state']}")
    print(f"Motor: {'ON' if st['motor_on'] else 'OFF'}")
    print(f"Motor_next_link: {'ON' if st['motor_on2'] else 'OFF'}")
    print(f"Counter: {st['counter']}")
    print(f"Alignator: {'STUCK OUT' if st['align_stopper'] else 'STUCK IN'}")
    print(f"Radiator aligned: {'YES' if st['aligned'] else 'NO'}")
    print(f"Clamping: {'YES' if st['clamp'] else 'NO'}")
    print(f"Clamped: {'YES' if st['clamped'] else 'NO'}")


def clear_log_file() -> None:
    open(LOG_FILE, "w", encoding="utf-8").close()

def deny_transfer(st: dict) -> None:
    """Safety: cancel any transfer attempt outputs."""
    st["motor_on2"] = False
    st["align_stopper"] = False

def log_event(run_id: str, command: str, message: str, st: dict,
              event_type: str = "command", level: str = "INFO",
              error_code: str | None = None, enabled: bool = True) -> None:
    if not enabled:
        return

    event = {
        "run_id": run_id,
        "ts": datetime.now().isoformat(timespec="seconds"),
        "command": command,
        "event_type": event_type,
        "level": level,
        "error_code": error_code,
        "message": message,
        "state": st.get("state"),
        "status": st  # snapshot
    }

    try:
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(json.dumps(event, ensure_ascii=False) + "\n")
    except Exception as e:
        print(f"[LOG ERROR] {e}")


# ---------- core FSM ----------
def handle_tick(st: dict) -> tuple[str, str | None]:
    """
    Tick-based FSM transition.

    Mutates st in-place.
    Returns:
        message (str), error_code (str|None)
    """
    message = "Tick ignored (not moving)"
    error_code = None

    state = st["state"]

    if state == "MOVE_TO_S2":
        st["motor_on"] = True
        st["counter"] += 1
        message = "Tick: moving to S2..."

        if st["counter"] >= 4:
            message = "ERROR: no S2 confirmation (timeout) -> auto reset"
            error_code = "E_S2_TIMEOUT"
            keep_completed = st.get("completed_count", 0)
            st.clear()
            st.update(reset_system())
            st["completed_count"] = keep_completed
            message = "DONE -> reset to WAIT_EMPTY"

    elif state == "PREP_TRANSFER":
        message = "Tick: next section moving, start current section motor -> TRANSFER"
        st ["station_clear"] = False
        st["motor_on"] = True
        st["state"] = "TRANSFER"
        st["counter"] = 0
        st["at_end_present"] = False
    elif state == "TRANSFER":
        st["counter"] += 1
        
        
        if st["n1"]:
            message = "N1 confirmed: hit stopper, waiting clamp"
            st["next_free"] = False
            st["motor_on"] = False
            st["motor_on2"] = True   # push into stopper for ALIGNING phase
            st["state"] = "ALIGNING"
            st["counter"] = 0
            st["n1"] = False

        elif st["counter"] >= 4:
            message = "ERROR: no N1 confirmation (timeout) -> auto reset"
            error_code = "E_N1_TIMEOUT"
            keep_completed = st.get("completed_count", 0)
            st.clear()
            st.update(reset_system())
            st["completed_count"] = keep_completed
        else:
            message = "Transfer in progress: waiting for N1"

    elif state == "ALIGNING":
        st["counter"] += 1
        message = "Aligning in progress..."

        # You chose 1 tick for impact
        if st["counter"] >= 1:
            st["motor_on"] = False
            st["motor_on2"] = False
            st["aligned"] = True
            st["align_stopper"] = False
            st["state"] = "WAIT_CLAMP"
            st["counter"] = 0
            message = "Radiator is aligned (stopper). Waiting clamp."

    elif state == "WAIT_CLAMP":
        # do nothing on tick
        message = "Waiting clamp command (manual manipulator)"

    elif state == "CLAMPING":
        st["counter"] += 1
        st["clamp"] = True
        message = "Clamping in progress..."
        
        if st["counter"] >= 10:
            st["state"] = "ERROR"
            st["motor_on"] = False
            st["motor_on2"] = False
            st["clamp"] = False
            st["error_code"] = "E_CLAMP_TIMEOUT"
            st["error_msg"] = "Clamp did not finish in time"
            message = "ERROR: clamp timeout -> manual reset required"
            return message, "E_CLAMP_TIMEOUT"
    
        elif st["counter"] >= 2:
            st["clamped"] = True
            st["clamp"] = False
            
            # Start discharge: next motor moves radiator away
            st["motor_on"] = False
            st["motor_on2"] = True
            st["state"] = "DISCHARGE"
            st["counter"] = 0
            message = "Clamp finished -> DISCHARGE (next motor moves radiator away)"
            
            

    elif state == "DISCHARGE":
        st["counter"] += 1
        message = "Discharging radiator..."

        if st["counter"] >= 2:
            st ["station_clear"] = True
            st["motor_on2"] = False
            st["clamp"] = False
            st["clamped"] = False
            st["align_stopper"] = False
            st["aligned"] = False
            st["next_free"] = True
            st["state"] = "DONE"
            st["counter"] = 0
            st["completed_count"] += 1
            message = "Radiator discharged. Simulation finished."
            
    return message, error_code


# ---------- main ----------
def main():
    run_id = uuid.uuid4().hex[:8]
    st = reset_system()

    logging_enabled = True
    auto_clear_log_on_start = False

    if auto_clear_log_on_start:
        clear_log_file()

    print("LineCheck Simulator started")
    print("Commands: s1, s2, next, n1, tick, clamp, reset, clearcount, clearlog, log, exit")

    should_exit = False

    while True:
        
        command = input("> ").strip().lower()
        message = ""
        error_code = None
        event_type = "command"
        level = "INFO"
        if st["state"] == "ERROR" and command not in ("reset", "exit", "log", "clearlog"):
            message = "ERROR state: only reset/exit allowed"
            event_type = "qa"
            level = "ERROR"
            error_code = st.get("error_code") or "E_ERROR_LOCK"

            st["motor_on"] = False
            st["motor_on2"] = False

            print_status(message, st)
            log_event(run_id, command, message, st, event_type=event_type, level=level,
                    error_code=error_code, enabled=logging_enabled)
            continue
        
        elif command == "exit":
            message = "Simulation stopped by user"
            should_exit = True

        elif command == "log":
            logging_enabled = not logging_enabled
            message = f"Logging = {logging_enabled}"

        elif command == "clearlog":
            clear_log_file()
            message = "Log cleared"

        elif command == "reset":
            keep_completed = st.get("completed_count", 0)
            st.clear()
            st.update(reset_system())
            st["completed_count"] = keep_completed
            message = "Manual reset: system returned to WAIT_EMPTY"

        elif command == "s1":
            st["entry_present"] = True
            st["counter"] = 1
            st["motor_on"] = True
            st["motor_on2"] = False
            st["n1"] = False
            message = "S1 triggered (radiator detected at entry)"
            
            st["state"] = "MOVE_TO_S2"

        elif command == "s2":
            st["entry_present"] = False
            st["at_end_present"] = True
            st["motor_on"] = False
            st["motor_on2"] = False
            st["counter"] = 0
            message = ("Manual load at S2 (radiator placed manually)" 
            if st["state"] == "WAIT_EMPTY" else "S2 triggered (radiator at end position)")
            
            st["state"] = "AT_END"
            

        elif command == "next":
            event_type = "controller"
            level = "INFO"
            error_code = None
            
            if not st["at_end_present"]:
                message = "Cannot transfer: radiator is not at end position"
                level = "WARN"
                error_code = "E_NO_PART_AT_END"
                event_type="interlock"
                deny_transfer(st)
                
            elif not st["station_clear"]:
                message = "Cannot transfer: station is busy"
                level = "WARN"
                error_code = "E_STATION_BUSY"
                event_type="interlock"
                deny_transfer(st)
                
            elif not st["next_free"]:
                message = "Next section blocked"
                level = "WARN"
                error_code = "E_NEXT_BLOCKED"
                event_type="interlock"
                deny_transfer(st)
                
            else:
                message = "Preparing transfer: starting next section motor + align stopper OUT"
                st["state"] = "PREP_TRANSFER"
                st["motor_on2"] = True
                st["align_stopper"] = True
                
                
        elif command == "n1":
            event_type = "sensor"
            error_code = None
            
            if st["state"] != "TRANSFER":
                message = "N1 ignored: no transfer in progress"
                level = "WARN"
                error_code = "E_N1_UNEXPECTED"
                st["n1"]= False
            
            else:
                st["n1"] = True
                level = "INFO"
                message = "N1 triggered (evaporator detected on next section)"
                message, error_code = handle_tick(st)

        elif command == "clamp":
            event_type = "actuator"
            error_code = None
            
            if st["state"] == "WAIT_CLAMP":
                st["state"] = "CLAMPING"
                st["counter"] = 0
                st["clamp"] = True
                st["clamped"] = False
                # safety: motors off while manipulator starts
                st["motor_on"] = False
                st["motor_on2"] = False
                message = "Clamp command accepted: manipulator started"
                level = "INFO"
                
            else:
                message = "Clamp not allowed in this state"
                level = "WARN"
                error_code = "E_INVALID_STATE"

        elif command == "tick":
            message, error_code = handle_tick(st)
            
            if st["state"] == "DONE":
                
                keep_completed = st.get("completed_count", 0)
                st.clear()
                st.update(reset_system())
                st["completed_count"] = keep_completed
                message = "DONE -> reset to WAIT_EMPTY"
                
        elif command == "clearcount":
            st["completed_count"] = 0
            message = "completed_count reset to 0"
            event_type = "maintenance"    
                
        else:
            message = "Unknown command"

        print_status(message, st)
        
        # event classification
        if error_code and level == "ERROR":
            event_type = "timeout"
            
        elif event_type == "command":
            if command in ("s1", "s2", "n1"):
                event_type = "sensor"
            elif command in ("next", "tick"):
                event_type = "controller"
            elif command in ("reset", "clearlog", "log"):
                event_type = "maintenance"
            elif command == "clamp":
                event_type = "actuator"
        
            
        log_event(run_id, command, message, st, event_type=event_type, level=level,
                  error_code=error_code, enabled=logging_enabled)
        
        
            
        if should_exit:
            print("Simulation finished.")
            break


if __name__ == "__main__":
    main()