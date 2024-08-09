package main

import (
	"flag"
	"fmt"
	"github.com/go-kit/log"
	"github.com/prometheus/prometheus/tsdb"
	"os"
)

func main() {
	path := flag.String("path", "./data", "Path to Prometheus database")
	flag.Parse()

	sandbox := *path + "-sandbox"
	output := *path + "-output"

	if _, err := os.Stat(*path); err != nil {
		fmt.Printf("Error: Unable to find database directory: %v\n", err)
		return
	}

	logger := log.NewLogfmtLogger(log.NewSyncWriter(os.Stdout))
	db, err := tsdb.OpenDBReadOnly(*path, sandbox, logger)
	if err != nil {
		fmt.Printf("Error: Unable to open Prometheus database: %v\n", err)
		return
	}

	err = db.FlushWAL(output)
	if err != nil {
		fmt.Println("Error: Failed to flush WAL: %v\n", err)
		return
	}
}
