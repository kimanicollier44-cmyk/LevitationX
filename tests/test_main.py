import math, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import main as lx


def test_ems_force_positive(): assert lx.ems_force(5.0, 0.010) > 0
def test_ems_inverse_square(): assert abs(lx.ems_force(5.0, 0.010) / lx.ems_force(5.0, 0.020) - 4.0) < 1e-9
def test_ems_equilibrium():
    i = lx.ems_equilibrium_current(10.0, 0.010)
    assert abs(lx.ems_force(i, 0.010) - 10.0 * lx.G) < 1e-6
def test_ems_stiffness_unstable(): assert lx.ems_stiffness(5.0, 0.010) < 0
def test_ems_open_loop_unstable(): assert lx.ems_open_loop_drifts() is True
def test_ems_pid_settles(): assert lx.ems_pid_sim()["settled"] is True
def test_eds_standstill_zero(): assert lx.eds_force(0.0, 0.05) == 0.0
def test_eds_rises_with_speed(): assert lx.eds_force(50.0, 0.05) > lx.eds_force(10.0, 0.05)
def test_eds_liftoff(): assert lx.eds_liftoff_speed(1.0, 0.05) > 0
def test_sc_force_decays(): assert lx.sc_force(0.002) > lx.sc_force(0.010)
def test_sc_equilibrium():
    g = lx.sc_equilibrium_gap(10.0)
    assert g > 0 and abs(lx.sc_force(g) - 10.0 * lx.G) < 0.5
def test_sc_stiffness_restoring(): assert lx.sc_stiffness(0.005) > 0
def test_sc_state_cold(): assert lx.superconductor_state("YBCO", 77.0, 1.0).startswith("superconducting")
def test_sc_state_warm(): assert lx.superconductor_state("YBCO", 300.0, 1.0).startswith("normal")
def test_sc_state_field(): assert lx.superconductor_state("NbTi", 4.0, 20.0).startswith("normal")
def test_meissner(): assert abs(lx.meissner_screening(1.0, 100e-9, 100e-9) - math.exp(-1)) < 1e-12
def test_spl_ref(): assert abs(lx.sound_pressure_pa(0.0) - lx.P_REF) < 1e-12
def test_spl_20db(): assert abs(lx.sound_pressure_pa(20.0) / lx.P_REF - 10.0) < 1e-9
def test_node_spacing(): assert abs(lx.node_spacing_m(40000.0) - lx.C_AIR / 80000.0) < 1e-12
def test_acoustic_mass(): assert lx.acoustic_max_mass_g(165.0) > lx.acoustic_max_mass_g(155.0) > 0
def test_acoustic_nodes(): assert lx.acoustic_nodes_in_cavity(40000.0, 0.10) >= 20
def test_electrostatic_force(): assert lx.electrostatic_force(10000.0, 0.01, 0.005) > 0
def test_electrostatic_voltage():
    v = lx.electrostatic_voltage_for_weight(0.001, 0.01, 0.005)
    assert abs(lx.electrostatic_force(v, 0.01, 0.005) - 0.001 * lx.G) < 1e-6
def test_charge_force(): assert lx.charge_force_n(1e-6, 1e6) == 1.0
def test_diamagnetic_water(): assert 1000.0 < lx.diamagnetic_required_gradient("water") < 2000.0
def test_diamagnetic_graphite_easier():
    assert lx.diamagnetic_required_gradient("pyrolytic_graphite") < lx.diamagnetic_required_gradient("water")
def test_diamagnetic_force_positive(): assert lx.diamagnetic_force("bismuth", 1e-6, 1.0, 100.0) > 0
def test_earnshaw_unstable(): assert lx.earnshaw_demo()["static_config_unstable"] is True
def test_earnshaw_evasions(): assert len(lx.EARNSHAW["evasions"]) == 5
def test_classifier_ems(): assert lx.stability_report()["ems"] == "unstable"
def test_classifier_sc(): assert lx.stability_report()["superconducting"] == "stable"
def test_classifier_dia(): assert lx.stability_report()["diamagnetic"] == "stable"
def test_classifier_pid(): assert lx.stability_report()["ems_with_pid"] == "stable-with-feedback"
def test_methods_six(): assert len(lx.METHODS) == 6
def test_curve_monotonic():
    c = lx.force_gap_curve("ems")
    assert c["2mm"] > c["10mm"] > c["30mm"]
def test_maglev():
    mv = lx.maglev_vehicle()
    assert abs(mv["total_lift_force_n"] - 40000.0 * lx.G) < 0.01 and mv["gate"] == "HOLD"
def test_holds_count(): assert len(lx.HOLD_GATES) == 14
def test_holds_all_hold(): assert all(v.startswith("HOLD") for v in lx.HOLD_GATES.values())
def test_gate(): assert lx.gate("human_levitation") == "HOLD" and lx.gate("run_simulation") == "PROCEED"
def test_hold_demo_exit_code(): assert lx.main(["hold-demo", "human_levitation"]) == 2
def test_carbon4(): 
    d = lx.carbon4_decide(); assert d["can_override_hold"] is False and d["live_calls"] == 0 and len(d["trace_sha256_16"]) == 16
def test_claude(): assert lx.claude_advisor()["can_override_hold"] is False
def test_flow(): 
    f = lx.google_flow_plan(); assert f["rendered"] is False and f["live"] == 0
def test_checks_all_pass():
    checks = lx.run_checks(); assert all(ok for _, ok in checks), [n for n, ok in checks if not ok]
def test_deterministic_pid(): assert lx.ems_pid_sim() == lx.ems_pid_sim()
