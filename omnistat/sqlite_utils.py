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
# Utility to aid joining HDF5 data collections from multiple compute nodes.

import argparse
import logging
import os
import pandas as pd
import sqlite3
import sys


def hostFromTableName(name):
    """Cull host from table name in the form hostname__cardid__metric"""
    return name.split("__")[0]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--infile", type=str, help="name of input sqlite file to read", required=True)
    parser.add_argument("--outfile", type=str, help="name of output sqlite to append", required=True)
    args = parser.parse_args()

    logging.basicConfig(format="%(message)s", level=logging.INFO, stream=sys.stdout)

    if not os.path.exists(args.infile):
        logging.error("Error: Cannot access infile -> %s" % args.infile)
        sys.exit(1)

    with sqlite3.connect(args.infile) as dbIn:
        cursor = dbIn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tables = cursor.fetchall()
        namesIn = [table[0] for table in tables]

        # Scan for existing hosts in output file (if present)
        existingHosts = []
        if os.path.exists(args.outfile):
            with sqlite3.connect(args.outfile) as dbOut:
                cursor = dbOut.cursor()
                cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
                tables = cursor.fetchall()
                namesExisting = [table[0] for table in tables]

            for name in namesExisting:
                host = hostFromTableName(name)
                if host not in existingHosts:
                    existingHosts.append(host)

        # Append data from infile to outfile; punt if data already exist for a given host in outfile
        with sqlite3.connect(args.outfile) as dbOut:

            for metric in namesIn:
                host = hostFromTableName(metric)
                if host in existingHosts:
                    logging.error("Error: cowardly refusing to add data for %s when host data already exists", host)
                    sys.exit(1)
                logging.info("Reading metric %s..." % metric)
                data = pd.read_sql_query("SELECT * FROM %s" % metric, dbIn)
                host = hostFromTableName(metric)
                data.to_sql(metric, dbOut, if_exists="append", index=False)

    logging.info("Just copied data from %s into %s" % (args.infile, args.outfile))


if __name__ == "__main__":
    main()
