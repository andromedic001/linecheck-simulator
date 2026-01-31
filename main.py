message = ""
should_exit = False
state = "WAIT_EMPTY"
print("LineCheck Simulator started")
print("Type 's1', 's2', 'next', or 'exit'")

while True:
    command = input("> ").strip().lower()
    
    if command == "exit":
        message="Simulation stopped by user"
        should_exit=True
        
    elif command == "s1":
        message="S1 triggered (radiator detected at entry)"
        state="MOVE_TO_S2"
        
    elif command == "s2":
        
        if state == "WAIT_EMPTY":
            message = "Manual load at S2 (radiator placed manually)"
        
        else:
            message="S2 triggered (radiator at end position)"
            
        state="AT_END"

    elif command == "next":
        
        if state == "AT_END":
            message="Next section is free"
            state = "TRANSFER"
        
        else:
            message="Cannot transfer: radiator is not at end position"
        
    else:
        message="Unknown command"
        
    print(message)
    print(f"Current state: {state}")
    
    if should_exit:
        break