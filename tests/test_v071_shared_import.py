from cdc_analyzer.gui_release_v071 import (
    classify_response_current_state,
    response_stage_name,
)


def test_current_state_mapping_uses_cdc_setpoint_convention():
    assert classify_response_current_state(0.30) == "Soft"
    assert classify_response_current_state(0.34) == "Soft"
    assert classify_response_current_state(0.80) == "Medium"
    assert classify_response_current_state(0.90) == "Medium"
    assert classify_response_current_state(0.95) == "Medium"
    assert classify_response_current_state(1.60) == "Hard"
    assert classify_response_current_state(1.62) == "Hard"


def test_stage_labels_follow_current_states_not_force_ranking():
    assert response_stage_name(0.30, 1.62) == "Soft → Hard"
    assert response_stage_name(1.60, 0.34) == "Hard → Soft"
    assert response_stage_name(0.30, 0.95) == "Soft → Medium"
    assert response_stage_name(1.61, 0.90) == "Hard → Medium"
    assert response_stage_name(0.80, 0.95) == "Medium → Medium"
