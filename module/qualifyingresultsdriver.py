import pandas as pd
import fastf1
import plotly.graph_objects as go
from fastf1.core import Laps
from timple.timedelta import strftimedelta
from fastf1.plotting import get_team_color

fastf1.Cache.enable_cache('fastf1_cache')

class QualifyingResultsTimeDriverPlotly:
    def __init__(self, session):
        self.session = session
        # Get unique drivers
        self.drivers = pd.unique(self.session.laps['Driver'])
        # Map driver number to abbreviation
        self.driver_mapping = {drv: self.session.get_driver(drv)['Abbreviation'] for drv in self.drivers}

    def plot(self):
        # Get each driver's fastest lap
        list_fastest_laps = []
        for drv in self.drivers:
            drv_fastest = self.session.laps.pick_driver(drv).pick_fastest()
            if drv_fastest is not None:
                list_fastest_laps.append(drv_fastest)

        fastest_laps = Laps(list_fastest_laps).sort_values(by='LapTime').reset_index(drop=True)
        pole_lap = fastest_laps.pick_fastest()
        fastest_laps['LapTimeDiff'] = (fastest_laps['LapTime'] - pole_lap['LapTime']).dt.total_seconds()

        # Plotly horizontal bar chart
        fig = go.Figure()
        for idx, row in fastest_laps.iterlaps():
            driver_name = self.driver_mapping[row['Driver']]
            team_color = get_team_color(row['Team'], session=self.session)
            fig.add_trace(go.Bar(
                x=[row['LapTimeDiff']],
                y=[driver_name],
                orientation='h',
                marker_color=team_color,
                name=driver_name,
                hovertemplate=f"{driver_name}<br>Diff: {row['LapTimeDiff']:.3f}s<extra></extra>"
            ))

        lap_time_string = strftimedelta(pole_lap['LapTime'], '%m:%s.%ms')
        fig.update_layout(
            title=f"{self.session.event['EventName']} {self.session.event.year} Qualifying<br>"
                  f"Fastest Lap: {lap_time_string} ({self.driver_mapping[pole_lap['Driver']]})",
            xaxis_title="Difference from Pole Lap (s)",
            yaxis_title="Driver",
            yaxis=dict(autorange='reversed'),
            plot_bgcolor='rgb(30,30,30)',
            paper_bgcolor='rgb(30,30,30)',
            font=dict(color='white'),
            legend_title="Driver"
        )
        return fig

def show_qualifying_results(session):
    import streamlit as st
    plotter = QualifyingResultsTimeDriverPlotly(session)
    fig = plotter.plot()
    st.plotly_chart(fig, use_container_width=True)
