import pandas as pd
import fastf1
import plotly.graph_objects as go
from fastf1.plotting import get_compound_mapping

fastf1.Cache.enable_cache('fastf1_cache')

class LapTimeDistributionPointFinishersPlotly:
    def __init__(self, session):
        self.session = session
        self.point_finishers = self.session.drivers[:10]
        self.driver_mapping = {drv: self.session.get_driver(drv)['Abbreviation'] for drv in self.point_finishers}
        self.compound_colors = get_compound_mapping(session=self.session)

    def plot(self):
        fig = go.Figure()
        for drv in self.point_finishers:
            laps = self.session.laps.pick_driver(drv).pick_quicklaps().reset_index()
            if laps.empty:
                continue
            laps['LapTime(s)'] = laps['LapTime'].dt.total_seconds()
            driver_name = self.driver_mapping[drv]
            for compound, group in laps.groupby('Compound'):
                color = self.compound_colors.get(compound, '#888888')
                fig.add_trace(go.Scatter(
                    x=group['LapNumber'],
                    y=group['LapTime(s)'],
                    mode='markers+lines',
                    name=f"{driver_name} ({compound})",
                    marker=dict(color=color, size=8),
                    line=dict(width=2),
                    hovertemplate='Driver: %{text}<br>Lap: %{x}<br>Lap Time: %{y:.3f}s<extra></extra>',
                    text=[driver_name]*len(group)
                ))

        fig.update_layout(
            title=f"{self.session.event['EventName']} {self.session.event.year} - Point Finishers Lap Times",
            xaxis_title="Lap Number",
            yaxis_title="Lap Time (s)",
            yaxis=dict(autorange='reversed'),
            plot_bgcolor='rgb(30,30,30)',
            paper_bgcolor='rgb(30,30,30)',
            font=dict(color='white'),
            legend_title="Driver (Compound)",
            hovermode='closest'
        )
        return fig

def show_point_finishers(session):
    import streamlit as st
    plotter = LapTimeDistributionPointFinishersPlotly(session)
    fig = plotter.plot()
    st.plotly_chart(fig, use_container_width=True)
