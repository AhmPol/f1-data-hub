import fastf1
import plotly.graph_objects as go
from fastf1.plotting import get_team_color
import colorsys

fastf1.Cache.enable_cache('fastf1_cache')

class SpeedComparisonDriversPlotly:
    """
    Interactive Plotly version of SpeedComparisonDrivers.
    Compares fastest laps of two drivers with distance vs speed and corner markers.
    """
    def __init__(self, session, driver_1, driver_2):
        self.session = session
        self.driver_1 = driver_1
        self.driver_2 = driver_2

    def _adjust_color_brightness(self, color, factor):
        """Lighten or darken a color by factor (1.2 = lighter, 0.8 = darker). Works with hex or rgb()."""
        import matplotlib.colors as mcolors
        try:
            # Convert color to RGB tuple (0-1 floats)
            rgb = mcolors.to_rgb(color)
        except ValueError:
            # If somehow invalid, fallback to orange
            rgb = (1.0, 0.5, 0.0)
        r, g, b = rgb
        import colorsys
        h, l, s = colorsys.rgb_to_hls(r, g, b)
        l = max(0, min(1, l * factor))
        r, g, b = colorsys.hls_to_rgb(h, l, s)
        # Return as rgb string for plotly
        return f'rgb({int(r*255)},{int(g*255)},{int(b*255)})'


    def plot(self):
        # Fastest laps and telemetry
        lap1 = self.session.laps.pick_drivers(self.driver_1).pick_fastest()
        lap2 = self.session.laps.pick_drivers(self.driver_2).pick_fastest()
        tel1 = lap1.get_car_data().add_distance()
        tel2 = lap2.get_car_data().add_distance()

        # Colors
        team1 = lap1['Team']
        team2 = lap2['Team']
        color1 = get_team_color(team1, session=self.session)
        color2 = get_team_color(team2, session=self.session)
        if team1 == team2:
            color1 = self._adjust_color_brightness(color1, 1.25)
            color2 = self._adjust_color_brightness(color2, 0.75)

        # Corner info
        circuit_info = self.session.get_circuit_info()

        fig = go.Figure()

        # Lap lines
        fig.add_trace(go.Scatter(
            x=tel1['Distance'], y=tel1['Speed'], mode='lines', name=f"{self.driver_1} ({team1})",
            line=dict(color=color1, width=3),
            hovertemplate="Driver: %{text}<br>Distance: %{x} m<br>Speed: %{y} km/h<extra></extra>",
            text=[self.driver_1]*len(tel1)
        ))
        fig.add_trace(go.Scatter(
            x=tel2['Distance'], y=tel2['Speed'], mode='lines', name=f"{self.driver_2} ({team2})",
            line=dict(color=color2, width=3),
            hovertemplate="Driver: %{text}<br>Distance: %{x} m<br>Speed: %{y} km/h<extra></extra>",
            text=[self.driver_2]*len(tel2)
        ))

        # Corner markers
        for _, corner in circuit_info.corners.iterrows():
            fig.add_vline(x=corner['Distance'], line=dict(color='grey', dash='dot', width=1))
            fig.add_annotation(x=corner['Distance'], y=min(tel1['Speed'].min(), tel2['Speed'].min())-20,
                               text=f"{corner['Number']}{corner['Letter']}", showarrow=False,
                               font=dict(size=10, color='grey'), yanchor='bottom', xanchor='center')

        # Layout
        fig.update_layout(
            title=f"{self.session.event['EventName']} {self.session.event.year} - Speed vs Distance",
            xaxis_title="Distance (m)",
            yaxis_title="Speed (km/h)",
            plot_bgcolor='rgb(30,30,30)',
            paper_bgcolor='rgb(30,30,30)',
            font=dict(color='white'),
            width=1000,
            height=600,
            legend=dict(title='Driver & Team')
        )

        return fig


def show_speed_comparison(session, key_prefix: str = ""):
    import streamlit as st

    drivers = sorted(list(set(session.laps['Driver'])))

    driver_1 = st.selectbox(
        "Select Driver 1",
        drivers,
        key=f"{key_prefix}speed_driver_1"
    )

    # default index: avoid crash if only 1 driver exists
    default_idx = 1 if len(drivers) > 1 else 0
    driver_2 = st.selectbox(
        "Select Driver 2",
        drivers,
        index=default_idx,
        key=f"{key_prefix}speed_driver_2"
    )

    plotter = SpeedComparisonDriversPlotly(session, driver_1, driver_2)
    fig = plotter.plot()
    st.plotly_chart(fig, use_container_width=True)

