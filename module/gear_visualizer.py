import streamlit as st
import numpy as np
import plotly.graph_objects as go
import fastf1
from matplotlib import cm

fastf1.Cache.enable_cache('fastf1_cache')

# Define discrete colors for gears 1-8 using a matplotlib colormap
gear_colors = cm.get_cmap('Paired', 8).colors
gear_colors_hex = [f'rgb({int(r*255)},{int(g*255)},{int(b*255)})' for r, g, b, _ in gear_colors]

class GearVisualizerPlotly:
    def __init__(self, session, driver):
        self.session = session
        self.driver = driver

    def plot(self):
        lap = self.session.laps.pick_driver(self.driver).pick_fastest()
        tel = lap.get_telemetry()
        x = tel['X'].values
        y = tel['Y'].values
        gear = tel['nGear'].values.astype(int)

        fig = go.Figure()
        gears_in_legend = set()
        start_idx = 0
        current_gear = gear[0]

        # Plot segments where gear is constant
        for i in range(1, len(gear)):
            if gear[i] != current_gear or i == len(gear)-1:
                show_legend = current_gear not in gears_in_legend
                fig.add_trace(go.Scattergl(
                    x=x[start_idx:i+1],
                    y=y[start_idx:i+1],
                    mode='lines',
                    line=dict(color=gear_colors_hex[current_gear-1], width=4),
                    name=f'Gear {current_gear}',
                    hoverinfo='text',
                    text=[f"Gear: {current_gear}"]*(i+1-start_idx),
                    showlegend=show_legend
                ))
                gears_in_legend.add(current_gear)
                start_idx = i
                current_gear = gear[i]

        fig.update_layout(
            title=f"Fastest Lap Gear Shift - {lap['Driver']} - {self.session.event['EventName']} {self.session.event.year}",
            xaxis=dict(showgrid=False, visible=False),
            yaxis=dict(showgrid=False, visible=False, scaleanchor="x", scaleratio=1),
            width=1200,
            height=600,
            plot_bgcolor='rgb(30,30,30)',
            paper_bgcolor='rgb(30,30,30)',
            font=dict(color='white'),
            legend=dict(title='Gear', bgcolor='rgba(50,50,50,0.5)')
        )

        return fig

def show_gear_visualizer(session):
    # Store selected driver in session_state to persist across reruns
    if 'selected_driver' not in st.session_state:
        st.session_state['selected_driver'] = None

    drivers = sorted(list(set(session.laps['Driver'])))
    driver = st.selectbox(
        "Select Driver", 
        drivers, 
        index=0 if st.session_state['selected_driver'] is None else drivers.index(st.session_state['selected_driver'])
    )
    st.session_state['selected_driver'] = driver

    gv = GearVisualizerPlotly(session, driver)
    fig = gv.plot()
    st.plotly_chart(fig, use_container_width=True)
