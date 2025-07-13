# Build

```
mkdir build
cd build
cmake ..
make
```

# Run

```
./pmc-collector
```

The pmc-collector binary is configured to collect a pre-defined set of hardware
counters at 1 sec intervals in an infinite loop.  Press `Ctrl+C` or
send `SIGTERM` to stop the process and collect counter values.

Note that device-mode profiling using rocprof-sdk requires elevated
credentials or, alternatively, for the sampling binary to have
`SYS_PERFMON` privileges.  To try and avoid invalid counters when
another profiling session is invoked, this demo utility monitors
`GRBM_COUNT` to flag invalid results caused by the presence of other
profiling sessions.

Sample output running rocHPL on single node of MI250 is shown below:

```
device-counters (priority=0) is using rocprofiler-sdk v0.6.0 (0.6.0)
E20250713 16:50:07.301306 140495314305152 agent_cache.cpp:139] Creating Profile Queue
E20250713 16:50:07.314254 140495314305152 agent_cache.cpp:139] Creating Profile Queue
E20250713 16:50:07.327028 140495314305152 agent_cache.cpp:139] Creating Profile Queue
E20250713 16:50:07.339700 140495314305152 agent_cache.cpp:139] Creating Profile Queue
E20250713 16:50:07.352265 140495314305152 agent_cache.cpp:139] Creating Profile Queue
E20250713 16:50:07.364906 140495314305152 agent_cache.cpp:139] Creating Profile Queue
E20250713 16:50:07.377586 140495314305152 agent_cache.cpp:139] Creating Profile Queue
E20250713 16:50:07.390222 140495314305152 agent_cache.cpp:139] Creating Profile Queue
Sampling interval set to 1 second(s).
start:
^CTerminating collector
end:
- gpu:
  - GRBM_COUNT: 7.96045e+10
  - SQ_INSTS_VALU_ADD_F32: 0
  - SQ_INSTS_VALU_ADD_F64: 5.45376e+08
  - SQ_INSTS_VALU_FMA_F32: 859004
  - SQ_INSTS_VALU_FMA_F64: 5.81143e+09
  - SQ_INSTS_VALU_MFMA_F32: 0
  - SQ_INSTS_VALU_MFMA_F64: 1.15079e+11
  - SQ_INSTS_VALU_MUL_F32: 1.29806e+06
  - SQ_INSTS_VALU_MUL_F64: 4.86953e+09
  - TCC_EA_RDREQ_32B_sum: 54292
  - TCC_EA_RDREQ_sum: 7.00065e+10
- gpu:
  - GRBM_COUNT: 7.9626e+10
  - SQ_INSTS_VALU_ADD_F32: 0
  - SQ_INSTS_VALU_ADD_F64: 5.41772e+08
  - SQ_INSTS_VALU_FMA_F32: 859004
  - SQ_INSTS_VALU_FMA_F64: 5.7715e+09
  - SQ_INSTS_VALU_MFMA_F32: 0
  - SQ_INSTS_VALU_MFMA_F64: 1.14319e+11
  - SQ_INSTS_VALU_MUL_F32: 1.29803e+06
  - SQ_INSTS_VALU_MUL_F64: 4.83705e+09
  - TCC_EA_RDREQ_32B_sum: 59564
  - TCC_EA_RDREQ_sum: 6.89132e+10
- gpu:
  - GRBM_COUNT: 7.96215e+10
  - SQ_INSTS_VALU_ADD_F32: 0
  - SQ_INSTS_VALU_ADD_F64: 5.41775e+08
  - SQ_INSTS_VALU_FMA_F32: 859004
  - SQ_INSTS_VALU_FMA_F64: 5.79403e+09
  - SQ_INSTS_VALU_MFMA_F32: 0
  - SQ_INSTS_VALU_MFMA_F64: 1.14782e+11
  - SQ_INSTS_VALU_MUL_F32: 1.29803e+06
  - SQ_INSTS_VALU_MUL_F64: 4.85686e+09
  - TCC_EA_RDREQ_32B_sum: 58326
  - TCC_EA_RDREQ_sum: 6.932e+10
- gpu:
  - GRBM_COUNT: 7.9712e+10
  - SQ_INSTS_VALU_ADD_F32: 0
  - SQ_INSTS_VALU_ADD_F64: 5.41756e+08
  - SQ_INSTS_VALU_FMA_F32: 859004
  - SQ_INSTS_VALU_FMA_F64: 5.81435e+09
  - SQ_INSTS_VALU_MFMA_F32: 0
  - SQ_INSTS_VALU_MFMA_F64: 1.1524e+11
  - SQ_INSTS_VALU_MUL_F32: 1.29803e+06
  - SQ_INSTS_VALU_MUL_F64: 4.87601e+09
  - TCC_EA_RDREQ_32B_sum: 58524
  - TCC_EA_RDREQ_sum: 6.96612e+10
- gpu:
  - GRBM_COUNT: 7.96546e+10
  - SQ_INSTS_VALU_ADD_F32: 0
  - SQ_INSTS_VALU_ADD_F64: 5.43413e+08
  - SQ_INSTS_VALU_FMA_F32: 858052
  - SQ_INSTS_VALU_FMA_F64: 5.80599e+09
  - SQ_INSTS_VALU_MFMA_F32: 0
  - SQ_INSTS_VALU_MFMA_F64: 1.15104e+11
  - SQ_INSTS_VALU_MUL_F32: 1.2966e+06
  - SQ_INSTS_VALU_MUL_F64: 4.89374e+09
  - TCC_EA_RDREQ_32B_sum: 21967
  - TCC_EA_RDREQ_sum: 6.99703e+10
- gpu:
  - GRBM_COUNT: 7.98701e+10
  - SQ_INSTS_VALU_ADD_F32: 0
  - SQ_INSTS_VALU_ADD_F64: 5.39844e+08
  - SQ_INSTS_VALU_FMA_F32: 858052
  - SQ_INSTS_VALU_FMA_F64: 5.76768e+09
  - SQ_INSTS_VALU_MFMA_F32: 0
  - SQ_INSTS_VALU_MFMA_F64: 1.14349e+11
  - SQ_INSTS_VALU_MUL_F32: 1.29657e+06
  - SQ_INSTS_VALU_MUL_F64: 4.86166e+09
  - TCC_EA_RDREQ_32B_sum: 22679
  - TCC_EA_RDREQ_sum: 6.86489e+10
- gpu:
  - GRBM_COUNT: 7.90289e+10
  - SQ_INSTS_VALU_ADD_F32: 0
  - SQ_INSTS_VALU_ADD_F64: 5.39825e+08
  - SQ_INSTS_VALU_FMA_F32: 858052
  - SQ_INSTS_VALU_FMA_F64: 5.78808e+09
  - SQ_INSTS_VALU_MFMA_F32: 0
  - SQ_INSTS_VALU_MFMA_F64: 1.14809e+11
  - SQ_INSTS_VALU_MUL_F32: 1.29657e+06
  - SQ_INSTS_VALU_MUL_F64: 4.88088e+09
  - TCC_EA_RDREQ_32B_sum: 23651
  - TCC_EA_RDREQ_sum: 6.88351e+10
- gpu:
  - GRBM_COUNT: 7.90285e+10
  - SQ_INSTS_VALU_ADD_F32: 0
  - SQ_INSTS_VALU_ADD_F64: 5.39828e+08
  - SQ_INSTS_VALU_FMA_F32: 858052
  - SQ_INSTS_VALU_FMA_F64: 5.81047e+09
  - SQ_INSTS_VALU_MFMA_F32: 0
  - SQ_INSTS_VALU_MFMA_F64: 1.15268e+11
  - SQ_INSTS_VALU_MUL_F32: 1.29657e+06
  - SQ_INSTS_VALU_MUL_F64: 4.90055e+09
  - TCC_EA_RDREQ_32B_sum: 22589
  - TCC_EA_RDREQ_sum: 6.9207e+10
valid: 1
```
