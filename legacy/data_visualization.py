import matplotlib.pyplot as plt

import astropy.units as u
import numpy as np

from sunpy.coordinates import get_horizons_coord, get_body_heliographic_stonyhurst
from sunpy.time import parse_time

def spacecrafts_names(name):
    if name != 'Earth':
        SC = {
            'PSP': "Parker Solar Probe",
            "SolO": "Solar Orbiter",
            "BC": "Bepi",  # Bepi Colombo MTM
            "SA": "STEREO-A",
            "Mercury": 1,
            "Mars": 4,
            "Jupiter": 5
        }
        if name in SC:
            return SC[name]
        else:
            return name

def colors(body_name):
    return {
        "Parker Solar Probe": 'purple',
        "Solar Orbiter": 'red',
        "Bepi": 'green',
        "STEREO-A": '#236B8E',
        1: 'grey', # Mercury
        4: 'brown', # Mars
        5: 'pink' # Jupiter
    }[body_name]

def coord_to_polar(coord):
    # print(coord)
    return coord.lon.to_value('rad'), coord.radius.to_value('AU')


def CME_cone_plot(ax, CME_lon, CME_half_angle_width, CME_v):
    # input angle in unit deg
    # CME_info is the panda frame of CME event
    #print(isinstance(CME_lon,str))
    lon = (int(CME_lon) * u.deg).to_value(u.rad)
    half = (int(CME_half_angle_width) * u.deg).to_value(u.rad)
    # ax.fill_between([lon-half, lon+half], 0, 1.5, color='orange', alpha=0.8)
    ax.plot([lon-half, lon-half], [0, 1.5], color='black', linestyle='dotted')
    ax.plot([lon+half, lon+half], [0, 1.5], color='black', linestyle='dotted')

    CME_v = int(CME_v) * u.km / u.s
    time_inte = 12 * u.h
    t = 0 * u.h
    CME_propa_dis_value = 0
    theta_rad = np.linspace(lon-half, lon+half, 100)
    while CME_propa_dis_value <= 1.5:
        t = t + time_inte
        CME_propa_dis_value = (CME_v * t).to_value(u.AU)
        r_plot = np.full_like(theta_rad, CME_propa_dis_value)
        ax.plot(theta_rad, r_plot, color='orange', alpha=0.7)

    def draw_sector(ax, lon, half, radius=1.5, color='orange', alpha=0.3):
        theta = np.linspace(lon-half, lon+half, 100)
        theta = np.append(theta, [lon-half])
        r = np.full_like(theta, radius)
        r[-1] = 0
        ax.fill(theta, r, color=color, alpha=alpha)
    draw_sector(ax, lon, half)
    est_half = half + (10 * u.deg).to_value(u.rad)
    draw_sector(ax, lon, est_half, alpha=0.1)

def body_plot(ax, obj, body_name, *time_points):
    # print(time_points[0],time_points[1])
    if body_name != 'Earth':
        body = obj[time_points[0]: time_points[1]+6]

        if time_points[0]-288 > 0:
            body_past_trajectory = obj[time_points[0]-384: time_points[0]]
        else:
            body_past_trajectory = obj[0:time_points[0]]

        # print(body_past_trajectory)
        body_color = colors(spacecrafts_names(body_name))
        ax.plot(*coord_to_polar(body), color=body_color, label=body_name)
        ax.plot(*coord_to_polar(body[-1]), color=body_color, marker='o', markersize=2)
        ax.plot(*coord_to_polar(body_past_trajectory), color=body_color, alpha=0.5)
'''
        start_time = parse_time(time_points[0])
        if len(time_points) == 2:
            end_time = parse_time(time_points[1])
        else:
            end_time = start_time + 5 * u.hour

        time_interval = (end_time - start_time).to(u.hour).value + 24
        obstime = start_time - 12 * u.hour+ np.arange(time_interval) * u.hour
        obstime_future_trajectory = end_time + 12 * u.hour + np.arange(72) * u.hour

        SC = spacecrafts_names(body_name)
        #print(body_name)
        body = get_horizons_coord(SC, obstime)
        body_future_trajectory = get_horizons_coord(SC, obstime_future_trajectory)
        body_color = colors(spacecrafts_names(body_name))
        ax.plot(*coord_to_polar(body), color=body_color, label=body_name)
        ax.plot(*coord_to_polar(body_future_trajectory), color=body_color, alpha=0.3)
        # body_start = coord_to_polar(body[0])
        # body_end = coord_to_polar(body[-1])

        # ax.plot(*body_start, 'o', color='#5F9F9F', ms=0.5) # grey blue starts

        # ax.plot(*body_end, 'o', color='#8E236B', ms=0.5) # red brown ends
'''


def plot_encounter_background():
    earth = get_body_heliographic_stonyhurst('earth')
    fig = plt.figure()
    ax = fig.add_subplot(projection='polar')
    ax.plot(0, 0, marker='o', label='Sun', color='orange')
    ax.plot(*coord_to_polar(earth), marker='o', label='Earth', color='blue', markersize=2)
    return ax,fig

