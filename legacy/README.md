Legacy flat-file implementation (pre-refactor), retained for scientific
traceability. These modules are no longer imported by the application.

Mapping to the new package
--------------------------

legacy file                 new location(s)
--------------------------- ----------------------------------------------------
cone_search_HEEQ.py         cmemoss/data/donki.py
                            cmemoss/data/ephemeris.py
                            cmemoss/physics/cone.py
                            cmemoss/physics/propagation.py
                            cmemoss/analysis/encounter.py
                            cmemoss/export/report.py

in_situ_data.py             cmemoss/data/insitu/{loaders,service}.py
                            cmemoss/preprocess/timeseries.py
                            cmemoss/visualization/timeseries_plot.py

data_visualization.py       cmemoss/visualization/{styles,encounter_plot}.py

gui.py                      cmemoss/app/{gui,controller,project_config}.py
                            cmemoss/cli.py

Removed third-party dependencies: scipy, pandas, python-dateutil (direct use),
BeautifulSoup. pyspedas is now an optional extra ("cmemoss[insitu]").

See docs/MIGRATION_SCIENCE.md for changes that can numerically affect results.
