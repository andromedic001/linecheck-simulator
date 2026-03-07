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
        "u_has_part": False,
        "a_has_part": False,
        "a_at_end": False,
        "b_has_part":True,
        "station_ready": True,
        "motor_u": False,
        "motor_a": False,
        "motor_b": False,
        "completed_count": 0,
        "s1_a": False,
        "s1_b": False,
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
    #print(f"At entry: {'YES' if st['a_has_part'] else 'NO'}")
    #print(f"At end position: {'YES' if st['a_at_end'] else 'NO'}")
    #print(f"Station clear: {'YES' if st['station_ready'] else 'NO'}")
    #print(f"Next section: {'FREE' if st['b_has_part'] else 'BLOCKED'}")
    print(f"Current state: {st['state']}")
    print(f"Motor_previous_line: {'ON' if st['motor_u'] else 'OFF'}")
    print(f"Motor_current_line: {'ON' if st['motor_a'] else 'OFF'}")
    print(f"Motor_next_line: {'ON' if st['motor_b'] else 'OFF'}")
    print(f"Counter: {st['counter']}")
    print(f"Alignator: {'STUCK OUT' if st['align_stopper'] else 'STUCK IN'}")
    print(f"Radiator aligned: {'YES' if st['aligned'] else 'NO'}")
    print(f"Clamping: {'YES' if st['clamp'] else 'NO'}")
    print(f"Clamped: {'YES' if st['clamped'] else 'NO'}")


def clear_log_file() -> None:
    open(LOG_FILE, "w", encoding="utf-8").close()

def deny_transfer(st: dict) -> None:
    """Safety: cancel any transfer attempt outputs."""
    st["motor_b"] = False
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
def handle_tick(st: dict) -> tuple[str, str | None, str, str]:
    """
    Tick-based FSM transition.

    Mutates st in-place.
    Returns:
        message (str), error_code (str|None)
    """
    state = st["state"]
    message = "Tick ignored (not moving)"
    error_code = None
    level = "INFO"
    event_type = "controller"
    
            
    if st["u_has_part"] and (not st["a_has_part"]) and st["state"] in ("WAIT_EMPTY", "WAIT_ENTRY"):
            st["a_has_part"] = False
            st["motor_u"] = False
            st["motor_a"] = True
            st["u_has_part"] = True
            st["counter"] = 0
            message = "Tick: preparing motor of the next section to transfer to s1_a"
            
            st["state"] = "PREP_TRANSFER_s1_a"
            
            return message, error_code, level, event_type
                                
    elif st["state"] == "PREP_TRANSFER_s1_a":
        st["motor_u"] = True
        st["motor_a"] =  True
        st["a_has_part"] = False
        st["u_has_part"] = False
        st["counter"] += 1
        
        message = "Tick: transfer of an evaporator to s1_a"       
        st["state"] = "TRANSFER_s1_a"
    
    elif st["state"] == "TRANSFER_s1_a":
        st["counter"] += 1
        st["motor_u"] = True
        st["motor_a"] =  True
        message = "Tick: moving upstream part -> s1_a (waiting for s1_a sensor)"
        
        if st["s1_a"]:
            st["s1_a"] = False
            st["u_has_part"] = False
            st["a_has_part"] = True
            
            st["motor_u"] = False
            st["motor_a"] = False
            st["counter"] = 0
            message = "s1_a confirmed -> moving to s2_a"
            
            st["state"] = "MOVE_TO_s2_a"
            
            return message, error_code, level, event_type
        
        if st["counter"] >= 4:
            error_code = "E_s1_a_TIMEOUT"
            level = "WARN"
            event_type = "auto_recover"
                
            if st["a_has_part"]:
                st["state"] = "WAIT_ENTRY"   # new state name only, logic minimal
                st["s1_a"] = False
                st["motor_u"] = False
                st["motor_a"] = False
                st["motor_b"] = False
                st["counter"] = 0
                message = "WARN: s1_a timeout in line zone -> auto reset to 'WAIT_ENTRY' state (operator may have removed part)"
                    
            else:
                message = "WARN: s1_a timeout in line zone -> auto reset to 'WAIT_EMPTY' state (operator may have removed part)"
                keep_completed = st.get("completed_count", 0)
                st.clear()
                st.update(reset_system())
                st["completed_count"] = keep_completed  
                                        
    elif state == "MOVE_TO_s2_a":
        st["motor_a"] = True
        st["counter"] += 1
        message = "Tick: moving to s2_a..."
        
        if st["counter"] >= 4:
            error_code = "E_s2_a_TIMEOUT"
            level = "WARN"
            event_type = "auto_recover"
            
            if st["a_has_part"]:
                st["state"] = "WAIT_ENTRY"   # new state name only, logic minimal
                st["motor_a"] = False
                st["motor_b"] = False
                st["counter"] = 0
                message = "WARN: s2_a timeout in line zone -> auto reset to 'WAIT_ENTRY' state (operator may have removed part)"
                
            elif st["a_at_end"]:
                st["state"] = "AT_END"
                st["motor_a"] = False
                st["motor_b"] = False
                st["counter"] = 0
                message = "WARN: s2_a timeout in line zone -> auto reset to 'AT_END' state (operator may have removed part)"
                
            else:
                message = "WARN: s2_a timeout in line zone -> auto reset to 'WAIT_EMPTY' state (operator may have removed part)"
                keep_completed = st.get("completed_count", 0)
                st.clear()
                st.update(reset_system())
                st["completed_count"] = keep_completed
                
    elif state == "WAIT_ENTRY":
        message = "WAIT_ENTRY: part present, operator buffer (manual s1_a/s2_a or next tick logic later)"     
           
    # --- AUTO TRANSFER LOGIC ---        
    elif state == "AT_END":
            event_type = "controller"
            level = "INFO"
            error_code = None
            
            if not st["a_at_end"]:
                message = "WARN: AT_END without a_at_end -> forcing WAIT_EMPTY"
                level = "WARN"
                error_code = "E_STATE_MISMATCH"
                event_type = "qa"
                st["state"] = "WAIT_EMPTY"
                deny_transfer(st)
                st["counter"] = 0
                
            elif not st["station_ready"]:
                message = "Cannot transfer: station is busy"
                level = "WARN"
                error_code = "E_STATION_BUSY"
                event_type="interlock"
                deny_transfer(st)
                
            elif not st["b_has_part"]:
                message = "Next section blocked"
                level = "WARN"
                error_code = "E_NEXT_BLOCKED"
                event_type="interlock"
                deny_transfer(st)
                
            else:
                message = "Preparing transfer: starting next section motor + align stopper OUT"
                st["state"] = "PREP_TRANSFER"
                st["motor_b"] = True
                st["align_stopper"] = True
                                                      
    elif state == "PREP_TRANSFER":
        message = "Tick: next section moving, start current section motor -> TRANSFER"
        st["station_ready"] = False
        st["motor_a"] = True
        st["state"] = "TRANSFER"
        st["counter"] = 0
        st["a_at_end"] = False
        
    elif state == "TRANSFER":
        st["counter"] += 1
        
        if st["s1_b"]:
            message = "s1_b confirmed: hit stopper, waiting clamp"
            st["b_has_part"] = False
            st["motor_a"] = False
            st["motor_b"] = True   # push into stopper for ALIGNING phase
            st["state"] = "ALIGNING"
            st["counter"] = 0
            st["s1_b"] = False

        elif st["counter"] >= 4:
            error_code = "E_s1_b_TIMEOUT"
            level = "WARN"
            event_type = "auto_recover"
            
            if st["a_has_part"]:
                st["state"] = "WAIT_ENTRY"   # new state name only, logic minimal
                st["motor_a"] = False
                st["motor_b"] = False
                st["s1_b"] = False
                st["counter"] = 0
                message = "WARN: s1_b timeout in line zone -> auto reset to 'WAIT_ENTRY' state (operator may have removed part)"
                
            elif st["a_at_end"]:
                st["state"] = "AT_END"
                st["motor_a"] = False
                st["motor_b"] = False
                st["s1_b"] = False
                st["counter"] = 0
                message = "WARN: s1_b timeout in line zone -> auto reset to 'AT_END' state (operator may have removed part)"
            else:    
                keep_completed = st.get("completed_count", 0)
                st.clear()
                st.update(reset_system())
                st["completed_count"] = keep_completed
                message = "WARN: s1_b timeout in line zone -> auto reset: system returned to WAIT_EMPTY"
            
        else:
            message = "Transfer in progress: waiting for s1_b"

    elif state == "ALIGNING":
        st["counter"] += 1
        message = "Aligning in progress..."

        # You chose 1 tick for impact
        if st["counter"] >= 1:
            st["motor_a"] = False
            st["motor_b"] = False
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
            level = "ERROR"
            event_type = "manual_reset"
            st["motor_a"] = False
            st["motor_b"] = False
            st["clamp"] = False
            st["error_code"] = "E_CLAMP_TIMEOUT"
            
            st["error_msg"] = "Clamp did not finish in time"
            message = "ERROR: clamp timeout -> manual reset required"
            return message, "E_CLAMP_TIMEOUT", level, event_type
    
        elif st["counter"] >= 2:
            st["clamped"] = True
            st["clamp"] = False
            
            # Start discharge: next motor moves radiator away
            st["motor_a"] = False
            st["motor_b"] = True
            st["state"] = "DISCHARGE"
            st["counter"] = 0
            message = "Clamp finished -> DISCHARGE (next motor moves radiator away)"
            
            

    elif state == "DISCHARGE":
        st["counter"] += 1
        message = "Discharging radiator..."

        if st["counter"] >= 2:
            st ["station_ready"] = True
            st["motor_b"] = False
            st["clamp"] = False
            st["clamped"] = False
            st["align_stopper"] = False
            st["aligned"] = False
            st["b_has_part"] = True
            st["state"] = "DONE"
            st["counter"] = 0
            st["completed_count"] += 1
            message = "Radiator discharged. Simulation finished."
            
    return message, error_code, level, event_type


# ---------- main ----------
def main():
    run_id = uuid.uuid4().hex[:8]
    st = reset_system()

    logging_enabled = True
    auto_clear_log_on_start = False

    if auto_clear_log_on_start:
        clear_log_file()

    print("LineCheck Simulator started")
    print("Commands: feed, s1_a, s2_a, s1_b, tick, clamp, reset, clearcount, clearlog, log, exit")

    should_exit = False

    while True:
        
        command = input("> ").strip().lower()
        message = ""
        error_code = None
        event_type = "command"
        level = "INFO"
        if st["state"] == "ERROR" and command not in ("reset", "exit", "log", "clearlog", "clearcount"):
            message = "ERROR state: only reset, exit, log, clearlog, clearcount allowed"
            event_type = "QA"
            level = "ERROR"
            error_code = st.get("error_code") or "E_ERROR_LOCK"

            st["motor_a"] = False
            st["motor_b"] = False

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
            if st["a_has_part"]:
                st["state"] = "WAIT_ENTRY"   # new state name only, logic minimal
                st["motor_a"] = False
                st["counter"] = 0
                message = "Manual reset: returning to 'WAIT_ENTRY' state"
                
            elif st["a_at_end"]:
                st["state"] = "AT_END"
                st["motor_a"] = False
                st["counter"] = 0
                message = "Manual reset: returning to 'AT_END' state"
                
            else:    
                keep_completed = st.get("completed_count", 0)
                st.clear()
                st.update(reset_system())
                st["completed_count"] = keep_completed
                message = "Manual reset: system returned to WAIT_EMPTY"
                
        elif command == "feed":
            if st["u_has_part"]:
                 message = "Feed ignored: upstream already has a part"
                 level = "WARN"
                 error_code = "E_FEED_ALREADY_PRESENT"
                 event_type = "QA"
                 
            else:
                st["u_has_part"] = True
                message = "Feed registered: part is at upstream end"
                level = "INFO"
                event_type = "sensor"
                
        elif command == "s1_a":
            
            if st["state"] not in ("PREP_TRANSFER_s1_a", "TRANSFER_s1_a"):
                message = "s1_a ignored: no transfer"
                level = "WARN"
                error_code = "E_s1_a_UNEXPECTED"
                st["s1_a"] = False
                
            else:  
                st["s1_a"] = True
                st["s1_b"] = False
                message = "s1_a triggered (radiator detected at entry)"
            
        elif command == "s2_a":
            st["a_has_part"] = False
            st["a_at_end"] = True
            st["motor_a"] = False
            st["motor_b"] = False
            st["counter"] = 0
            message = ("Manual load at s2_a (radiator placed manually)" 
            if st["state"] == "WAIT_EMPTY" else "s2_a triggered (radiator at end position)")
            
            st["state"] = "AT_END"
            
        elif command == "s1_b":
            event_type = "sensor"
            error_code = None
            
            if st["state"] != "TRANSFER":
                message = "s1_b ignored: no transfer in progress"
                level = "WARN"
                error_code = "E_s1_b_UNEXPECTED"
                st["s1_b"]= False
            
            else:
                st["s1_b"] = True
                level = "INFO"
                message = "s1_b triggered (evaporator detected on next section)"
                message, error_code, level, event_type = handle_tick(st)

        elif command == "clamp":
            event_type = "actuator"
            error_code = None
            
            if st["state"] == "WAIT_CLAMP":
                st["state"] = "CLAMPING"
                st["counter"] = 0
                st["clamp"] = True
                st["clamped"] = False
                # safety: motors off while manipulator starts
                st["motor_a"] = False
                st["motor_b"] = False
                message = "Clamp command accepted: manipulator started"
                level = "INFO"
                
            else:
                message = "Clamp not allowed in this state"
                level = "WARN"
                error_code = "E_INVALID_STATE"

        elif command == "tick":
            message, error_code, level, event_type = handle_tick(st)
            
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
        if event_type == "command":
            if command in ("s1_a", "s2_a_a", "s1_b"):
                event_type = "sensor"
            elif command == "tick":
                event_type = "controller"
            elif command in ("reset", "clearlog", "log", "clearcount"):
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