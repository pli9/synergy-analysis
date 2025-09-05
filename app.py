import streamlit as st
import plotly.graph_objects as go
import pandas as pd

st.title("Synergy Half Hourly Data Analysis")
st.markdown("This app allows you to upload Synergy half hourly data and Sigenergy solar data, and visualize the energy usage, generation, and costs associated with different plans.")

with st.container(border=True):
  st.header("Input Synergy and Sigenergy Data")
  # Import a file uploader
  uploaded_synergy_files = st.file_uploader(
    label = "Upload Synergy Half Hourly Data File(s)",
    accept_multiple_files=True,
    type=["csv"]
  )
  if len(uploaded_synergy_files) > 0:
    data_list = [pd.read_csv(f, skiprows=5) for f in uploaded_synergy_files]
    data = pd.concat(data_list, ignore_index=True).drop_duplicates()
    
    # Wrap this in a collapsed box
    with st.expander("View Data"):
      # Display the DataFrame
      st.write(data)

  uploaded_sigenergy_file = st.file_uploader(
    label = "Upload Sigenergy Solar Data File",
    accept_multiple_files=True,
    type=["xlsx"]
  )

  if len(uploaded_sigenergy_file) > 0:
    # Read the solar data file into a DataFrame
    solar_list = [pd.read_excel(f, sheet_name=0) for f in uploaded_sigenergy_file]
    solar = pd.concat(solar_list, ignore_index=True).drop_duplicates()

    # Wrap this in a collapsed box
    with st.expander("View Solar Data"):
      # Display the DataFrame
      st.write(solar)
  
@st.cache_data(show_spinner=False)
def process_data(data, solar):
  # Rename columns
  data.columns = ['date', 'time', 'usage_1', 'usage_2', 'generation', 'meter_reading_status']
  data.fillna({'usage_1': 0, 'usage_2': 0}, inplace=True)
  data['syn_usage'] = data['usage_1'] + data['usage_2']
  data = data[['date', 'time', 'syn_usage', 'generation']].rename(columns={'generation': 'syn_generation'})

  # Format date
  data['date'] = pd.to_datetime(data['date'], format="%d/%m/%Y")
  # Fix times that are 4 digits long (e.g., '0:30' to '00:30')
  data['time'] = [f"0{t}" if len(t)==4 else t for t in data['time']]
  # Sort by date and time
  data.sort_values(['date', 'time'], inplace=True)

  # Load other datasets
  supply_charge = pd.DataFrame(
    {
      'plan': ['home_plan', 'midday_saver', 'electric_vehicle_add_on'],
      'supply_charge': [116.0505, 129.2269, 129.2269]
    }
  )
  tou_costs = pd.DataFrame(
    {
      'time': [f"{h:02d}:{m:02d}" for h in range(24) for m in (0, 30)],
      'home_plan': 32.3719,
      'midday_saver': [23.6916]*18 + [8.6151]*12 + [53.8446]*12 + [23.6916]*6,
      'electric_vehicle_add_on': [19.3841]*12 +[23.6916]*6 + [8.6151]*12 + [53.8446]*12 + [23.6916]*4 + [19.3841]*2,
      'debs': [2]*30 + [10]*12 + [2]*6,
    }
  )
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

  return data, data_daily

if len(uploaded_synergy_files) > 0 and len(uploaded_sigenergy_file) > 0:
  data, data_daily = process_data(data, solar)

  st.header("Overview of Energy Usage and Costs")

  # Plotting functions
  def p_usage_line(input_date):
    plot_data = data[data['date'] == pd.to_datetime(input_date)]
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=plot_data['time'], y=plot_data['syn_usage'], mode='lines', name='From Grid', line=dict(color='blue')))
    fig.add_trace(go.Scatter(x=plot_data['time'], y=plot_data['syn_generation'], mode='lines', name='To Grid', line=dict(color='orange')))
    fig.update_layout(
      title="Half Hourly Usage and Generation",
      xaxis_title="Time",
      yaxis_title="Energy (kWh)",
      legend=dict(x=0.1, y=0.9),
      hovermode='x'
    )
    return(fig)


  # Add input for date selection
  with st.container(
    border=True
  ):
    input_date = st.slider(
      "Select a date to view usage line plot",
      min_value=data['date'].min().date(),
      max_value=data['date'].max().date(),
      value=data['date'].min().date(),
      format="YYYY-MM-DD"
    )
    if input_date:    
      st.plotly_chart(p_usage_line(input_date.strftime('%Y-%m-%d')))

  # Use plotly to plot line charts for costs ####
  with st.container(border=True):
    input_date_range = st.date_input(
      "Select a date range to view costs",
      value=(data_daily['date'].min(), data_daily['date'].max())
    )
    
    data_daily_filtered = data_daily[
      (data_daily['date'] >= pd.to_datetime(input_date_range[0])) &
      (data_daily['date'] <= pd.to_datetime(input_date_range[1]))
    ]

    st.write(f"Total Home Plan Costs: **${data_daily_filtered ['home_plan_costs'].sum() / 100:.2f}**")
    st.write(f"Total Midday Saver Costs: **${data_daily_filtered['midday_saver_costs'].sum() / 100:.2f}**")
    st.write(f"Total Electric Vehicle Add-On Costs: **${data_daily_filtered['electric_vehicle_add_on_costs'].sum() / 100:.2f}**")
    st.write(f"Total Feed-In Tariff: **${data_daily_filtered['debs_feed_in_tariff'].sum() / 100:.2f}**")
    st.write(f"Opportunity Cost from Self-Consumption: **${(data_daily_filtered['self_consumption'] * (32.3719 - 2)).sum() / 100:.2f}**")

    fig_costs = go.Figure()
    fig_costs.add_trace(go.Scatter(x=data_daily_filtered['date'], y=data_daily_filtered['home_plan_costs'],
                                  name='Home Plan Costs', line=dict(color='blue')))
    fig_costs.add_trace(go.Scatter(x=data_daily_filtered['date'], y=data_daily_filtered['midday_saver_costs'],
                                  name='Midday Saver Costs', line=dict(color='orange')))
    fig_costs.add_trace(go.Scatter(x=data_daily_filtered['date'], y=data_daily_filtered['electric_vehicle_add_on_costs'],
                                  name='EV Add-On Costs', line=dict(color='green')))
    fig_costs.update_layout(title="Daily Electricity Costs",
                            xaxis_title="Date", yaxis_title="Cost (in currency units)",
                            legend=dict(x=0.1, y=0.9), hovermode='x')
    st.plotly_chart(fig_costs)

    # Use plotly to plot stacked bar chart for from_grid, and self_consumption ####
    fig_usage = go.Figure()
    fig_usage.add_trace(go.Bar(x=data_daily_filtered['date'], y=data_daily_filtered['from_grid'],
                              name='From Grid', marker_color='blue'))
    fig_usage.add_trace(go.Bar(x=data_daily_filtered['date'], y=data_daily_filtered['self_consumption'],
                              name='Self Consumption', marker_color='green'))
    fig_usage.add_trace(go.Bar(x=data_daily_filtered['date'], y=-data_daily_filtered['to_grid'],
                              name='To Grid', marker_color='orange'))
    fig_usage.add_trace(go.Scatter(x=data_daily_filtered['date'], y=[-16]*len(data_daily_filtered),
                                  name='Battery Max Charge', line=dict(color='red', dash='dash')))
    fig_usage.update_layout(title="Daily Energy Flow",
                            xaxis_title="Date", yaxis_title="Energy (kWh)",
                            barmode='relative', legend=dict(x=0.1, y=0.9), hovermode='x')
    st.plotly_chart(fig_usage)

    # Use plotly to plot 100% stacked bar chart for from_grid, and self_consumption ####
    fig_usage_pct = go.Figure()
    fig_usage_pct.add_trace(go.Bar(
        x=data_daily_filtered['date'],
        y=(data_daily_filtered['from_grid'] / data_daily_filtered['total_usage']) * 100,
        name='From Grid', marker_color='blue'))
    fig_usage_pct.add_trace(go.Bar(
        x=data_daily_filtered['date'],
        y=(data_daily_filtered['self_consumption'] / data_daily_filtered['total_usage']) * 100,
        name='Self Consumption', marker_color='green'))
    fig_usage_pct.update_layout(title="Daily Energy Flow (Percentage)",
                                xaxis_title="Date", yaxis_title="Percentage (%)",
                                barmode='relative', legend=dict(x=0.1, y=0.9), hovermode='x')
    st.plotly_chart(fig_usage_pct)

    # Use plotly to plot stacked bar chart for to_grid and self_consumption relative to sig_solar_production ####
    fig_solar = go.Figure()
    fig_solar.add_trace(go.Bar(x=data_daily_filtered['date'], y=data_daily_filtered['to_grid'],
                              name='To Grid', marker_color='orange'))
    fig_solar.add_trace(go.Bar(x=data_daily_filtered['date'], y=data_daily_filtered['self_consumption'],
                              name='Self Consumption', marker_color='green'))
    fig_solar.update_layout(title="Daily Solar Production Flow",
                            xaxis_title="Date", yaxis_title="Energy (kWh)",
                            barmode='relative', legend=dict(x=0.1, y=0.9), hovermode='x')
    st.plotly_chart(fig_solar)

    # Use plotly to plot 100% stacked bar chart for to_grid and self_consumption relative to sig_solar_production ####
    fig_solar_pct = go.Figure()
    fig_solar_pct.add_trace(go.Bar(
        x=data_daily_filtered['date'],
        y=(data_daily_filtered['to_grid'] / data_daily_filtered['sig_solar_production']) * 100,
        name='To Grid', marker_color='orange'))
    fig_solar_pct.add_trace(go.Bar(
        x=data_daily_filtered['date'],
        y=(data_daily_filtered['self_consumption'] / data_daily_filtered['sig_solar_production']) * 100,
        name='Self Consumption', marker_color='green'))
    fig_solar_pct.update_layout(title="Daily Solar Production Flow (Percentage)",
                                xaxis_title="Date", yaxis_title="Percentage (%)",
                                barmode='relative', legend=dict(x=0.1, y=0.9), hovermode='x')
    st.plotly_chart(fig_solar_pct)

    # Use plotly to plot bar chart of to_grid ####
    fig_to_grid = go.Figure()
    fig_to_grid.add_trace(go.Bar(x=data_daily_filtered['date'], y=data_daily_filtered['to_grid'],
                                name='To Grid', marker_color='orange'))
    fig_to_grid.update_layout(title="Daily Energy Sent to Grid",
                              xaxis_title="Date", yaxis_title="Energy (kWh)",
                              legend=dict(x=0.1, y=0.9), hovermode='x')
    st.plotly_chart(fig_to_grid)
