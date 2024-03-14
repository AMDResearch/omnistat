#ifndef DEVICE_SESSION_HPP
#define DEVICE_SESSION_HPP

#include <iostream>
#include <vector>

#include <hip/hip_runtime.h>
#include <rocprofiler/v2/rocprofiler.h>

#define HIP_CHECK(call)                                \
  do {                                                 \
    hipError_t err = call;                             \
    if (err != hipSuccess) {                           \
      fprintf(stderr, "%s\n", hipGetErrorString(err)); \
      abort();                                         \
    }                                                  \
  } while (0)

#define ROCPROF_CHECK(call)                                    \
  do {                                                         \
    if ((call) != ROCPROFILER_STATUS_SUCCESS)                  \
      fprintf(stderr, "Error: ROCProfiler API Call Error!\n"); \
  } while (false)

class DeviceSession {
public:
  DeviceSession() {
    hipDeviceProp_t prop;
    HIP_CHECK(hipGetDeviceProperties(&prop, 0));
    ROCPROF_CHECK(rocprofiler_initialize());
  }

  void create(std::vector<const char*>& counters) {
    m_metrics = std::vector<rocprofiler_device_profile_metric_t>(counters.size());
    int gpu_agent = 0;
    int cpu_agent = 0;
    ROCPROF_CHECK(rocprofiler_device_profiling_session_create(&counters[0], counters.size(), &m_id,
                                                              cpu_agent, gpu_agent));
  }

  void destroy() {
    ROCPROF_CHECK(rocprofiler_device_profiling_session_destroy(m_id));
  }

  void start() {
    ROCPROF_CHECK(rocprofiler_device_profiling_session_start(m_id));
  }

  void stop() {
    ROCPROF_CHECK(rocprofiler_device_profiling_session_stop(m_id));
  }

  const std::vector<rocprofiler_device_profile_metric_t>& poll() {
    ROCPROF_CHECK(rocprofiler_device_profiling_session_poll(m_id, &m_metrics[0]));
    return m_metrics;
  }

private:
  rocprofiler_session_id_t m_id;
  std::vector<rocprofiler_device_profile_metric_t> m_metrics;
};

#endif
