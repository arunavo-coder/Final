import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import random

# --------------------------- PAGE CONFIG ---------------------------
st.set_page_config(page_title="EWU FUB BEMS", layout="wide", initial_sidebar_state="expanded")

# --------------------------- BUILDING LAYOUT ---------------------------
FLOORS = [f"Floor {i}" for i in range(1, 11)]
ROOMS_PER_FLOOR = 8
rooms = [f"FUB-{str(i).zfill(2)}{str(j).zfill(2)}" for i in range(1, 11) for j in range(1, ROOMS_PER_FLOOR + 1)]

# --------------------------- GENERATE 2 WEEKS DATA ---------------------------
@st.cache_data
def generate_data():
    start = datetime(2025, 11, 1)
    end = datetime(2025, 11, 15, 23, 59)
    ts = pd.date_range(start, end, freq='1min')
    
    data = []
    np.random.seed(42)
    
    for room in rooms:
        base = random.uniform(1000, 2200)
        for t in ts:
            wd, h = t.weekday(), t.hour
            if wd >= 5 or h < 8 or h >= 18:
                power = 0
            elif 12 <= h < 14:
                power = base * random.uniform(0.3, 0.6)
            else:
                power = base * random.uniform(0.9, 1.1)
                
            voltage = random.uniform(220, 230)
            current = round(power / voltage, 3) if power > 0 else 0
            energy_min = power / 60000  # kWh per minute
            
            data.append({
                "timestamp": t,
                "room": room,
                "floor": room[4:6],
                "voltage": round(voltage, 2),
                "current": current,
                "power": round(power, 1),
                "energy_kwh": energy_min,
                "status": "ON" if power > 100 else "OFF"
            })
    return pd.DataFrame(data)

df = generate_data()
df["date"] = df["timestamp"].dt.date
daily = df.groupby(["room", "date"])["energy_kwh"].sum().reset_index()
daily["cost"] = daily["energy_kwh"] * 8.5
daily["co2_kg"] = daily["energy_kwh"] * 0.72
df = df.merge(daily[["room","date","cost","co2_kg"]], on=["room","date"], how="left")

# --------------------------- SIDEBAR ---------------------------
st.sidebar.image("https://www.ewubd.edu/themes/custom/ewu/logo.png", width=200)
st.sidebar.title("FUB BEMS")
page = st.sidebar.radio("Navigation", ["Building Overview", "Floor View", "Room Detail", "Schedules"])

# --------------------------- BUILDING OVERVIEW ---------------------------
if page == "Building Overview":
    st.title("FUB Building Energy Management System")
    st.markdown("**Real-time Monitoring Dashboard • 01–15 Nov 2025**")

    today = datetime.today().date()
    today_df = df[df["date"] == today]

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Total Live Power", f"{df[df['status']=='ON']['power'].sum():,.0f} W")
    col2.metric("Today's Energy", f"{today_df['energy_kwh'].sum():.2f} kWh")
    col3.metric("Today's Cost", f"৳{today_df['cost'].sum():,.0f}")
    col4.metric("Today's CO₂", f"{today_df['co2_kg'].sum():.1f} kg")

    st.markdown("### Click a Floor")
    cols = st.columns(5)
    for i, floor in enumerate(FLOORS):
        floor_num = floor.split()[1]
        floor_data = df[df["floor"] == floor_num.zfill(2)]
        avg_w = floor_data[floor_data["date"]==today]["power"].mean()
        with cols[i % 5]:
            if st.button(f"{floor}\n~{avg_w:.0f} W avg", key=floor):
                st.session_state.floor = floor
                st.rerun()

# --------------------------- FLOOR VIEW ---------------------------
elif page == "Floor View":
    floor = st.selectbox("Select Floor", FLOORS)
    floor_code = floor.split()[1].zfill(2)
    floor_rooms = [r for r in rooms if r.startswith(f"FUB-{floor_code}")]

    st.title(f"{floor} – All Rooms")

    cols = st.columns(4)
    for idx, room in enumerate(floor_rooms):
        latest = df[df["room"]==room].sort_values("timestamp").iloc[-1]
        color = "🟢" if latest["status"]=="ON" else "🔴"
        with cols[idx % 4]:
            if st.button(f"{color} **{room}**\n{latest['power']:.0f} W", key=room):
                st.session_state.room = room
                st.rerun()

    if "room" in st.session_state and st.session_state.room in floor_rooms:
        page = "Room Detail"
        st.rerun()

# --------------------------- ROOM DETAIL ---------------------------
elif page == "Room Detail":
    room = st.selectbox("Room", rooms, index=rooms.index(st.session_state.get("room", rooms[0])))
    data = df[df["room"] == room].copy()

    st.title(f"Room {room} – Detailed View")

    col1, col2 = st.columns(2)
    with col1:
        start = st.date_input("Start", datetime(2025,11,1))
    with col2:
        end = st.date_input("End", datetime(2025,11,15))

    mask = (data["timestamp"].dt.date >= start) & (data["timestamp"].dt.date <= end)
    filtered = data[mask]
    latest = filtered.iloc[-1]

    c1,c2,c3,c4,c5 = st.columns(5)
    c1.metric("Voltage", f"{latest.voltage} V")
    c2.metric("Current", f"{latest.current} A")
    c3.metric("Power", f"{latest.power:.0f} W")
    c4.metric("Cost (Period)", f"৳{filtered['cost'].sum():,.0f}")
    c5.metric("CO₂ (Period)", f"{filtered['co2_kg'].sum():.1f} kg")

    # Built-in Streamlit charts (no Plotly!)
    st.subheader("Power Trend")
    chart_data = filtered.set_index("timestamp")[["power"]].resample("10min").mean()
    st.line_chart(chart_data)

    st.subheader("Daily Energy (kWh)")
    daily_chart = filtered.groupby("date")["energy_kwh"].sum()
    st.bar_chart(daily_chart)

    st.markdown("### Manual Control")
    action = "OFF" if latest.status == "ON" else "ON"
    if st.button(f"Turn AC {action}"):
        st.success(f"AC in {room} turned {action}!")

# --------------------------- SCHEDULES ---------------------------
else:
    st.title("Scheduled Automation")
    st.success("All ACs automatically OFF outside 8 AM – 6 PM (Mon–Fri)")
    st.info("Estimated savings: ~20%")
    st.image("https://via.placeholder.com/800x400?text=Schedule+Graph+Here")

st.caption("EWU CSE407 Green Computing • Midterm Project • Nov 2025 • Synthetic Data")
