import streamlit as st
import pandas as pd
import plotly.express as px
from pathlib import Path
import time
import streamlit.components.v1 as components
from datetime import timedelta

# --- Config ---
st.set_page_config(page_title="HealthOps Dashboard", layout="wide")
DATA_DIR = Path(__file__).resolve().parents[1] / "data"

# --- Helpers ---
def load_data():
    patients_path = DATA_DIR / "patients.csv"
    doctors_path = DATA_DIR / "doctors.csv"
    patients = pd.read_csv(patients_path, parse_dates=["arrival_time"])
    doctors = pd.read_csv(doctors_path)
    return patients, doctors

def get_kpis(patients, doctors):
    total = len(patients)
    waiting = int((patients["status"] == "waiting").sum()) if "status" in patients.columns else 0
    in_consult = int((patients["status"] == "in_consultation").sum()) if "status" in patients.columns else 0
    doctors_count = len(doctors)
    avg_wait = round(patients["waiting_time_mins"].astype(float).mean(), 1) if len(patients) > 0 else 0
    return total, waiting, in_consult, doctors_count, avg_wait

# --- Sidebar ---
with st.sidebar:
    st.header("Controls")
    if st.button("Refresh data (manual)"):
        st.rerun()
    auto_refresh = st.checkbox("Auto refresh", value=False)
    refresh_interval = st.slider("Auto-refresh interval (secs)", 1, 10, 5)
    queue_alert_threshold = st.number_input("Queue alert threshold (patients)", min_value=1, max_value=200, value=10, step=1)
    # populate department dropdown safely (read doctors file directly)
    try:
        tmp_docs = pd.read_csv(DATA_DIR / "doctors.csv")
        dept_options = ["All"] + sorted(tmp_docs["dept"].unique().tolist())
    except Exception:
        dept_options = ["All"]
    dept_filter = st.selectbox("Department", options=dept_options)
    show_only_active = st.checkbox("Show only doctors on duty", value=False)

# --- Load data ---
try:
    patients, doctors = load_data()
except FileNotFoundError:
    st.error("Data files not found. Run `src/generate_mock_data.py` first.")
    st.stop()
except Exception as e:
    st.error(f"Error loading data: {e}")
    st.stop()

# Apply department filter
if dept_filter != "All":
    patients = patients[patients["dept"] == dept_filter].copy()

# --- KPIs ---
total, waiting, in_consult, doctors_count, avg_wait = get_kpis(patients, doctors)
k1, k2, k3, k4, k5 = st.columns([1,1,1,1,1])
k1.metric("Total Patients", total)
k2.metric("Waiting", waiting)
k3.metric("In Consultation", in_consult)
k4.metric("Doctors (total)", doctors_count)
k5.metric("Avg Waiting (mins)", avg_wait)

st.markdown("---")

# --- Dept overload alerts ---
dept_wait = patients[patients["status"] == "waiting"].groupby("dept").size().reset_index(name="waiting_count") if "status" in patients.columns else pd.DataFrame(columns=["dept","waiting_count"])
all_depts = pd.DataFrame({"dept": doctors["dept"].unique()})
if dept_wait.empty:
    dept_wait = all_depts.merge(dept_wait, how="left", on="dept").fillna(0)
else:
    dept_wait = all_depts.merge(dept_wait, how="left", on="dept").fillna(0)
dept_wait["waiting_count"] = dept_wait["waiting_count"].astype(int)
overloaded = dept_wait[dept_wait["waiting_count"] >= int(queue_alert_threshold)].sort_values("waiting_count", ascending=False)

if not overloaded.empty:
    st.error(f"⚠️ Department overload detected: {len(overloaded)} dept(s) over threshold ({queue_alert_threshold})")
    for _, row in overloaded.iterrows():
        st.warning(f"{row['dept']}: {row['waiting_count']} waiting")
else:
    st.success("All departments within queue threshold.")

st.markdown("---")

# --- Charts: arrivals & waiting distribution ---
if not patients.empty:
    patients = patients.sort_values("arrival_time").copy()
    # ensure arrival_time is datetime
    if patients["arrival_time"].dtype == "O":
        patients["arrival_time"] = pd.to_datetime(patients["arrival_time"], errors="coerce")
    patients["arrival_hour"] = patients["arrival_time"].dt.floor("H")
    arrivals = patients.groupby("arrival_hour").size().reset_index(name="count")

    st.subheader("Patient arrivals timeline")
    fig_arrivals = px.area(arrivals, x="arrival_hour", y="count", title="Arrivals per hour", markers=True)
    st.plotly_chart(fig_arrivals, use_container_width=True)

    st.subheader("Waiting time distribution")
    fig_wait = px.histogram(patients, x="waiting_time_mins", nbins=25, title="Waiting time (mins)")
    st.plotly_chart(fig_wait, use_container_width=True)
else:
    st.info("No patient records to chart for the selected filters.")

st.markdown("---")

# --- Doctor availability & queue table ---
st.subheader("Doctor availability & Queue")

if show_only_active:
    visible_doctors = doctors[doctors["is_on_duty"] == True].copy()
else:
    visible_doctors = doctors.copy()

patient_counts = pd.DataFrame()
if not patients.empty:
    patient_counts = patients.groupby("doctor_id").agg(
        waiting_count = ("status", lambda s: (s == "waiting").sum()),
        in_consult = ("status", lambda s: (s == "in_consultation").sum()),
        total_assigned = ("patient_id", "count")
    ).reset_index()

if patient_counts.empty:
    # make sure columns exist for merge
    patient_counts = pd.DataFrame(columns=["doctor_id", "waiting_count", "in_consult", "total_assigned"])

doc_view = visible_doctors.merge(patient_counts, how="left", left_on="doctor_id", right_on="doctor_id")
for col in ["waiting_count","in_consult","total_assigned"]:
    if col in doc_view.columns:
        doc_view[col] = doc_view[col].fillna(0).astype(int)
    else:
        doc_view[col] = 0

st.dataframe(doc_view.reset_index(drop=True))

st.markdown("---")

# --- Live Activity Log ---
st.subheader("Live Activity Log")
now = pd.Timestamp.now()
lookback_min = 30
recent_cutoff = now - timedelta(minutes=lookback_min)
recent_arrivals = patients[patients["arrival_time"] >= recent_cutoff].sort_values("arrival_time", ascending=False) if not patients.empty else pd.DataFrame()
recent_discharges = patients[patients["status"] == "discharged"].sort_values("arrival_time", ascending=False).head(20) if not patients.empty else pd.DataFrame()

col_a, col_b = st.columns(2)
with col_a:
    st.markdown(f"**Recent arrivals (last {lookback_min} min)** — total: {len(recent_arrivals)}")
    if not recent_arrivals.empty:
        st.table(recent_arrivals[["patient_id", "name", "dept", "doctor_id", "arrival_time", "waiting_time_mins"]].reset_index(drop=True).head(10))
    else:
        st.write("No arrivals in the last 30 minutes.")
with col_b:
    st.markdown("**Recent discharges** (latest)")
    if not recent_discharges.empty:
        st.table(recent_discharges[["patient_id", "name", "dept", "doctor_id", "arrival_time"]].reset_index(drop=True).head(10))
    else:
        st.write("No recent discharges.")

st.markdown("---")

# --- Patient snapshot table ---
st.subheader("Patient snapshot")
st.dataframe(patients.sort_values("arrival_time").head(200).reset_index(drop=True))

# --- Export filtered dataset ---
st.markdown("---")
st.download_button(
    label="Download filtered patient CSV",
    data=patients.to_csv(index=False).encode("utf-8"),
    file_name="patients_snapshot.csv",
    mime="text/csv"
)

# --- Auto-refresh logic (non-blocking client-side reload) ---
if auto_refresh:
    ms = int(refresh_interval) * 1000
    components.html(
        f"""
        <script>
        setTimeout(function() {{
            window.location.reload();
        }}, {ms});
        </script>
        """,
        height=0,
        scrolling=False,
    )
