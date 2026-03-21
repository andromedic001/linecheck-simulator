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