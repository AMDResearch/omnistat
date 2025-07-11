# Build

```
mkdir build
cd build
cmake ..
make
```

# Run

```
./pmc-collector GRBM_COUNT SQ_WAVES
```

Press `Ctrl+C` or send `SIGTERM` to stop the process and collect counter
values. Sample output:

```
start:
- gpu:
  - SQ_WAVES: 0
  - GRBM_COUNT: 18323
- gpu:
  - SQ_WAVES: 0
  - GRBM_COUNT: 22633
end:
- gpu:
  - SQ_WAVES: 0
  - GRBM_COUNT: 2.50067e+09
- gpu:
  - SQ_WAVES: 0
  - GRBM_COUNT: 2.48401e+09
valid: 1
```
