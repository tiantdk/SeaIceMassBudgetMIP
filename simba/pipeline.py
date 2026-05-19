"""
pipeline.py

Description: I/O functions for Sea Ice Mass Budget Analysis package.

Created By: Ollie Tooth (oliver.tooth@noc.ac.uk)
"""

# -- Import Dependencies -- #
import glob
import logging

import dask
import xarray as xr

from simba.compute import compute_sea_ice_mass_budget
from simba.utils import get_output_filename, load_config


# -- Define Utility Functions -- #
def _get_variable_filepaths(
    config : dict,
    ) -> dict[str, str]:
    """
    Create dictionary of variable filepaths from config.

    Parameters:
    -----------
    config : dict
        Configuration parameters, including output file paths.

    Returns:
    --------
    dict[str, str]
        Dictionary of variable filepaths.
    """
    # -- Verify Input -- #
    if not isinstance(config, dict):
        raise TypeError("config must be a dictionary.")

    # -- Define variable filepaths from config -- #
    inputs = config["inputs"]
    var_list = [var for var in inputs if var not in ['dimensions', 'data_dir']]

    # Replace input pattern in config filepaths:
    variable_filepaths = {}
    for var in var_list:
        filepath = inputs[var].get("filepath", None)
        if filepath is not None:
            if '{data_dir}' in filepath:
                filepath = filepath.replace('{data_dir}', inputs['data_dir'])
        else:
            raise ValueError(f"Missing filepath for variable '{var}' in table [inputs.{var}] of config .toml file.")

        variable_filepaths[var] = filepath

    return variable_filepaths


def _get_variable_names(
    config : dict,
    ) -> dict[str, str]:
    """
    Create dictionary of variable names from config.

    Parameters:
    -----------
    config : dict
        Configuration parameters, including output file paths.

    Returns:
    --------
    dict[str, str]
        Dictionary of variable names.
    """
    # -- Verify Input -- #
    if not isinstance(config, dict):
        raise TypeError("config must be a dictionary.")

    # -- Define variable names from config -- #
    inputs = config["inputs"]
    var_list = [var for var in inputs if var not in ['dimensions', 'data_dir']]

    variable_names = {}
    for var in var_list:
        name = inputs[var].get("name", None)
        if name is not None:
            variable_names[var] = name
        else:
            raise ValueError(f"Missing name for variable '{var}' in table [inputs.{var}] of config .toml file.")

    return variable_names


def _open_variable_da(
    filepath: str,
    variable: str,
    rename: str
    ) -> xr.DataArray:
    """
    Open input variable DataArray from a netCDF file(s).

    Parameters:
    -----------
    filepath : str
        Filepath pattern to input variable netCDF file(s).
    variable : str
        Name of variable to load from the dataset.
    rename : str
        Standard name to assign to the DataArray.

    Returns:
    --------
    xr.DataArray
        Input variable DataArray.
    """
    # -- Validate Inputs -- #
    if not isinstance(filepath, str):
        raise TypeError("filepath must be a string.")
    if not isinstance(variable, str):
        raise TypeError("variable must be a string.")
    if not isinstance(rename, str):
        raise TypeError("rename must be a string.")

    filepaths = glob.glob(filepath)
    if len(filepaths) == 0:
        raise FileNotFoundError(f"No files found matching filepath: {filepath}")

    # Define CFDatetimeCoder to decode time coords:
    coder = xr.coders.CFDatetimeCoder(time_unit="s")

    # -- Open input variable dataset with specified variable only -- #
    if len(filepaths) == 1:
        try:
            da_var = xr.open_dataset(filepaths[0], decode_times=coder, engine="netcdf4")[variable]

        except FileNotFoundError as e:
            raise FileNotFoundError(f"Failed to open netCDF file: {filepaths[0]}") from e
    else:
        try:           
            da_var = xr.open_mfdataset(filepaths,
                                       data_vars="minimal",
                                       compat="no_conflicts",
                                       decode_times=coder,
                                       parallel=False,
                                       engine="netcdf4",
                                       preprocess=lambda ds: ds[variable]
                                       )[variable]
        except FileNotFoundError as e:
            raise FileNotFoundError(f"Failed to open netCDF files: {filepaths}") from e
        
    # -- Rename variable to standard name -- #
    da_var.name = rename

    return da_var


def open_sea_ice_datasets(
    config: dict,
    ) -> xr.Dataset:
    """
    Create dataset of sea ice mass budget variables from a collection of netCDF files.

    Parameters:
    -----------
    config : dict
        Configuration parameters, including sea ice model output file paths.

    Returns:
    --------
    xr.Dataset
        Dataset containing sea ice mass budget variables.
    """
    # -- Verify Input -- #
    if not isinstance(config, dict):
        raise TypeError("config must be a dictionary.")

    # -- Define variable filepaths from config -- #
    filepaths = _get_variable_filepaths(config=config)
    variables = _get_variable_names(config=config)

    # -- Open mask as xarray.Dataset -- #
    ds_simba = _open_variable_da(filepath=filepaths["mask"], variable=variables["mask"], rename="mask").to_dataset(name="mask")
    logging.info("--> Completed: Opened 'mask' variable.")

    # -- Open & merge CMORISED variables into single sea ice mass budget dataset -- #
    logging.info("In Progress: Creating sea ice mass budget dataset from variables.")
    var_list = [var for var in variables if var != "mask"]
    for var in var_list:
        try:
            # Appending each CMORISED variable to ds_simba Dataset:
            ds_simba[var] = _open_variable_da(filepath=filepaths[var], variable=variables[var], rename=var)
        except Exception as e:
            raise RuntimeError(f"Failed to merge variable {var} into sea ice mass budget dataset") from e
    
        logging.info(f"--> Completed: Opened '{var}' variable.")

    # Update dimensions to CMORISED standard names:
    update_dims = config['inputs']['dimensions']
    if update_dims is not None:
        try:
            ds_simba = ds_simba.rename(update_dims)
        except Exception as e:
            raise RuntimeError("Failed to rename dimensions in sea ice mass budget dataset") from e

    logging.info("--> Completed: Created sea ice mass budget dataset from variables.")

    return ds_simba


def save_simba_diagnostics(
    ds_out: xr.Dataset,
    output_dir: str,
    output_name: str,
    date_format: str,
    ) -> None:
    """
    Save Sea Ice Mass Budget Analysis outputs to netCDF file.

    Parameters:
    -----------
    ds_out : xr.Dataset
        NEMO Pipeline output dataset.
    output_dir : str
        Directory to save output file.
    output_name : str
        Name of output file (without extension).
    date_format : str
        Date format for time dimension in output filename.
        Options are 'Y' (YYYY), 'M' (YYYY-MM) or 'D' (YYYY-MM-DD).

    Returns:
    --------
    str
        Filepath to saved NEMO Pipeline output file.
    """
    # Validate inputs:
    if not isinstance(ds_out, xr.Dataset):
        raise TypeError("ds_out must be an xr.Dataset.")
    if not isinstance(output_dir, str):
        raise TypeError("output_dir must be a string.")
    if not isinstance(output_name, str):
        raise TypeError("output_name must be a string.")

    # Define output filepath:
    output_filepath = get_output_filename(
        ds_out=ds_out,
        output_dir=output_dir,
        output_name=output_name,
        date_format=date_format
        )

    # Use single chunk along time dimension:
    ds_out = ds_out.chunk({"time": ds_out["time"].size})

    # Write Sea Ice Mass Budget Analysis outputs to file:
    with dask.config.set(scheduler="synchronous"):
        ds_out.to_netcdf(path=output_filepath, unlimited_dims="time", mode="w")

    return output_filepath


def run_simba_pipeline(
    args: dict
    ) -> None:
    """
    Run Sea Ice Mass Budget Analysis using specified config .ini file.

    Pipeline Steps:
    1. Read & validate config .ini file.
    2. Open mask, areacello & sea ice mass budget diagnostic datasets.
    3. Create combined sea ice diagnostics datasets.
    4. Calculate regionally integrated Sea Ice Mass Budget terms.
    5. Save regionally integrated Sea Ice Mass Budget terms to netCDF file.

    Parameters:
    -----------
    args : dict
        Command line arguments.
    """
    # === Inputs === #
    logging.info("==== Inputs ====")
    # Load config .toml file:
    config = load_config(args=args)
    logging.info(f"Completed: Read & validated config file -> {args['config_file']}")

    # Open NEMO model domain & grid datasets:
    logging.info("In Progress: Reading sea ice mass budget variables...")
    ds_simba = open_sea_ice_datasets(config=config)

    # === Diagnostics === #
    logging.info("==== Sea Ice Mass Budget Calculation ====")
    logging.info("In Progress: Calculating Regional Sea Ice Mass Budget...")
    mask_name = config['inputs']['mask']['name']
    ds_diag = compute_sea_ice_mass_budget(ds=ds_simba, mask_name=mask_name)
    logging.info("Completed: Calculated Regional Sea Ice Mass Budget.")

    # === Outputs === #
    logging.info("==== Outputs ====")
    logging.info("In Progress: Saving Sea Ice Mass Budget Analysis outputs to netCDF file...")

    # Write Sea Ice Mass Budget Analysis output dataset to file:
    output_filepath = save_simba_diagnostics(
        ds_out=ds_diag.squeeze(),
        output_dir=config['outputs']['output_dir'],
        output_name=config['outputs']['output_name'],
        date_format=config['outputs']['date_format']
        )
    logging.info(f"Completed: Saved Sea Ice Mass Budget Analysis outputs to file -> {output_filepath}")

    # Close all files associated with NEMODataTree:
    ds_simba.close()
    logging.info("Completed: Succesfully closed all netcdf files.")


def describe_simba_pipeline(
    args: dict
    ) -> str:
    """
    Describe & validate Sea Ice Mass Budget Analysis using config.

    Parameters:
    -----------
    args : dict
        Command line arguments.

    Returns:
    --------
    str
        Description of Sea Ice Mass Budget Analysis.
    """
    logging.info("==== Inputs ====")
    # Read config file:
    config = load_config(args=args)
    logging.info(f"Read & validated config file --> {args['config_file']}")

    # Read sea ice variables 
    logging.info("Read sea ice mass budget variables:")
    filepaths = _get_variable_filepaths(config=config)
    variables = _get_variable_names(config=config)
    for var in variables:
        logging.info(f"* Open '{var}' variable from file --> {filepaths[var]}")

    logging.info("==== Sea Ice Mass Budget Calculation ====")
    logging.info("Calculate Regional Sea Ice Mass Budget --> compute_sea_ice_mass_budget(ds)")

    logging.info("==== Outputs ====")
    logging.info("Save Sea Ice Mass Budget Analysis outputs to netCDF file:")
    # Parse config chunking str into dict:
    logging.info(f"* Output Directory = {config['outputs']['output_dir']}")
    # Determine output file name:
    logging.info(f"* Output File Name = {config['outputs']['output_name']}_YYYY-MM_YYYY-MM.nc")