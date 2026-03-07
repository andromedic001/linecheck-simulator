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
        "S1A": False,
        "S1B": False,
    
        "u_has_part": False,
        "a_has_part": False,
        "a_at_end": False,
        "b_has_part": False,
        "station_ready": True,
        
        "motor_u": False,
        "motor_a": False,
        "motor_b": False,
        "counter": 0, 
        
        "align_stopper": False,
        "aligned": False,     # meaning: aligned by stopper (longitudinal)
        "clamp": False,       # meaning: clamping process active
        "clamped": False, # meaning: clamp finished / holding
        
        "error_code": None,
        "error_msg": "",
        "completed_count": 0,
    }


# ---------- helpers ----------
def print_status(message: str, st: dict) -> None:
    print(message)
    print(f"Section 'U' has a part: {'YES' if st['u_has_part'] else 'NO'}")
    print(f"Section 'A' has a part: {'YES' if st['a_has_part'] else 'NO'}")
    print(f"Section 'A' at end position: {'YES' if st['a_at_end'] else 'NO'}")
    print(f"Section 'B' has a part: {'YES' if st['b_has_part'] else 'NO'}")
    print(f"Station clear: {'YES' if st['station_ready'] else 'NO'}\n")
    print(f"Motor_previous_line: {'ON' if st['motor_u'] else 'OFF'}")
    print(f"Motor_current_line: {'ON' if st['motor_a'] else 'OFF'}")
    print(f"Motor_next_line: {'ON' if st['motor_b'] else 'OFF'}")
    print(f"Counter: {st['counter']}\n")
    print(f"Alignator: {'STUCK OUT' if st['align_stopper'] else 'STUCK IN'}")
    print(f"Radiator aligned: {'YES' if st['aligned'] else 'NO'}")
    print(f"Clamping: {'YES' if st['clamp'] else 'NO'}")
    print(f"Clamped: {'YES' if st['clamped'] else 'NO'}\n")
    print(f"Current state: {st['state']}")

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
    
    # CASCADE START
    
    # A -> B Transfer
    if st["a_at_end"] and not st["b_has_part"] and st["station_ready"] and st["state"] == "WAIT_EMPTY":
        message = "Cascade: A at end -> B transfer starting"
        
        st["state"] = "PREP_TRANSFER_S1B"
        
        return message, None, "INFO", "controller"
    
    # A begin to A end section Transfer
    elif st["a_has_part"] and not st["a_at_end"] and st["state"] == "WAIT_EMPTY":
        message = "Cascade A -> A at end transfer starting"
        
        st["state"] = "MOVE_TO_S2A"
        
        return message, None, "INFO", "controller"
    
    # U -> A Transfer
    elif st["u_has_part"] and not st["a_has_part"] and not st["a_at_end"] and st["state"] == "WAIT_EMPTY":
        message = "Cascade: U -> A transfer starting"
        
        st["state"] = "PREP_TRANSFER_S1A"
        
        return message, None, "INFO", "controller"
    
    
    
    # FINITE STATE MACHINE 
    elif state == "DISCHARGE":
        message = "Discharging radiator..."
        st["counter"] += 1
        

        if st["counter"] >= 2:
            message = "Radiator discharged. Simulation finished."
            
            st["motor_b"] = False
            st["counter"] = 0
            
            st["align_stopper"] = False
            st["aligned"] = False
            st["clamp"] = False
            st["clamped"] = False
            
            st ["station_ready"] = True
            st["b_has_part"] = False

            st["completed_count"] += 1  
            st["state"] = "DONE" 
            
    elif state == "CLAMPING":
        message = "Clamping in progress..."
        
        st["counter"] += 1
        st["clamp"] = True

        if st["counter"] >= 10:
            message = "ERROR: clamp timeout -> manual reset required"
            st["error_msg"] = "Clamp did not finish in time"
            
            st["motor_a"] = False
            st["motor_b"] = False
            
            st["clamp"] = False
            
            st["error_code"] = "E_CLAMP_TIMEOUT"
            level = "ERROR"
            event_type = "manual_reset"
            
            st["state"] = "ERROR"
            return message, "E_CLAMP_TIMEOUT", level, event_type
    
        elif st["counter"] >= 2:
            message = "Clamp finished -> DISCHARGE (next motor moves radiator away)"
            
            st["motor_a"] = False
            st["motor_b"] = True 
            st["counter"] = 0
            
            st["clamped"] = True
            st["clamp"] = False
            
            st["state"] = "DISCHARGE"
            
    elif state == "WAIT_CLAMP":
        message = "Auto clamp start"
        
        st["clamp"] = True
        st["clamped"] = False
        st["counter"] = 0
        
        st["state"] = "CLAMPING"
        
    elif state == "ALIGNING":
        st["counter"] += 1
        message = "Aligning in progress..."

        # You chose 1 tick for impact
        if st["counter"] >= 1:
            message = "Radiator is aligned (stopper)"
            
            st["motor_a"] = False
            st["motor_b"] = False
            st["counter"] = 0
            
            st["aligned"] = True
            st["align_stopper"] = False
            
            st["state"] = "WAIT_CLAMP"
    
    elif state == "TRANSFER_S1B":
        message = "Transfer in progress: moving A -> B"
        
        st["counter"] += 1
        
        if st["S1B"]:
            message = "S1B confirmed: hit stopper, pushing a part into align stopper (1 sec)"
            st["S1B"] = False
            
            st["motor_a"] = False
            st["motor_b"] = True   # push into stopper for ALIGNING phase
            st["counter"] = 0

            st["b_has_part"] = True
            st["a_at_end"] = False
            
            st["state"] = "ALIGNING"
        
        # Auto sensor S1B after 1 tick
        if st["counter"] >= 1:
            message = "Auto S1B confirmed: hit stopper, pushing a part into align stopper (1 sec)"
            st["S1B"] = False
            
            st["motor_a"] = False
            st["motor_b"] = True   # push into stopper for ALIGNING phase
            st["counter"] = 0

            st["b_has_part"] = True
            st["a_at_end"] = False
            
            st["state"] = "ALIGNING"
                
        elif st["counter"] >= 4:
            error_code = "E_S1B_TIMEOUT"
            level = "WARN"
            event_type = "auto_recover"
            
            if st["a_has_part"]:
                message = "WARN: S1B timeout in line zone -> auto reset to 'MOVE_TO_S2A' state (operator may have removed part)"
                st["S1B"] = False
                
                st["motor_a"] = False
                st["motor_b"] = False
                st["counter"] = 0
                
                st["state"] = "MOVE_TO_S2A"   # new state name only, logic minimal
                
            elif st["a_at_end"]:
                message = "WARN: S1B timeout in line zone -> auto reset to 'AT_END' state (operator may have removed part)"
                st["S1B"] = False
                
                st["motor_a"] = False
                st["motor_b"] = False
                st["counter"] = 0
                
                st["state"] = "AT_END"
            else:    
                keep_completed = st.get("completed_count", 0)
                st.clear()
                st.update(reset_system())
                st["completed_count"] = keep_completed
                message = "WARN: S1B timeout in line zone -> auto reset: system returned to WAIT_EMPTY"
            
        else:
            message = "Transfer in progress: waiting for S1B"
            
    elif state == "PREP_TRANSFER_S1B":
        message = "Tick: next section moving, start current section motor -> TRANSFER"

        st["motor_a"] = True
        st["counter"] = 0
        
        st["a_at_end"] = True
        st["station_ready"] = False
        
        st["state"] = "TRANSFER_S1B"
    
        # --- AUTO TRANSFER LOGIC ---        
    elif state == "AT_END":
            event_type = "controller"
            level = "INFO"
            error_code = None
            
            if not st["a_at_end"]:
                message = "WARN: AT_END without a_at_end -> forcing WAIT_EMPTY"
                
                st["counter"] = 0
                
                level = "WARN"
                error_code = "E_STATE_MISMATCH"
                event_type = "qa"
                
                deny_transfer(st)
                
                st["state"] = "WAIT_EMPTY"
                
            elif not st["station_ready"]:
                message = "Cannot transfer: station is busy"
                
                level = "WARN"
                error_code = "E_STATION_BUSY"
                event_type="interlock"
                
                deny_transfer(st)
                
            elif st["b_has_part"]:
                message = "Next section blocked"
                
                level = "WARN"
                error_code = "E_NEXT_BLOCKED"
                event_type="interlock"
                
                deny_transfer(st)
                
            else:
                message = "Preparing transfer: starting next section motor + align stopper OUT"
                
                st["motor_b"] = True
                st["align_stopper"] = True
                
                st["a_at_end"] = True
                st["a_has_part"] = False
                
                st["state"] = "PREP_TRANSFER_S1B"
    
    elif state == "MOVE_TO_S2A":
        message = "Tick: moving to S2A..."
        
        st["motor_a"] = True
        st["counter"] += 1
        
        # Auto sensor S2A after 2 ticks
        if st["counter"] >= 2:
            message = "Auto S2A confirmed -> AT_END"
            
            st["a_at_end"]=True
            st["a_has_part"] = False
            
            st["motor_a"] = False
            st["counter"] = 0
            
            st["state"] = "AT_END"
            
        if st["counter"] >= 4:
            error_code = "E_S2A_TIMEOUT"
            event_type = "auto_recover"
            level = "WARN"
            
            if st["a_has_part"]:
                message = "WARN: S2A timeout in line zone -> auto reset to 'MOVE_TO_S2A' state (operator may have removed part)"
                
                st["motor_a"] = False
                st["motor_b"] = False
                st["counter"] = 0
                
                st["state"] = "MOVE_TO_S2A"
                
            elif st["a_at_end"]:
                message = "WARN: S2A timeout in line zone -> auto reset to 'AT_END' state (operator may have removed part)"
                
                st["motor_a"] = False
                st["motor_b"] = False
                st["counter"] = 0
                
                st["state"] = "AT_END"
                
            else:
                message = "WARN: S2A timeout in line zone -> auto reset to 'WAIT_EMPTY' state (operator may have removed part)"
                
                keep_completed = st.get("completed_count", 0)
                st.clear()
                st.update(reset_system())
                st["completed_count"] = keep_completed   
    
    elif st["state"] == "TRANSFER_S1A":
        message = "Tick: moving upstream part -> S1A (waiting for S1A sensor)"
        
        st["motor_u"] = True
        st["motor_a"] =  True
        st["counter"] += 1
        
        if st["S1A"]:
            message = "Auto S1A confirmed -> moving to S2A"
            st["S1A"] = False
            
            st["motor_u"] = False
            st["motor_a"] = False
            st["counter"] = 0
            
            st["a_has_part"] = True
            st["u_has_part"] = False

            st["state"] = "MOVE_TO_S2A"
            
            return message, error_code, level, event_type
        
        # Auto sensor S1A after 1 tick
        if st["counter"] >= 1:
            message = "Auto S1A confirmed -> moving to S2A"
            st["S1A"] = False
            
            st["motor_u"] = False
            st["motor_a"] = False
            st["counter"] = 0
            
            st["a_has_part"] = True
            st["u_has_part"] = False

            st["state"] = "MOVE_TO_S2A"
            
            return message, error_code, level, event_type
        
        
        if st["counter"] >= 4:
            message = "WARN: S1A timeout in line zone -> auto reset to 'WAIT_EMPTY' state (operator may have removed part)"
            
            error_code = "E_S1A_TIMEOUT"
            event_type = "auto_recover"
            level = "WARN"
  
            keep_completed = st.get("completed_count", 0)
            st.clear()
            st.update(reset_system())
            st["completed_count"] = keep_completed
                
    elif st["state"] == "PREP_TRANSFER_S1A":
        message = "Tick: transfer of an evaporator to S1A" 
        
        st["motor_u"] = True
        st["motor_a"] =  True
        st["counter"] += 1
        
        st["u_has_part"] = True
        st["a_has_part"] = False

        st["state"] = "TRANSFER_S1A" 
               
    elif st["u_has_part"] and (not st["a_has_part"]) and st["state"] == "WAIT_EMPTY":
            message = "Tick: preparing motor of the next section to transfer to S1A"
            
            st["motor_u"] = False
            st["motor_a"] = True
            st["counter"] = 0
 
            st["state"] = "PREP_TRANSFER_S1A"
            
            return message, error_code, level, event_type
                                
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
    print("Commands: feed, S1A, S2A, S1B, tick, reset, clearcount, clearlog, log, exit")

    should_exit = False

    while True:
        
        command = input("> ").strip().lower()
        message = ""
        
        error_code = None
        event_type = "command"
        level = "INFO"
        
        if st["state"] == "ERROR" and command not in ("reset", "exit", "log", "clearlog", "clearcount"):
            message = "ERROR state: only reset, exit, log, clearlog, clearcount allowed"
            
            error_code = st.get("error_code") or "E_ERROR_LOCK"
            event_type = "QA"
            level = "ERROR"

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
                message = "Manual reset: returning to 'MOVE_TO_S2A' state"
                
                st["motor_a"] = False
                st["counter"] = 0
                
                st["state"] = "MOVE_TO_S2A"   # new state name only, logic minimal
                
            elif st["a_at_end"]:
                message = "Manual reset: returning to 'AT_END' state"
                
                st["motor_a"] = False
                st["counter"] = 0
                
                st["state"] = "AT_END"
                
            else:    
                message = "Manual reset: system returned to WAIT_EMPTY"
                
                keep_completed = st.get("completed_count", 0)
                st.clear()
                st.update(reset_system())
                st["completed_count"] = keep_completed
                
                
        elif command == "feed":
            
            if st["u_has_part"]:
                 message = "Feed ignored: upstream already has a part"
                 
                 error_code = "E_FEED_ALREADY_PRESENT"
                 event_type = "QA"
                 level = "WARN"
                 
            else:
                message = "Feed registered: part is at upstream end"
                
                st["u_has_part"] = True
             
                event_type = "sensor"
                level = "INFO"
                
        elif command == "s1a":
            
            if st["state"] not in ("PREP_TRANSFER_S1A", "TRANSFER_S1A"):
                message = "S1A ignored: no transfer"
                st["S1A"] = False
                
                error_code = "E_S1A_UNEXPECTED"
                level = "WARN"
                  
            else:  
                message = "S1A triggered (radiator detected at entry)"
                st["S1A"] = True
                st["S1B"] = False
                
            
        elif command == "s2a":
            message = ("Manual load at S2A (radiator placed manually)" 
            if st["state"] == "WAIT_EMPTY" else "S2A triggered (radiator at end position)")
            
            st["motor_a"] = False
            st["motor_b"] = False
            st["counter"] = 0
            
            st["a_has_part"] = False
            st["a_at_end"] = True
            
            st["state"] = "AT_END"
            
        elif command == "s1b":
            error_code = None
            event_type = "sensor"
            
            
            if st["state"] != "TRANSFER_S1B":
                message = "S1B ignored: no transfer in progress"
                st["S1B"]= False
                
                error_code = "E_S1B_UNEXPECTED"
                level = "WARN"
            
            else:
                message = "S1B triggered (evaporator detected on next section)"
                st["S1B"] = True
                
                level = "INFO"
                
                message, error_code, level, event_type = handle_tick(st)

        elif command == "clamp":
            error_code = None
            event_type = "actuator"

            if st["state"] == "WAIT_CLAMP":
                message = "Clamp command accepted: manipulator started"

                st["clamp"] = True
                st["clamped"] = False
                # safety: motors off while manipulator starts
                st["motor_a"] = False
                st["motor_b"] = False
                st["counter"] = 0
                
                level = "INFO"
                st["state"] = "CLAMPING"
            else: 
                message = "Clamp not allowed in this state"
                
                error_code = "E_INVALID_STATE"
                level = "WARN"
                
        elif command == "tick":
            message, error_code, level, event_type = handle_tick(st)
            
            if st["state"] == "DONE":
                message = "DONE -> reset to WAIT_EMPTY"
                
                keep_completed = st.get("completed_count", 0)
                st.clear()
                st.update(reset_system())
                st["completed_count"] = keep_completed
                
                
        elif command == "clearcount":
            message = "completed_count reset to 0"
            
            st["completed_count"] = 0
            
            event_type = "maintenance"    
                
        else:
            message = "Unknown command"

        print_status(message, st)
        
        # event classification
        if event_type == "command":
            if command in ("s1A", "s2a", "s1b"):
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