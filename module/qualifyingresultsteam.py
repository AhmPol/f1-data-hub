import pandas as pd
import fastf1
import plotly.graph_objects as go
from fastf1.core import Laps
from fastf1.plotting import get_team_color

fastf1.Cache.enable_cache('fastf1_cache')


class TeamAverageDiffDriverPlotly:
    """
    Interactive Plotly chart for team average difference from pole lap.
    Bars are sorted from fastest to slowest team.
    """

    def __init__(self, session):
        self.session = session

    def plot(self):
        # Get unique drivers and their fastest laps
        drivers = pd.unique(self.session.laps['Driver'])
        fastest_laps = []
        for drv in drivers:
            drv_fastest = self.session.laps.pick_driver(drv).pick_fastest()
            if drv_fastest is not None:
                fastest_laps.append(drv_fastest)

        laps_df = Laps(fastest_laps).reset_index(drop=True)
        pole_lap = laps_df.pick_fastest()
        pole_time_sec = pole_lap['LapTime'].total_seconds()

        # Compute team average lap time
        team_avg = (
            laps_df.groupby('Team')['LapTime']
            .apply(lambda x: x.dt.total_seconds().mean())
            .reset_index()
        )
        team_avg['DiffFromPole'] = team_avg['LapTime'] - pole_time_sec

        # Sort teams by fastest average (smallest DiffFromPole first)
        team_avg = team_avg.sort_values('DiffFromPole')

        # Plotly horizontal bar chart
        fig = go.Figure()
        for _, row in team_avg.iterrows():
            fig.add_trace(go.Bar(
                x=[row['DiffFromPole']],
                y=[row['Team']],
                orientation='h',
                marker_color=get_team_color(row['Team'], session=self.session),
                name=row['Team'],
                hovertemplate=f"{row['Team']}<br>Diff: {row['DiffFromPole']:.3f}s<extra></extra>"
            ))

        fig.update_layout(
            title=f"{self.session.event['EventName']} {self.session.event.year} - Team Average Diff from Pole",
            xaxis_title="Difference from Pole Lap (s)",
            yaxis_title="Team",
            yaxis=dict(autorange='reversed'),  # Fastest team on top
            plot_bgcolor='rgb(30,30,30)',
            paper_bgcolor='rgb(30,30,30)',
            font=dict(color='white')
        )
        return fig


def show_team_avg(session):
    import streamlit as st
    plotter = TeamAverageDiffDriverPlotly(session)
    fig = plotter.plot()
    st.plotly_chart(fig, use_container_width=True)
