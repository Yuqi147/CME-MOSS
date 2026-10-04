import pyspedas
from pyspedas import tplot, get_data, get_units, store_data, options, tplot_options
from dateutil.parser import parse
from sunpy.coordinates import get_horizons_coord
import astropy.units as u
from sunpy.time import parse_time
import numpy as np

class DataLoader:
    def __init__(self, time1, time2):
        self.start_time = self.to_standard_date(time1)
        self.end_time = self.to_standard_date(time2)

    def to_standard_date(self, date_str):
        try:
            dt = parse(date_str)
            return dt.strftime('%Y-%m-%d')
        except Exception as e:
            return f"Time Error: {e}"


class PSP_data(DataLoader):
    def load_data(self):
        spi_vars = pyspedas.projects.psp.spi(trange=[self.start_time, self.end_time],
                                  time_clip=True)
        fld_vars = pyspedas.projects.psp.fields(trange=[self.start_time, self.end_time],
                                     time_clip=True,
                                     datatype='mag_RTN_4_Sa_per_Cyc')
        fld_vars_verif = pyspedas.projects.psp.fields(trange=[self.start_time, self.end_time],
                                     time_clip=True, datatype='sqtn_rfs_V1V2',
                                     level='l3')
        tplot(['psp_spi_DENS', 'psp_spi_VEL_RTN_SUN', 'psp_spi_TEMP', 'psp_fld_l2_mag_RTN_4_Sa_per_Cyc', 'electron_density'])

    def load_mag_data(self):
        # 'psp_fld_l2_mag_RTN_4_Sa_per_Cyc'
        fld_vars = pyspedas.projects.psp.fields(trange=[self.start_time, self.end_time],
                                                datatype='mag_RTN_4_Sa_per_Cyc', time_clip=True)
    def load_vel_data(self):
        # 'psp_spi_VEL_RTN_SUN'
        spi_vars = pyspedas.projects.psp.spi(trange=[self.start_time, self.end_time],
                                             time_clip=True)
    def load_dens_data(self):
        # ion density: 'psp_spi_DENS'
        # electron density: 'electron_density'
        spi_vars = pyspedas.projects.psp.spi(trange=[self.start_time, self.end_time],
                                             time_clip=True)
        e_dens_vars = pyspedas.projects.psp.fields(trange=[self.start_time, self.end_time],
                                                   time_clip=True,
                                                   datatype='sqtn_rfs_V1V2',
                                                   level='l3')


    def load_temp_data(self):
        # 'psp_spi_TEMP'
        spi_vars = pyspedas.projects.psp.spi(trange=[self.start_time, self.end_time],
                                             time_clip=True)

class SolO_data(DataLoader):
    def load_data(self):
        mag_vars = pyspedas.projects.solo.mag(trange=[self.start_time, self.end_time], datatype='rtn-normal', time_clip=True)
        swa_vars = pyspedas.projects.solo.swa(trange=[self.start_time, self.end_time], datatype='pas-grnd-mom', time_clip=True)
        tplot(['B_RTN', 'V_RTN', 'P_RTN', 'N', 'T'])

    def load_mag_data(self):
        # 'B_RTN'
        mag_vars = pyspedas.projects.solo.mag(trange=[self.start_time, self.end_time],
                                              datatype='rtn-normal', time_clip=True)

    def load_vel_data(self):
        # 'V_RTN'
        swa_vars = pyspedas.projects.solo.swa(trange=[self.start_time, self.end_time], datatype='pas-grnd-mom', time_clip=True)

    def load_dens_data(self):
        # 'N'
        swa_vars = pyspedas.projects.solo.swa(trange=[self.start_time, self.end_time], datatype='pas-grnd-mom', time_clip=True)

    def load_temp_data(self):
        # 'T'
        swa_vars = pyspedas.projects.solo.swa(trange=[self.start_time, self.end_time], datatype='pas-grnd-mom', time_clip=True)

class STEREO_A_data(DataLoader):
    def load_data(self):
        plastic_vars = pyspedas.projects.stereo.plastic(trange=[self.start_time, self.end_time], time_clip=True)
        sept_vars = pyspedas.projects.stereo.sept(trange=[self.start_time, self.end_time], time_clip=True)
        mag_vars = pyspedas.projects.stereo.mag(trange=[self.start_time, self.end_time], time_clip=True)
        tplot(['BFIELD', 'proton_bulk_speed', 'proton_number_density', 'proton_number_density', 'proton_temperature'])

    def load_mag_data(self):
        # 'BFIELD'
        mag_vars = pyspedas.projects.stereo.mag(trange=[self.start_time, self.end_time], time_clip=True)

    def load_vel_data(self):
        # 'proton_Vr_RTN'
        plastic_vars = pyspedas.projects.stereo.plastic(trange=[self.start_time, self.end_time], time_clip=True)

    def load_dens_data(self):
        # 'proton_number_density'
        plastic_vars = pyspedas.projects.stereo.plastic(trange=[self.start_time, self.end_time], time_clip=True)

    def load_temp_data(self):
        # 'Temperature_E' ion temp
        sept_vars = pyspedas.projects.stereo.sept(trange=[self.start_time, self.end_time], time_clip=True)
class WIND_data(DataLoader):
    def load_data(self):
        mfi_vars = pyspedas.projects.wind.mfi(trange=[self.start_time, self.end_time], time_clip=True)
        swe_vars = pyspedas.projects.wind.swe(trange=[self.start_time, self.end_time], time_clip=True)
        # tplot(['NcElec', 'TcElec', 'BGSE'])

    def load_mag_data(self):
        # 'BGSE'
        # GSE frame x from Earth to Sun
        mfi_vars = pyspedas.projects.wind.mfi(trange=[self.start_time, self.end_time], time_clip=True)

    def load_vel_data(self):
        return

    def load_dens_data(self):
        # electron density 'NcElec'
        swe_vars = pyspedas.projects.wind.swe(trange=[self.start_time, self.end_time], time_clip=True)

    def load_temp_data(self):
        # 'TcElec'
        swe_vars = pyspedas.projects.wind.swe(trange=[self.start_time, self.end_time], time_clip=True)

class ACE_data(DataLoader):
    def load_data(self):
        mfi_vars = pyspedas.projects.ace.mfi(trange=[self.start_time, self.end_time], time_clip=True)
        swe_vars = pyspedas.projects.ace.swe(trange=[self.start_time, self.end_time], time_clip=True)

    def load_mag_data(self):
        # 'BGSEc' GSE == GSEc
        mfi_vars = pyspedas.projects.ace.mfi(trange=[self.start_time, self.end_time], time_clip=True)

    def load_vel_data(self):
        # 'V_GSE'
        swe_vars = pyspedas.projects.ace.swe(trange=[self.start_time, self.end_time], time_clip=True)

    def load_dens_data(self):
        # ion density 'Np'
        swe_vars = pyspedas.projects.ace.swe(trange=[self.start_time, self.end_time], time_clip=True)

    def load_temp_data(self):
        return

class L1_data(DataLoader):

    def __init__(self, start_time, end_time):
        super().__init__(start_time, end_time)
        self.ace = ACE_data(self.start_time, self.end_time)
        self.wind = WIND_data(self.start_time, self.end_time)
        self.subs = [self.ace, self.wind]

    def _run(self, func):
        for loader in self.subs:
            getattr(loader, func)()

    def load_data(self):
        self._run('load_data')
        tplot(['BGSE', 'V_GSE', 'Np', ''])


    def load_mag_data(self):
        self._run('load_mag_data')


    def load_vel_data(self):
        self._run('load_vel_data')


    def load_dens_data(self):
        self._run('load_dens_data')


    def load_temp_data(self):
        self._run('load_temp_data')



class MAVEN_data(DataLoader):
    def load_data(self):
        # pyspedas.projects.maven
        return
    def load_mag_data(self):
        return
    def load_vel_data(self):
        return
    def load_dens_data(self):
        return
    def load_temp_data(self):
        return

target_dict = {"PSP": PSP_data, "SolO": SolO_data, "SA": STEREO_A_data, "Mars": MAVEN_data, "Earth": L1_data}

class CMEParameters(DataLoader):
    # target_dict = {"PSP": PSP_data, "SolO": SolO_data, "SA": STEREO_A_data, "Mars": MAVEN_data, "Earth": L1_data}

    def __init__(self, time_idx, objs):
        # super().__init__(time1, time2)
        print(time_idx)
        self.time_idx = time_idx
        self.objs = objs

    def load_data_for_type(self, method_name):
        """
        通用加载方法，调用对应的 load_***_data 方法
        :param method_name: str，例如 'mag'、'vel'，会调用 load_mag_data/load_vel_data 方法
        """

        for target in target_dict:
            if target in self.time_idx:
                start_time_idx = self.time_idx[target][0]
                end_time_idx = self.time_idx[target][1]
                start_time = self.objs[target].obstime[start_time_idx]
                end_time = self.objs[target].obstime[end_time_idx]
                current_tar = target_dict[target](str(start_time), str(end_time))

                # 动态调用方法：如 current_tar.load_mag_data()
                getattr(current_tar, f'load_{method_name}_data')()

    def multiplot(self, time_idx, var_list, type_name, figsize=(14, 2.5)):
        """
        Plot tplot variables with:
        - Independent x-axis ranges and ticks,
        - X-axis formatted as '%Y-%m-%d %H:%M',
        - Each subplot shows its own x-tick labels with proper spacing and rotation.
        """
        import matplotlib.pyplot as plt
        import matplotlib.dates as mdates
        from pytplot import get_data
        import datetime

        type_legend_dict = {
            "mag": ['Br', 'Bt', 'Bn', 'Btotal'],
            "vel": ['Vr', 'Vt', 'Vn', 'Vtotal'],
            "dens": [],
            "temp": []
        }

        n = len(time_idx)
        total_height = (figsize[1] + 0.6) * n
        fig, axs = plt.subplots(n, 1, figsize=(figsize[0], total_height), sharex=False)

        if n == 1:
            axs = [axs]

        # 为每个 subplot 保存该 subplot 里所有曲线的数据和对应的注释对象
        subplot_series_annots = []

        for i, var in enumerate(time_idx):
            ax = axs[i]
            series_data = []  # 存储该subplot所有曲线的数据和注释

            try:
                result = get_data(var_list[var])
                result_unit = get_units(var_list[var])
                if result is None:
                    raise ValueError("Variable not found or empty")

                time = result.times
                y = result.y
                # 转成 datetime 列表
                time_dt = [datetime.datetime.utcfromtimestamp(t) for t in time]

                if hasattr(y[0], '__len__') and not isinstance(y[0], (float, int)):
                    if len(y[0]) == 3:
                        norm = np.linalg.norm(y, axis=1)
                        y = np.hstack((y, norm[:, np.newaxis]))

                    # 多条向量曲线
                    for j in range(len(y[0])):
                        line, = ax.plot(time_dt, [yy[j] for yy in y],
                                        label=type_legend_dict.get(type_name, [])[j] if type_legend_dict.get(type_name) else f"comp{j}",
                                        linewidth=0.7)
                        # 创建注释框（隐藏）
                        annot = ax.annotate("",
                                            xy=(0, 0),
                                            xycoords="data",
                                            xytext=(0.75, 1.2 - 0.25*j),
                                            textcoords="axes fraction",
                                            bbox=dict(boxstyle="round", fc=line.get_color(), alpha=0.7),
                                            arrowprops=dict(arrowstyle="->", color=line.get_color()))
                        annot.set_visible(False)

                        series_data.append({
                            'x': time_dt,
                            'y': [yy[j] for yy in y],
                            'label': line.get_label(),
                            'color': line.get_color(),
                            'annot': annot
                        })
                    ax.legend(loc='upper right', fontsize=7)
                else:
                    # 单条曲线
                    line, = ax.plot(time_dt, y, linewidth=0.7)
                    annot = ax.annotate("",
                                        xy=(0, 0),
                                        xycoords="data",
                                        xytext=(0.75, 0.9),
                                        textcoords="axes fraction",
                                        bbox=dict(boxstyle="round", fc=line.get_color(), alpha=0.7),
                                        arrowprops=dict(arrowstyle="->", color=line.get_color()))
                    annot.set_visible(False)
                    series_data.append({
                        'x': time_dt,
                        'y': y,
                        'label': var_list[var],
                        'color': line.get_color(),
                        'annot': annot
                    })

                ax.set_ylabel(f"{var_list[var]}\n{var}\n{str(result_unit)}", fontsize=9)
                ax.set_xlabel("Time (UTC)", fontsize=9)
                ax.xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m-%d %H:%M'))
                ax.tick_params(axis='x', which='both', labelbottom=True)
                for label in ax.get_xticklabels():
                    label.set_visible(True)
                    label.set_rotation(30)
                    label.set_ha('right')

            except Exception as e:
                ax.text(0.5, 0.5, f"Error: {e}", ha='center', va='center')
                print(f"[Error] {var_list[var]}: {e}")

            subplot_series_annots.append(series_data)

        plt.subplots_adjust(hspace=0.6)

        def on_click(event):
            if event.inaxes not in axs:
                return

            ax = event.inaxes
            idx_ax = list(axs).index(ax)
            series_data = subplot_series_annots[idx_ax]

            # 右键隐藏所有注释
            if event.button == 1 and event.key == 'shift':
                for s in series_data:
                    s['annot'].set_visible(False)
                fig.canvas.draw_idle()
                return

            if event.button != 3:
                return

            x_click = mdates.num2date(event.xdata).replace(tzinfo=None) if event.xdata else None
            if x_click is None:
                return

            # 隐藏所有注释，避免残留
            for s in series_data:
                s['annot'].set_visible(False)

            for s in series_data:
                # 找最近点索引
                # 注意 time 是 datetime 列表，计算绝对秒数差距
                times = s['x']
                seconds_diff = [abs((t - x_click).total_seconds()) for t in times]
                min_idx = np.argmin(seconds_diff)

                x_near = times[min_idx]
                y_near = s['y'][min_idx]

                annot = s['annot']
                annot.xy = (x_near, y_near)
                annot.set_text(f"{x_near.strftime('%Y-%m-%d %H:%M:%S')}\n{s['label']}: {y_near}")
                annot.set_visible(True)

            fig.canvas.draw_idle()

        fig.canvas.mpl_connect("button_press_event", on_click)
        plt.show()

class MAG_data(CMEParameters):
    '''

    '''
    def load_mag(self):

        self.load_data_for_type('mag')

        '''options('x_axis_type', 'individual')
        tplot_options('psp_fld_l2_mag_RTN_4_Sa_per_Cyc', {'title': 'PSP'})
        tplot_options('B_RTN', {'title': 'SOLO'})
        tplot_options('BFIELD', {'title': 'STEREO-A'})
        tplot_options('BGSE', {'title': 'Earth L1'})
        
        tplot([
            'psp_fld_l2_mag_RTN_4_Sa_per_Cyc',
            'B_RTN',
            'BFIELD',
            'BGSE'
        ])'''

        self.multiplot(
            var_list={"PSP": 'psp_fld_l2_mag_RTN_4_Sa_per_Cyc',
                      "SolO": 'B_RTN',
                      "SA": 'BFIELD',
                      "Earth": 'BGSE'},
            time_idx=self.time_idx,
            type_name='mag'
        )



class VEL_data(CMEParameters):
    '''
        ion speed km/s
    '''
    def load_vel(self):
        '''
        GSE coordinates to RTN coor
        :return:
        '''
        self.load_data_for_type('vel')

        '''
        options('x_axis_type', 'individual')
        tplot_options('psp_spi_VEL_RTN_SUN', {'title': 'PSP'})
        tplot_options('V_RTN', {'title': 'SOLO'})
        tplot_options('proton_bulk_speed', {'title': 'STEREO-A'})
        tplot_options('V_GSE', {'title': 'Earth L1'})

        tplot([
            'psp_spi_VEL_RTN_SUN',
            'V_RTN',
            'proton_bulk_speed',
            'V_GSE'
        ])'''
        self.multiplot(
            var_list={"PSP": 'psp_spi_VEL_RTN_SUN',
                      "SolO": 'V_RTN',
                      "SA": 'proton_bulk_speed',
                      "Earth": 'V_GSE'},
            time_idx=self.time_idx,
            type_name='vel'
        )


class DENS_data(CMEParameters):
    '''
    ion dens
    '''
    def load_dens(self):
        self.load_data_for_type('dens')
        self.multiplot(
            var_list={"PSP": 'psp_spi_DENS',
                      "SolO": 'N',
                      "SA": 'proton_number_density',
                      "Earth": 'Np'},
            time_idx=self.time_idx,
            type_name='vel'
        )
    def load_dens_ion(self):
        self.load_data_for_type('dens')
        self.multiplot(
            var_list={"PSP": 'psp_spi_VEL_DENS',
                      "SolO": 'N',
                      "SA": 'proton_number_density',
                      "Earth": 'Np'},
            time_idx=self.time_idx,
            type_name='vel'
        )
    def load_dens_ele(self):
        self.load_data_for_type('dens')
        self.multiplot(
            var_list={"PSP": 'electron_density',
                      # "SolO": 'N', No direct data from Solar Orbiter
                      "SA": 'proton_number_density',
                      "Earth": 'Ncelec'},
            time_idx=self.time_idx,
            type_name='vel'
        )


class TEMP_data(CMEParameters):
    '''
    keV
    '''
    def load_temp(self):
        self.multiplot(
            var_list={"PSP": 'psp_spi_TEMP',
                      "SolO": 'T',
                      "SA": 'proton_temperature',
                      "Earth": 'Tpr'},
            time_idx=self.time_idx,
            type_name='vel'
        )
        self.load_data_for_type('temp')

type_dict = {"mag": MAG_data, "vel": VEL_data, "dens": DENS_data, "temp": TEMP_data}

'''CME_time1 = parse_time('2022-09-05')
CME_time2 = parse_time('2022-09-07')
psp_test = get_horizons_coord(
    'Parker Solar Probe',
    {
        'start': CME_time1,
        'stop': CME_time2 + 8 * u.day,
        'step': '15m'
    }
)

SolO_test = get_horizons_coord(
    'Solar Orbiter',
    {
        'start': CME_time1,
        'stop': CME_time2 + 8 * u.day,
        'step': '15m'
    }
)
objs = {"PSP": psp_test, "SolO": SolO_test}

time_idx = {"PSP": [100, 900], "SolO": [0, 500]}
test_exe = VEL_data(time_idx, objs)
test_exe.load_vel()
'''
