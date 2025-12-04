import pandas as pd
import fastf1
import plotly.express as px
from fastf1.plotting import get_driver_color_mapping

class DriverConsistency:
    def __init__(self, session):
        self.session = session
        self.driver_colors = get_driver_color_mapping(session=self.session)

    def plot(self):
        laps = self.session.laps.pick_quicklaps().reset_index()
        laps['LapTime(s)'] = laps['LapTime'].dt.total_seconds()

        # Standard deviation per driver
        consistency = laps.groupby('Driver')['LapTime(s)'].std().reset_index()
        consistency = consistency.sort_values('LapTime(s)')  # low std = more consistent

        fig = px.bar(
            consistency,
            x='Driver',
            y='LapTime(s)',
            color='Driver',
            color_discrete_map=self.driver_colors,
            hover_data={'LapTime(s)': ':.3f'}
        )
        fig.update_layout(
            title=f"Driver Consistency (Std Dev of Lap Times) - {self.session.event['EventName']} {self.session.event.year}",
            xaxis_title='Driver',
            yaxis_title='Std Dev of Lap Times (s)',
            plot_bgcolor='rgb(30,30,30)',
            paper_bgcolor='rgb(30,30,30)',
            font=dict(color='white')
        )
        return fig

def show_driver_consistency(session):
    import streamlit as st
    plotter = DriverConsistency(session)
    fig = plotter.plot()
    st.plotly_chart(fig, use_container_width=True)
