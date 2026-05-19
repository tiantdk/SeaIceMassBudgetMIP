"""
utils.py

Description: Utility functions for SIMBA package.

Created By: Ollie Tooth (oliver.tooth@noc.ac.uk)
"""

# -- Import dependencies -- #
import tomllib
from pathlib import Path
from typing import Literal, Optional

import cftime
import numpy as np
import xarray as xr
from pydantic import BaseModel, Field


# Define Pydantic sub-models for each section of config .toml file:
class InputVariable(BaseModel):
    """
    SIMBA Input Variable Configuration Model.
    """
    # Define variable name & filepath for each SIMBA input variable:
    name: str
    filepath: str


class InputConfig(BaseModel):
    """
    SIMBA Input Configuration Model.
    """
    # Define dimensions of all SIMBA input variables:
    dimensions: dict[str, str] = Field(default_factory=dict)

    # Define data directory for SIMBA input files:
    data_dir: str | None = None

    # Define sub-models for all SIMBA input variables:
    mask: InputVariable
    areacello: InputVariable
    siconc: InputVariable | None = None
    sivol: InputVariable | None = None
    simass: InputVariable | None = None
    sidmassth: InputVariable | None = None
    sidmassdyn: InputVariable | None = None
    sidmassgrowthwat: InputVariable | None = None
    sidmassgrowthbot: InputVariable | None = None
    sidmasssi: InputVariable | None = None
    sidmassevapsubl: InputVariable | None = None
    sidmassmelttop: InputVariable | None = None
    sidmassmeltbot: InputVariable | None = None
    sidmasslat: InputVariable | None = None


class OutputConfig(BaseModel):
    """
    SIMBA Output Configuration Model.
    """
    # Define SIMBA output file:
    output_dir: str
    output_name: str
    date_format: Literal["Y", "M", "D"]


class AppConfig(BaseModel):
    """
    SIMBA CLI Configuration Model.
    """
    inputs: InputConfig
    outputs: OutputConfig


def load_config(args: dict) -> dict:
    """
    Load SIMBA configuration .toml file.

    Uses Pydantic models to parse and validate
    configuration .toml files.

    Parameters:
    -----------
    args : dict
        Command line arguments.

    Returns:
    --------
    dict
        Configuration parameters.
    """
    # Open config .toml file:
    path = Path(args['config_file'])
    with open(path, "rb") as f:
        data = tomllib.load(f)

    # Parse and validate config data using Pydantic models:
    config = AppConfig(**data)
    # Convert config params to dict:
    d_config = config.model_dump(mode="json",
                                 exclude_none=True
                                )

    return d_config


def get_output_filename(
    ds_out: xr.Dataset,
    output_dir: str,
    output_name: str,
    date_format: str
     ) -> str:
    """
    Define SIMBA output filename.

    Parameters:
    -----------
    ds_out : xr.Dataset
        Output xarray Dataset.
    output_dir : str
        Directory to save output file.
    output_name : str
        Prefix of output file name.
    date_format : str
        Date format for datetime limits in output filename.
        Options are 'Y' (YYYY), 'M' (YYYY-MM) or 'D' (YYYY-MM-DD).
    """
    # Validate inputs:
    if not isinstance(ds_out, xr.Dataset):
        raise TypeError("ds_out must be an xr.Dataset.")
    if not isinstance(output_dir, str):
        raise TypeError("output_dir must be a string.")
    if not isinstance(output_name, str):
        raise TypeError("output_name must be a string.")

    # Define time-limits of output dataset:
    time_limits = ds_out['time'].values[[0, -1]]

    # Create date string from CFTime datetime objects:
    if isinstance(time_limits[0], cftime.datetime):
        if date_format == "Y":
            fmt = "%Y"
        elif date_format == "M":
            fmt = "%Y-%m"
        elif date_format == "D":
            fmt = "%Y-%m-%d"
        else:
            raise ValueError(f"Invalid date_format: '{date_format}'. Options are 'Y', 'M', 'D'.")
        date_str = f"{time_limits[0].strftime(fmt)}-{time_limits[1].strftime(fmt)}"

    # Create date string from numpy datetime64:
    elif isinstance(time_limits[0], np.datetime64):
        date_str = f"{np.datetime_as_string(time_limits[0], unit=date_format)}-{np.datetime_as_string(time_limits[1], unit=date_format)}"
    else:
        raise TypeError(f"Invalid type ({type(time_limits[0])}) for dates. Expected cftime.datetime or np.datetime64.")

    # Define output filename:
    output_filename = f"{output_dir}/{output_name}_{date_str}.nc"

    return output_filename
