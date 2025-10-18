"""
Simple simulator for HealthOps MVP.
Run in a separate terminal; it will mutate data/patients.csv and data/doctors.csv
so the Streamlit app can pick up "real-time" changes.
"""

import pandas as pd
import random
import time
from datetime import datetime
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parents[1] / "data"
PATIENTS_PATH = DATA_DIR / "patients.csv"
DOCTORS_PATH = DATA_DIR / "doctors.csv"

# Simulation parameters
INTERVAL_SECONDS = 3      # update every few seconds
NEW_ARRIVAL_PROB = 0.8    # highest probability for demo - increase arrivals
CHANGE_STATUS_PROB = 0.6
TOGGLE_DOCTOR_PROB = 0.15
MAX_NEW_PER_INTERVAL = 3

def load():
    patients = pd.read_csv(PATIENTS_PATH, parse_dates=["arrival_time"])
    doctors = pd.read_csv(DOCTORS_PATH)
    return patients, doctors

def save(patients, doctors):
    patients.to_csv(PATIENTS_PATH, index=False)
    doctors.to_csv(DOCTORS_PATH, index=False)

def _next_patient_id(patients):
    if patients.empty:
        return 1000
    # Extract numeric part safely
    ids = patients["patient_id"].astype(str).str.extract(r"P(\d+)").dropna().astype(int)
    if ids.empty:
        return 1000 + len(patients)
    return int(ids.max().values[0])

def add_new_patients(patients, doctors, n=1):
    next_id = _next_patient_id(patients)
    names = ["Alex Parker", "Priya Sharma", "Rohit Verma", "Maya Singh", "Liam Brown", "Aisha Khan", "Satish Kumar", "Isha Patel"]
    for i in range(n):
        assigned = doctors.sample(1).iloc[0]
        next_id += 1
        new = {
            "patient_id": f"P{next_id}",
            "name": random.choice(names),
            "age": random.randint(1, 90),
            "gender": random.choice(["Male", "Female"]),
            "dept": assigned["dept"],
            "doctor_id": assigned["doctor_id"],
            "arrival_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "status": "waiting",
            "waiting_time_mins": random.randint(1, 10),
            "triage_level": random.choice(["Low", "Medium", "High"]),
            "reason": "Walk-in"
        }
        patients = pd.concat([patients, pd.DataFrame([new])], ignore_index=True)
    return patients

def progress_patient_status(patients):
    if patients.empty:
        return patients
    # waiting -> in_consultation
    waiting_idx = patients[patients["status"] == "waiting"].index.tolist()
    if waiting_idx and random.random() < CHANGE_STATUS_PROB:
        k = min(len(waiting_idx), random.randint(1, 2))
        to_promote = random.sample(waiting_idx, k=k)
        for idx in to_promote:
            patients.at[idx, "status"] = "in_consultation"
            # reduce waiting time if promoted
            patients.at[idx, "waiting_time_mins"] = max(0, int(patients.at[idx, "waiting_time_mins"]) - random.randint(1, 6))
    # in_consultation -> discharged
    in_idx = patients[patients["status"] == "in_consultation"].index.tolist()
    if in_idx and random.random() < CHANGE_STATUS_PROB:
        k = min(len(in_idx), random.randint(1, 2))
        to_discharge = random.sample(in_idx, k=k)
        for idx in to_discharge:
            patients.at[idx, "status"] = "discharged"
            patients.at[idx, "waiting_time_mins"] = random.randint(0, 10)
    # age waiting times up a bit
    if not patients[patients["status"] == "waiting"].empty:
        patients.loc[patients["status"] == "waiting", "waiting_time_mins"] = (
            patients.loc[patients["status"] == "waiting", "waiting_time_mins"].astype(int) + random.randint(0, 2)
        )
    return patients

def toggle_doctor_shifts(doctors):
    if random.random() < TOGGLE_DOCTOR_PROB:
        idx = doctors.sample(1).index[0]
        doctors.at[idx, "is_on_duty"] = not bool(doctors.at[idx, "is_on_duty"])
    return doctors

def main():
    print("Simulator starting — updating CSVs in", DATA_DIR)
    while True:
        try:
            patients, doctors = load()
        except Exception as e:
            print("Error loading data:", e)
            time.sleep(INTERVAL_SECONDS)
            continue

        # Possibly add new arrivals
        if random.random() < NEW_ARRIVAL_PROB:
            n_new = random.randint(1, MAX_NEW_PER_INTERVAL)
            patients = add_new_patients(patients, doctors, n=n_new)
            print(f"Added {n_new} new patient(s) at {datetime.now().strftime('%H:%M:%S')}")

        # Progress statuses and waiting times
        patients = progress_patient_status(patients)

        # Toggle doctor on-duty sometimes
        doctors = toggle_doctor_shifts(doctors)

        # Save back to CSV
        save(patients, doctors)

        # Log simple snapshot
        num_waiting = int((patients["status"] == "waiting").sum())
        num_in_consult = int((patients["status"] == "in_consultation").sum())
        print(f"[{datetime.now().strftime('%H:%M:%S')}] waiting={num_waiting}, in_consult={num_in_consult}, total={len(patients)}")

        time.sleep(INTERVAL_SECONDS)

if __name__ == "__main__":
    main()
