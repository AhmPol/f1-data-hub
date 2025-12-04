import pandas as pd
import fastf1
import plotly.express as px
import streamlit as st
from fastf1.plotting import get_compound_mapping

fastf1.Cache.enable_cache('fastf1_cache')

class TyreDegradationPlotly:
    def __init__(self, session, drivers=None):
        """
        session: FastF1 session object
        drivers: list of drivers to include, default all drivers
        """
        self.session = session
        self.drivers = drivers or sorted(list(session.laps['Driver'].unique()))
        self.compound_colors = get_compound_mapping(session=self.session)

    def plot(self):
        data = []

        for drv in self.drivers:
            laps = self.session.laps.pick_driver(drv).pick_quicklaps().reset_index()
            if laps.empty:
                continue

            # Lap time in seconds
            laps['LapTime(s)'] = laps['LapTime'].dt.total_seconds()
            for _, lap in laps.iterrows():
                data.append({
                    'Driver': drv,
                    'LapNumber': lap['LapNumber'],
                    'LapTime(s)': lap['LapTime(s)'],
                    'Compound': lap['Compound'],
                    'Stint': lap['Stint']
                })

        df = pd.DataFrame(data)
        if df.empty:
            st.warning("No lap data available for selected drivers.")
            return None

        # Optional: sort drivers by median lap time (fastest first)
        median_times = df.groupby('Driver')['LapTime(s)'].median().sort_values()
        sorted_drivers = median_times.index.tolist()

        fig = px.line(
            df,
            x='LapNumber',
            y='LapTime(s)',
            color='Compound',
            line_group='Stint',
            facet_col='Driver' if len(self.drivers) <= 4 else None,
            facet_col_wrap=2,
            markers=True,
            hover_data=['LapNumber', 'LapTime(s)', 'Stint'],
            color_discrete_map=self.compound_colors,
            category_orders={'Driver': sorted_drivers}
        )

        fig.update_traces(mode='lines+markers')
        fig.update_layout(
            title=f"Tyre Life / Degradation - {self.session.event['EventName']} {self.session.event.year}",
            xaxis_title="Lap Number",
            yaxis_title="Lap Time (s)",
            plot_bgcolor='rgb(30,30,30)',
            paper_bgcolor='rgb(30,30,30)',
            font=dict(color='white'),
            width=1000,
            height=600
        )
        return fig

def show_tyre_degradation(session):
    drivers = sorted(list(session.laps['Driver'].unique()))
    selected_drivers = st.multiselect(
        "Select Drivers to Visualize Tyre Degradation",
        options=drivers,
        default=drivers[:4]  # default top 4
    )
    plotter = TyreDegradationPlotly(session, selected_drivers)
    fig = plotter.plot()
    if fig:
        st.plotly_chart(fig, use_container_width=True)
