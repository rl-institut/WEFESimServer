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
from utils import to_jsonable

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

        # Extract parameter block
        parameters = simulation_input.get("parameters", {})

        # ------------------- ECONOMICS --------------------
        # weighted average cost of capital (WACC) - might move later
        # this parameter is needed if CAPEX, OPEX fix and lifetime are included
        # set 0.06 as default
        wacc = parameters.get("wacc", 0.06)

        # -------------- ADDITIONAL FUNCTIONALITIES (OEMOF-TABULAR-PLUGINS) --------------
        # include the custom attribute parameters to be included in the model
        # this can be moved somewhere and included in a dict or something similar with all possible additional attributes
        custom_attributes = [
            "ghg_emission_factor",
            "renewable_factor",
            "land_requirement_factor",
            "water_consumption_factor",
            "indirect_water_consumption_factor",
            "land_requirement",
            "water_footprint",
            "ghg_emissions",
            "resource_cost",
            "annuity"
        ]

        # Extract user-defined MOO weights
        moo_wf = parameters.get("moo_wf", {})

        # Determine if MOO should be active
        wf_cost = moo_wf.get("wf_cost", None)
        moo = moo_wf is not None and wf_cost is not None and float(wf_cost) != 1.0

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
                skip_infer_datapackage_metadata=True,
            )
            logger.info(f"Simulation of {scenario} finished")
            results = {"df_results": calculator.df_results.to_json(orient="split", date_format="iso"), "dash_tables": to_jsonable(calculator.dash_tables)}
            simulation_output["results"] = results
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

