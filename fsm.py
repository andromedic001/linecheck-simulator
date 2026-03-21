from helpers import stop_all_motors, deny_transfer, update_statistics
from cascade import cascade_logic
from qa import qa_checks

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
        st["auto_run"] = False
        
        st["error_code"] = error_code
        st["error_msg"] = escalate_message
        st["state_A"] = "ERROR"
        st["state_B"] = "ERROR"
        return escalate_message, error_code, "ERROR", "manual_reset"

    recover_fn(st)
    return recover_message, error_code, "WARN", "auto_recover"

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
        st["msg_B"] = "INFO: transfer to B"
        st["counter_B"] += 1
        st["motor_a"] = True
        st["motor_b"] = True

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
        st["msg_B"] = "INFO: waiting clamp"
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
            st["auto_run"] = False
            
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
            st["msg_B"] = "INFO: discharging"
            
            st["counter_B"] = 0
            st["motor_b"] = False
            st["align_stopper"] = False
            st["aligned"] = False
            st["clamp"] = False
            st["clamped"] = False
            st["station_ready"] = True
            st["b_has_part"] = False
            st["completed_count"] += 1
            
            # throughput optimization:
            # if next part is already waiting at A_END,
            # do not go through full idle loop, start next transfer immediately
            if st["a_at_end"] and not st["b_has_part"]:
                st["msg_B"] = "INFO: next transfer immediately"
                st["state_B"] = "TRANSFER_S1B"
                return "B discharge -> next transfer immediately", None, "INFO", "controller"
            else: 
                st["state_B"] = "IDLE"
                return "B: discharge complete -> IDLE", None, "INFO", "controller"

        return "B: discharging...", None, "INFO", "controller"

    if state_B == "ERROR":
        
        st["auto_run"] = False
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
                return "INFO: S1A confirmed, but A end is occupied -> waiting", None, "INFO", "interlock"
            else:
                st["msg_A"] = "INFO: moving to A end"
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
                return "INFO: auto S1A confirmed, but A end is occupied -> waiting", None, "INFO", "interlock"
            else:
                st["msg_A"] = "INFO: moving to A end"
                st["counter_A"] = 1
                st["motor_a"] = True
                st["state_A"] = "MOVE_TO_S2A"
                return "Auto S1A confirmed -> continue moving to S2A", None, "INFO", "controller"
            
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
            return "A: waiting, station busy", None, "INFO", "interlock"

        if st["b_has_part"]:
            deny_transfer(st)
            return "A: waiting, next section blocked", None, "INFO", "interlock"

        # transfer launch is handled by cascade
        st["msg_A"] = ""
        return "A: part at end, waiting transfer to B", None, "INFO", "controller"
    
    if state_A == "A_CLEARING":
        # throughput optimization:
        # keep line moving without going back to IDLE,
        # pre-arm next transfer while A tail is clearing
        message = "A: clearing tail motion..."
        st["msg_A"] = "INFO: clearing tail motion"
        st["counter_A"] += 1
        st["motor_a"] = True

        if st["counter_A"] >= 1:
            st["counter_A"] = 0

            if st["u_has_part"] and (not st["a_has_part"]) and (not st["a_at_end"]):
                st["msg_A"] = "INFO: direct next transfer"
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
        
        st["auto_run"] = False
        stop_all_motors(st)
        
        return "A: ERROR state", st.get("error_code"), "ERROR", "controller"

    return None