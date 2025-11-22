import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import random

# --------- FIX: Use built-in Plotly that comes with Streamlit ---------
import plotly.express as px
import plotly.graph_objects as go

# --------------------------- CONFIG ---------------------------
st.set_page_config(page_title="EWU FUB - BEMS", layout="wide", initial_sidebar_state="expanded")

# Building Structure
FLOORS = [f"Floor {i}" for i in range(1, 11)]
ROOMS_PER_FLOOR = 8
rooms = [f"FUB-{str(i).zfill(2)}{str(j).zfill(2)}" for i in range(1, 11) for j in range(1, ROOMS_PER_FLOOR + 1)]

# ------------------- Generate 2 Weeks Synthetic Data -------------------
@st.cache_data
def generate_data():
    start = datetime(2025, 11, 1)
    end = datetime(2025, 11, 15, 23, 59)
    timestamps = pd.date_range(start, end, freq='1min')
    
    data = []
    np.random.seed(42)
    
    for room in rooms:
        base_power = random.uniform(900, 2200)  # Typical AC power
        
        for ts in timestamps:
            weekday = ts.weekday()
            hour = ts.hour
            
            # Schedule: Mon–Fri 8 AM – 6 PM only (20% savings logic)
            if weekday >= 5 or hour < 8 or hour >= 18:
                power = 0
            elif 12 <= hour < 14:
                power = base_power * random.uniform(0.3, 0.6)  # Lunch break
            else:
                power = base_power * random.uniform(0.85, 1.15)
            
            voltage = random.uniform(218, 232)
            current = power / voltage if power > 0 else 0
            energy_min = power / 1000 / 60  # kWh per minute
            
            data.append({
                "timestamp": ts,
                "room": room,
                "floor": room[4:6].lstrip("0") or "0",
                "voltage": round(voltage, 2),
                "current": round(current, 3),
                "power": round(power, 1),
                "energy_kwh": energy_min,
                "status": "ON" if power > 100 else "OFF"
            })
    
    return pd.DataFrame(data)

df = generate_data()

# Pre-calculate daily totals
df["date"] = df["timestamp"].dt.date
daily = df.groupby(["room", "date"]).agg({
    "energy_kwh": "sum",
    "power": "mean"
}).reset_index()
daily["cost_bdt"] = daily["energy_kwh"] * 8.5
daily["co2_g"] = daily["energy_kwh"] * 720

# Merge back for easy access
df = df.merge(daily[["room", "date", "cost_bdt", "co2_g"]], on=["room", "date"], how="left")

# --------------------------- SIDEBAR ---------------------------
st.sidebar.image("https://www.ewubd.edu/themes/custom/ewu/logo.png", width=180)
st.sidebar.title("FUB - BEMS")
page = st.sidebar.radio("Go to", ["Building Overview", "Floor View", "Room Detail", "Schedules"])

# --------------------------- BUILDING OVERVIEW ---------------------------
if page == "Building Overview":
    st.title("FUB Building Energy Management System")
    st.markdown("**Real-time & Historical Energy Dashboard** | 01–15 Nov 2025")

    today = datetime.today().date()
    today_df = df[df["date"] == today]

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Live Power", f"{df[df['status']=='ON']['power'].sum():,.0f} W")
    c2.metric("Today Energy", f"{today_df['energy_kwh'].sum():.2f} kWh")
    c3.metric("Today Cost", f"৳{today_df['cost_bdt'].sum():,.0f}")
    c4.metric("Today CO₂", f"{today_df['co2_g'].sum()/1000:,.1f} kg")

    st.markdown("### Select Floor")
    cols = st.columns(5)
    for idx, floor in enumerate(FLOORS):
        floor_num = floor.split()[1]
        floor_data = df[df["floor"] == floor_num]
        avg_power = floor_data[floor_data["date"] == today]["power"].mean()
        with cols[idx % 5]:
            if st.button(f"{floor}\n≈{avg_power:.0f} W", key=floor):
                st.session_state.selected_floor = floor
                st.switch_page("Floor View")

# --------------------------- FLOOR VIEW ---------------------------
elif page == "Floor View":
    floor = st.selectbox("Floor", FLOORS, key="floor_select")
    floor_num = floor.split()[1]
    floor_rooms = [r for r in rooms if r[4:6] == floor_num.zfill(2)]

    st.title(f"{floor} – Room Status")

    cols = st.columns(4)
    for i, room in enumerate(floor_rooms):
        latest = df[df["room"] == room].sort_values("timestamp").iloc[-1]
        color = "#27AE60" if latest["status"] == "ON" else "#E74C3C"
        with cols[i % 4]:
            if st.button(f"**{room}**\n{latest['power']:.0f} W\n{latest['status']}", 
                        key=room, help="Click for details"):
                st.session_state.selected_room = room
                st.rerun()
    
    if "selected_room" in st.session_state and st.session_state.selected_room in floor_rooms:
        st.switch_page("Room Detail")

# --------------------------- ROOM DETAIL ---------------------------
elif page == "Room Detail":
    room = st.selectbox("Room", rooms, index=rooms.index(st.session_state.get("selected_room", rooms[0])))
    room_data = df[df["room"] == room].copy()

    st.title(f"Room {room} – Detailed Dashboard")

    col1, col2 = st.columns(2)
    with col1:
        start_date = st.date_input("From", datetime(2025, 11, 1))
    with col2:
        end_date = st.date_input("To", datetime(2025, 11, 15))

    filtered = room_data[(room_data["timestamp"].dt.date >= start_date) & 
                        (room_data["timestamp"].dt.date <= end_date)]

    latest = filtered.iloc[-1]
    c1, c2, c3, c4, c5, c6 = st.columns(6)
    c1.metric("Voltage", f"{latest.voltage} V")
    c2.metric("Current", f"{latest.current} A")
    c3.metric("Power", f"{latest.power:.0f} W")
    c4.metric("Status", latest.status)
    c5.metric("Est. Bill", f"৳{filtered['cost_bdt'].sum():,.0f}")
    c6.metric("CO₂", f"{filtered['co2_g'].sum()/1000:.1f} kg")

    st.plotly_chart(px.line(filtered, x="timestamp", y="power", 
                           title="Real-time Power (W)"), use_container_width=True)
    
    hourly = filtered.set_index("timestamp").resample("1H")["energy_kwh"].sum().reset_index()
    st.plotly_chart(px.bar(hourly, x="timestamp", y="energy_kwh", 
                          title="Hourly Energy Consumption (kWh)"), use_container_width=True)

    st.markdown("### Manual Control (Demo)")
    if st.button(f"Turn AC {'OFF' if latest.status=='ON' else 'ON'}"):
        st.success(f"AC in {room} turned {'OFF' if latest.status=='ON' else 'ON'}!")

# --------------------------- SCHEDULES ---------------------------
else:
    st.title("Scheduled Automation")
    st.success("All ACs automatically turn OFF outside 8:00 AM – 6:00 PM on weekdays")
    st.info("20% estimated electricity savings achieved through scheduling")
    st.dataframe(pd.DataFrame({
        "Rule": ["Weekday Schedule", "Weekend", "Lunch Break"],
        "Time": ["08:00–18:00", "OFF", "50% Power"],
        "Status": ["Active", "Active", "Active"]
    }))

st.caption("EWU CSE407 Green Computing – Midterm Project Demo | Nov 2025")
