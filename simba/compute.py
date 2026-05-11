# file: compute.py

from datetime import datetime

import xarray as xr

from .__init__ import __version__


def _strip_bad_coords(da: xr.DataArray) -> xr.DataArray:
    keep = [name for name in da.coords if name in da.dims]
    return da.reset_coords(drop=True).assign_coords({name: da.coords[name] for name in keep})


def _compute_area_sum(
    ds: xr.Dataset,
    var: str,
) -> xr.DataArray:
    if not isinstance(ds, xr.Dataset):
        raise TypeError("input dataset must be an xarray Dataset.")
    if not isinstance(var, str):
        raise TypeError("variable name must be a string.")
    if var not in ds:
        raise ValueError(f"variable '{var}' not found in input dataset.")

    da = (ds[var] * ds["areacello"]).where(ds["mask"]).sum(dim=["i", "j"], skipna=True)
    da = _strip_bad_coords(da)

    return da


def compute_sea_ice_mass_budget(
    ds: xr.Dataset,
    mask_name: str = "mask"
) -> xr.Dataset:
    if not isinstance(ds, xr.Dataset):
        raise TypeError("input dataset must be an xarray Dataset.")

    simass_total = _compute_area_sum(ds=ds, var="simass")
    ds_simba = simass_total.to_dataset(name="simass_total")

    ds_simba["simass_total"].attrs = ds["simass"].attrs.copy()
    for key in ["cell_measures", "_FillValue", "coordinates", "original_name"]:
        ds_simba["simass_total"].attrs.pop(key, None)

    timestamp = datetime.now().strftime("%Y-%m-%dT%H:%M:%SZ")
    history_str = f"{timestamp} Computed using SIMBA (Sea Ice Mass Budget Analysis) version {__version__}."

    ds_simba["simass_total"].attrs.update({
        "units": "kg",
        "long_name": "Total Sea-Ice Mass Over Masked Region",
        "cell_methods": f"area: sum where {mask_name} time: mean",
        "comment": "Total sea ice mass multiplied by grid-cell area over the masked region.",
        "history": history_str
    })

    if "siconc" in ds:
        siarea_total = _compute_area_sum(ds=ds, var="siconc") / 1.0e8
        siarea_total = _strip_bad_coords(siarea_total)
        ds_simba["siarea_total"] = siarea_total

        ds_simba["siarea_total"].attrs = ds["siconc"].attrs.copy()
        for key in ["cell_measures", "_FillValue", "coordinates", "original_name"]:
            ds_simba["siarea_total"].attrs.pop(key, None)

        ds_simba["siarea_total"].attrs.update({
            "units": "km2",
            "long_name": "Total Sea-Ice Area Over Masked Region",
            "cell_methods": f"area: sum where {mask_name} time: mean",
            "comment": (
                "Total sea ice concentration multiplied by grid-cell area over "
                "the masked region, converted from m2 to km2."
            ),
            "history": history_str,
        })

    var_list = [var for var in ds.data_vars if var.startswith("sidmass")]
    for var in var_list:
        ds_simba[var] = _strip_bad_coords(_compute_area_sum(ds=ds, var=var))

        ds_simba[var].attrs = ds[var].attrs.copy()
        for key in ["cell_measures", "_FillValue", "coordinates", "original_name"]:
            ds_simba[var].attrs.pop(key, None)

        ds_simba[var].attrs.update({
            "units": "kg s-1",
            "long_name": f"Total {ds[var].attrs.get('long_name', var)} Over Masked Region",
            "cell_methods": f"area: sum where {mask_name} time: mean",
            "comment": f"{ds[var].attrs.get('comment', var).replace('divided by grid-cell area', 'multiplied by grid-cell area')}",
            "history": history_str
        })

    ds_simba = ds_simba.reset_coords(drop=True)
    ds_simba = ds_simba.drop_vars("type", errors="ignore")

    return ds_simba
