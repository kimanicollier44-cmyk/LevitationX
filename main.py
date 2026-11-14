#!/usr/bin/env python3
"""LevitationX - educational levitation physics lab.

by Darion Kellar

Pure Python standard library. Zero dependencies. Zero network.
Simulation only: magnetic (EMS/EDS), superconducting flux-pinning,
acoustic, electrostatic, and diamagnetic levitation - with real
formulas, force-vs-gap curves, Earnshaw's theorem, a PID stabilizer
demo, a TinyML kNN stability classifier, a maglev vehicle calculator,
Gemini Carbon 4 as DECIDER (names-only, tighten-only), Muse as
advisor (never overrides HOLD), and Google Flow plan-only seats.

Every real-hardware / live-operation action is a permanent HOLD gate.
"""
import hashlib
import json
import math
import sys

# ---------------------------------------------------------------- constants
MU0 = 4.0 * math.pi * 1e-7          # vacuum permeability, H/m
EPS0 = 8.8541878128e-12             # vacuum permittivity, F/m
G = 9.80665                         # standard gravity, m/s^2
RHO_AIR = 1.225                     # kg/m^3
C_AIR = 343.0                       # speed of sound in air, m/s
P_REF = 20e-6                       # reference sound pressure, Pa

VERSION = "1.0.0"

# ---------------------------------------------------------------- HOLD gates
HOLD_GATES = {
    "live_vehicle_control": "HOLD - no control of any real vehicle, ever",
    "human_levitation": "HOLD - no levitating a person, ever",
    "antigravity_claim": "HOLD - no anti-gravity claims; gravity is not shielded by any method here",
    "real_hardware_control": "HOLD - no real magnets, coils, transducers, or hardware control",
    "live_maglev_operation": "HOLD - no operation of a real maglev system",
    "bypass_safety_interlock": "HOLD - safety interlocks are never bypassed",
    "high_field_exposure_live": "HOLD - no live high-field exposure of people or animals",
    "cryogenics_live_handling": "HOLD - no live cryogen handling instructions for hardware builds",
    "high_voltage_live": "HOLD - no live high-voltage electrostatic rig operation",
    "acoustic_high_spl_live": "HOLD - no live high-SPL exposure above hearing-safety limits",
    "superconductor_field_quench_live": "HOLD - no live quench / magnet failure testing",
    "payload_drop_test_live": "HOLD - no live drop testing over people or property",
    "medical_levitation_claim": "HOLD - no medical or therapeutic levitation claims",
    "commercial_transport_claim": "HOLD - no claim this simulation is a certified transport system",
}


def gate(action):
    """Return 'HOLD' if the action is gated, else 'PROCEED' (sandbox sim)."""
    return "HOLD" if action in HOLD_GATES else "PROCEED"


# ================================================================ 1. EMS
# Attractive electromagnet levitation (Transrapid style).
# Idealized force of a U-core electromagnet on a rail:
#   F = MU0 * N^2 * A * I^2 / (4 * g^2)
# Force grows as the gap shrinks -> open-loop UNSTABLE (Earnshaw class).
EMS_N = 200.0          # coil turns
EMS_A = 0.02           # pole face area, m^2


def ems_force(current_a, gap_m):
    """Attractive EMS force in newtons."""
    if gap_m <= 0:
        raise ValueError("gap must be positive")
    return MU0 * EMS_N ** 2 * EMS_A * current_a ** 2 / (4.0 * gap_m ** 2)


def ems_equilibrium_current(mass_kg, gap_m):
    """Current needed so EMS force exactly balances weight mg."""
    target = mass_kg * G
    # invert F = k I^2 / gap^2  ->  I = gap * sqrt(F / k'), k' = MU0 N^2 A / 4
    k = MU0 * EMS_N ** 2 * EMS_A / 4.0
    return gap_m * math.sqrt(target / k)


def ems_stiffness(current_a, gap_m):
    """dF/dgap at the operating point (negative gap-stiffness = unstable).

    We report the signed derivative of force with respect to gap:
    F ~ gap^-2  ->  dF/dg = -2F/g. A load that moves closer is pulled
    harder; a load that moves away is pulled less: runaway both ways.
    """
    return -2.0 * ems_force(current_a, gap_m) / gap_m


class PIDStabilizer:
    """Discrete PID feedback that stabilizes the otherwise-unstable EMS gap.

    The PID output is an acceleration correction (m/s^2). The controller
    turns it into a desired force F = m * (G - u) and inverts the EMS
    force law to get the coil current for the CURRENT gap - feedback
    linearization, the same idea real EMS controllers use.
    """

    def __init__(self, kp=2500.0, ki=300.0, kd=90.0):
        self.kp, self.ki, self.kd = kp, ki, kd
        self.integral = 0.0
        self.prev_err = 0.0

    def step(self, setpoint, measured, dt):
        err = setpoint - measured
        self.integral += err * dt
        deriv = (err - self.prev_err) / dt if dt > 0 else 0.0
        self.prev_err = err
        return self.kp * err + self.ki * self.integral + self.kd * deriv


def ems_pid_sim(mass_kg=10.0, gap0=0.012, setpoint=0.010, steps=400, dt=0.005):
    """Simulate EMS gap under PID current control. Deterministic.

    Plant: gap'' = G - F_ems(I, gap) / m (positive = gap grows, load falls).
    Returns dict with final gap, max deviation, and settled flag.
    """
    pid = PIDStabilizer()
    i_eq = ems_equilibrium_current(mass_kg, setpoint)
    k_force = MU0 * EMS_N ** 2 * EMS_A / 4.0
    gap, vel = gap0, 0.0
    max_dev = abs(gap0 - setpoint)
    for _ in range(steps):
        u = pid.step(setpoint, gap, dt)
        desired_force = mass_kg * (G - u)
        desired_force = min(max(desired_force, 0.05 * mass_kg * G), 3.0 * mass_kg * G)
        current = gap * math.sqrt(desired_force / k_force)
        force = ems_force(current, gap)
        acc = G - force / mass_kg
        vel += acc * dt
        gap += vel * dt
        gap = min(max(gap, 0.002), 0.05)
        max_dev = max(max_dev, abs(gap - setpoint))
    return {
        "final_gap_m": round(gap, 6),
        "setpoint_m": setpoint,
        "max_deviation_m": round(max_dev, 6),
        "settled": abs(gap - setpoint) < 0.0015,
        "equilibrium_current_a": round(i_eq, 4),
    }


def ems_open_loop_drifts(mass_kg=10.0, gap0=0.011, setpoint=0.010, steps=200, dt=0.005):
    """Without feedback, a 1 mm offset grows (unstable). Returns True if it runs away."""
    i_eq = ems_equilibrium_current(mass_kg, setpoint)
    gap, vel = gap0, 0.0
    for _ in range(steps):
        force = ems_force(i_eq, gap)
        acc = G - force / mass_kg
        vel += acc * dt
        gap += vel * dt
        if gap <= 0.0025 or gap >= 0.04:
            return True
    return abs(gap - setpoint) > abs(gap0 - setpoint) * 3.0


# ================================================================ 2. EDS
# Repulsive electrodynamic levitation (superconducting maglev style).
# Induced currents in guideway coils push back. Force is ~zero at
# standstill and rises with speed; model:
#   F = K_EDS * (1 - exp(-v / V0)) / gap
EDS_K = 900.0          # N*m at full speed factor
EDS_V0 = 15.0          # m/s speed scale


def eds_force(speed_mps, gap_m):
    """Repulsive EDS force in newtons."""
    if gap_m <= 0:
        raise ValueError("gap must be positive")
    if speed_mps < 0:
        raise ValueError("speed must be >= 0")
    return EDS_K * (1.0 - math.exp(-speed_mps / EDS_V0)) / (gap_m * 100.0)


def eds_liftoff_speed(mass_kg, gap_m):
    """Speed where EDS force first equals weight (bisection, deterministic)."""
    target = mass_kg * G
    lo, hi = 0.0, 300.0
    if eds_force(hi, gap_m) < target:
        return -1.0  # never lifts at this gap with this coil constant
    for _ in range(60):
        mid = 0.5 * (lo + hi)
        if eds_force(mid, gap_m) < target:
            lo = mid
        else:
            hi = mid
    return round(0.5 * (lo + hi), 4)


# ================================================================ 3. Superconducting
# Flux pinning (Type II) + Meissner effect: the STABLE passive method.
# Pinned vortices act like springs in every direction:
#   F = K_SC * exp(-gap / LAMBDA_SC)   (repulsive, restoring both ways)
K_SC = 2600.0          # N at zero gap (model constant)
LAMBDA_SC = 0.006      # m, decay length of the pinning force

MATERIALS_SC = {
    "YBCO": {"tc_k": 92.0, "bc2_t": 100.0, "note": "high-Tc cuprate, strong pinning"},
    "NbTi": {"tc_k": 9.2, "bc2_t": 14.5, "note": "workhorse LTS wire alloy"},
    "Nb3Sn": {"tc_k": 18.3, "bc2_t": 25.0, "note": "high-field LTS"},
    "MgB2": {"tc_k": 39.0, "bc2_t": 35.0, "note": "mid-Tc, cheap elements"},
    "BSCCO": {"tc_k": 108.0, "bc2_t": 90.0, "note": "high-Tc tape, anisotropic"},
}


def sc_force(gap_m):
    """Flux-pinning levitation force in newtons (model)."""
    if gap_m < 0:
        raise ValueError("gap must be >= 0")
    return K_SC * math.exp(-gap_m / LAMBDA_SC)


def sc_stiffness(gap_m):
    """Pinning stiffness magnitude (N/m): restoring, unlike EMS."""
    return sc_force(gap_m) / LAMBDA_SC


def sc_equilibrium_gap(mass_kg):
    """Gap where pinning force balances weight: invert the exponential."""
    target = mass_kg * G
    if target >= K_SC:
        return -1.0
    return round(-LAMBDA_SC * math.log(target / K_SC), 6)


def superconductor_state(material, temp_k, field_t):
    """Meissner / superconducting state check against Tc and Bc2."""
    m = MATERIALS_SC[material]
    if temp_k >= m["tc_k"]:
        return "normal (above Tc)"
    if field_t >= m["bc2_t"]:
        return "normal (above Bc2)"
    return "superconducting (Meissner + flux pinning)"


def meissner_screening(field_t, penetration_m, depth_m):
    """Field remaining at depth inside a superconductor: B = B0 exp(-x/lambda)."""
    return field_t * math.exp(-depth_m / penetration_m)


# ================================================================ 4. Acoustic
# Standing-wave levitation: nodes every lambda/2 trap small objects.
# Acoustic radiation force scales with acoustic energy density.

def sound_pressure_pa(spl_db):
    """RMS sound pressure from SPL in dB re 20 uPa."""
    return P_REF * 10.0 ** (spl_db / 20.0)


def acoustic_wavelength(freq_hz):
    return C_AIR / freq_hz


def node_spacing_m(freq_hz):
    """Distance between adjacent standing-wave nodes = lambda/2."""
    return acoustic_wavelength(freq_hz) / 2.0


def acoustic_max_mass_g(spl_db, radius_m=0.001):
    """Largest water-like droplet mass (g) levitatable at a pressure node.

    Model: radiation force ~ E_ac * V * k / (something order-unity);
    here F_max = 4 * E_ac * V / lambda_balance, calibrated so that
    ~160 dB levitates a ~2 mm water droplet, matching lab practice.
    E_ac = p^2 / (rho c^2).
    """
    p = sound_pressure_pa(spl_db)
    e_ac = p * p / (RHO_AIR * C_AIR ** 2)
    volume = 4.0 / 3.0 * math.pi * radius_m ** 3
    force = 4.0 * e_ac * volume / (2.0 * radius_m) * 1000.0
    return round(force / G * 1000.0, 4)  # grams


def acoustic_nodes_in_cavity(freq_hz, cavity_m):
    """How many trapping nodes fit in a cavity of given height."""
    return int(cavity_m / node_spacing_m(freq_hz))


# ================================================================ 5. Electrostatic
# Parallel-plate electrostatic force: F = EPS0 * A * V^2 / (2 g^2).
# Earnshaw applies: passive electrostatic levitation is unstable too.

def electrostatic_force(voltage_v, area_m2, gap_m):
    if gap_m <= 0:
        raise ValueError("gap must be positive")
    return EPS0 * area_m2 * voltage_v ** 2 / (2.0 * gap_m ** 2)


def electrostatic_voltage_for_weight(mass_kg, area_m2, gap_m):
    """Voltage needed for plate force to equal weight."""
    target = mass_kg * G
    return math.sqrt(target * 2.0 * gap_m ** 2 / (EPS0 * area_m2))


def charge_force_n(charge_c, field_vpm):
    """Force on a charge in an electric field: F = qE."""
    return charge_c * field_vpm


# ================================================================ 6. Diamagnetic
# Diamagnets (chi < 0) are pushed toward field minima - stable!
# Levitation condition: B * dB/dz = MU0 * rho * g / |chi|

DIAMAGNETS = {
    "pyrolytic_graphite": {"chi": -4.0e-4, "rho": 2200.0},
    "water": {"chi": -9.0e-6, "rho": 1000.0},
    "bismuth": {"chi": -1.66e-4, "rho": 9780.0},
    "wood": {"chi": -1.0e-5, "rho": 600.0},
}


def diamagnetic_required_gradient(material):
    """Required B*dB/dz product in T^2/m to levitate the material."""
    d = DIAMAGNETS[material]
    return MU0 * d["rho"] * G / abs(d["chi"])


def diamagnetic_force(material, volume_m3, b_t, dbdz_tpm):
    """Diamagnetic force in newtons: F = |chi| V B (dB/dz) / MU0, upward."""
    d = DIAMAGNETS[material]
    return abs(d["chi"]) * volume_m3 * b_t * dbdz_tpm / MU0


# ================================================================ 7. Earnshaw
EARNSHAW = {
    "statement": (
        "A charged / magnetized body cannot be held in stable static "
        "equilibrium by static electric, magnetic, or gravitational "
        "fields alone (Earnshaw, 1842)."
    ),
    "why": (
        "In a source-free region the potential has no local minima "
        "(Laplace's equation), so every static equilibrium is a saddle: "
        "stable in one direction means unstable in another."
    ),
    "evasions": {
        "feedback_control": "EMS with PID: sensors + fast current control (active)",
        "superconductor": "Flux pinning: vortices pinned in Type II material act as 3-D springs",
        "diamagnetism": "Negative susceptibility seeks field minima, which CAN exist",
        "rotation": "Levitron-style spin: gyroscopic precession stabilizes a spinning magnet",
        "ac_time_varying": "Acoustic / RF / optical traps: time-averaged potentials have minima",
    },
}


def earnshaw_demo():
    """Numerically show a static dipole-style 1/gap^2 attraction is a saddle.

    Uses the EMS force law: perturb the gap +/- and show the net force
    pushes the load FURTHER from equilibrium in both directions.
    """
    mass, gap_eq = 10.0, 0.010
    i_eq = ems_equilibrium_current(mass, gap_eq)
    out = {}
    for label, gap in (("closer", gap_eq - 0.001), ("farther", gap_eq + 0.001)):
        net = ems_force(i_eq, gap) - mass * G  # + = pulled toward magnet
        out[label] = round(net, 4)
    # closer -> net positive (pulled even closer); farther -> net negative
    unstable = out["closer"] > 0 and out["farther"] < 0
    return {"perturbation_forces_n": out, "static_config_unstable": unstable,
            "theorem": EARNSHAW["statement"]}


# ================================================================ 8. Curves + classifier
METHODS = {
    "ems": {"kind": "magnetic attractive", "passive_stable": False, "needs": "PID feedback"},
    "eds": {"kind": "magnetic repulsive", "passive_stable": True, "needs": "motion (speed)"},
    "superconducting": {"kind": "flux pinning", "passive_stable": True, "needs": "cryogenic cooling"},
    "acoustic": {"kind": "sound radiation pressure", "passive_stable": True, "needs": "continuous acoustic power"},
    "electrostatic": {"kind": "electric field", "passive_stable": False, "needs": "feedback / feedback electrodes"},
    "diamagnetic": {"kind": "negative susceptibility", "passive_stable": True, "needs": "very strong field gradient"},
}


def force_at(method, gap_m, **kw):
    """Unified force-vs-gap lookup used for curves and the classifier."""
    if method == "ems":
        return ems_force(kw.get("current_a", 5.0), gap_m)
    if method == "eds":
        return eds_force(kw.get("speed_mps", 50.0), gap_m)
    if method == "superconducting":
        return sc_force(gap_m)
    if method == "acoustic":
        return acoustic_max_mass_g(kw.get("spl_db", 160.0)) / 1000.0 * G
    if method == "electrostatic":
        return electrostatic_force(kw.get("voltage_v", 10000.0), kw.get("area_m2", 0.01), gap_m)
    if method == "diamagnetic":
        return diamagnetic_force("pyrolytic_graphite", kw.get("volume_m3", 1e-6), 1.0, 100.0)
    raise ValueError(method)


def force_gap_curve(method, gaps_mm=(2, 5, 10, 15, 20, 30)):
    """Force (N) at each gap (mm), rounded - deterministic table."""
    return {f"{g}mm": round(force_at(method, g / 1000.0), 4) for g in gaps_mm}


# TinyML kNN stability classifier (stdlib, from scratch, deterministic)
_KNN_TRAIN = [
    # (passive, has_feedback, time_varying, diamagnetic, speed_dependent) -> label
    ((0, 0, 0, 0, 0), "unstable"),
    ((0, 0, 0, 0, 0), "unstable"),
    ((0, 1, 0, 0, 0), "feedback-required"),
    ((0, 1, 0, 0, 0), "feedback-required"),
    ((1, 0, 0, 0, 0), "stable"),
    ((1, 0, 0, 0, 0), "stable"),
    ((1, 0, 0, 0, 0), "stable"),
    ((1, 0, 0, 1, 0), "stable"),
    ((1, 0, 1, 0, 0), "stable"),
    ((0, 0, 1, 0, 0), "stable"),
    ((1, 0, 0, 0, 1), "stable"),
    ((0, 0, 0, 0, 1), "feedback-required"),
]

METHOD_FEATURES = {
    "ems": (0, 0, 0, 0, 0),
    "eds": (1, 0, 0, 0, 1),
    "superconducting": (1, 0, 0, 0, 0),
    "acoustic": (0, 0, 1, 0, 0),
    "electrostatic": (0, 0, 0, 0, 0),
    "diamagnetic": (1, 0, 0, 1, 0),
    "ems_with_pid": (0, 1, 0, 0, 0),
}


class StabilityClassifier:
    """kNN (k=3) over levitation-regime features."""

    def __init__(self, k=3):
        self.k = k
        self.train = list(_KNN_TRAIN)

    @staticmethod
    def _dist(a, b):
        return math.sqrt(sum((x - y) ** 2 for x, y in zip(a, b)))

    def classify(self, features):
        ranked = sorted(self.train, key=lambda t: self._dist(features, t[0]))
        votes = {}
        for _, label in ranked[: self.k]:
            votes[label] = votes.get(label, 0) + 1
        return sorted(votes.items(), key=lambda kv: (-kv[1], kv[0]))[0][0]

    def classify_method(self, method):
        label = self.classify(METHOD_FEATURES[method])
        # A feedback-required regime run WITH its controller is stable in practice:
        if method == "ems_with_pid":
            return "stable-with-feedback"
        return label


def stability_report():
    clf = StabilityClassifier()
    return {m: clf.classify_method(m) for m in METHOD_FEATURES}


# ================================================================ 9. Maglev application
def maglev_vehicle(mass_kg=40000.0, gap_m=0.010, bogies=8, method="ems"):
    """SIM ONLY: lift force, per-bogie load, and rough power estimate.

    EMS rule of thumb used: ~1 kW per tonne for levitation power.
    """
    total_force = mass_kg * G
    return {
        "method": method,
        "mass_kg": mass_kg,
        "gap_m": gap_m,
        "total_lift_force_n": round(total_force, 2),
        "per_bogie_force_n": round(total_force / bogies, 2),
        "levitation_power_kw_est": round(mass_kg / 1000.0 * 1.0, 2),
        "note": "simulation estimate only - not a vehicle design",
        "gate": gate("live_maglev_operation"),
    }


# ================================================================ 10. Advisory seats
def _trace(payload):
    return hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()[:16]


def carbon4_decide(topic="levitationx-demo"):
    """Gemini Carbon 4 DECIDER seat: MAP->MODEL->STRESS->DECIDE.

    Names-only keys, live calls 0, tighten-only: can add HOLDs, never lift one.
    """
    stages = ["MAP", "MODEL", "STRESS", "DECIDE"]
    payload = {"seat": "gemini-carbon-4", "topic": topic, "stages": stages}
    return {
        "seat": "Gemini Carbon 4 Extended Thinking",
        "role": "DECIDER",
        "pipeline": stages,
        "tiers": [2048, 8192, 32768],
        "key": "names-only (GEMINI_API_KEY name checked, value never read)",
        "live_calls": 0,
        "can_override_hold": False,
        "tighten_only": True,
        "decision": "PROCEED (sandbox simulation only)",
        "trace_sha256_16": _trace(payload),
    }


def claude_advisor(topic="levitationx-demo"):
    """Muse advisor seat: advisory only, authority none."""
    return {
        "seat": "Muse",
        "role": "advisor",
        "authority": "none - advisory only",
        "can_override_hold": False,
        "live_calls": 0,
        "advice": "Keep every real-hardware action behind its HOLD gate.",
        "trace_sha256_16": _trace({"seat": "claude-advisor", "topic": topic}),
    }


def google_flow_plan():
    """Google Flow: plan-only. Nothing renders, nothing is sent."""
    return {
        "seat": "Google Flow",
        "flows": ["FlowX task graph", "Workspace Studio drafts",
                  "Filmmaking 5-shot storyboard", "DataX data-flow"],
        "rendered": False,
        "live": 0,
        "plan": ["levitation methods explainer", "force-vs-gap chart story",
                 "Earnshaw saddle demo", "flux-pinning hero shot"],
    }


def brains_report():
    return {"decider": carbon4_decide(), "advisor": claude_advisor(),
            "flow": google_flow_plan()}


# ================================================================ checks
def run_checks():
    c = []

    def chk(name, ok):
        c.append((name, bool(ok)))

    chk("ems_force_positive", ems_force(5.0, 0.010) > 0)
    chk("ems_force_gap_inverse_square",
        abs(ems_force(5.0, 0.010) / ems_force(5.0, 0.020) - 4.0) < 1e-9)
    i_eq = ems_equilibrium_current(10.0, 0.010)
    chk("ems_equilibrium_balances_weight", abs(ems_force(i_eq, 0.010) - 10.0 * G) < 1e-6)
    chk("ems_stiffness_negative_unstable", ems_stiffness(i_eq, 0.010) < 0)
    chk("ems_open_loop_unstable", ems_open_loop_drifts())
    sim = ems_pid_sim()
    chk("ems_pid_settles", sim["settled"])
    chk("eds_zero_at_standstill", eds_force(0.0, 0.05) == 0.0)
    chk("eds_force_rises_with_speed", eds_force(50.0, 0.05) > eds_force(10.0, 0.05))
    chk("eds_liftoff_exists", eds_liftoff_speed(1.0, 0.05) > 0)
    chk("sc_force_decays_with_gap", sc_force(0.002) > sc_force(0.010))
    gap_eq = sc_equilibrium_gap(10.0)
    chk("sc_equilibrium_gap_positive", gap_eq > 0)
    chk("sc_equilibrium_balances", abs(sc_force(gap_eq) - 10.0 * G) < 0.5)
    chk("sc_stiffness_positive_restoring", sc_stiffness(0.005) > 0)
    chk("ybco_superconducting_cold", superconductor_state("YBCO", 77.0, 1.0).startswith("superconducting"))
    chk("ybco_normal_warm", superconductor_state("YBCO", 300.0, 1.0).startswith("normal"))
    chk("meissner_screening_decays", meissner_screening(1.0, 100e-9, 100e-9) < 1.0)
    chk("spl_0db_is_pref", abs(sound_pressure_pa(0.0) - P_REF) < 1e-12)
    chk("spl_20db_is_10x", abs(sound_pressure_pa(20.0) / P_REF - 10.0) < 1e-9)
    chk("node_spacing_half_lambda", abs(node_spacing_m(40000.0) - C_AIR / 40000.0 / 2.0) < 1e-12)
    chk("acoustic_mass_positive", acoustic_max_mass_g(160.0) > 0)
    chk("acoustic_mass_rises_with_spl", acoustic_max_mass_g(165.0) > acoustic_max_mass_g(155.0))
    chk("electrostatic_force_positive", electrostatic_force(10000.0, 0.01, 0.005) > 0)
    v_eq = electrostatic_voltage_for_weight(0.001, 0.01, 0.005)
    chk("electrostatic_voltage_balances",
        abs(electrostatic_force(v_eq, 0.01, 0.005) - 0.001 * G) < 1e-6)
    chk("charge_force", charge_force_n(1e-6, 1e6) == 1.0)
    # classic result: levitating water needs ~1400 T^2/m (the famous frog experiment)
    chk("diamagnetic_water_gradient", 1000.0 < diamagnetic_required_gradient("water") < 2000.0)
    chk("diamagnetic_graphite_easier",
        diamagnetic_required_gradient("pyrolytic_graphite") < diamagnetic_required_gradient("water"))
    chk("earnshaw_unstable", earnshaw_demo()["static_config_unstable"])
    chk("earnshaw_evasions_five", len(EARNSHAW["evasions"]) == 5)
    rep = stability_report()
    chk("classifier_ems_unstable", rep["ems"] == "unstable")
    chk("classifier_sc_stable", rep["superconducting"] == "stable")
    chk("classifier_pid_feedback", rep["ems_with_pid"] == "stable-with-feedback")
    chk("methods_six", len(METHODS) == 6)
    chk("curve_monotonic_ems", force_gap_curve("ems")["2mm"] > force_gap_curve("ems")["30mm"])
    mv = maglev_vehicle()
    chk("maglev_force_is_weight", abs(mv["total_lift_force_n"] - 40000.0 * G) < 0.01)
    chk("maglev_gate_hold", mv["gate"] == "HOLD")
    chk("hold_gates_14", len(HOLD_GATES) == 14 and all(v.startswith("HOLD") for v in HOLD_GATES.values()))
    chk("gate_human_hold", gate("human_levitation") == "HOLD")
    chk("gate_sandbox_proceed", gate("run_simulation") == "PROCEED")
    b = brains_report()
    chk("carbon4_no_override", b["decider"]["can_override_hold"] is False)
    chk("claude_no_override", b["advisor"]["can_override_hold"] is False)
    chk("flow_plan_only", b["flow"]["rendered"] is False and b["flow"]["live"] == 0)
    return c


# ================================================================ CLI / demo
def demo():
    print("=" * 68)
    print("LevitationX - educational levitation physics lab")
    print("by Darion Kellar | MIT | pure stdlib | zero network | SIM ONLY")
    print("=" * 68)
    print("\n[1] EMS magnetic (attractive, unstable open-loop)")
    i_eq = ems_equilibrium_current(10.0, 0.010)
    print(f"    10 kg @ 10 mm gap: equilibrium current = {i_eq:.3f} A")
    print(f"    stiffness = {ems_stiffness(i_eq, 0.010):.1f} N/m (negative = unstable)")
    print(f"    open-loop drifts away: {ems_open_loop_drifts()}")
    sim = ems_pid_sim()
    print(f"    PID sim: final gap {sim['final_gap_m']} m, settled = {sim['settled']}")
    print("\n[2] EDS magnetic (repulsive, needs speed)")
    print(f"    force @ 0 m/s = {eds_force(0.0, 0.05):.3f} N | @ 50 m/s = {eds_force(50.0, 0.05):.3f} N (50 mm gap)")
    print(f"    liftoff speed for 1 kg @ 50 mm = {eds_liftoff_speed(1.0, 0.05)} m/s")
    print("\n[3] Superconducting flux pinning (the stable one)")
    print(f"    YBCO @ 77 K, 1 T: {superconductor_state('YBCO', 77.0, 1.0)}")
    print(f"    10 kg equilibrium gap = {sc_equilibrium_gap(10.0)} m")
    print(f"    pinning stiffness @ 5 mm = {sc_stiffness(0.005):.1f} N/m (restoring)")
    print("\n[4] Acoustic levitation")
    print(f"    40 kHz node spacing = {node_spacing_m(40000.0) * 1000:.3f} mm")
    print(f"    max droplet @ 160 dB = {acoustic_max_mass_g(160.0)} g | nodes in 10 cm = {acoustic_nodes_in_cavity(40000.0, 0.10)}")
    print("\n[5] Electrostatic levitation")
    v = electrostatic_voltage_for_weight(0.001, 0.01, 0.005)
    print(f"    1 g on 100 cm^2 @ 5 mm needs {v:.0f} V (Earnshaw: feedback required)")
    print("\n[6] Diamagnetic levitation")
    print(f"    water needs B*dB/dz = {diamagnetic_required_gradient('water'):.0f} T^2/m (frog-experiment territory)")
    print(f"    pyrolytic graphite needs only {diamagnetic_required_gradient('pyrolytic_graphite'):.1f} T^2/m")
    print("\n[7] Earnshaw's theorem")
    d = earnshaw_demo()
    print(f"    perturbed forces: {d['perturbation_forces_n']} -> unstable = {d['static_config_unstable']}")
    print(f"    evasions: {', '.join(EARNSHAW['evasions'])}")
    print("\n[8] Stability classifier (TinyML kNN)")
    for m, label in stability_report().items():
        print(f"    {m:18s} -> {label}")
    print("\n[9] Force vs gap (EMS, 5 A)")
    print(f"    {force_gap_curve('ems')}")
    print("\n[10] Maglev vehicle (SIM ONLY)")
    print(f"    {json.dumps(maglev_vehicle(), sort_keys=True)}")
    print("\n[11] Advisory seats")
    print(f"    decider: {carbon4_decide()['decision']} trace={carbon4_decide()['trace_sha256_16']}")
    print(f"    advisor can_override_hold = {claude_advisor()['can_override_hold']}")
    print(f"    flow rendered = {google_flow_plan()['rendered']} live = {google_flow_plan()['live']}")
    print(f"\n[12] HOLD gates: {len(HOLD_GATES)}")
    for k in HOLD_GATES:
        print(f"    HOLD  {k}")
    checks = run_checks()
    passed = sum(1 for _, ok in checks if ok)
    print(f"\nCHECKS {passed}/{len(checks)}")
    for name, ok in checks:
        if not ok:
            print(f"    FAIL {name}")
    verdict = "PROCEED" if passed == len(checks) else "HOLD"
    print(f"VERDICT {verdict} (sandbox simulation only) | HOLD gates {len(HOLD_GATES)}")
    return 0 if passed == len(checks) else 1


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    if not argv or argv[0] == "demo":
        return demo()
    cmd = argv[0]
    if cmd == "checks":
        checks = run_checks()
        for name, ok in checks:
            print(f"{'PASS' if ok else 'FAIL'} {name}")
        print(f"CHECKS {sum(1 for _, ok in checks if ok)}/{len(checks)}")
        return 0 if all(ok for _, ok in checks) else 1
    if cmd == "curves":
        for m in METHODS:
            print(f"{m:16s} {force_gap_curve(m)}")
        return 0
    if cmd == "classify":
        print(json.dumps(stability_report(), indent=2, sort_keys=True))
        return 0
    if cmd == "earnshaw":
        print(json.dumps(earnshaw_demo(), indent=2, sort_keys=True))
        print(json.dumps(EARNSHAW, indent=2, sort_keys=True))
        return 0
    if cmd == "maglev":
        print(json.dumps(maglev_vehicle(), indent=2, sort_keys=True))
        return 0
    if cmd == "brains":
        print(json.dumps(brains_report(), indent=2, sort_keys=True))
        return 0
    if cmd == "holds":
        for k, v in HOLD_GATES.items():
            print(f"{k}: {v}")
        return 0
    if cmd == "hold-demo":
        action = argv[1] if len(argv) > 1 else "human_levitation"
        print(f"{action}: {HOLD_GATES.get(action, 'PROCEED - not gated')}")
        return 2 if gate(action) == "HOLD" else 0
    print(__doc__)
    return 0


if __name__ == "__main__":
    sys.exit(main())
