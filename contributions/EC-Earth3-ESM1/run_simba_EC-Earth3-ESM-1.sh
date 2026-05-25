#!/bin/bash

set -euo pipefail
# ================================================================
# run_simba_EC-Earth3-ESM-1.sh
#
# Description: Run SeaIceMassBudgetAnalysis (SIMBA) to perform a
# sea ice mass budget analysis from the EC-Earth3-ESM-1 simulations.
#
# SIMBA will be executed in the current process.
#
# Created By: Ollie Tooth (oliver.tooth@noc.ac.uk) 
# ================================================================

# ==== Input arguments to SIMBA ==== #
# Define config file & log file paths:
config_file=./configs/EC-Earth3-ESM1_esm-up2p0_config.toml
log_file=./logs/EC-Earth3-ESM1_v1_simba.log

# Run multiple pipelines:
l_multi=false

# Define Experiment IDs [l_multi=true] -> esm-up2p0-gwl
# exp_ids=("esm-up2p0-gwl1p5" "esm-up2p0-gwl2p0" "esm-up2p0-gwl3p0" "esm-up2p0-gwl4p0" "esm-up2p0-gwl5p0" "esm-up2p0-gwl6p0")

# Define Experiment IDs [l_multi=true] -> esm-up2p0-gwl-dn
# exp_ids=("esm-up2p0-gwl1p5-50y-dn2p0" "esm-up2p0-gwl2p0-200y-dn2p0" "esm-up2p0-gwl2p0-50y-dn1p0" "esm-up2p0-gwl2p0-50y-dn2p0" "esm-up2p0-gwl3p0-50y-dn2p0" "esm-up2p0-gwl4p0-200y-dn2p0" "esm-up2p0-gwl4p0-50y-dn1p0" "esm-up2p0-gwl4p0-50y-dn2p0")

# ================================== #

if [ "$l_multi" = false ]; then
    # -- Run SIMBA CLI -- #
    simba run $config_file --log $log_file

else
    # Iterate over all experiment IDs...
    for exp_id in "${exp_ids[@]}"; do
        echo "Running ==> $exp_id"
        # -- Updating Experiment IDs in config.toml -- #
        sed -i "s|esm-[^/_]*|$exp_id|g" $config_file
    
        # -- Run SIMBA CLI -- #
        simba run $config_file --log $log_file
        echo "Completed ==> $exp_id" 
    done
fi
