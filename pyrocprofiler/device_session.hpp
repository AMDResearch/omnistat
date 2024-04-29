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
  int create(std::vector<const char*>& metric_names) {
    HIP_CHECK(hipGetDeviceCount(&m_num_gpus));
    ROCPROF_CHECK(rocprofiler_initialize());

    m_sessions = std::vector<rocprofiler_session_id_t>(m_num_gpus);
    m_metrics = std::vector<std::vector<rocprofiler_device_profile_metric_t>>(
      m_num_gpus, std::vector<rocprofiler_device_profile_metric_t>(metric_names.size()));

    int cpu_agent = 0;
    for (int i = 0; i < m_num_gpus; i++) {
      ROCPROF_CHECK(rocprofiler_device_profiling_session_create(
        &metric_names[0], metric_names.size(), &m_sessions[i], cpu_agent, i));
    }

    return m_num_gpus;
  }

  void destroy() {
    for (int i = 0; i < m_num_gpus; i++) {
      ROCPROF_CHECK(rocprofiler_device_profiling_session_destroy(m_sessions[i]));
    }
  }

  void start() {
    for (int i = 0; i < m_num_gpus; i++) {
      ROCPROF_CHECK(rocprofiler_device_profiling_session_start(m_sessions[i]));
    }
  }

  void stop() {
    for (int i = 0; i < m_num_gpus; i++) {
      ROCPROF_CHECK(rocprofiler_device_profiling_session_stop(m_sessions[i]));
    }
  }

  void fake_event() {
    hipEvent_t event;
    ROCPROF_CHECK(hipEventCreate(&event));
    ROCPROF_CHECK(hipEventRecord(event, hipStreamDefault));
    ROCPROF_CHECK(hipEventDestroy(event));
  }

  const std::vector<std::vector<rocprofiler_device_profile_metric_t>>& poll() {
    for (int i = 0; i < m_num_gpus; i++) {
      ROCPROF_CHECK(rocprofiler_device_profiling_session_poll(m_sessions[i], &m_metrics[i][0]));
    }
    return m_metrics;
  }

private:
  int m_num_gpus;
  std::vector<rocprofiler_session_id_t> m_sessions;
  std::vector<std::vector<rocprofiler_device_profile_metric_t>> m_metrics;
};

#endif
