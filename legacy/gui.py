import tkinter as tk
from tkinter import messagebox, ttk
from datetime import datetime

import os
from sunpy.time import parse_time
import astropy.units as u
from astropy.time import Time, TimeDelta

from cone_search_HEEQ import cone_search
from data_visualization import plot_encounter_background, CME_cone_plot, body_plot
# from instru_data import load_func
from in_situ_data import target_dict, type_dict

import matplotlib.pyplot as plt
import numpy as np

# SC = ["PSP", "SolO", "BC", "SA", "Mercury", "Earth", "Mars"]

def run_analysis(start_date, end_date, speed_lim):
    print(f"Time range：{start_date} to {end_date}")
    # print(f"velocity range：{min_speed} ~ {max_speed} km/s")
    result, CME_info, objs = cone_search(str(start_date), str(end_date), speed_lim)
    messagebox.showinfo(message="Search completed")
    # except :
    #     messagebox.showerror("Error occurred", f"Debug and rerun\nerror{error}")
    return result, CME_info, objs

def on_search_click():

    # try:
    today_str = datetime.today().strftime("%Y-%m-%d")
    start_date = entry_start_date.get().strip() or today_str
    end_date = entry_end_date.get().strip() or today_str

    # test
    # start_date = '2022-09-05'
    # end_date = '2022-09-07'

    datetime.strptime(start_date, "%Y-%m-%d")
    datetime.strptime(end_date, "%Y-%m-%d")

    speed_lim = int(speed_vary_entry.get().strip() or 100)

    result, CME_info, objs = run_analysis(start_date, end_date, speed_lim)
    show_list = []
    # print(result)
    for i in range(CME_info.shape[0]):
        current_CME = {"CME ID": i}
        CME_time = CME_info.loc[i, 'event_time']
        current_CME['time'] = CME_time
        current_CME['lon'] = CME_info.loc[i, 'lon']
        current_CME['lat'] = CME_info.loc[i, 'lat']
        current_CME['rad'] = CME_info.loc[i, 'rad']
        current_CME['vel'] = CME_info.loc[i, 'vel']

        if i in result:
            current_CME["Visualizable"] = True
            inside = '' # display the objects inside the cone
            for obj in result[i]:
                inside = inside + obj + " "
                # print('inside')
                # print(inside)
            current_CME['inside'] = inside

        else:
            current_CME["Visualizable"] = False
            current_CME['inside'] = ''
        '''cases_idx = list(map(lambda x : x[1], result.keys()))

        if i in cases_idx:
            current_CME["Visualizable"] = True
            inside = ''
            for obj in SC:
                encounter = list(filter(lambda dict: dict['target'] == obj, result[parse_time(CME_time)]))
                if encounter:
                    # print(obj)
                    inside = inside + obj + " "
                    # print(inside)
            current_CME['inside'] = inside

        else:
            current_CME["Visualizable"] = False
            current_CME['inside'] = '''''

        show_list.append(current_CME)

    show_result_window(show_list, objs, result)
    # except ValueError:
        # messagebox.showerror("Error Entry", "Please make sure dates YYYY-MM-DD，velocity are numbers")


def show_result_window(results, objs, CME_result):
    win = tk.Toplevel()
    win.title("CME Results")
    win.geometry("1100x600")

    def on_closing():
        if messagebox.askokcancel("Exit Alert", "Confirm Window Close"):
            win.destroy()

    win.protocol("WM_DELETE_WINDOW", on_closing)

    tk.Label(win, text="CME List", font=("Arial", 11)).pack(pady=5)

    left_frame = tk.Frame(win)
    left_frame.pack(side="left", fill="both", expand=True)

    # Scrollbar
    tree_scroll = tk.Scrollbar(left_frame)
    tree_scroll.pack(side="right", fill="y")

    # Treeview form
    tree = ttk.Treeview(left_frame, columns=("id", "time", "lon", "lat", "rad", "vel", "visual", "inside"
                                        ), show="headings", yscrollcommand=tree_scroll.set)
    tree.pack(fill="both", expand=True)
    tree_scroll.config(command=tree.yview)

    tree.heading("id", text="ID", anchor="center")
    tree.heading("time", text="time", anchor="center")
    tree.heading("lon", text="lon", anchor="center")
    tree.heading("lat", text="lat", anchor="center")
    tree.heading("rad", text="rad", anchor="center")
    tree.heading("vel",text="vel", anchor="center")
    tree.heading("visual", text="Visualizable", anchor="center")
    tree.heading("inside", text="inside", anchor="center")


    tree.column("id", anchor="center", width=20)
    tree.column("time", anchor="center")
    tree.column("lon", anchor="center", width=40)
    tree.column("lat", anchor="center", width=40)
    tree.column("rad", anchor="center", width=40)
    tree.column("vel", anchor="center", width=40)
    tree.column("visual", anchor="center", width=100)
    tree.column("inside", anchor="center")


    for res in results:
        # print(res)
        tree.insert("", "end",
                    values=(res["CME ID"],
                            res["time"],
                            res["lon"],
                            res["lat"],
                            res["rad"],
                            res["vel"],
                            "✅" if res["Visualizable"] else "❌",
                            res["inside"])
                    )

    # detailed obj info onthe right
    right_frame = tk.Frame(win, bd=2, relief="groove", padx=10, pady=10)
    right_frame.pack(side="right", fill="both", expand=True)

    # single click to
    def on_row_click(event):
        for widget in right_frame.winfo_children():
            widget.destroy()
        selected = tree.focus()
        if not selected:
            return
        values = tree.item(selected, "values")
        cme_id = int(values[0])
        inside_objs = values[7].split()


        if inside_objs:
            detail_text = f"{values[1]}\n"
            tk.Label(right_frame, text=detail_text, font=("Arial", 12, "bold")).pack(anchor="w", pady=(0, 10))

            # spacecrafts data
            for obj_name in inside_objs:
                time_idx1 = CME_result[cme_id][obj_name][0]
                time_idx2 = CME_result[cme_id][obj_name][1]
                target = objs[obj_name]

                # detail obj text
                time_str = str(target.obstime[time_idx1])[:16]
                distance_km = target.radius[time_idx1].to(u.km)
                detail = f"time: {time_str}\ndistance: {distance_km:.2f}"

                time1 = target.obstime[time_idx1] - 6 * u.hour
                time2 = target.obstime[time_idx2] + 6 * u.hour

                row_frame = tk.Frame(right_frame)
                row_frame.pack(fill="x", pady=4)
                # detail_text += f"time: {str(target.radius[time_idx1].obstime)[:16]}\ndistance: {target.radius[time_idx1].to(u.km)}"

                # new row frames for load data
                tk.Button(row_frame, text=obj_name,
                          command=lambda name=obj_name: load_sci_data(name, str(time1), str(time2))
                          ).grid(row=0, column=0, padx=5)
                tk.Label(row_frame, text=detail, justify="left", anchor="w").grid(row=0, column=1, sticky="w")

            parameter_types = {"mag": ["Magnetic field", "nT"],
                               "vel": ["Solar wind velocity", "km/s"],
                               "dens": ["Density", ""],
                               "temp": ["Temperature", ""]}
            # CME parameters
            for type_name in parameter_types:
                time_idx = CME_result[cme_id]

                # type_data = type_dict[type_name](time_idx, objs)
                # load_CME_parameters(type_name, time_idx, objs)

                subtitle = f"{parameter_types[type_name][0]}\n{parameter_types[type_name][1]}"

                row_frame = tk.Frame(right_frame)
                row_frame.pack(fill="x", pady=4)
                tk.Button(row_frame, text=type_name,
                          command=lambda t=type_name, idx=time_idx, o=objs: load_CME_parameters(t, idx, o)
                          ).grid(row=0, column=1, padx=5)
                tk.Label(row_frame, text=subtitle, justify="left", anchor="w"
                         ).grid(row=0, column=0, sticky="w")



        '''
        # 'results' change
        cme_data = next((c for c in results if c["CME ID"] == cme_id), None)
        if not cme_data:
            return

        detail_text = f"CME ID: {cme_data['CME ID']}\n"
        detail_text += f"Time: {cme_data['Time']}\n"
        detail_text += f"Longitude: {cme_data['lon']}°\n"
        detail_text += f"Latitude: {cme_data['lat']}°\n"
        detail_text += f"Velocity: {cme_data['velocity']} km/s\n"
        detail_text += f"Angular Width: {cme_data['width']}°"

        info_label.config(text=detail_text)

        plot_button.config(state="normal", command=lambda cid=cme_id: load_sci_data(cid)) # Improve'''


    # click to open the orbital figures
    def on_row_double_click(event):
        selected = tree.focus()
        if not selected:
            return
        values = tree.item(selected, "values")
        cme_id, cme_time, cme_lon, cme_lat, cme_rad, cme_v, vis_flag, inside = values
        if vis_flag == "✅":
            plot_results(cme_id, cme_time, cme_lon, cme_rad, cme_v)
        else:
            messagebox.showinfo("Hint", f"CME {cme_id} at {cme_time} no matches")

    def plot_results(cme_id, cme_time, lon, rad, vel):
        ax, fig = plot_encounter_background()

        CME_time = Time(cme_time)

        cme_id = int(cme_id)
        for obj_name in objs:
            obj = objs[obj_name]
            if obj_name in CME_result[cme_id]:
                time1_idx = CME_result[cme_id][obj_name][0]
                time2_idx = CME_result[cme_id][obj_name][1]


            else:
                time_diff = np.abs((obj.obstime - CME_time).value)

                indices = np.where(time_diff <= 0.25)[0]
                if indices.any():
                    time1_idx = min(indices)
                    time2_idx = max(indices)
                else:
                    time1_idx = 0
                    time2_idx = 12

            body_plot(ax, obj, obj_name, time1_idx, time2_idx)

        # create matplot of the CME cone
        cme_str = str(cme_time)

        CME_cone_plot(ax, lon, rad, vel)
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

        plt.show()


    def load_sci_data(inside, *times):
        if inside in target_dict:
            target_data = target_dict[inside](times[0], times[1])
            target_data.load_data()
        '''
        if inside in load_func:
            load_func[inside](times[0], times[1])

        else:
            messagebox.showinfo("Hint", f"{inside} data currently under development")
        '''

    def load_CME_parameters(type_str, time_idx, objs):
        sci_data = type_dict[type_str](time_idx, objs)
        getattr(sci_data, f"load_{type_str}")()

    tree.bind("<Double-1>", on_row_double_click)

    tree.bind("<<TreeviewSelect>>", on_row_click)




# main window
root = tk.Tk()
root.title("CME-MOSS")
root.geometry("500x300")
root.minsize(400, 250)

# flexible layout
root.grid_rowconfigure(0, weight=1)  # top
root.grid_rowconfigure(6, weight=1)  # bottom
root.grid_columnconfigure(0, weight=1)  # left
root.grid_columnconfigure(2, weight=1)  # right

main_frame = tk.Frame(root)
main_frame.grid(row=1, column=1, sticky="nsew", padx=20, pady=20)

# Buttons and entries
tk.Label(main_frame, text="start date (YYYY-MM-DD)").grid(row=0, column=0, sticky="e", padx=5, pady=5)
entry_start_date = tk.Entry(main_frame)
entry_start_date.grid(row=0, column=1, sticky="we", padx=5, pady=5)

tk.Label(main_frame, text="end date (YYYY-MM-DD)").grid(row=1, column=0, sticky="e", padx=5, pady=5)
entry_end_date = tk.Entry(main_frame)
entry_end_date.grid(row=1, column=1, sticky="we", padx=5, pady=5)

tk.Label(main_frame, text="Speed limit").grid(row=2, column=0, sticky="e", padx=5, pady=5)
speed_vary_entry = tk.Entry(main_frame)
speed_vary_entry.grid(row=2, column=1, sticky="we", padx=5, pady=5)

search_button = tk.Button(main_frame, text="Search", command=on_search_click)
search_button.grid(row=3, column=0, padx=5, pady=10)

exit_button = tk.Button(main_frame, text="Exit", command=root.quit)
exit_button.grid(row=3, column=1, padx=5, pady=10)

# Entry auto fitting horizontally
main_frame.grid_columnconfigure(0, weight=0)
main_frame.grid_columnconfigure(1, weight=1)

# activation
# root.mainloop()
