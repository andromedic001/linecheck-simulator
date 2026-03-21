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
