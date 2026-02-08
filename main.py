import os
import json  
import uuid   
from datetime import datetime

def collect_status(state, motor_on, motor_on2, counter, next_section_available, n1):
    return{
        "state":state,
        "motor_on":motor_on,
        "motor_on2":motor_on2,
        "counter":counter,
        "next_section_available":next_section_available,
        "next_sensor":n1
    }

def print_status(message, status):
    print(message)
    print(f"Current state: {status['state']}")
    print(f"Motor: {'ON' if status['motor_on'] else 'OFF'}")
    print(f"Motor_next_link: {'ON' if status['motor_on2'] else 'OFF'}")
    print(f"Counter: {status['counter']}")
    print(f"Next section available:{status['next_section_available']}")
    
def clear_log_file():
    base_dir = os.path.dirname(os.path.abspath(__file__))
    filepath = os.path.join(base_dir, "events.jsonl")
    open(filepath, "w", encoding="utf-8").close()

# Our trying to simple the code
# Order: state, counter, motor_on, motor_on2, n1

def reset_system(): 
    return "WAIT_EMPTY", 0, False, False, False
    
def handle_tick(state, counter, motor_on, motor_on2, n1):
    message = "Tick ignored (not moving)"
    
    if state == "MOVE_TO_S2":
        motor_on = True
        counter += 1
        message = "Tick: moving to S2..."
        
        if counter >=4:
            message = "ERROR: no S2 confirmation (timeout) -> auto reset"
            return "WAIT_EMPTY", 0, False, False, False, message
        
    elif state == "PREP_TRANSFER":
        message = "Tick: next section moving, now start current section motor"
        motor_on = True
        state = "TRANSFER"
        counter = 0
        
    elif state == "TRANSFER":
        counter += 1
        
        if n1:
            message = "Transfer completed: N1 confirmed"
            return "WAIT_EMPTY", 0, False, False, False, message
        if counter >=4:
            message = "ERROR: no N1 confirmation (timeout) -> auto reset"
            return "WAIT_EMPTY", 0, False, False, False, message
        message = "Transfer in progress: waiting for N1"
        
    return state, counter, motor_on, motor_on2, n1, message

def log_event(command, message, status, enabled=True):
    if not enabled:
        return

    base_dir = os.path.dirname(os.path.abspath(__file__))
    filepath = os.path.join(base_dir, "events.jsonl")

    event = {
        "run_id": run_id,
        "ts": datetime.now().isoformat(timespec="seconds"),
        "command": command,
        "message": message,
        "status": status
    }

    with open(filepath, "a", encoding="utf-8") as f:
        f.write(json.dumps(event, ensure_ascii=False) + "\n")
    
counter = 0
motor_on = False
motor_on2 = False
next_section_available = True
n1 = False
logging_enabled = True
run_id = uuid.uuid4().hex[:8]
auto_clear_log_on_start = False

message = ""
should_exit = False
state = "WAIT_EMPTY"

if auto_clear_log_on_start:
    clear_log_file()
    
print("LineCheck Simulator started")
print("Type 'clearlog','s1', 's2', 'next', 'next_section_available', 'n1', 'tick', 'log', 'reset' or 'exit'")

while True:
    message=""
    command = input("> ").strip().lower()
    
    if state == "ERROR" and command not in ("reset", "exit"):
        message = "ERROR state: only 'reset' or 'exit' allowed"
        print(message)
        print(f"Current state:{state}")
        continue
    
    if command == "exit":
        message="Simulation stopped by user"
        should_exit = True
    
    elif command == "log":
        logging_enabled = not logging_enabled
        message= f"Logging = {logging_enabled}"
        
    elif command == "clearlog":
        clear_log_file()
        message = "Log cleared"
        
    elif command == "reset":
        state, counter, motor_on, motor_on2, n1 = reset_system()
        next_section_available = True
        message = "Manual reset: system returned to WAIT_EMPTY"
        
    elif command == "next_section_available":
        next_section_available = not next_section_available
        message = f"Next section free = {next_section_available}"
        
    elif command == "n1":
        n1=True
        message = "N1 triggered(radiator detected on next section)"
                             
    elif command == "s1":
        counter += 1 
        motor_on = True
        motor_on2 = False
        message="S1 triggered (radiator detected at entry)"
        state="MOVE_TO_S2"
       
    elif command == "s2":
        motor_on = False
        motor_on2 = False
        counter = 0
        if state == "WAIT_EMPTY":
            message = "Manual load at S2 (radiator placed manually)"
        
        else:
            message="S2 triggered (radiator at end position)"
       
        state="AT_END"
        
    elif command == "next":
        if state == "AT_END":
            if next_section_available:
                message = "Preparing transfer: starting next section motor"
                state = "PREP_TRANSFER"
                motor_on2 = True
            else:
                message = "Next section blocked"
                motor_on2 = False
        else:
            message="Cannot transfer: radiator is not at end position"
                 
    elif command == "tick":
        state, counter, motor_on, motor_on2, n1, message = handle_tick(
            state, counter, motor_on, motor_on2, n1
        )
        n1 = False
    
    else:
        message="Unknown command"
    
    status = collect_status(state, motor_on, motor_on2, counter, next_section_available, n1)
    print_status(message, status)
    

    log_event(command, message, status, enabled = logging_enabled)
  
    if should_exit:
        break