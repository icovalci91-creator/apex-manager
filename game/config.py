"""Costanti globali del gioco."""
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
SAVES = ROOT / "saves"

GAME_TITLE = "Apex Manager"
GAME_VERSION = "0.1"

SCREEN_W, SCREEN_H = 1600, 900
# sotto queste misure le schermate non stanno piu' in piedi
MIN_SCREEN_W, MIN_SCREEN_H = 1180, 680
FPS = 60

# --- Fisica della vettura (era 2026) -------------------------------------
RHO = 1.225                 # densita aria kg/m3
G = 9.81
CAR_MASS_KG = 768.0         # peso minimo regolamentare
FUEL_MASS_KG = 100.0        # carico massimo di benzina
POWER_W = 745_000.0         # ~1000 CV: 400 kW termico + 350 kW elettrico
MU_LAT = 1.75               # coefficiente di aderenza laterale slick
MU_BRAKE = 1.60             # aderenza longitudinale in frenata
CLA_BASE = 3.10             # ClA di riferimento (downforce index 1.0)
CDA_BASE = 1.85             # CdA di riferimento

# Raggi di curvatura indicativi per classe di curva (metri)
CORNER_RADIUS = {1: 22.0, 2: 45.0, 3: 90.0, 4: 170.0, 5: 340.0}

# --- Gomme ---------------------------------------------------------------
COMPOUNDS = {
    "soft":   {"label": "Soft",   "grip": 1.000, "wear": 1.55, "colour": (225, 6, 0),     "warmup": 0.8},
    "medium": {"label": "Medium", "grip": 0.985, "wear": 1.00, "colour": (255, 214, 0),   "warmup": 1.0},
    "hard":   {"label": "Hard",   "grip": 0.970, "wear": 0.70, "colour": (235, 235, 235), "warmup": 1.3},
    "inter":  {"label": "Inter",  "grip": 0.930, "wear": 1.10, "colour": (67, 176, 42),   "warmup": 1.0},
    "wet":    {"label": "Wet",    "grip": 0.870, "wear": 0.95, "colour": (0, 103, 173),    "warmup": 1.0},
}

# --- Aree di sviluppo della vettura --------------------------------------
CAR_PARTS = {
    "front_wing":  {"label": "Ala anteriore",  "aero": 0.9, "mech": 0.1, "pu": 0.0, "cost": 1.0},
    "rear_wing":   {"label": "Ala posteriore", "aero": 0.9, "mech": 0.1, "pu": 0.0, "cost": 1.0},
    "floor":       {"label": "Fondo",          "aero": 1.3, "mech": 0.1, "pu": 0.0, "cost": 1.6},
    "sidepods":    {"label": "Fiancate",       "aero": 0.7, "mech": 0.2, "pu": 0.2, "cost": 1.2},
    "suspension":  {"label": "Sospensioni",    "aero": 0.2, "mech": 1.1, "pu": 0.0, "cost": 1.1},
    "gearbox":     {"label": "Trasmissione",   "aero": 0.0, "mech": 0.7, "pu": 0.5, "cost": 1.0},
    "brakes":      {"label": "Impianto frenante", "aero": 0.1, "mech": 0.9, "pu": 0.0, "cost": 0.8},
    "chassis":     {"label": "Telaio",         "aero": 0.3, "mech": 1.2, "pu": 0.0, "cost": 1.8},
    "active_aero": {"label": "Aero attiva",    "aero": 1.0, "mech": 0.3, "pu": 0.2, "cost": 1.4},
    "cooling":     {"label": "Raffreddamento", "aero": 0.4, "mech": 0.2, "pu": 0.7, "cost": 0.9},
}

# --- Infrastrutture ------------------------------------------------------
FACILITIES = {
    "windtunnel":    {"label": "Galleria del vento", "cost": 4.2, "boost": "aero"},
    "cfd":           {"label": "Cluster CFD",        "cost": 3.0, "boost": "aero"},
    "simulator":     {"label": "Simulatore",         "cost": 3.4, "boost": "setup"},
    "factory":       {"label": "Fabbrica",           "cost": 5.0, "boost": "production"},
    "aero_dept":     {"label": "Reparto aerodinamica", "cost": 3.6, "boost": "aero"},
    "design_office": {"label": "Ufficio tecnico",    "cost": 3.2, "boost": "mech"},
    "pit_crew":      {"label": "Squadra ai box",     "cost": 1.8, "boost": "pitstop"},
    "academy":       {"label": "Academy",            "cost": 2.2, "boost": "youth"},
    "logistics":     {"label": "Logistica",          "cost": 2.0, "boost": "cost"},
    # Una pista di proprieta': chi ce l'ha prova quando vuole invece di
    # aspettare le prove libere. Costruirla da zero e' un investimento a parte.
    "private_track": {"label": "Pista di proprieta'", "cost": 5.5, "boost": "testing",
                      "build_cost": 140.0},
}

POINTS_DEFAULT = [25, 18, 15, 12, 10, 8, 6, 4, 2, 1]

WEATHER_TYPES = ["sereno", "nuvoloso", "coperto", "pioggia leggera", "pioggia intensa"]
