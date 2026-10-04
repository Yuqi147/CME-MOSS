# from collections import defaultdict
# from datetime import datetime
from sunpy.time import parse_time
from sunpy.coordinates import spice, frames, get_horizons_coord
from sunpy.data import cache
import astropy.units as u

# from bs4 import BeautifulSoup
import numpy as np
from scipy.spatial import KDTree


import csv
import requests
import pandas as pd
import re



SC = ["PSP", "SolO", "BC", "SA", "Mercury", "Earth", "Mars"] # , "Jupiter" out cluded

# def CME_info(start_YYYY, start_MM, start_DD, end_YYYY, end_MM, end_DD):
#     start_date = f"{start_YYYY}-{start_MM:02}-{start_DD:02}"
#     end_date = f"{end_YYYY}-{end_MM:02}-{end_DD:02}"
def CME_query(start_str, end_str):
    # request URL
    url = f"https://kauai.ccmc.gsfc.nasa.gov/DONKI/WS/get/CMEAnalysis.txt?startDate={start_str}&endDate={end_str}"
    response = requests.get(url)

    # True return?
    if response.status_code == 200:
        lines = response.text.strip().split("\n")

        data = []

        for line in lines:

            match = re.match(
                r"(?P<trigger_time>\S+)\s+lat=(?P<lat>-?\d+)\s+lon=(?P<lon>-?\d+)\s+rad=(?P<rad>\d+)\s+vel=(?P<vel>\d+)\s+#(?P<event_time>\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2})-(?P<cme_id>[^ ]+)\s+(?P<source>[^ ]+)\s+(?P<catalog_flag>\S+)\s+(?P<type>\S+)",
                line
            )
            if match:
                data.append(match.groupdict())

        CME_info = pd.DataFrame(data)

    else:
        print(f"Failed to fetch data: {response.status_code}")

    return CME_info

# hourly accuracy is enough
def get_PSP(CME_time1, CME_time2):
    launch_time = parse_time('2018-08-12T08:17:00')
    if CME_time1 > launch_time:
        PSP = get_horizons_coord(
            'Parker Solar Probe',
            {
                'start': CME_time1,
                'stop': CME_time2 + 8 * u.day,
                'step': '15m'
            }
        )
    elif CME_time1 < launch_time< CME_time2:
        PSP = get_horizons_coord(
            'Parker Solar Probe',
            {
                'start': launch_time,
                'stop': CME_time2 + 8 * u.day,
                'step': '15m'
            }
        )
    else:
        PSP = False
    return PSP

def get_SolO(CME_time1, CME_time2):
    launch_time = parse_time('2020-02-10T05:00:00')
    if CME_time1 > launch_time:
        SolO = get_horizons_coord(
            'Solar Orbiter',
            {
                'start': CME_time1,
                'stop': CME_time2 + 8* u.day,
                'step': '15m'
            }
        )
    elif CME_time1 < launch_time< CME_time2:
        SolO = get_horizons_coord(
            'Solar Orbiter',
            {
                'start': launch_time,
                'stop': CME_time2 + 8 * u.day,
                'step': '15m'
            }
        )
    else:
        SolO = False
    return SolO

# not included 2025.6.8
def get_STEREO_A(CME_time1, CME_time2):
    SA = get_horizons_coord(
        'STEREO-A',
        {
            'start': CME_time1,
            'stop': CME_time2 + 8 * u.day,
            'step': '30m'
        }
    )

    return SA

def get_BepiColombo(CME_time1, CME_time2):
    launch_time = parse_time('2018-10-20T02:14:00')
    if CME_time1 > launch_time:
        BC = get_horizons_coord(
            'Bepi',
            {
                'start': CME_time1,
                'stop': CME_time2 + 8* u.day,
                'step': '15m'
            }
        )

    elif CME_time1 < launch_time< CME_time2:
        BC = get_horizons_coord(
            'Bepi',
            {
                'start': launch_time,
                'stop': CME_time2 + 8 * u.day,
                'step': '15m'
            }
        )
    else:
        BC = False
    return BC

def get_Planets(CME_time1, CME_time2):
    start_time_Mer = CME_time1
    end_time_Mer = CME_time2 + 3.5 * u.day
    start_time = CME_time1
    end_time = CME_time2 + 14 * u.day
    # start_time_Ju = CME_time1 + 10 * u.day
    # end_time_Ju = CME_time2 + 40 * u.day
    Mercury = get_horizons_coord(
        1,
        {
            'start': start_time_Mer,
            'stop': end_time_Mer,
            'step': '60m'
        }
    )
    Earth = get_horizons_coord(
        3,
        {
            'start': start_time,
            'stop': end_time,
            'step': '60m'
        }
    )
    Mars = get_horizons_coord(
        4,
        {
            'start': start_time,
            'stop': end_time,
            'step': '60m'
        }
    )

    return Mercury, Earth, Mars

def convert_to_arrays(obj):
    # print(obj)
    # print()
    times = obj.obstime
    lons = np.array([coord.lon.value for coord in obj])
    lats = np.array([coord.lat.value for coord in obj])
    radii = np.array([coord.radius.to(u.km).value for coord in obj])

    return times, lons, lats, radii

def inside_cone(data_arrays, target_name, tol, cme_tree, CME_time, CME_v, speed_lim, CME_ind):
    # CME_time datetime
    target_data = data_arrays[target_name]
    target_points = target_data['points']
    tol = int(tol) + 10
    # KDTree query for all points within tolerance
    indices = cme_tree.query_ball_point(target_points, tol)

    matches = []

    for i, (time, radius) in enumerate(zip(target_data['times'], target_data['radii'])):
        if CME_time <= time <= CME_time + 9 * u.day:
            for j in indices[i]:
                # check radial velocity
                time_diff = abs((time - CME_time).to(u.s).value)
                radius_diff = abs(radius)

                if min((CME_v-speed_lim), 400) * time_diff <= radius_diff <= (CME_v+speed_lim) * time_diff:
                    matches.append((CME_time, CME_ind, time, radius, i))
    return matches

def CME_search(start_str, end_str, speed_lim):
    CME = CME_query(start_str, end_str)
    CME_time1 = parse_time(CME.loc[0, 'event_time'])
    CME_time1 = CME_time1 - 1 * u.day
    CME_time2 = parse_time(CME.loc[CME.shape[0]-1, 'event_time'])
    CME_time2 = CME_time2 + 1 * u.day

    objects = {}



    PSP = get_PSP(CME_time1, CME_time2)
    if PSP:
        objects["PSP"] = PSP
    else:
        print("Parker Solar Probe has not launched")
    SolO = get_SolO(CME_time1, CME_time2)
    if SolO:
        objects["SolO"] = SolO
    else:
        print("Solar Orbiter has not launched")

    BC = get_BepiColombo(CME_time1, CME_time2)
    if BC:
        objects["BC"] = BC
    else:
        print("Bepi Colombo Probe has not launched")

    SA = get_STEREO_A(CME_time1, CME_time2)
    if SA:
        objects["SA"] = SA
    else:
        print("STEREO A has not launched")

    Mercury, Earth, Mars = get_Planets(CME_time1, CME_time2)
    objects["Mercury"] = Mercury
    objects["Earth"] = Earth
    objects["Mars"] = Mars

    '''objects = {
        "PSP": PSP,
        "SolO": SolO,
        "BC": BC,
        "SA": SA,
        "Mercury": Mercury,
        "Earth": Earth,
        "Mars": Mars,

    }'''

    # data tranform to numpy array
    data_arrays = {}
    for name, obj in objects.items():
        # print(f"######{name}########")
        times, lons, lats, radii = convert_to_arrays(obj)
        data_arrays[name] = {
            'times': times,
            'lons': lons,
            'lats': lats,
            'radii': radii,
            'points': np.column_stack((lons, lats))  # 用于KDTree的二维点
        }

    overlaps_CME_cone = {}
    for i in range(CME.shape[0]):
        cme_point = np.column_stack((CME.loc[i, 'lon'], CME.loc[i, 'lat']))
        cme_tree = KDTree(cme_point)
        CME_time = parse_time(CME.loc[i, 'event_time'])
        CME_v = int(CME.loc[i, 'vel'])

        for target in objects.keys():

            matches = inside_cone(data_arrays, target, CME.loc[i, 'rad'], cme_tree, CME_time, CME_v, speed_lim, i)
            for CME_time, CME_ind, time, radius, target_idx in matches:

                result_key = (CME_time, i)
                if result_key not in overlaps_CME_cone:
                    overlaps_CME_cone[result_key] = []

                overlaps_CME_cone[result_key].append({
                    'target': target,
                    'target_time': (time, target_idx),
                    'target_radius': radius
                })
    return overlaps_CME_cone, CME, objects


def result_output_txt(start_date, end_date, overlaps):
    results_CME = {}  # index passing through
    headers = ['#event: CME occurrence time',
               '#Object: Spacecrafts or planets',
               '#start: Cone-zone entering time',
               '#end: Cone-zone exiting time',
               '#distance1: entering distance from the sun (km)',
               '#distance2: exiting distance from the sun (km)']
    txt_name = 'CME'+start_date+'to'+end_date+'.txt'
    with open(txt_name, 'w', encoding='utf-8',newline='') as f:
        f.write('###header start###\n')
        f.write('precision at the hour level\n')
        f.write("\n".join(headers) + "\n")
        f.write('event\n')
        f.write('Object\tstart\tend\tdistance1\tdistance2\n')
        f.write('###header end###\n')

        writer = csv.writer(f, delimiter='\t')
        for cme in overlaps.keys():
            writer.writerow([cme[0]])
            results_CME[cme[1]] = {}
            for obj in SC:
                encounter = list(filter(lambda dict: dict['target'] == obj, overlaps[cme]))
                if encounter:
                    row = [
                        obj,
                        str(encounter[0]['target_time'][0]),
                        str(encounter[-1]['target_time'][0]),
                        str(encounter[0]['target_radius']),
                        str(encounter[-1]['target_radius'])
                    ]
                    encounter_idx = [encounter[0]['target_time'][1], encounter[-1]['target_time'][1]]

                    results_CME[cme[1]][obj] = encounter_idx
                    writer.writerow(row)
            writer.writerow([])

    return results_CME
'''
def result_output_plot(in_cone_dic, CME_info):
    cases_time = list(map(lambda x: x[0], in_cone_dic.keys()))

    for i in range(CME_info.shape[0]):
        cme_str = CME_info.loc[i, 'event_time']
        cme = parse_time(cme_str)
        # print(cme)
        if cme in cases_time:
            ax, fig = plot_encounter_background()
            CME_cone_plot(ax, i, CME_info)
            for obj in SC:
                encounter = list(filter(lambda dict: dict['target'] == obj, in_cone_dic[cme]))
                if encounter:
                    body_plot(ax, obj, encounter[0]['target_time'], encounter[-1]['target_time'])


            ax.set_title('CME'+cme_str)

            # 关键参数组合
            ax.legend(
                loc='upper left',  # 基准位置
                bbox_to_anchor=(1.05, 1),  # 相对基准点的偏移
                borderaxespad=0.5,  # 边框与图表间距
                frameon=True,  # 是否显示边框
                fontsize=10,
            )

            # 调整图表边距
            plt.tight_layout()
            plt.subplots_adjust(right=0.75)  # 保留右侧空间

            plt.savefig(
                'CME' + str(i) + '.png',
                dpi=600,
                bbox_inches='tight',
            )
            plt.close(fig)
'''

def cone_search(start_str, end_str, speed_lim):
    result_cone, CME_info, objs = CME_search(start_str, end_str, speed_lim)

    result_CME = result_output_txt(start_str, end_str, result_cone)
    # result_CME passing index
    # result_output_plot(result_cone, CME_info)
    return result_CME, CME_info, objs
