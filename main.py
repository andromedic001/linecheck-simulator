import uuid
import time
import threading
import copy
import random

from state import reset_system
from helpers import (
    clear_log_file,
    clear_qa_counts,
    clear_runtime_messages,
    stop_all_motors,
    log_event,
    print_status,
)
from fsm import handle_tick
from qa import recover_faults

def main():
    run_id = uuid.uuid4().hex[:8]
    st = reset_system()

    logging_enabled = True
    auto_clear_log_on_start = False

    state_lock = threading.Lock()
    auto_thread = None
    should_exit = False

    if auto_clear_log_on_start:
        clear_log_file()

    def generate_next_feed_interval(mode: str) -> int:
        if mode == "max":
            return random.randint(3, 4)
        if mode == "normal":
            return random.randint(4, 6)
        if mode == "random":
            return random.randint(3, 10)
        return 3

    def try_auto_feed(st_local: dict) -> str | None:
        if st_local["u_has_part"]:
            return None
        st_local["u_has_part"] = True
        return "AUTO FEED: new part arrived at U"

    def do_auto_step(st_local: dict):
        message, error_code, level, event_type = handle_tick(st_local)
        auto_msg = None

        st_local["next_feed_in"] -= 1

        if st_local["next_feed_in"] <= 0:
            auto_msg = try_auto_feed(st_local)
            st_local["next_feed_in"] = generate_next_feed_interval(st_local["flow_mode"])

        if auto_msg:
            message = f"{message} | {auto_msg}"

        return message, error_code, level, event_type

    def auto_run_loop():
        nonlocal should_exit, logging_enabled
        while True:
            with state_lock:
                if not st["auto_run"] or should_exit:
                    break

                message, error_code, level, event_type = do_auto_step(st)

                print_status(message, st)
                log_event(
                    run_id,
                    "auto_tick",
                    message,
                    st,
                    event_type=event_type,
                    level=level,
                    error_code=error_code,
                    enabled=logging_enabled,
                )
            time.sleep(st["tick_delay"])

    def can_reset_error(st: dict) -> tuple[bool, str]:
        
        if st["a_has_part"] and st["a_at_end"]:
            return False, "Reset denied: A occupancy conflict still present"   
        
        if st["b_has_part"] and st["station_ready"]:
            return False, "Reset denied: B occupancy conflict still present"
        
        if st["clamp"]:
            return False, "Reset denied: clamp is still active"
        
        if st["a_at_end"] and st["b_has_part"]:
            return False, "Reset denied: downstream path is still blocked"
        
        return True, "Reset allowed"
    print("LineCheck Simulator started")
    print("Commands: run, stop, status, stepauto, tick, feed, s2a, reset, recover, flow max/normal/random, clearcount, clearlog, log, exit")

    while True:
        command = input("> ").strip().lower()

        message = ""
        error_code = None
        event_type = "command"
        level = "INFO"

        with state_lock:
            if (st["state_A"] == "ERROR" or st["state_B"] == "ERROR") and command not in (
                "reset", "recover", "stop", "exit", "log", "clearlog", "clearcount", "status"
            ):
                message = "ERROR state: only recover, reset, stop, exit, log, clearlog, clearcount, status allowed"
                error_code = st.get("error_code") or "E_ERROR_LOCK"
                event_type = "qa"
                level = "ERROR"
                stop_all_motors(st)
                print_status(message, st)
                log_event(run_id, command, message, st, event_type=event_type, level=level,
                          error_code=error_code, enabled=logging_enabled)
                continue

            if command == "exit":
                st["auto_run"] = False
                should_exit = True
                message = "Simulation stopped by user"

            elif command == "log":
                logging_enabled = not logging_enabled
                message = f"Logging = {logging_enabled}"

            elif command == "clearlog":
                clear_log_file()
                message = "Log cleared"

            elif command == "clearcount":
                st["completed_count"] = 0
                st["tick"] = 0
                event_type = "maintenance"
                message = "completed_count reset to 0"

    # if system is in ERROR, allow reset only when fault is cleared
            elif command == "reset":
                # if system is in ERROR, allow reset only when fault is cleared
                if st["state_A"] == "ERROR" or st["state_B"] == "ERROR":
                    can_reset, reset_msg = can_reset_error(st)

                        
                    if not can_reset:
                        message = reset_msg
                        error_code = st.get("error_code") or "E_RESET_DENIED"
                        event_type = "qa"
                        level = "WARN" 
                    
                    else:
                        stop_all_motors(st)
                        clear_qa_counts(st)
                                
                        # clear latched error
                        st["error_code"] = None
                        st["error_msg"] = ""

                        # clear fault history
                        for key in st["fault_counts"]:
                            st["fault_counts"][key] = 0
                        for key in st["fault_last_tick"]:
                            st["fault_last_tick"][key] = -999999
                            
                        # clear section messages if you already added them
                        clear_runtime_messages(st)

                        # recover to safe state
                        if st["a_has_part"]:
                                
                            st["counter_A"] = 0
                            st["state_A"] = "MOVE_TO_S2A"
                            st["state_B"] = "IDLE"
                            message = "Manual reset accepted -> MOVE_TO_S2A"

                        elif st["a_at_end"]:
                                
                            st["counter_A"] = 0
                            st["state_A"] = "AT_END"
                            st["state_B"] = "IDLE"
                            message = "Manual reset accepted -> AT_END"

                        else:

                            keep_completed = st.get("completed_count", 0)
                            st.clear()
                            st.update(reset_system())
                            st["completed_count"] = keep_completed
                            message = "Manual reset accepted -> IDLE"

                        event_type = "maintenance"
                        level = "INFO"
                        
                else:
                    clear_qa_counts(st)
                    clear_runtime_messages(st)
                    # normal reset when system is not in ERROR
                    if st["a_has_part"]:
                        stop_all_motors(st)
                        st["counter_A"] = 0
                        st["state_A"] = "MOVE_TO_S2A"
                        message = "Manual reset -> MOVE_TO_S2A"

                    elif st["a_at_end"]:
                        stop_all_motors(st)
                        st["counter_A"] = 0
                        st["state_A"] = "AT_END"
                        st["state_B"] = "IDLE"
                        message = "Manual reset -> AT_END"

                    else:
                        keep_completed = st.get("completed_count", 0)
                        st.clear()
                        st.update(reset_system())
                        st["completed_count"] = keep_completed
                        message = "Manual reset -> IDLE"
                           
                    event_type = "maintenance"
                    level = "INFO"
                    
                    # clear fault history
                    for key in st["fault_counts"]:
                        st["fault_counts"][key] = 0
                    for key in st["fault_last_tick"]:
                        st["fault_last_tick"][key] = -999999
                        
            elif command == "recover":
                message = recover_faults(st)
                event_type = "maintenance"
                level = "INFO"
    
            elif command == "run":
                if st["auto_run"]:
                    message = "Auto run is already ON"
                    level = "WARN"
                else:
                    st["auto_run"] = True
                    message = "Auto run -> ON"

                    auto_thread = threading.Thread(target=auto_run_loop, daemon=True)
                    auto_thread.start()

            elif command == "stop":
                if not st["auto_run"]:
                    message = "Auto run is already OFF"
                    level = "WARN"
                else:
                    st["auto_run"] = False
                    message = "Auto run -> OFF"

            elif command == "status":
                message = "Current system status"

            elif command.startswith("flow "):
                mode = command.split(" ", 1)[1].strip()
                if mode in ("max", "normal", "random"):
                    st["flow_mode"] = mode
                    st["next_feed_in"] = generate_next_feed_interval(mode)
                    message = f"Flow mode set to {mode}"
                else:
                    message = "Unknown flow mode"

            elif command == "tick":
                message, error_code, level, event_type = handle_tick(st)
                
            elif command == "qa2":
                st["b_has_part"] = True
                st["station_ready"] = True
                message = "QA test: forced B ready conflict"
                
            elif command == "stepauto":
                message, error_code, level, event_type = do_auto_step(st)

            elif command == "feed":
                if st["u_has_part"]:
                    message = "Feed ignored: upstream already has a part"
                    error_code = "E_FEED_ALREADY_PRESENT"
                    event_type = "qa"
                    level = "WARN"
                else:
                    st["u_has_part"] = True
                    message = "Feed registered: part is at upstream end"
                    event_type = "sensor"

            elif command == "s2a":
                stop_all_motors(st)
                st["counter_A"] = 0
                st["a_has_part"] = False
                st["a_at_end"] = True
                st["state_A"] = "AT_END"
                message = "Manual load at S2A -> AT_END"

            else:
                message = "Unknown command"

            # snapshot for watch command
            snapshot = copy.deepcopy(st)

        print_status(message, snapshot if command.startswith("watch") else st)

        if event_type == "command":
            if command in ("reset", "clearlog", "log", "clearcount"):
                event_type = "maintenance"
            elif command == "tick":
                event_type = "controller"

        with state_lock:
            log_event(
                run_id,
                command,
                message,
                st,
                event_type=event_type,
                level=level,
                error_code=error_code,
                enabled=logging_enabled,
            )

            if should_exit:
                print("Simulation finished.")
                break
        
                    

if __name__ == "__main__":
    main()