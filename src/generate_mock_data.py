
from faker import Faker
import pandas as pd
import random
from datetime import datetime, timedelta
import os

fake = Faker()

# Config
NUM_PATIENTS = 120
NUM_DOCTORS = 10
departments = ["Cardiology", "Neurology", "Orthopedics", "Pediatrics", "General Medicine"]

# Create doctors (simple shifts)
doctors = []
for i in range(NUM_DOCTORS):
    doc = {
        "doctor_id": f"D{100+i}",
        "name": fake.name(),
        "dept": random.choice(departments),
        "shift_start": "08:00",
        "shift_end": "16:00",
        "is_on_duty": random.choice([True, False])
    }
    doctors.append(doc)

# Generate patient records
patients = []
start_time = datetime.now().replace(hour=8, minute=0, second=0, microsecond=0)
for i in range(NUM_PATIENTS):
    arrival_offset_minutes = random.randint(0, 8 * 60)  # within 8 hours
    arrival_time = start_time + timedelta(minutes=arrival_offset_minutes)
    assigned_doctor = random.choice(doctors)
    status = random.choices(
        ["waiting", "in_consultation", "discharged"],
        weights=[0.5, 0.3, 0.2],
        k=1
    )[0]
    waiting_time = random.randint(2, 90) if status != "discharged" else random.randint(2, 30)
    triage_level = random.choices(["Low", "Medium", "High"], weights=[0.6, 0.3, 0.1], k=1)[0]

    patients.append({
        "patient_id": f"P{1000+i}",
        "name": fake.name(),
        "age": random.randint(0, 90),
        "gender": random.choice(["Male", "Female"]),
        "dept": assigned_doctor["dept"],
        "doctor_id": assigned_doctor["doctor_id"],
        "arrival_time": arrival_time.strftime("%Y-%m-%d %H:%M:%S"),
        "status": status,
        "waiting_time_mins": waiting_time,
        "triage_level": triage_level,
        "reason": fake.sentence(nb_words=4)
    })

# Create data folder and save CSVs
os.makedirs("data", exist_ok=True)
pd.DataFrame(patients).to_csv("data/patients.csv", index=False)
pd.DataFrame(doctors).to_csv("data/doctors.csv", index=False)

print("✅ Mock data generated and saved in /data/")
