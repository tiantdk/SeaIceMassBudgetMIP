"""
compute.py

Description: Functions for Sea Ice Mass Budget Analysis calculations.

Created By: Ollie Tooth (oliver.tooth@noc.ac.uk)
"""

# -- Import Dependencies -- #
from datetime import datetime

import xarray as xr

from .__init__ import __version__


def _compute_area_sum(
        ds: xr.Dataset,
        var: str,
    ) -> xr.DataArray:
    """
    Compute masked sum of the product of a variable and horizontal grid cell area
    (`areacello`).

    Horizontal dimensions are assumed to be named 'i' and 'j'
     
    `mask` is applied as a boolean mask, where True = included | False = excluded.

    Parameters:
    -----------
    ds : xr.Dataset
        Input dataset containing variable, `mask`, and `areacello`.
    var : str
        Name of variable to sum.

    Returns:
    --------
    xr.DataArray
        Masked area-weighted sum of variable over (i, j) dimensions.
    """
    # -- Valid Inputs -- #
    if not isinstance(ds, xr.Dataset):
        raise TypeError("input dataset must be an xarray Dataset.")
    if not isinstance(var, str):
        raise TypeError("variable name must be a string.")
    if var not in ds:
        raise ValueError(f"variable '{var}' not found in input dataset.")

    # -- Determine Sea Ice Concentration Units -- #
    if var == "siconc":
        if ds[var].max() > 1:
            # Transform Sea Ice Concentration [0-100%] -> [0-1]:
            ds[var] = ds[var] / 100

    # -- Compute Masked Area-Weighted Sum -- #
    da = (ds[var] * ds["areacello"]).where(ds["mask"]).sum(dim=["i", "j"], skipna=True)

    return da


def compute_sea_ice_mass_budget(
        ds: xr.Dataset,
        mask_name: str = "mask"
    ) -> xr.Dataset:
    """
    Compute sea ice mass budget from input dataset.

    Parameters:
    -----------
    ds : xr.Dataset
        Input dataset containing sea ice mass budget variables.
    mask_name : str, optional
        Original name of mask variable.

    Returns:
    --------
    ds_simba : xr.Dataset
        Dataset containing sea ice mass budget variables with renamed dimensions.
    """
    # -- Valid Inputs -- #
    if not isinstance(ds, xr.Dataset):
        raise TypeError("input dataset must be an xarray Dataset.")

    # === Compute Sea Ice Mass Budget == #
    # --> Total Sea Ice Mass <-- #
    simass_total = _compute_area_sum(ds=ds, var="simass")
    # Define Sea Ice Mass Budget output dataset:
    ds_simba = simass_total.to_dataset(name="simass_total")

    # Add CF-compliant attributes:
    ds_simba["simass_total"].attrs = ds["simass"].attrs.copy()
    # Drop legacy attributes:
    for key in ["cell_measures", "_FillValue", "coordinates", "original_name"]:
        ds_simba["simass_total"].attrs.pop(key, None)

    # Define history CF-attribute:
    timestamp = datetime.now().strftime("%Y-%m-%dT%H:%M:%SZ")
    history_str = f"{timestamp} Computed using SIMBA (Sea Ice Mass Budget Analysis) version {__version__}."

    # Update CF attributes:
    ds_simba["simass_total"].attrs.update({
        "units": "kg",
        "long_name": "Total Sea-Ice Mass Over Masked Region",
        "cell_methods": f"area: sum where {mask_name} time: mean",
        "comment": "Total sea ice mass multiplied by grid-cell area over the masked region.",
        "history": history_str
    })

    # --> Total Sea Ice Area <-- #
    if "siconc" in ds.data_vars:
        # Compute masked area-weighted sum of sea ice concentration [m2 -> km2]:
        ds_simba["siarea_total"] = _compute_area_sum(ds=ds, var="siconc") / 1E6

        # Add CF-compliant attributes:
        ds_simba["siarea_total"].attrs = ds["siconc"].attrs.copy()
        # Drop legacy attributes:
        for key in ["cell_measures", "_FillValue", "coordinates", "original_name"]:
            ds_simba["siarea_total"].attrs.pop(key, None)
        # Update CF attributes:
        ds_simba["siarea_total"].attrs.update({
            "units": "km2",
            "long_name": "Total Sea-Ice Area Over Masked Region",
            "cell_methods": f"area: sum where {mask_name} time: mean",
            "comment": "Total sea ice concentration multiplied by grid-cell area over the masked region.",
            "history": history_str
        })

    # --> Total Sea Ice Volume <-- #
    if "sivol" in ds.data_vars:
        # Compute masked area-weighted sum of sea ice thickness [m3]:
        ds_simba["sivol_total"] = _compute_area_sum(ds=ds, var="sivol")

        # Add CF-compliant attributes:
        ds_simba["sivol_total"].attrs = ds["sivol"].attrs.copy()
        # Drop legacy attributes:
        for key in ["cell_measures", "_FillValue", "coordinates", "original_name"]:
            ds_simba["sivol_total"].attrs.pop(key, None)
        # Update CF attributes:
        ds_simba["sivol_total"].attrs.update({
            "units": "m3",
            "long_name": "Total Sea-Ice Volume Within Masked Region",
            "cell_methods": f"area: sum where {mask_name} time: mean",
            "comment": "Total sea ice volume (thickness) multiplied by grid-cell area over the masked region.",
            "history": history_str
        })

    # --> Total Sea Ice Mass Change by Component <-- #
    var_list = [var for var in ds.data_vars if var.startswith("sidmass")]
    for var in var_list:
        # Compute masked area-weighted sum of variable:
        ds_simba[var] = _compute_area_sum(ds=ds, var=var)

        # Add CF-compliant attributes:
        ds_simba[var].attrs = ds[var].attrs.copy()
        # Drop legacy attributes:
        for key in ["cell_measures", "_FillValue", "coordinates", "original_name"]:
            ds_simba[var].attrs.pop(key, None)
        # Update CF attributes:
        ds_simba[var].attrs.update({
            "units": "kg s-1",
            "long_name": f"Total {ds[var].attrs.get('long_name', var)} Over Masked Region",
            "cell_methods": f"area: sum where {mask_name} time: mean",
            "comment": f"{ds[var].attrs.get('comment', var).replace('divided by grid-cell area', 'multiplied by grid-cell area')}",
            "history": history_str
        })

    return ds_simba
