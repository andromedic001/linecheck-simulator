import os
import json
import uuid
import time
import threading
from datetime import datetime


BASE_DIR = os.path.dirname(os.path.abspath(__file__))
LOG_FILE = os.path.join(BASE_DIR, "events.jsonl")


# =========================================================
# STATE
# =========================================================
def reset_system() -> dict:
    return {
        # local FSM
        "state_A": "IDLE",
        "state_B": "IDLE",

        # debug/manual sensors
        "S1A": False,
        "S1B": False,

        # occupancy flags
        "u_has_part": False,
        "a_has_part": False,
        "a_at_end": False,
        "b_has_part": False,
        "station_ready": True,

        # outputs
        "motor_u": False,
        "motor_a": False,
        "motor_b": False,

        # local timers
        "counter_A": 0,
        "counter_B": 0,

        # station process
        "align_stopper": False,
        "aligned": False,
        "clamp": False,
        "clamped": False,

        # errors
        "error_code": None,
        "error_msg": "",

        # runtime
        "tick": 0,
        "tick_delay": .1,
        "auto_run": False,

        # flow
        "flow_mode": "normal",   # max / normal / random
        "next_feed_in": 3,

        # stats
        "completed_count": 0,
        "rate": 0
    }


# =========================================================
# HELPERS
# =========================================================
def clear_screen() -> None:
    os.system("cls" if os.name == "nt" else "clear")


def stop_all_motors(st: dict) -> None:
    st["motor_u"] = False
    st["motor_a"] = False
    st["motor_b"] = False


def deny_transfer(st: dict) -> None:
    """Safety: cancel transfer outputs."""
    st["motor_b"] = False
    st["align_stopper"] = False


def clear_log_file() -> None:
    open(LOG_FILE, "w", encoding="utf-8").close()


def log_event(
    run_id: str,
    command: str,
    message: str,
    st: dict,
    event_type: str = "command",
    level: str = "INFO",
    error_code: str | None = None,
    enabled: bool = True,
) -> None:
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
        "status": st,
    }

    try:
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(json.dumps(event, ensure_ascii=False) + "\n")
    except Exception as e:
        print(f"[LOG ERROR] {e}")


def print_status(message: str, st: dict) -> None:
    clear_screen()
    print("=" * 56)
    print("LINECHECK SIMULATOR HMI")
    print("=" * 56)
    print(f"Message      : {message}\n")

    print("SYSTEM")
    print(f"Flow mode    : {st['flow_mode']}")
    print(f"Next feed in : {st['next_feed_in']}")
    print(f"Auto run     : {'ON' if st['auto_run'] else 'OFF'}")
    print(f"Tick         : {st['tick']}")
    print(f"Completed    : {st['completed_count']}\n")

    print("LINE OCCUPANCY")
    print(f"U            : {'PART' if st['u_has_part'] else 'EMPTY'}")
    print(f"A            : {'PART' if st['a_has_part'] else 'EMPTY'}")
    print(f"A_END        : {'PART' if st['a_at_end'] else 'EMPTY'}")
    print(f"B            : {'PART' if st['b_has_part'] else 'EMPTY'}")
    print(f"B ready      : {'YES' if st['station_ready'] else 'NO'}\n")

    print("MOTORS / ACTUATORS")
    print(f"Motor U      : {'ON' if st['motor_u'] else 'OFF'}")
    print(f"Motor A      : {'ON' if st['motor_a'] else 'OFF'}")
    print(f"Motor B      : {'ON' if st['motor_b'] else 'OFF'}")
    print(f"Align stopper: {'OUT' if st['align_stopper'] else 'IN'}")
    print(f"Aligned      : {'YES' if st['aligned'] else 'NO'}")
    print(f"Clamp        : {'ON' if st['clamp'] else 'OFF'}")
    print(f"Clamped      : {'YES' if st['clamped'] else 'NO'}\n")

    print("SECTION STATES")
    print(f"State A      : {st['state_A']}")
    print(f"State B      : {st['state_B']}")
    print(f"Counter A    : {st['counter_A']}")
    print(f"Counter B    : {st['counter_B']}\n")

    if st["error_code"]:
        print("ERROR")
        print(f"Code         : {st['error_code']}")
        print(f"Message      : {st['error_msg']}\n")

    print("Commands:")
    print("run | stop | status | stepauto | tick")
    print("feed | s2a | reset | flow max/normal/random")
    print("log | clearlog | clearcount | exit")
    print("=" * 56)
    print(f"Parts per tick : {st['rate']:.4f}")
    
# =========================================================
# CASCADE
# =========================================================
def cascade_logic(st: dict) -> tuple[str, str | None, str, str] | None:
    section_A_ready = (not st["a_has_part"]) and (not st["a_at_end"])
    section_B_ready = (not st["b_has_part"]) and st["station_ready"]
    transfer_U_to_A_allowed = (
        st["u_has_part"]
        and section_A_ready
        and st["state_A"] == "IDLE"
    )

    # U -> A
    if transfer_U_to_A_allowed:
        st["state_A"] = "PREP_TRANSFER_S1A"
        return "Cascade: U -> A transfer starting", None, "INFO", "controller"
        
    # A -> A_END
    if st["a_has_part"] and st["state_A"] == "IDLE":
        st["state_A"] = "MOVE_TO_S2A"
        return "Cascade: A -> A_END transfer starting", None, "INFO", "controller"

    # A_END -> B
    if st["a_at_end"] and section_B_ready and st["state_A"] == "AT_END" and st["state_B"] == "IDLE":
        st["motor_b"] = True
        st["align_stopper"] = True
        st["state_B"] = "PREP_TRANSFER_S1B"
        return "Cascade: A_END -> B transfer starting", None, "INFO", "controller"

    return None


# =========================================================
# FSM SECTION B
# =========================================================
def fsm_section_B(st: dict) -> tuple[str, str | None, str, str] | None:
    state_B = st["state_B"]

    if state_B == "IDLE":
        return None

    if state_B == "PREP_TRANSFER_S1B":
        st["motor_a"] = True
        st["align_stopper"] = True
        st["station_ready"] = False
        st["counter_B"] = 0
        st["state_B"] = "TRANSFER_S1B"
        return "B: prep transfer -> TRANSFER_S1B", None, "INFO", "controller"

    if state_B == "TRANSFER_S1B":
        st["counter_B"] += 1
        st["motor_a"] = True
        st["motor_b"] = True
        # manual confirm
        if st["S1B"]:
            st["S1B"] = False
            st["counter_A"] = 0
            st["counter_B"] = 0
            st["motor_a"] = False
            st["motor_b"] = True
            st["b_has_part"] = True
            st["a_at_end"] = False
            st["state_A"] = "A_CLEARING"
            
            st["state_B"] = "ALIGNING"
            return "S1B confirmed -> ALIGNING", None, "INFO", "controller"

        # auto confirm after 1 tick
        if st["counter_B"] >= 1:
            st["counter_B"] = 0
            st["motor_a"] = False
            st["motor_b"] = True
            st["b_has_part"] = True
            st["a_at_end"] = False
            st["state_A"] = "A_CLEARING"
            st["state_B"] = "ALIGNING"
            return "Auto S1B confirmed -> ALIGNING", None, "INFO", "controller"

        return "B: transfer in progress", None, "INFO", "controller"

    if state_B == "ALIGNING":
        st["counter_B"] += 1

        if st["counter_B"] >= 2:
            st["counter_B"] = 0
            st["motor_b"] = False
            st["aligned"] = True
            st["align_stopper"] = False
            st["state_B"] = "WAIT_CLAMP"
            return "B: aligned -> WAIT_CLAMP", None, "INFO", "controller"

        return "B: aligning...", None, "INFO", "controller"

    if state_B == "WAIT_CLAMP":
        st["clamp"] = True
        st["clamped"] = False
        st["counter_B"] = 0
        st["state_B"] = "CLAMPING"
        return "B: auto clamp start", None, "INFO", "controller"

    if state_B == "CLAMPING":
        st["counter_B"] += 1
        st["clamp"] = True

        if st["counter_B"] >= 10:
            stop_all_motors(st)
            st["clamp"] = False
            st["error_code"] = "E_CLAMP_TIMEOUT"
            st["error_msg"] = "Clamp did not finish in time"
            st["state_B"] = "ERROR"
            return "ERROR: clamp timeout", "E_CLAMP_TIMEOUT", "ERROR", "manual_reset"

        if st["counter_B"] >= 2:
            st["counter_B"] = 0
            st["clamp"] = False
            st["clamped"] = True
            st["motor_b"] = True
            st["state_B"] = "DISCHARGE"
            return "B: clamp finished -> DISCHARGE", None, "INFO", "controller"

        return "B: clamping...", None, "INFO", "controller"

    if state_B == "DISCHARGE":
        st["counter_B"] += 1

        if st["counter_B"] >= 2:
            st["counter_B"] = 0
            st["motor_b"] = False
            st["align_stopper"] = False
            st["aligned"] = False
            st["clamp"] = False
            st["clamped"] = False
            st["station_ready"] = True
            st["b_has_part"] = False
            st["completed_count"] += 1
            
            #look - ahead optimization
            if st["a_at_end"] and not st["b_has_part"]:
                st["state_B"] = "TRANSFER_S1B"
                return "B discharge -> next transfer immediately", None, "INFO", "controller"
            else: 
                st["state_B"] = "IDLE"
                return "B: discharge complete -> IDLE", None, "INFO", "controller"

        return "B: discharging...", None, "INFO", "controller"

    if state_B == "ERROR":
        stop_all_motors(st)
        return "B: ERROR state", st.get("error_code"), "ERROR", "controller"

    return None


# =========================================================
# FSM SECTION A
# =========================================================
def fsm_section_A(st: dict) -> tuple[str, str | None, str, str] | None:
    state_A = st["state_A"]

    if state_A == "IDLE":
        return None

    if state_A == "PREP_TRANSFER_S1A":
        st["motor_u"] = False
        st["motor_a"] = True
        st["counter_A"] = 0
        st["state_A"] = "TRANSFER_S1A"
        return "A: prep transfer -> TRANSFER_S1A", None, "INFO", "controller"

    if state_A == "TRANSFER_S1A":
        st["counter_A"] += 1
        st["motor_u"] = True
        st["motor_a"] = True

        # manual confirm
        if st["S1A"]:
            st["S1A"] = False
            st["counter_A"] = 1
            st["motor_u"] = False
            st["u_has_part"] = False
            st["a_has_part"] = True

            if st["a_at_end"]:
                st["motor_a"] = False
                st["state_A"] = "A_WAIT_END_FREE"
                return "WARN: S1A confirmed, but A end is occupied -> waiting", "E_A_END_BLOCKED", "WARN", "interlock"
            else:
                st["motor_a"] = True
                st["state_A"] = "MOVE_TO_S2A"
                return "S1A confirmed -> continue moving to S2A", None, "INFO", "controller"

        # auto confirm after 1 tick
        if st["counter_A"] >= 1:
            st["motor_u"] = False
            st["u_has_part"] = False
            st["a_has_part"] = True

            if st["a_at_end"]:
                st["counter_A"] = 0
                st["motor_a"] = False
                st["state_A"] = "A_WAIT_END_FREE"
                return "WARN: auto S1A confirmed, but A end is occupied -> waiting", "E_A_END_BLOCKED", "WARN", "interlock"
            else:
                st["counter_A"] = 1
                st["motor_a"] = True
                st["state_A"] = "MOVE_TO_S2A"
                return "Auto S1A confirmed -> continue moving to S2A", None, "INFO", "controller"

        return "A: transfer in progress", None, "INFO", "controller"
    
    if state_A == "A_WAIT_END_FREE":
        if st["a_at_end"]:
            st["motor_a"] = False
            return "A: waiting, A end still occupied", None, "INFO", "interlock"

        st["motor_a"] = True
        st["counter_A"] = 1
        st["state_A"] = "MOVE_TO_S2A"
        return "A: end became free -> resume MOVE_TO_S2A", None, "INFO", "controller"
    
    if state_A == "MOVE_TO_S2A":
        st["counter_A"] += 1
        st["motor_a"] = True

        if st["counter_A"] >= 2:
            st["counter_A"] = 0
            st["motor_a"] = False
            st["a_has_part"] = False
            st["a_at_end"] = True
            st["state_A"] = "AT_END"
            return "Auto S2A confirmed -> AT_END", None, "INFO", "controller"

        return "A: moving to S2A...", None, "INFO", "controller"

    if state_A == "AT_END":
        if not st["a_at_end"]:
            deny_transfer(st)
            st["state_A"] = "IDLE"
            return "WARN: AT_END mismatch -> IDLE", "E_STATE_MISMATCH", "WARN", "qa"

        if not st["station_ready"]:
            deny_transfer(st)
            return "A: waiting, station busy", "E_STATION_BUSY", "WARN", "interlock"

        if st["b_has_part"]:
            deny_transfer(st)
            return "A: waiting, next section blocked", "E_NEXT_BLOCKED", "WARN", "interlock"

        # transfer launch is handled by cascade
        return "A: part at end, waiting transfer to B", None, "INFO", "controller"
    
    if state_A == "A_CLEARING":
        message = "A: clearing tail motion..."
        st["counter_A"] += 1
        st["motor_a"] = True

        if st["counter_A"] >= 1:
            st["counter_A"] = 0

            if st["u_has_part"] and (not st["a_has_part"]) and (not st["a_at_end"]):
                st["motor_u"] = True
                st["motor_a"] = True
                st["state_A"] = "TRANSFER_S1A"
                st["align_stopper"] = True
                st["station_ready"] = False
                return "A: clearing complete -> direct next TRANSFER_S1A", None, "INFO", "controller"

            st["motor_a"] = False
            st["state_A"] = "IDLE"
            return "A: clearing complete -> IDLE", None, "INFO", "controller"

        return message, None, "INFO", "controller"
    
    if state_A == "ERROR":
        stop_all_motors(st)
        return "A: ERROR state", st.get("error_code"), "ERROR", "controller"

    return None


# =========================================================
# MAIN TICK
# =========================================================
def handle_tick(st: dict) -> tuple[str, str | None, str, str]:
    st["tick"] += 1

    # 1) Cascade decisions
    cascade_result = cascade_logic(st)
    if cascade_result:
        return cascade_result

    # 2) Section B runs independently
    result_b = fsm_section_B(st)

    # 3) Section A runs independently
    result_a = fsm_section_A(st)

    # priority for visible message: B first, then A
    if result_b:
        return result_b
    if result_a:
        return result_a

    return "Tick ignored (no active movement)", None, "INFO", "controller"


# =========================================================
# MAIN
# =========================================================
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

    import random

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
            if st["tick"] > 0:
                st["rate"] = st["completed_count"] / st["tick"]
            time.sleep(st["tick_delay"])

    print("LineCheck Simulator started")
    print("Commands: run, stop, status, stepauto, tick, feed, s2a, reset, flow max/normal/random, clearcount, clearlog, log, exit")

    while True:
        command = input("> ").strip().lower()

        message = ""
        error_code = None
        event_type = "command"
        level = "INFO"

        with state_lock:
            if (st["state_A"] == "ERROR" or st["state_B"] == "ERROR") and command not in (
                "reset", "exit", "log", "clearlog", "clearcount", "status"
            ):
                message = "ERROR state: only reset, exit, log, clearlog, clearcount, status allowed"
                error_code = st.get("error_code") or "E_ERROR_LOCK"
                event_type = "QA"
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
                event_type = "maintenance"
                message = "completed_count reset to 0"

            elif command == "reset":
                if st["a_has_part"]:
                    stop_all_motors(st)
                    st["counter_A"] = 0
                    st["state_A"] = "MOVE_TO_S2A"
                    message = "Manual reset -> MOVE_TO_S2A"
                elif st["a_at_end"]:
                    stop_all_motors(st)
                    st["counter_A"] = 0
                    st["state_A"] = "AT_END"
                    message = "Manual reset -> AT_END"
                else:
                    keep_completed = st.get("completed_count", 0)
                    st.clear()
                    st.update(reset_system())
                    st["completed_count"] = keep_completed
                    message = "Manual reset -> IDLE"

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

            elif command == "feed":
                if st["u_has_part"]:
                    message = "Feed ignored: upstream already has a part"
                    error_code = "E_FEED_ALREADY_PRESENT"
                    event_type = "QA"
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
            snapshot = dict(st)

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