import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta
import random

# --------------------------- CONFIG ---------------------------
st.set_page_config(page_title="EWU FUB - Building Energy Management System", layout="wide")

# Building Structure (FUB has 10 floors, example rooms)
FLOORS = [f"Floor {i}" for i in range(1, 11)]
ROOMS_PER_FLOOR = 8
TOTAL_ROOMS = len(FLOORS) * ROOMS_PER_FLOOR

# Generate room IDs
rooms = [f"FUB-{floor.split()[1]}{f'{room:02d}'}" 
         for floor in FLOORS for room in range(1, ROOMS_PER_FLOOR + 1)]

# ------------------- SYNTHETIC DATA GENERATION (2 weeks) -------------------
@st.cache_data
def generate_data():
    start_date = datetime(2025, 11, 1)
    end_date = datetime(2025, 11, 15, 23, 59)
    dates = pd.date_range(start=start_date, end=end_date, freq='1min')
    
    np.random.seed(42)
    data = []
    
    for room in rooms:
        base_power = random.uniform(800, 2500)  # AC power in watts
        for ts in dates:
            # Simulate class schedule: off 00:00-07:59, on 08:00-17:59, off weekends partially
            if ts.weekday() >= 5:  # Weekend
                usage = 0 if random.random() < 0.9 else base_power * random.uniform(0.1, 0.4)
            else:
                hour = ts.hour
                if 0 <= hour < 8 or hour >= 18:
                    usage = 0
                elif 12 <= hour < 14:
                    usage = base_power * random.uniform(0.3, 0.6)  # Lunch break lower
                else:
                    usage = base_power * random.uniform(0.8, 1.1)
            
            voltage = random.uniform(220, 230)
            current = usage / voltage if usage > 0 else 0
            power = usage
            energy_kwh = power / 1000 / 60  # per minute
            
            data.append({
                'timestamp': ts,
                'room': room,
                'floor': room[4:7].replace('0', ''),  # e.g., Floor 5
                'voltage': round(voltage, 2),
                'current': round(current, 3),
                'power': round(power, 1),
                'energy_kwh': energy_kwh,
                'status': 'ON' if power > 100 else 'OFF',
                'scheduled': True
            })
    
    return pd.DataFrame(data)

df = generate_data()
df['date'] = df['timestamp'].dt.date
df['energy_daily'] = df.groupby(['room', 'date'])['energy_kwh'].transform('sum')
df['cost_daily'] = df['energy_daily'] * 8.5  # 8.5 BDT per kWh (approx)
df['co2_g'] = df['energy_kwh'] * 720  # gCO2 per kWh in BD grid

# --------------------------- SIDEBAR ---------------------------
st.sidebar.image("https://www.ewubd.edu/themes/custom/ewu/logo.png", width=200)
st.sidebar.title("EWU FUB - BEMS")
page = st.sidebar.radio("Navigation", ["Building Overview", "Floor View", "Room Detail", "Schedules"])

# --------------------------- BUILDING OVERVIEW ---------------------------
if page == "Building Overview":
    st.title("🏢 FUB Building Energy Management System")
    st.markdown("### Real-time Monitoring Dashboard | 1–15 November 2025")

    now = datetime.now()
    live_df = df[df['timestamp'] >= now - timedelta(minutes=5)]

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Total Power", f"{df[df['status']=='ON']['power'].sum():,.0f} W", "Live")
    with col2:
        st.metric("Daily Energy", f"{df[df['date']==datetime.today().date()]['energy_kwh'].sum():.1f} kWh")
    with col3:
        st.metric("Est. Daily Cost", f"৳{df[df['date']==datetime.today().date()]['cost_daily'].sum():,.0f}")
    with col4:
        st.metric("Est. CO2", f"{df[df['date']==datetime.today().date()]['co2_g'].sum()/1000:,.1f} kg")

    st.markdown("### 🏠 Click a Floor Tile to Drill Down")
    cols = st.columns(5)
    for i, floor in enumerate(FLOORS):
        with cols[i % 5]:
            floor_data = df[df['floor'] == floor.split()[1]]
            today_power = floor_data[floor_data['date'] == datetime.today().date()]['power'].mean()
            st.markdown(f"""
            <a href="?page=Floor+View&floor={floor}" style="text-decoration:none;">
                <div style="background:#2E86C1; padding:20px; border-radius:10px; text-align:center; color:white; margin:10px;">
                    <h3>{floor}</h3>
                    <p>{len(floor_data['room'].unique())} Rooms</p>
                    <p>~{today_power:.0f} W avg</p>
                </div>
            </a>
            """, unsafe_allow_html=True)

# --------------------------- FLOOR VIEW ---------------------------
elif page == "Floor View":
    floor = st.selectbox("Select Floor", FLOORS)
    floor_num = floor.split()[1]
    floor_rooms = [r for r in rooms if r[6] == floor_num[0]] if len(floor_num)==1 else [r for r in rooms if r[5:7] == floor_num]

    st.title(f"{floor} - Energy Overview")

    cols = st.columns(4)
    for i, room in enumerate(floor_rooms):
        with cols[i % 4]:
            room_data = df[df['room'] == room]
            latest = room_data.sort_values('timestamp').iloc[-1]
            st.markdown(f"""
            <a href="?page=Room+Detail&room={room}">
                <div style="background:{'#27AE60' if latest['status']=='ON' else '#E74C3C'}; 
                            padding:15px; border-radius:10px; text-align:center; color:white; margin:10px;">
                    <h4>{room}</h4>
                    <p>{latest['power']:.0f} W</p>
                    <p>{latest['status']}</p>
                </div>
            </a>
            """, unsafe_allow_html=True)

# --------------------------- ROOM DETAIL ---------------------------
elif page == "Room Detail":
    room = st.selectbox("Select Room", rooms)
    room_data = df[df['room'] == room].copy()

    st.title(f"Room {room} - Detailed Dashboard")

    # Date range selector
    col1, col2 = st.columns(2)
    with col1:
        start_date = st.date_input("Start Date", datetime(2025, 11, 1))
    with col2:
        end_date = st.date_input("End Date", datetime(2025, 11, 15))

    mask = (room_data['timestamp'].dt.date >= start_date) & (room_data['timestamp'].dt.date <= end_date)
    filtered = room_data[mask]

    # Live values
    latest = filtered.sort_values('timestamp').iloc[-1]
    col1, col2, col3, col4, col5 = st.columns(5)
    col1.metric("Voltage", f"{latest['voltage']} V")
    col2.metric("Current", f"{latest['current']} A")
    col3.metric("Power", f"{latest['power']:.0f} W", delta=f"{latest['status']}")
    col4.metric("Daily Energy", f"{filtered[filtered['date']==end_date]['energy_kwh'].sum():.2f} kWh")
    col5.metric("Est. Bill", f"৳{filtered[filtered['date']==end_date]['cost_daily'].sum():.0f}")

    # Charts
    st.plotly_chart(px.line(filtered, x='timestamp', y='power', title="Power Trend (W)"), use_container_width=True)
    st.plotly_chart(px.line(filtered.set_index('timestamp').resample('1H')['energy_kwh'].sum().reset_index(),
                            x='timestamp', y='energy_kwh', title="Hourly Energy (kWh)"), use_container_width=True)

    # Manual Control (Demo)
    st.markdown("### Manual AC Control")
    if st.button(f"Turn {'OFF' if latest['status']=='ON' else 'ON'} AC in {room}"):
        st.success(f"AC in {room} turned {'OFF' if latest['status']=='ON' else 'ON'}!")

# --------------------------- SCHEDULES ---------------------------
else:
    st.title("Scheduled On/Off Rules")
    st.info("Demo: All ACs automatically turn OFF outside 8:00–18:00 on weekdays → ~20% estimated savings")
    st.success("Scheduled automation active across all rooms (8 AM – 6 PM only)")

st.markdown("---")
st.caption("© 2025 EWU CSE407 Green Computing - Midterm Project Demo | Synthetic Data: 1–15 Nov 2025")
