import os
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import plotly.express as px

# File paths
file_path = "C:/Users/pli/OneDrive/House/19b reddington/electricity"
files = [os.path.join(file_path, f) for f in os.listdir(file_path) if "HalfHourlyMeterData" in f]

# Load and transform half hourly meter data
data_list = [pd.read_csv(f, skiprows=5) for f in files]
data = pd.concat(data_list, ignore_index=True).drop_duplicates()

# Rename columns
data.columns = ['date', 'time', 'usage_1', 'usage_2', 'generation', 'meter_reading_status']
data.fillna({'usage_1': 0, 'usage_2': 0}, inplace=True)
data['syn_usage'] = data['usage_1'] + data['usage_2']
data = data[['date', 'time', 'syn_usage', 'generation']].rename(columns={'generation': 'syn_generation'})

# Format date and sort
data['date'] = pd.to_datetime(data['date'], format="%d/%m/%Y")
data.sort_values(['date', 'time'], inplace=True)

# Load other datasets
supply_charge = pd.read_csv(os.path.join(file_path, "synergy_supply_charge.csv"))
tou_costs = pd.read_csv(os.path.join(file_path, "synergy_tou_costs.csv"))
tou_costs['time'] = tou_costs['time'].apply(lambda x: x if len(x)==5 else '0'+x)

# Merge TOU costs
data = data.merge(tou_costs, on='time', how='left')

# Calculate cost columns
data['home_plan_costs'] = data['home_plan'] * data['syn_usage']
data['midday_saver_costs'] = data['midday_saver'] * data['syn_usage']
data['electric_vehicle_add_on_costs'] = data['electric_vehicle_add_on'] * data['syn_usage']
data['debs_feed_in_tariff'] = data['debs'] * data['syn_generation']

# Daily aggregation
data_daily = data.groupby('date').agg({
    'syn_usage': 'sum',
    'syn_generation': 'sum',
    'home_plan_costs': 'sum',
    'midday_saver_costs': 'sum',
    'electric_vehicle_add_on_costs': 'sum',
    'debs_feed_in_tariff': 'sum'
}).reset_index()

# Add supply charges
for plan in ['home_plan', 'midday_saver', 'electric_vehicle_add_on']:
    charge = supply_charge.loc[supply_charge['plan'] == plan, 'supply_charge'].values[0]
    data_daily[f'{plan}_costs'] += charge

# Load solar data
solar = pd.read_excel(os.path.join(file_path, "stationData-38723016.xlsx"), sheet_name=0)
solar = solar[['Date', 'Daily Solar Production (kWh)', 'Daily Consumption (kWh)', 'Daily From Grid (kWh)', 'Daily To Grid (kWh)']]
solar.columns = ['date', 'sig_solar_production', 'sig_consumption', 'sig_from_grid', 'sig_to_grid']
solar['date'] = pd.to_datetime(solar['date'].astype(str), format='%Y%m%d')

# Merge with daily data
data_daily = pd.merge(data_daily, solar, on='date', how='left')

# Calculations
data_daily['from_grid'] = data_daily['syn_usage']
data_daily['to_grid'] = data_daily['syn_generation']
data_daily['self_consumption'] = data_daily['sig_solar_production'] - data_daily['syn_generation']
data_daily['total_usage'] = data_daily['from_grid'] + data_daily['self_consumption']

# Plotting functions
def p_usage_line(input_date):
    plot_data = data[data['date'] == pd.to_datetime(input_date)]
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=plot_data['time'], y=plot_data['syn_usage'],
                             mode='lines', name='From Grid', line=dict(color='blue')))
    fig.add_trace(go.Scatter(x=plot_data['time'], y=plot_data['syn_generation'],
                             mode='lines', name='To Grid', line=dict(color='orange')))
    fig.update_layout(title="Half Hourly Usage and Generation",
                      xaxis_title="Time", yaxis_title="Energy (kWh)",
                      legend=dict(x=0.1, y=0.9), hovermode='x')
    fig.show()

# Generate plots
fig_costs = go.Figure()
fig_costs.add_trace(go.Scatter(x=data_daily['date'], y=data_daily['home_plan_costs'], name='Home Plan Costs', line=dict(color='blue')))
fig_costs.add_trace(go.Scatter(x=data_daily['date'], y=data_daily['midday_saver_costs'], name='Midday Saver Costs', line=dict(color='orange')))
fig_costs.add_trace(go.Scatter(x=data_daily['date'], y=data_daily['electric_vehicle_add_on_costs'], name='EV Add-On Costs', line=dict(color='green')))
fig_costs.update_layout(title="Daily Electricity Costs", xaxis_title="Date", yaxis_title="Cost", hovermode='x')
fig_costs.show()

fig_usage = go.Figure()
fig_usage.add_trace(go.Bar(x=data_daily['date'], y=data_daily['from_grid'], name='From Grid', marker_color='blue'))
fig_usage.add_trace(go.Bar(x=data_daily['date'], y=data_daily['self_consumption'], name='Self Consumption', marker_color='green'))
fig_usage.add_trace(go.Bar(x=data_daily['date'], y=-data_daily['to_grid'], name='To Grid', marker_color='orange'))
fig_usage.add_trace(go.Scatter(x=data_daily['date'], y=[-16]*len(data_daily), name='Battery Max Charge', line=dict(color='red', dash='dash')))
fig_usage.update_layout(barmode='relative', title='Daily Energy Flow', xaxis_title='Date', yaxis_title='Energy (kWh)', hovermode='x')
fig_usage.show()

# More plots can be added similarly...

# Summary
print(f"Total Home Plan Costs: ${data_daily['home_plan_costs'].sum() / 100:.2f}")
print(f"Total Midday Saver Costs: ${data_daily['midday_saver_costs'].sum() / 100:.2f}")
print(f"Total Electric Vehicle Add-On Costs: ${data_daily['electric_vehicle_add_on_costs'].sum() / 100:.2f}")
print(f"Total Feed-In Tariff: ${data_daily['debs_feed_in_tariff'].sum() / 100:.2f}")
print(f"Opportunity Cost from Self-Consumption: ${(data_daily['self_consumption'] * (32.3719 - 2)).sum() / 100:.2f}")

# Example usage plot
p_usage_line('2025-06-21')
