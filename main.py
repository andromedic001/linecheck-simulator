import time
import threading
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
        "state_A": "IDLE",
        "state_B": "IDLE",
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
        "counter_A": 0,
        "counter_B": 0, 
        
        "align_stopper": False,
        "aligned": False,     # meaning: aligned by stopper (longitudinal)
        "clamp": False,       # meaning: clamping process active
        "clamped": False, # meaning: clamp finished / holding
        
        "error_code": None,
        "error_msg": "",
        
        "tick": 0,
        "tick_delay": 0.5,
        "auto_run": False, 
        "flow_mode": "normal", #max / normal / random
        "next_feed_in": 3,
        "completed_count": 0,
    }
    
def clear_screen() -> None:
    os.system("cls" if os.name == "nt" else "clear")
    
def print_status(message: str, st: dict) -> None:
    clear_screen()
    print("=" * 50)
    print("LINECHECK SIMULATOR HMI")
    print("=" * 50)
    print(f"Message: {message}\n")

    print(f"Flow mode   : {st['flow_mode']}")
    print(f"Next feed in: {st['next_feed_in']}")
    print(f"Auto run    : {'ON' if st['auto_run'] else 'OFF'}")
    print(f"Tick        : {st['tick']}")
    print(f"Completed   : {st['completed_count']}\n")

    print("LINE OCCUPANCY")
    print(f"U      : {'PART' if st['u_has_part'] else 'EMPTY'}")
    print(f"A      : {'PART' if st['a_has_part'] else 'EMPTY'}")
    print(f"A_END  : {'PART' if st['a_at_end'] else 'EMPTY'}")
    print(f"B      : {'PART' if st['b_has_part'] else 'EMPTY'}")
    print(f"B ready: {'YES' if st['station_ready'] else 'NO'}\n")

    print("MOTORS / ACTUATORS")
    print(f"Motor U      : {'ON' if st['motor_u'] else 'OFF'}")
    print(f"Motor A      : {'ON' if st['motor_a'] else 'OFF'}")
    print(f"Motor B      : {'ON' if st['motor_b'] else 'OFF'}")
    print(f"Align stopper: {'OUT' if st['align_stopper'] else 'IN'}")
    print(f"Aligned      : {'YES' if st['aligned'] else 'NO'}")
    print(f"Clamp        : {'ON' if st['clamp'] else 'OFF'}")
    print(f"Clamped      : {'YES' if st['clamped'] else 'NO'}\n")

    print("SECTION STATES")
    print(f"State A   : {st['state_A']}")
    print(f"State B   : {st['state_B']}")
    print(f"Counter A : {st['counter_A']}")
    print(f"Counter B : {st['counter_B']}\n")

    print("Commands: run, stop, stepauto, feed, s2a, reset, flow max/normal/random, log, exit")
    print("=" * 50)
# ---------- helpers ----------
'''
def print_status(message: str, st: dict) -> None:
    print(message)
    print(f"Flow mode: {st['flow_mode']}")
    print(f"Next feed in: {st['next_feed_in']}")
    print(f"Auto run: {'ON' if st['auto_run'] else 'OFF'}\n")
    print(f"Section 'U' has a part: {'YES' if st['u_has_part'] else 'NO'}")
    print(f"Section 'A' has a part: {'YES' if st['a_has_part'] else 'NO'}")
    print(f"Section 'A' at end position: {'YES' if st['a_at_end'] else 'NO'}")
    print(f"Section 'B' has a part: {'YES' if st['b_has_part'] else 'NO'}")
    print(f"Station clear: {'YES' if st['station_ready'] else 'NO'}\n")
    print(f"Motor_previous_line: {'ON' if st['motor_u'] else 'OFF'}")
    print(f"Motor_current_line: {'ON' if st['motor_a'] else 'OFF'}")
    print(f"Motor_next_line: {'ON' if st['motor_b'] else 'OFF'}\n")
    print(f"Counter section A: {st['counter_A']}")
    print(f"Counter section B: {st['counter_B']}\n")
    print(f"Alignator: {'STUCK OUT' if st['align_stopper'] else 'STUCK IN'}")
    print(f"Radiator aligned: {'YES' if st['aligned'] else 'NO'}")
    print(f"Clamping: {'YES' if st['clamp'] else 'NO'}")
    print(f"Clamped: {'YES' if st['clamped'] else 'NO'}\n")
    print(f"Current state section A: {st['state_A']}")
    print(f"Current state section B: {st['state_B']}")
    print(f"Global completed count: {st['completed_count']}")
    print(f"Global tick: {st['tick']}")
'''
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
        "state_A": st.get("state_A"),
        "state_B": st.get("state_B"),
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
    state_A = st["state_A"]
    state_B = st["state_B"]
    message = "Tick ignored (not moving)"
    st["tick"] += 1
    
    error_code = None
    level = "INFO"
    event_type = "controller"
    
    section_A_ready = (not st["a_has_part"]) and (not st["a_at_end"])
    
    # CASCADE START

    # A begin to A end section Transfer
    if (st["a_has_part"] and st["state_A"] == "IDLE"): 
        message = "Cascade A -> A at end transfer starting"
        
        st["state_A"] = "MOVE_TO_S2A"
        
        return message, None, "INFO", "controller"
    
    # U -> A Transfer
    elif (st["u_has_part"] and section_A_ready 
        and st["state_A"] == "IDLE"): 
        message = "Cascade: U -> A transfer starting"
        
        st["state_A"] = "PREP_TRANSFER_S1A"
        
        return message, None, "INFO", "controller"
    
    
    
    # FINITE STATE MACHINE 
    elif st["state_B"] == "DISCHARGE":
        message = "Discharging radiator..."
        st["counter_B"] += 1
        

        if st["counter_B"] >= 2:
            message = "Radiator discharged -> system ready for next part."
            
            st["motor_b"] = False
            st["counter_B"] = 0
            
            st["align_stopper"] = False
            st["aligned"] = False
            st["clamp"] = False
            st["clamped"] = False
            
            st ["station_ready"] = True
            st["b_has_part"] = False

            st["completed_count"] += 1  
            st["state_B"] = "IDLE" 
            
    elif st["state_B"] == "CLAMPING":
        message = "Clamping in progress..."
        
        st["counter_B"] += 1
        st["clamp"] = True

        if st["counter_B"] >= 10:
            message = "ERROR: clamp timeout -> manual reset required"
            st["error_msg"] = "Clamp did not finish in time"
            
            st["motor_a"] = False
            st["motor_b"] = False
            
            st["clamp"] = False
            
            st["error_code"] = "E_CLAMP_TIMEOUT"
            level = "ERROR"
            event_type = "manual_reset"
            
            st["state_B"] = "ERROR"
            return message, "E_CLAMP_TIMEOUT", level, event_type
    
        elif st["counter_B"] >= 2:
            message = "Clamp finished -> DISCHARGE (next motor moves radiator away)"
            
            st["motor_a"] = False
            st["motor_b"] = True 
            st["counter_B"] = 0
            
            st["clamped"] = True
            st["clamp"] = False
            
            st["state_B"] = "DISCHARGE"
            
    elif st["state_B"] == "WAIT_CLAMP":
        message = "Auto clamp start"
        
        st["clamp"] = True
        st["clamped"] = False
        st["counter_B"] = 0
        
        st["state_B"] = "CLAMPING"
        
    elif st["state_B"] == "ALIGNING":
        st["counter_B"] += 1
        message = "Aligning in progress..."

        # You chose 1 tick for impact
        if st["counter_B"] >= 1:
            message = "Radiator is aligned (stopper)"
            
            st["motor_a"] = False
            st["motor_b"] = False
            st["counter_B"] = 0
            
            st["aligned"] = True
            st["align_stopper"] = False
            
            st["state_B"] = "WAIT_CLAMP"
    
    elif st["state_B"] == "TRANSFER_S1B":
        message = "Transfer in progress: moving A -> B"
        
        st["counter_B"] += 1
        
        if st["S1B"]:
            message = "S1B confirmed: hit stopper, pushing a part into align stopper (1 sec)"
            st["S1B"] = False
            
            st["motor_a"] = False
            st["motor_b"] = True   # push into stopper for ALIGNING phase
            st["counter_B"] = 0

            st["b_has_part"] = True
            st["a_at_end"] = False
            
            st["state_A"] = "IDLE"
            st["state_B"] = "ALIGNING"
            
        # Auto sensor S1B after 1 tick
        if st["counter_B"] >= 1:
            message = "Auto S1B confirmed: hit stopper, pushing a part into align stopper (1 sec)"
            st["S1B"] = False
            
            st["motor_a"] = False
            st["motor_b"] = True   # push into stopper for ALIGNING phase
            st["counter_B"] = 0

            st["b_has_part"] = True
            st["a_at_end"] = False
            
            st["state_A"] = "IDLE"
            st["state_B"] = "ALIGNING"
                
        elif st["counter_B"] >= 4:
            error_code = "E_S1B_TIMEOUT"
            level = "WARN"
            event_type = "auto_recover"
            
            if st["a_has_part"]:
                message = "WARN: S1B timeout in line zone -> auto reset to 'MOVE_TO_S2A' state (operator may have removed part)"
                st["S1B"] = False
                
                st["motor_a"] = False
                st["motor_b"] = False
                st["counter_A"] = 0
                
                st["state_A"] = "MOVE_TO_S2A"   # new state name only, logic minimal
                
            elif st["a_at_end"]:
                message = "WARN: S1B timeout in line zone -> auto reset to 'AT_END' state (operator may have removed part)"
                st["S1B"] = False
                
                st["motor_a"] = False
                st["motor_b"] = False
                st["counter_A"] = 0
                
                st["state_A"] = "AT_END"
            else:    
                keep_completed = st.get("completed_count", 0)
                st.clear()
                st.update(reset_system())
                st["completed_count"] = keep_completed
                message = "WARN: S1B timeout in line zone -> auto reset: system returned to IDLE"
            
        else:
            message = "Transfer in progress: waiting for S1B"
            
    elif st["state_B"] == "PREP_TRANSFER_S1B":
        message = "Tick: next section moving, start current section motor -> TRANSFER"

        st["motor_a"] = True
        st["counter_B"] = 0
        
        st["a_at_end"] = True
        st["station_ready"] = False
        
        st["state_B"] = "TRANSFER_S1B"
        
        

             
    if st["state_A"] == "AT_END":
            event_type = "controller"
            level = "INFO"
            error_code = None
            
            if not st["a_at_end"]:
                message = "WARN: AT_END without a_at_end -> forcing IDLE"
                
                st["counter_B"] = 0
                
                level = "WARN"
                error_code = "E_STATE_MISMATCH"
                event_type = "qa"
                
                deny_transfer(st)
                
                st["state_A"] = "IDLE"
                
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
                
                st["state_B"] = "PREP_TRANSFER_S1B"
    
    elif st["state_A"] == "MOVE_TO_S2A":
        message = "Tick: moving to S2A..."
        
        st["motor_a"] = True
        st["counter_A"] += 1
        
        # Auto sensor S2A after 2 ticks
        if st["counter_A"] >= 2:
            message = "Auto S2A confirmed -> AT_END"
            
            st["a_at_end"]=True
            st["a_has_part"] = False
            
            st["motor_a"] = False
            st["counter_A"] = 0
            
            st["state_A"] = "AT_END"
            
        if st["counter_A"] >= 4:
            error_code = "E_S2A_TIMEOUT"
            event_type = "auto_recover"
            level = "WARN"
            
            if st["a_has_part"]:
                message = "WARN: S2A timeout in line zone -> auto reset to 'MOVE_TO_S2A' state (operator may have removed part)"
                
                st["motor_a"] = False
                st["motor_b"] = False
                st["counter_A"] = 0
                
                st["state_A"] = "MOVE_TO_S2A"
                
            elif st["a_at_end"]:
                message = "WARN: S2A timeout in line zone -> auto reset to 'AT_END' state (operator may have removed part)"
                
                st["motor_a"] = False
                st["motor_b"] = False
                st["counter_A"] = 0
                
                st["state_A"] = "AT_END"
                
            else:
                message = "WARN: S2A timeout in line zone -> auto reset to 'IDLE' state (operator may have removed part)"
                
                keep_completed = st.get("completed_count", 0)
                st.clear()
                st.update(reset_system())
                st["completed_count"] = keep_completed   
    
    elif st["state_A"] == "TRANSFER_S1A":
        message = "Tick: moving upstream part -> S1A (waiting for S1A sensor)"
        
        st["motor_u"] = True
        st["motor_a"] =  True
        st["counter_A"] += 1
        
        if st["S1A"]:
            message = "Auto S1A confirmed -> moving to S2A"
            st["S1A"] = False
            
            st["motor_u"] = False
            st["motor_a"] = False
            st["counter_A"] = 0
            
            st["a_has_part"] = True
            st["u_has_part"] = False

            st["state_A"] = "MOVE_TO_S2A"
            
            return message, error_code, level, event_type
        
        # Auto sensor S1A after 1 tick
        if st["counter_A"] >= 1:
            message = "Auto S1A confirmed -> moving to S2A"
            st["S1A"] = False
            
            st["motor_u"] = False
            st["motor_a"] = False
            st["counter_A"] = 0
            
            st["a_has_part"] = True
            st["u_has_part"] = False

            st["state_A"] = "MOVE_TO_S2A"
            
            return message, error_code, level, event_type
        
        
        if st["counter_A"] >= 4:
            message = "WARN: S1A timeout in line zone -> auto reset to 'IDLE' state (operator may have removed part)"
            
            error_code = "E_S1A_TIMEOUT"
            event_type = "auto_recover"
            level = "WARN"
  
            keep_completed = st.get("completed_count", 0)
            st.clear()
            st.update(reset_system())
            st["completed_count"] = keep_completed
                
    elif st["state_A"] == "PREP_TRANSFER_S1A":
        message = "Tick: transfer of an evaporator to S1A" 
        
        st["motor_u"] = True
        st["motor_a"] =  True
        st["counter_A"] += 1

        st["state_A"] = "TRANSFER_S1A" 
               
    elif st["u_has_part"] and (not st["a_has_part"]) and st["state_A"] == "IDLE":
            message = "Tick: preparing motor of the next section to transfer to S1A"
            
            st["motor_u"] = False
            st["motor_a"] = True
            st["counter_A"] = 0
 
            st["state_A"] = "PREP_TRANSFER_S1A"
            
            return message, error_code, level, event_type
                                
    return message, error_code, level, event_type


# ---------- main ----------
def main():
    run_id = uuid.uuid4().hex[:8]
    st = reset_system()
    state_lock = threading.Lock()
    auto_thread = None
    
    import random
    
    def generate_next_feed_interval(mode: str) -> int:
        if mode == "max":
            return random.randint(3,4)
        elif mode == "normal":
            return random.randint(4,6)
        elif mode == "random":
            return random.randint(3,10)
        return 3
    
    def try_auto_feed(st:dict) -> str | None:
        if st["u_has_part"]:
            return None
        
        st["u_has_part"] = True
        return "AUTO FEED: new part arrived at U"
    
    
    def do_auto_step(st:dict):
            message, error_code, level, event_type = handle_tick(st)
            auto_msg = None
            st["next_feed_in"]-=1
            
            if st["next_feed_in"] <= 0:
                auto_msg = try_auto_feed(st)
                st["next_feed_in"] = generate_next_feed_interval(st["flow_mode"])
                
            if auto_msg:
                message = f"{message} | {auto_msg}"
                
            return message, error_code, level, event_type
        
    def auto_run_loop():
        nonlocal should_exit
        while True:
            with state_lock:
                if st["tick"] % 5 == 0:
                    print_status("Auto update", st)
                if not st["auto_run"] or should_exit:
                    break
                message, error_code, level, event_type = do_auto_step(st)
                
                log_event(
                    run_id,
                    "auto_tick",
                    message,
                    st,
                    event_type = event_type,
                    level = level,
                    error_code = error_code,
                    enabled = logging_enabled,
                )
            time.sleep(st["tick_delay"])
    logging_enabled = True
    auto_clear_log_on_start = False

    if auto_clear_log_on_start:
        clear_log_file()

    print("LineCheck Simulator started")
    print("Commands: run, stop, flow (max / normal / random), stepauto, feed, S1A, S2A, S1B, tick, reset, clearcount, clearlog, log, exit")

    should_exit = False

    while True:
        
        command = input("> ").strip().lower()
        message = ""
        
        error_code = None
        event_type = "command"
        level = "INFO"
        
        
                
        if (st["state_A"]  == "ERROR" or st["state_B"] == "ERROR") and command not in ("reset", "exit", "log", "clearlog", "clearcount"):
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
            with state_lock:
                message = "Simulation stopped by user"
                
                should_exit = True

        elif command == "log":
            logging_enabled = not logging_enabled
            message = f"Logging = {logging_enabled}"

        elif command == "clearlog":
            clear_log_file()
            message = "Log cleared"

        elif command == "reset":
            with state_lock:
                if st["a_has_part"]:
                    message = "Manual reset: returning to 'MOVE_TO_S2A' state"
                    
                    st["motor_a"] = False
                    st["counter_A"] = 0
                    
                    st["state_A"] = "MOVE_TO_S2A"   # new state name only, logic minimal
                    
                elif st["a_at_end"]:
                    message = "Manual reset: returning to 'AT_END' state"
                    
                    st["motor_a"] = False
                    st["counter_A"] = 0
                    
                    st["state_A"] = "AT_END"
                    
                else:    
                    message = "Manual reset: system returned to IDLE"
                    
                    keep_completed = st.get("completed_count", 0)
                    st.clear()
                    st.update(reset_system())
                    st["completed_count"] = keep_completed
                
        elif command == "run":
            with state_lock:
                if st["auto_run"]:
                    message = "Auto run is already ON"
                    level = "WARN"
                
                else:
                    message = "Auto run -> ON"
                    st["auto_run"] = True
                    
                    auto_thread = threading.Thread(target = auto_run_loop, daemon = True)
                    auto_thread.start()
                    
                '''    
                print_status(message, st)
                
                log_event(run_id, command, message, st, event_type = "controller", level = "INFO", error_code = None, enabled = logging_enabled)
               
                while st["auto_run"]:
                    message, error_code, level, event_type = do_auto_step(st)
                    print_status(message, st)
                    
                    log_event(run_id, "auto_tick", message, st, event_type = event_type, level = level, error_code = error_code, enabled = logging_enabled)
                    
                    time.sleep(st["tick_delay"])
            '''
        elif command == "stop":
            with state_lock:
                if not st["auto_run"]:
                    message = "Auto run is already OFF"
                    level = "WARN"
                
                else:
                    message = "Auto run -> OFF"
                    st["auto_run"] = False     
            
        elif command.startswith("flow "):
            with state_lock:
                mode = command.split(" ", 1)[1].strip()
                
                if mode in ("max", "normal", "random"):
                    st["flow_mode"] = mode
                    st["next_feed_in"] = generate_next_feed_interval(mode)
                    
                    message = f"Flow mode set to {mode}"
                
                else:
                    message = "Unknown flow mode"
                
        elif command == "stepauto":
            with state_lock:
                message, error_code, level, event_type = do_auto_step(st)
                
                event_type = do_auto_step(st)
            
        elif command == "feed":
            with state_lock:
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

            
        elif command == "s2a":
            with state_lock:
                message = ("Manual load at S2A (radiator placed manually)" 
                if st["state_A"] == "IDLE" else "S2A triggered (radiator at end position)")
                
                st["motor_a"] = False
                st["motor_b"] = False
                st["counter_A"] = 0
                
                st["a_has_part"] = False
                st["a_at_end"] = True
                
                st["state_A"] = "AT_END"
            
                
        elif command == "tick":
            with state_lock:
                message, error_code, level, event_type = handle_tick(st)
                                
        elif command == "clearcount":
            with state_lock:
                message = "completed_count reset to 0"
                
                st["completed_count"] = 0
                
                event_type = "maintenance"    
                
        else:
            message = "Unknown command"

        print_status(message, st)
        
        # event classification
        if event_type == "command":
            #if command in ("s1a", "s2a", "s1b"):
                #event_type = "sensor"
            if command == "tick":
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