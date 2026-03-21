from helpers import stop_all_motors

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
            st["auto_run"] = False
            
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
        st["auto_run"] = False
        
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
            st["auto_run"] = False
            
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
            st["auto_run"] = False
            
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
        st["auto_run"] = False
        
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
        st["auto_run"] = False
        
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
        st["auto_run"] = False
        
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

    # align stopper active at invalid state
    if st["align_stopper"] and st["state_B"] not in ("PREP_TRANSFER_S1B", "TRANSFER_S1B", "ALIGNING"):
        st["align_stopper"] = False
        return "Recovered: align stopper flag cleared"

    # A state mismatch
    if st["state_A"] == "AT_END" and not st["a_at_end"]:
        st["state_A"] = "IDLE"
        return "Recovered: state_A corrected from AT_END to IDLE"

    # unexpected motor A
    if st["motor_a"] and st["state_A"] not in ("TRANSFER_S1A", "MOVE_TO_S2A", "A_CLEARING", "A_WAIT_END_FREE"):
        st["motor_a"] = False
        return "Recovered: unexpected motor A stopped"

    # unexpected motor B
    if st["motor_b"] and st["state_B"] not in ("PREP_TRANSFER_S1B", "TRANSFER_S1B", "ALIGNING", "CLAMPING", "DISCHARGE"):
        st["motor_b"] = False
        return "Recovered: unexpected motor B stopped"

    return "No recoverable faults detected"