#!/usr/bin/env python3
# -------------------------------------------------------------------------------
# MIT License
#
# Copyright (c) 2023 - 2024 Advanced Micro Devices, Inc. All Rights Reserved.
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.
# -------------------------------------------------------------------------------
# Utility to join sqlite data collections from multiple compute nodes using MPI.

import argparse
import logging
import os
import pandas as pd
import platform
import sqlite3
import sys
import time
from mpi4py import MPI


def getSQLTableNames(dbfile):
    """Get table names from sqlite3 input file"""
    with sqlite3.connect(dbfile) as dbIn:
        cursor = dbIn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tables = cursor.fetchall()
        names = [table[0] for table in tables]
        return(names)

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--indir", type=str, help="input directory where local omnistat .db file is located", default="/tmp")
    parser.add_argument("--outfile", type=str, help="name of output sqlite to append", required=True)
    args = parser.parse_args()

    logging.basicConfig(format="%(message)s", level=logging.INFO, stream=sys.stdout)

    comm = MPI.COMM_WORLD
    localRank = comm.Get_rank()
    numRanks = comm.Get_size()

    # print("Hello from %i of %i tasks" % (localRank,numRanks))

    hostname = platform.node().split(".", 1)[0]
    infile = os.path.join(args.indir,"omnistat." + hostname + ".db")


    if not os.path.exists(infile):
        logging.error("Error: Cannot access infile -> %s" % infile)
        comm.Abort(1)

    if os.path.exists(args.outfile):
        logging.error("Cowardly refusing to overwrite existing outfile = %s" % args.outfile)
        comm.Abort(1)

    # --
    # Simple data aggration variant: 
    #   - Step 1: rank0 first reads local telemetry data and writes to sqlite file
    #   - Step 2: all other ranks read local telemetry data and send to rank 0 who appends to sqlite file
    # --

    comm.Barrier()
    start_time = time.perf_counter()

    if localRank == 0:
        names = getSQLTableNames(infile)
        with sqlite3.connect(infile) as dbIn:
            with sqlite3.connect(args.outfile) as dbOut:
                for metric in names:
                    data = pd.read_sql_query("SELECT * FROM %s" % metric,dbIn)
                    data.to_sql(metric, dbOut, if_exists="append", index=False)
        logging.info("[%5i] Just wrote local telemetry data to aggregate file -> %s" % (localRank,args.outfile))


    comm.Barrier()


    # simple variant: serialize read of data from all ranks and append to desired output file
    for rank in range(1,numRanks):

        # gather metric names available
        if rank == localRank:
            logging.info("[%5i] Reading %s on host %s" % (localRank,infile,hostname))
            with sqlite3.connect(infile) as dbIn:
                cursor = dbIn.cursor()
                cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
                tables = cursor.fetchall()
                namesIn = [table[0] for table in tables]

                logging.debug("Sending telemetry data from %i -> %i" % (localRank,0))
                comm.send(namesIn, dest=0, tag=1)
                tag = 10*rank
                for metric in namesIn:
                    data = pd.read_sql_query("SELECT * FROM %s" % metric,dbIn)
                    comm.send(data,dest=0,tag=tag)
                    tag += 1

        if localRank == 0:
            # receive list of metrics
            logging.debug("Expecting receive from rank %i" % rank)
            metrics = comm.recv(source=rank, tag=1)

            # receive each metric and append to sqlite3 file
            tag = 10*rank
            with sqlite3.connect(args.outfile) as dbOut:
                for metric in metrics:
                    data = comm.recv(source=rank,tag=tag)
                    logging.debug("Just received %s from index %i"  % (metric,rank) )
                    tag += 1

                    data.to_sql(metric, dbOut, if_exists="append", index=False)
            
            logging.info("[%5i] Just received and wrote all data from rank %i" % (localRank,rank))


    if(localRank == 0):
        duration_secs = time.perf_counter() - start_time
        logging.info("")
        logging.info("Data aggregation complete -> %s" % (args.outfile))
        logging.info("--> wallclock time = %.3f (secs)" % duration_secs)


if __name__ == "__main__":
    main()
