import os
import time
import traceback
import json
from copy import deepcopy
from celery import Celery
from celery.utils.log import get_task_logger
import tempfile
import shutil
from pathlib import Path

from oemof_tabular_plugins.datapackage import rebuild_single_json
from oemof_tabular_plugins.script import compute_scenario
from oemof_tabular_plugins.wefe import WEFE_TYPEMAP as TYPEMAP

SIMULATION_VERSION = os.environ.get("SIMULATION_VERSION", "no_version")

logger = get_task_logger(__name__)
CELERY_BROKER_URL = (os.environ.get("CELERY_BROKER_URL", "redis://localhost:6379"),)
CELERY_RESULT_BACKEND = os.environ.get(
    "CELERY_RESULT_BACKEND", "redis://localhost:6379"
)

CELERY_TASK_NAME = os.environ.get("CELERY_TASK_NAME", "dev")

app = Celery(CELERY_TASK_NAME, broker=CELERY_BROKER_URL, backend=CELERY_RESULT_BACKEND)


def __run_simulation(simulation_input):
    logger.info("Start new simulation")
    simulation_output = {"SERVER" : CELERY_TASK_NAME, "VERSION": SIMULATION_VERSION}

    with tempfile.TemporaryDirectory(prefix="dp_") as td:
        temp_path = Path(td)
        dp_path = rebuild_single_json(simulation_input, temp_path)
        logger.debug("Converted datapackage in JSON format back to datapackage")

        # TODO set this a default pass those parameters in the json file
        # Regionalized Characterisation Factor for Available water remaining (AWARE) - might move later;
        # this parameter is needed to calculate the regionalized water scarcity footprint in moo.
        # weighted average cost of capital (WACC) - might move later
        # this parameter is needed if CAPEX, OPEX fix and lifetime are included
        wacc = 0.06

        # -------------- ADDITIONAL FUNCTIONALITIES (OEMOF-TABULAR-PLUGINS) --------------
        # include the custom attribute parameters to be included in the model
        # this can be moved somewhere and included in a dict or something similar with all possible additional attributes
        custom_attributes = [
            "ghg_emission_factor",
            "renewable_factor",
            "land_requirement_factor",
            "water_consumption_factor",
            "indirect_water_consumption_factor"
            "land_requirement",
            "water_footprint",
            "ghg_emissions",
            "resource_cost",
            "annuity"
        ]
        # set whether the multi-objective optimization should be performed
        moo = False

        # MOO weight factors
        moo_wf = {
            "wf_cost": 15,
            "wf_ghg": 1,
            "wf_lr": 343434,
            "wf_wf": 0,
        }

        # -------------- RUNNING THE SCENARIOS --------------
        scenario = dp_path.name
        # set paths for scenario and result directories
        results_path = dp_path / "results"
        results_path.mkdir()
        try:
            calculator = compute_scenario(
                dp_path,
                results_path,
                wacc,
                scenario_name=scenario,
                custom_attributes=custom_attributes,
                typemap=TYPEMAP,
                moo=moo,
                moo_wf=moo_wf,
                dash_app=False,
            )
            logger.info(f"Simulation of {scenario} finished")
            df = calculator.df_results

            simulation_output["results"] = df.to_json()
        except Exception as e:
            logger.error(
                "An exception occured in the simulation task: {}".format(
                    traceback.format_exc()
                )
            )
            simulation_output.update(dict(
                ERROR="{}".format(traceback.format_exc()),
                INPUT_JSON=simulation_input,
            ))

    return json.dumps(simulation_output)

@app.task(name=f"{CELERY_TASK_NAME}.run_simulation")
def run_simulation(simulation_input: dict,) -> dict:
   return __run_simulation(simulation_input)

@app.task(name=f"{CELERY_TASK_NAME}.get_version")
def get_version() -> str:
   return SIMULATION_VERSION

