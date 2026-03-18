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
        #section messages
        "msg_U": "",
        "msg_A": "",
        "msg_B": "",
        
        #qa - section messages
        "qa_msg_U": "",
        "qa_msg_A": "",
        "qa_msg_B": "",
        
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
        "fault_counts": {
            "E_S1A_TIMEOUT": 0,
            "E_S2A_TIMEOUT": 0,
            "E_S1B_TIMEOUT": 0,
            "E_UPSTREAM_TIMEOUT": 0,
        },
        "fault_last_tick": {
            "E_S1A_TIMEOUT": -999999,
            "E_S2A_TIMEOUT": -999999,
            "E_S1B_TIMEOUT": -999999,
            "E_UPSTREAM_TIMEOUT": -999999,
        },
        
        "qa_counts": {
            "E_A_OCCUPANCY_CONFLICT": 0,
            "E_MOTOR_A_UNEXPECTED": 0,
            "E_MOTOR_B_UNEXPECTED": 0,   
        },
        
        # runtime
        "tick": 0,
        "tick_delay": .5,
        "auto_run": False,

        # flow
        "flow_mode": "normal",   # max / normal / random
        "next_feed_in": 3,

        # stats
        "completed_count": 0,
        
        # statistics
        "parts_per_tick": 0.0,
        "parts_1h_current": 0.0,
        "parts_1h_ref_05": 0.0,
        "parts_8h_current": 0.0,
        "parts_8h_ref_05": 0.0,
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

def update_statistics(st: dict) -> None:
    if st["tick"] > 0:
        st["parts_per_tick"] = st["completed_count"] / st["tick"]
        st["parts_1h_current"] = st["parts_per_tick"] * (3600 / st["tick_delay"])
        st["parts_1h_ref_05"] = st["parts_per_tick"] * (3600 / 0.5)
        st["parts_8h_current"] = st["parts_per_tick"] * (28800 / st["tick_delay"])
        st["parts_8h_ref_05"] = st["parts_per_tick"] * (28800 / 0.5)
        
    else:
        st["parts_per_tick"] = 0.0
        st["parts_1h_current"] = 0.0
        st["parts_1h_ref_05"] = 0.0
        st["parts_8h_current"] = 0.0
        st["parts_8h_ref_05"] = 0.0

def print_status(message: str, st: dict) -> None:
    
    parts_1h = st["parts_1h_ref_05"] if st["tick_delay"] == 0.5 else st["parts_1h_current"]
    parts_8h = st["parts_8h_ref_05"] if st["tick_delay"] == 0.5 else st["parts_8h_current"]

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
    
    print("SECTION MESSAGES")
    print(f"U: {st['msg_U'] or '-'}")
    print(f"A: {st['msg_A'] or '-'}")
    print(f"B: {st['msg_B'] or '-'}\n")
    
    print("QA SECTION MESSAGES")
    print(f"QA U: {st['qa_msg_U'] or '-'}")
    print(f"QA A: {st['qa_msg_A'] or '-'}")
    print(f"QA B: {st['qa_msg_B'] or '-'}\n")


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
    print("recover | log | clearlog | clearcount | exit\n")
    
    print("STATISTICS")
    print(f"Parts per tick : {st['parts_per_tick']:.4f}")
    print(f"Parts for / 1 hour : {parts_1h:.0f}")
    print(f"Parts for / 8 hours :{parts_8h:.0f}")
    print("=" * 56)
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
    if st["u_has_part"] and not transfer_U_to_A_allowed:
        st["msg_U"] = "INFO: part waiting"
    elif not st["u_has_part"]:
        st["msg_U"] = ""
        
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
        st["msg_B"] = ""
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

        # auto confirm after 1 tick
        if st["counter_B"] >= 4:
            def recover_s1b(st_local):
                stop_all_motors(st_local)
                st_local["counter_B"] = 0

                if st_local["a_at_end"]:
                    st_local["state_B"] = "IDLE"
                    st_local["state_A"] = "AT_END"
                else:
                    st_local["state_B"] = "IDLE"

            return auto_recover_or_escalate(
                st,
                "E_S1B_TIMEOUT",
                "WARN: S1B timeout -> auto recover applied",
                "ERROR: repeated S1B timeout -> manual reset required",
                recover_s1b,
    )
    
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
        st["msg_B"] = "INFO: aligning"
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
        st["msg_B"] = "INFO: clamping"
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
        st["msg_A"] = ""
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

        if st["counter_A"] >= 4:
            def recover_s1a(st_local):
                stop_all_motors(st_local)
                st_local["counter_A"] = 0
                st_local["state_A"] = "IDLE"
                st_local["u_has_part"] = False
                st_local["a_has_part"] = False

            return auto_recover_or_escalate(
                st,
                "E_S1A_TIMEOUT",
                "WARN: S1A timeout -> auto recover to IDLE",
                "ERROR: repeated S1A timeout -> manual reset required",
                recover_s1a,
            )
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

        if st["counter_A"] >= 4:
            def recover_s2a(st_local):
                stop_all_motors(st_local)
                st_local["counter_A"] = 0

                if st_local["a_has_part"]:
                    st_local["state_A"] = "MOVE_TO_S2A"
                elif st_local["a_at_end"]:
                    st_local["state_A"] = "AT_END"
                else:
                    st_local["state_A"] = "IDLE"

            return auto_recover_or_escalate(
        st,
        "E_S2A_TIMEOUT",
        "WARN: S2A timeout -> auto recover applied",
        "ERROR: repeated S2A timeout -> manual reset required",
        recover_s2a,
    )
            
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
            st["msg_A"] = "INFO: station busy"
            return "A: waiting, station busy", "E_STATION_BUSY", "INFO", "interlock"

        if st["b_has_part"]:
            deny_transfer(st)
            return "A: waiting, next section blocked", "E_NEXT_BLOCKED", "WARN", "interlock"

        # transfer launch is handled by cascade
        st["msg_A"] = ""
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
    
    
    # 2) Section B runs independently
    result_b = fsm_section_B(st)

    # 3) Section A runs independently
    result_a = fsm_section_A(st)
    # 4) QA 
    qa_result = qa_checks(st) 
    
    #statistics
    update_statistics(st)   
    
    # priority for visible message: B first, then 
    if qa_result:
        return qa_result
    if result_b:
        return result_b
    if result_a:
        return result_a
    if cascade_result:
        return cascade_result 
    
    return "Tick ignored (no active movement)", None, "INFO", "controller"


# =========================================================
# QA 
# =========================================================

def qa_checks(st: dict) -> tuple[str, str | None, str, str] | None:
    # clear QA messages every tick
    st["qa_msg_A"] = ""
    st["qa_msg_B"] = ""
    st["qa_msg_U"] = ""

    # ---------------------------------------------------------
    # helper: repeated WARN -> ERROR after N repeats
    # ---------------------------------------------------------
    def bump(counter_key: str, limit: int = 10) -> bool:
        st["qa_counts"][counter_key] += 1
        return st["qa_counts"][counter_key] >= limit

    def clear_counter(counter_key: str) -> None:
        st["qa_counts"][counter_key] = 0

    # A occupancy conflict

    if st["a_has_part"] and st["a_at_end"]:
        if bump("E_A_OCCUPANCY_CONFLICT"):
            stop_all_motors(st)
            st["error_code"] = "E_A_OCCUPANCY_CONFLICT_X_TIMES"
            st["error_msg"] = "A occupancy conflict repeated too many times"
            st["qa_msg_A"] = "ERROR: A occupancy conflict repeated too many times"
            st["state_A"] = "ERROR"
            return (
                "ERROR: A occupancy conflict repeated too many times",
                "E_A_OCCUPANCY_CONFLICT_X_TIMES",
                "ERROR",
                "qa",
            )

        st["qa_msg_A"] = "WARN: A occupancy conflict"
        return (
            "WARN: A occupancy conflict",
            "E_A_OCCUPANCY_CONFLICT",
            "WARN",
            "qa",
        )
    else:
        clear_counter("E_A_OCCUPANCY_CONFLICT")

    # B ready conflict

    if st["b_has_part"] and st["station_ready"]:
        stop_all_motors(st)
        st["error_code"] = "E_B_READY_CONFLICT"
        st["error_msg"] = "B has part but station_ready is True"
        st["qa_msg_B"] = "ERROR: B has part but station_ready is True"
        st["state_A"] = "ERROR"
        st["state_B"] = "ERROR"
        return (
            "ERROR: B has part but station_ready is True",
            "E_B_READY_CONFLICT",
            "ERROR",
            "qa",
        )

    # Motor A unexpected

    if st["motor_a"] and not (
        st["u_has_part"]
        or st["a_has_part"]
        or st["a_at_end"]
        or st["state_A"] in ("TRANSFER_S1A", "MOVE_TO_S2A", "A_CLEARING", "A_WAIT_END_FREE")
    ):
        if bump("E_MOTOR_A_UNEXPECTED"):
            stop_all_motors(st)
            st["error_code"] = "E_MOTOR_A_UNEXPECTED_X_TIMES"
            st["error_msg"] = "Motor A ran unexpectedly too many times"
            st["qa_msg_A"] = "ERROR: motor A running without valid state too many times"
            st["state_A"] = "ERROR"
            return (
                "ERROR: motor A running without valid state too many times",
                "E_MOTOR_A_UNEXPECTED_X_TIMES",
                "ERROR",
                "qa",
            )

        st["qa_msg_A"] = "WARN: motor A running without valid state"
        return (
            "WARN: motor A running without valid state",
            "E_MOTOR_A_UNEXPECTED",
            "WARN",
            "qa",
        )
    else:
        clear_counter("E_MOTOR_A_UNEXPECTED")

    # Motor B unexpected

    if st["motor_b"] and not (
        st["a_has_part"]
        or st["a_at_end"]
        or st["b_has_part"]
        or st["state_B"] in ("PREP_TRANSFER_S1B", "TRANSFER_S1B", "ALIGNING", "CLAMPING", "DISCHARGE")
    ):
        if bump("E_MOTOR_B_UNEXPECTED"):
            stop_all_motors(st)
            st["error_code"] = "E_MOTOR_B_UNEXPECTED_X_TIMES"
            st["error_msg"] = "Motor B ran unexpectedly too many times"
            st["qa_msg_B"] = "ERROR: motor B running without valid state too many times"
            st["state_B"] = "ERROR"
            return (
                "ERROR: motor B running without valid state too many times",
                "E_MOTOR_B_UNEXPECTED_X_TIMES",
                "ERROR",
                "qa",
            )

        st["qa_msg_B"] = "WARN: motor B running without valid state"
        return (
            "WARN: motor B running without valid state",
            "E_MOTOR_B_UNEXPECTED",
            "WARN",
            "qa",
        )
    else:
        clear_counter("E_MOTOR_B_UNEXPECTED")

    # Clamp active at invalid state

    if st["clamp"] and st["state_B"] != "CLAMPING":
        stop_all_motors(st)
        st["error_code"] = "E_INVALID_CLAMP"
        st["error_msg"] = "Clamp is active at invalid state"
        st["qa_msg_B"] = "ERROR: clamp is active at invalid state"
        st["state_B"] = "ERROR"
        return (
            "ERROR: clamp is active at invalid state",
            "E_INVALID_CLAMP",
            "ERROR",
            "qa",
        )

    # Aligner active at invalid state

    if st["align_stopper"] and st["state_B"] not in ("PREP_TRANSFER_S1B", "TRANSFER_S1B", "ALIGNING"):
        stop_all_motors(st)
        st["error_code"] = "E_INVALID_ALIGN_STOPPER"
        st["error_msg"] = "Align stopper is out at invalid state"
        st["qa_msg_B"] = "ERROR: align stopper is out at invalid state"
        st["state_B"] = "ERROR"
        return (
            "ERROR: align stopper is out at invalid state",
            "E_INVALID_ALIGN_STOPPER",
            "ERROR",
            "qa",
        )

    # A state mismatch

    if st["state_A"] == "AT_END" and not st["a_at_end"]:
        stop_all_motors(st)
        st["error_code"] = "E_F_AND_S_MISMATCH"
        st["error_msg"] = "State A is AT_END but a_at_end flag is False"
        st["qa_msg_A"] = "ERROR: state A and a_at_end flag mismatch"
        st["state_A"] = "ERROR"
        return (
            "ERROR: state A and a_at_end flag mismatch",
            "E_F_AND_S_MISMATCH",
            "ERROR",
            "qa",
        )

    return None

# Auto recovers functions

def register_recoverable_fault(st: dict, error_code: str, window_ticks: int = 30, limit: int = 3) -> bool:
    last_tick = st["fault_last_tick"][error_code]
    current_tick = st["tick"]

    if current_tick - last_tick <= window_ticks:
        st["fault_counts"][error_code] += 1
    else:
        st["fault_counts"][error_code] = 1

    st["fault_last_tick"][error_code] = current_tick

    return st["fault_counts"][error_code] >= limit

def auto_recover_or_escalate(
    st: dict,
    error_code: str,
    recover_message: str,
    escalate_message: str,
    recover_fn,
) -> tuple[str, str | None, str, str]:
    escalate = register_recoverable_fault(st, error_code)

    if escalate:
        stop_all_motors(st)
        st["error_code"] = error_code
        st["error_msg"] = escalate_message
        st["state_A"] = "ERROR"
        st["state_B"] = "ERROR"
        return escalate_message, error_code, "ERROR", "manual_reset"

    recover_fn(st)
    return recover_message, error_code, "WARN", "auto_recover"

# recover faults

def recover_faults(st: dict) -> str:
    # B impossible state
    if st["b_has_part"] and st["station_ready"]:
        st["station_ready"] = False
        return "Recovered: station_ready corrected (B occupied)"

    # A impossible occupancy
    if st["a_has_part"] and st["a_at_end"]:
        st["a_has_part"] = False
        return "Recovered: A occupancy conflict cleared"

    # clamp still active but state wrong
    if st["clamp"] and st["state_B"] != "CLAMPING":
        st["clamp"] = False
        return "Recovered: clamp flag cleared"

    return "No recoverable faults detected"

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
    print("Commands: run, stop, status, stepauto, tick, feed, s2a, reset, qa_clear, flow max/normal/random, clearcount, clearlog, log, exit")

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
                message = "ERROR state: only reset, exit, log, clearlog, clearcount, status allowed"
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
  
                        # clear latched error
                        st["error_code"] = None
                        st["error_msg"] = ""

                        # clear fault history
                        for key in st["fault_counts"]:
                            st["fault_counts"][key] = 0
                        for key in st["fault_last_tick"]:
                            st["fault_last_tick"][key] = -999999
                            
                        # clear section messages if you already added them
                        if "msg_A" in st:
                            st["msg_A"] = ""
                        if "msg_B" in st:
                            st["msg_B"] = ""
                        if "msg_U" in st:
                            st["msg_U"] = ""

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
                            
                            for key in st["qa_counts"]:
                                st["qa_counts"][key] = 0
                                
                            keep_completed = st.get("completed_count", 0)
                            st.clear()
                            st.update(reset_system())
                            st["completed_count"] = keep_completed
                            message = "Manual reset accepted -> IDLE"

                        event_type = "maintenance"
                        level = "INFO"
                        
                    
                        
                else:
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