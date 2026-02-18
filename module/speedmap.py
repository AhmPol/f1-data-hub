import numpy as np
import plotly.graph_objects as go
import fastf1

fastf1.Cache.enable_cache('fastf1_cache')

class SpeedDiffTrackMapPlotly:
    """
    Interactive Plotly version of speed comparison along the track
    between two drivers.
    """
    def __init__(self, session, driver_1, driver_2):
        self.session = session
        self.driver_1 = driver_1
        self.driver_2 = driver_2

    def plot(self):
        # Get fastest laps
        lap1 = self.session.laps.pick_drivers(self.driver_1).pick_fastest()
        lap2 = self.session.laps.pick_drivers(self.driver_2).pick_fastest()

        # Telemetry with distance
        tel1 = lap1.get_telemetry().add_distance()
        tel2 = lap2.get_telemetry().add_distance()

        # Ensure 'X' and 'Y' exist
        if 'X' not in tel1.columns or 'Y' not in tel1.columns:
            tel1['X'] = tel1['Distance']  # fallback linear mapping
            tel1['Y'] = tel1['Speed']     # fallback vertical mapping
            tel2['X'] = tel2['Distance']
            tel2['Y'] = tel2['Speed']

        # Interpolate to common distance points
        common_distance = np.linspace(0, min(tel1['Distance'].max(), tel2['Distance'].max()), 1500)
        tel1_speed = np.interp(common_distance, tel1['Distance'], tel1['Speed'])
        tel2_speed = np.interp(common_distance, tel2['Distance'], tel2['Speed'])

        # Speed difference for coloring
        speed_diff = tel1_speed - tel2_speed
        max_diff = np.max(np.abs(speed_diff))
        normalized_diff = speed_diff / max_diff

        # Track coordinates interpolation
        x = np.interp(common_distance, tel1['Distance'], tel1['X'])
        y = np.interp(common_distance, tel1['Distance'], tel1['Y'])

        # Build line segments colored by speed difference
        fig = go.Figure()

        # Add base gray track line
        fig.add_trace(go.Scatter(
            x=x, y=y,
            mode='lines',
            line=dict(color='lightgray', width=10),
            showlegend=False
        ))

        # Add colored speed difference line
        colors = ['rgb(0,0,{0})'.format(int(255*(0.5 + 0.5*(1-abs(v))))) if v > 0 
                  else 'rgb({0},0,0)'.format(int(255*(0.5 + 0.5*(1-abs(v))))) for v in normalized_diff]

        for i in range(len(x)-1):
            fig.add_trace(go.Scatter(
                x=x[i:i+2],
                y=y[i:i+2],
                mode='lines',
                line=dict(color=colors[i], width=5),
                showlegend=False
            ))

        # Lap times annotations
        fig.add_annotation(
            x=max(x),
            y=max(y),
            text=f"{self.driver_1}: {lap1['LapTime'].total_seconds():.3f}s",
            showarrow=False,
            xanchor='right',
            font=dict(color='navy')
        )
        fig.add_annotation(
            x=max(x),
            y=max(y)*0.95,
            text=f"{self.driver_2}: {lap2['LapTime'].total_seconds():.3f}s",
            showarrow=False,
            xanchor='right',
            font=dict(color='darkred')
        )

        fig.update_layout(
            title=f"{self.session.event['EventName']} {self.session.event.year} - "
                  f"{self.driver_1} vs {self.driver_2} Speed Comparison",
            xaxis=dict(visible=False),
            yaxis=dict(visible=False, scaleanchor="x", scaleratio=1),
            plot_bgcolor='rgb(30,30,30)',
            paper_bgcolor='rgb(30,30,30)',
            font=dict(color='white'),
            width=1200,
            height=600,
            showlegend=False
        )

        return fig

def show_speed_diff_track(session, key_prefix: str = ""):
    import streamlit as st

    drivers = sorted(list(set(session.laps['Driver'])))

    driver_1 = st.selectbox(
        "Select First Driver",
        drivers,
        key=f"{key_prefix}speed_diff_driver_1"
    )
    driver_2 = st.selectbox(
        "Select Second Driver",
        drivers,
        key=f"{key_prefix}speed_diff_driver_2"
    )

    plotter = SpeedDiffTrackMapPlotly(session, driver_1, driver_2)
    fig = plotter.plot()
    st.plotly_chart(fig, use_container_width=True, key=f"{key_prefix}speed_diff_track_chart")


