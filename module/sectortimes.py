import pandas as pd
import fastf1
import plotly.express as px
import streamlit as st
from fastf1.plotting import get_driver_color_mapping

fastf1.Cache.enable_cache('fastf1_cache')

class SectorTimesPlotly:
    def __init__(self, session, drivers=None):
        """
        session: FastF1 session object
        drivers: list of driver codes to include, defaults to all drivers in session
        """
        self.session = session
        self.drivers = drivers or sorted(list(session.laps['Driver'].unique()))
        self.driver_colors = get_driver_color_mapping(session=self.session)

    def plot(self):
        data = []

        for drv in self.drivers:
            laps = self.session.laps.pick_driver(drv).pick_quicklaps().reset_index()
            if laps.empty:
                continue

            # Extract sector times
            if 'Sector1Time' in laps.columns:
                laps['Sector1(s)'] = laps['Sector1Time'].dt.total_seconds()
                laps['Sector2(s)'] = laps['Sector2Time'].dt.total_seconds()
                laps['Sector3(s)'] = laps['Sector3Time'].dt.total_seconds()
            elif 'Sector1' in laps.columns:
                laps['Sector1(s)'] = laps['Sector1'].dt.total_seconds()
                laps['Sector2(s)'] = laps['Sector2'].dt.total_seconds()
                laps['Sector3(s)'] = laps['Sector3'].dt.total_seconds()
            else:
                st.warning(f"No sector data found for {drv}. Skipping.")
                continue

            # Prepare long-format data
            for _, lap in laps.iterrows():
                data.append({'Driver': drv, 'LapNumber': lap['LapNumber'], 'Sector': 'Sector 1', 'Time(s)': lap['Sector1(s)']})
                data.append({'Driver': drv, 'LapNumber': lap['LapNumber'], 'Sector': 'Sector 2', 'Time(s)': lap['Sector2(s)']})
                data.append({'Driver': drv, 'LapNumber': lap['LapNumber'], 'Sector': 'Sector 3', 'Time(s)': lap['Sector3(s)']})

        df = pd.DataFrame(data)
        if df.empty:
            st.warning("No sector data available for selected drivers.")
            return None

        # Compute median total sector time for each driver
        median_total = df.groupby('Driver')['Time(s)'].sum().groupby(level=0).median()
        sorted_drivers = median_total.sort_values().index.tolist()

        fig = px.violin(
            df,
            x="Driver",
            y="Time(s)",
            color="Driver",
            facet_col="Sector",
            box=True,
            points="all",
            hover_data=["LapNumber"],
            category_orders={"Driver": sorted_drivers},  # sort from fastest to slowest median
            color_discrete_map=self.driver_colors,
        )

        fig.update_traces(marker=dict(size=6, opacity=0.8), line=dict(width=1))
        fig.update_layout(
            title=f"Sector Times - {self.session.event['EventName']} {self.session.event.year}",
            yaxis_title="Sector Time (s)",
            plot_bgcolor='rgb(30,30,30)',
            paper_bgcolor='rgb(30,30,30)',
            font=dict(color='white'),
            width=1000,
            height=600
        )
        return fig

def show_sector_times(session):
    drivers = sorted(list(session.laps['Driver'].unique()))
    selected_drivers = st.multiselect(
        "Select Drivers for Sector Comparison",
        options=drivers,
        default=drivers[:6]
    )
    plotter = SectorTimesPlotly(session, selected_drivers)
    fig = plotter.plot()
    if fig:
        st.plotly_chart(fig, use_container_width=True)
