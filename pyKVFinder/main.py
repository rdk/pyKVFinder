import os
import sys
import time
import logging
from datetime import datetime

import numpy as np

from .argparser import argparser
from .utils import read_vdw, read_pdb, write_results
from .grid import detect, spatial, constitutional, export

def run():
    # Start time
    start_time = time.time()

    # Load pyKVFinder argument parser
    parser = argparser()

    # Parse command-line arguments
    args = parser.parse_args()

    # Print message to stdout
    print (f"[PID {os.getpid()}] Running pyKVFinder for: {args.pdb}")

    # Start logging
    logging.basicConfig(filename=f"{os.path.join(args.output_directory, 'KVFinder.log')}", level=logging.INFO, format='%(message)s')
    logging.info("=" * 80)
    logging.info(f"Date: {datetime.now().strftime('%a %d %B, %Y')}\nTime: {datetime.now().strftime('%H:%M:%S')}\n")
    logging.info(f"[ Running pyKVFinder for: {args.pdb} ]")
    logging.info(f"> vdW radii file: {args.dictionary}")

    if args.verbose:
        print("> Loading atomic dictionary file")
    vdw = read_vdw(args.dictionary)

    if args.verbose:
        print("> Reading PDB coordinates")
    pdb, xyzr = read_pdb(args.pdb, vdw)

    if args.ligand:
        if args.verbose:
            print("> Reading ligand coordinates")
        ligand, lxyzr = read_pdb(args.ligand, vdw)

    if args.verbose: 
        print("> Calculating 3D grid dimensions")
    P1 = np.min(xyzr[:, 0:3], axis=0) - args.probe_out 
    xmax, ymax, zmax = np.max(xyzr[:, 0:3], axis=0) + args.probe_out 
    P2 = np.array([xmax, P1[1], P1[2]])
    P3 = np.array([P1[0], ymax, P1[2]])
    P4 = np.array([P1[0], P1[1], zmax])

    # Calculate distance between points
    norm1 = np.linalg.norm(P2-P1)
    norm2 = np.linalg.norm(P3-P1)
    norm3 = np.linalg.norm(P4-P1)

    # Calculate grid dimensions
    nx = int ( norm1 / args.step ) + 1
    ny = int ( norm2 / args.step ) + 1
    nz = int ( norm3 / args.step ) + 1
    if args.verbose:
        print(f"Dimensions: (nx:{nx}, ny:{ny}, nz:{nz})")

    # Calculate sin and cos of angles a and b
    sincos = np.array([
        ( P4[1] - P1[1] ) / norm3, # sin a
        ( P3[1] - P1[1] ) / norm2, # cos a
        ( P2[2] - P1[2] ) / norm1, # sin b
        ( P2[0] - P1[0] ) / norm1  # cos b
    ])
    if args.verbose:
        print(f"sina: {sincos[0]}\tsinb: {sincos[2]}")
        print(f"cosa: {sincos[1]}\tcosb: {sincos[3]}")

    # Logging parameters
    logging.info(f"> Step: {args.step} \u00c5")
    logging.info(f"> Probe In: {args.probe_in} \u00c5")
    logging.info(f"> Probe Out: {args.probe_out} \u00c5")
    logging.info(f"> Voxel volume: {args.step * args.step * args.step} \u00c5\u00b3")
    logging.info(f"> Dimensions: (nx:{nx}, ny:{ny}, nz:{nz})")
    logging.info(f"> sina: {sincos[0]}\tcosa: {sincos[1]}")
    logging.info(f"> sinb: {sincos[2]}\tcosb: {sincos[3]}")

    if args.surface == 'SES':
        args.surface = True
        if args.verbose:
            print ("> Surface representation: Solvent Excluded Surface (SES)") 
    else:
        args.surface = False
        if args.verbose:
            print ("> Surface representation: Solvent Accessible Surface (SAS)")

    # Cavity detection
    ncav, cavities = detect(nx, ny, nz, xyzr, P1, sincos, args.step, args.probe_in, args.probe_out, args.removal_distance, args.volume_cutoff, args.surface, 15, args.verbose)

    # No cavities were found
    if (not ncav):
        return True

    # Spatial characterization
    surface, volume, area = spatial(cavities, nx, ny, nz, ncav, args.step, 15, args.verbose)

    # Constitutional characterization
    ignore_backbone = False
    residues = constitutional(cavities, pdb, xyzr, P1, sincos, ncav, args.step, args.probe_in, ignore_backbone, 15, args.verbose)

    # Export cavities
    output = "tests/cavity.pdb"
    export(output, cavities, surface, P1, sincos, ncav, args.step, 15)

    # Write results
    write_results("tests/results.toml", args.pdb, args.ligand, output, volume, area, residues, args.step)

    # Elapsed time
    elapsed_time = time.time() - start_time
    print(f"[ \033[1mElapsed time:\033[0m {elapsed_time:.4f} ]")
    logging.info(f"[ Elapsed time (s): {elapsed_time:.4f} ]\n")

    return True
