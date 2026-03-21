import os
import json
from datetime import datetime

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
LOG_FILE = os.path.join(BASE_DIR, "events.jsonl")

def clear_screen() -> None:
    os.system("cls" if os.name == "nt" else "clear")

def clear_qa_counts(st: dict) -> None:
    for key in st["qa_counts"]:
        st["qa_counts"][key] = 0
        
def clear_runtime_messages(st: dict) -> None:
    st["msg_U"] = ""
    st["msg_A"] = ""
    st["msg_B"] = ""
    st["qa_msg_U"] = ""
    st["qa_msg_A"] = ""
    st["qa_msg_B"] = ""

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
    print("feed | s2a | reset | recover | flow max/normal/random")
    print(" log | clearlog | clearcount | exit\n")
    
    print("STATISTICS")
    print(f"Parts per tick : {st['parts_per_tick']:.4f}")
    print(f"Parts for / 1 hour : {parts_1h:.0f}")
    print(f"Parts for / 8 hours :{parts_8h:.0f}")
    print("=" * 56)