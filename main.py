counter = 0
motor_on = False
message = ""
should_exit = False
state = "WAIT_EMPTY"
print("LineCheck Simulator started")
print("Type 's1', 's2', 'next','tick', 'reset' or 'exit'")

while True:
    command = input("> ").strip().lower()
    
    if state == "ERROR" and command not in ("reset", "exit"):
        message = "ERROR state: only 'reset' or 'exit' allowed"
        print(message)
        print(f"Current state:{state}")
        continue
    
    elif command == "exit":
        message="Simulation stopped by user"
        should_exit = True
        
    elif command == "s1":
        counter = 0
        motor_on = True
        message="S1 triggered (radiator detected at entry)"
        state="MOVE_TO_S2"
       
        
    elif command == "tick":
        if state == "MOVE_TO_S2":
            motor_on = True
            counter += 1 
            message = f"Tick: moving... counter={counter}"
       
            
            if counter >=3:
                message = "ERROR: no S2 confirmation (timeout) -> reset"
                state = "ERROR"
                motor_on = False
            if state == "ERROR":
                message = "Auto reset to WAIT_EMPTY"
                state = "WAIT_EMPTY"
                counter = 0 
                
        elif state == "TRANSFER":
            motor_on = False
            state = "WAIT_EMPTY"
            message="Transfer completed"
            
        else:
            message = "Tick ignored (not moving)"
                
    elif command == "s2":
        motor_on = False
        counter = 0
        if state == "WAIT_EMPTY":
            message = "Manual load at S2 (radiator placed manually)"
        
        else:
            message="S2 triggered (radiator at end position)"
       
        state="AT_END" 
    elif command == "next":
        
        if state == "AT_END":
            message="Next section is free"
            state = "TRANSFER"
            motor_on = True
        else:
            message="Cannot transfer: radiator is not at end position"
            motor_on = False
    
    elif command == "reset":
        message = "Manual reset: system returned to WAIT_EMPTY"
        state = "WAIT_EMPTY"
        counter = 0
        motor_on = False     
        
    else:
        message="Unknown command"
    
   
    print(f"Motor: {'ON' if motor_on else 'OFF'}")
    print(message)
    print(f"Current state: {state}")
  
    if should_exit:
        break