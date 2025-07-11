// MIT License
//
// Copyright (c) 2025 Advanced Micro Devices, Inc. All rights reserved.
//
// Permission is hereby granted, free of charge, to any person obtaining a copy
// of this software and associated documentation files (the "Software"), to deal
// in the Software without restriction, including without limitation the rights
// to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
// copies of the Software, and to permit persons to whom the Software is
// furnished to do so, subject to the following conditions:
//
// The above copyright notice and this permission notice shall be included in
// all copies or substantial portions of the Software.
//
// THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
// IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
// FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
// AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
// LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
// OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
// SOFTWARE.

#include <rocprofiler-sdk/buffer.h>
#include <rocprofiler-sdk/context.h>
#include <rocprofiler-sdk/fwd.h>
#include <rocprofiler-sdk/registration.h>
#include <rocprofiler-sdk/rocprofiler.h>

#include <atomic>
#include <chrono>
#include <csignal>
#include <cstdlib>
#include <iostream>
#include <map>
#include <memory>
#include <unordered_map>
#include <vector>

#define ROCPROFILER_CALL(result, msg)                                                              \
  {                                                                                                \
    rocprofiler_status_t CHECKSTATUS = result;                                                     \
    if (CHECKSTATUS != ROCPROFILER_STATUS_SUCCESS) {                                               \
      std::string status_msg = rocprofiler_get_status_string(CHECKSTATUS);                         \
      std::cerr << "[" #result "][" << __FILE__ << ":" << __LINE__ << "] " << msg                  \
                << " failed with error code " << CHECKSTATUS << ": " << status_msg << std::endl;   \
      std::stringstream errmsg{};                                                                  \
      errmsg << "[" #result "][" << __FILE__ << ":" << __LINE__ << "] " << msg " failure ("        \
             << status_msg << ")";                                                                 \
      throw std::runtime_error(errmsg.str());                                                      \
    }                                                                                              \
  }

namespace {

class device_collector {
public:
  device_collector(rocprofiler_agent_id_t agent);

  // Sample the counter values for a set of counters, returns the records in the
  // out parameter.
  void sample_counters(const std::vector<std::string> &counters,
                       std::vector<rocprofiler_record_counter_t> &out);

  // Decode the counter name of a record
  const std::string &decode_record_name(const rocprofiler_record_counter_t &rec) const;

  // Get the dimensions of a record (what CU/SE/etc the counter is for). High
  // cost operation; should be cached if possible.
  static std::unordered_map<std::string, size_t>
  get_record_dimensions(const rocprofiler_record_counter_t &rec);

  // Get the available agents on the system
  static std::vector<rocprofiler_agent_v0_t> get_agents();

  void stop() const { rocprofiler_stop_context(ctx_); }

private:
  rocprofiler_agent_id_t agent_ = {};
  rocprofiler_context_id_t ctx_ = {};
  rocprofiler_profile_config_id_t profile_ = {.handle = 0};

  std::map<std::vector<std::string>, rocprofiler_profile_config_id_t> cached_profiles_;
  std::map<uint64_t, uint64_t> profile_sizes_;
  mutable std::map<uint64_t, std::string> id_to_name_;

  void set_profile(rocprofiler_context_id_t ctx, rocprofiler_agent_set_profile_callback_t cb) const;

  static size_t get_counter_size(rocprofiler_counter_id_t counter);

  static std::unordered_map<std::string, rocprofiler_counter_id_t>
  get_supported_counters(rocprofiler_agent_id_t agent);

  static std::vector<rocprofiler_record_dimension_info_t>
  get_counter_dimensions(rocprofiler_counter_id_t counter);
};

device_collector::device_collector(rocprofiler_agent_id_t agent) : agent_(agent) {
  auto client_thread = rocprofiler_callback_thread_t{};
  ROCPROFILER_CALL(rocprofiler_create_context(&ctx_), "context creation failed");

  ROCPROFILER_CALL(rocprofiler_configure_device_counting_service(
                       ctx_, rocprofiler_buffer_id_t{.handle = 0}, agent,
                       [](rocprofiler_context_id_t context_id, rocprofiler_agent_id_t,
                          rocprofiler_agent_set_profile_callback_t set_config, void *user_data) {
                         if (user_data) {
                           auto *collector = static_cast<device_collector *>(user_data);
                           collector->set_profile(context_id, set_config);
                         }
                       },
                       this),
                   "Could not setup buffered service");
}

const std::string &
device_collector::decode_record_name(const rocprofiler_record_counter_t &rec) const {
  if (id_to_name_.empty()) {
    auto name_to_id = device_collector::get_supported_counters(agent_);
    for (const auto &[name, id] : name_to_id) {
      id_to_name_.emplace(id.handle, name);
    }
  }

  rocprofiler_counter_id_t counter_id = {.handle = 0};
  rocprofiler_query_record_counter_id(rec.id, &counter_id);
  return id_to_name_.at(counter_id.handle);
}

std::unordered_map<std::string, size_t>
device_collector::get_record_dimensions(const rocprofiler_record_counter_t &rec) {
  std::unordered_map<std::string, size_t> out;
  rocprofiler_counter_id_t counter_id = {.handle = 0};
  rocprofiler_query_record_counter_id(rec.id, &counter_id);
  auto dims = get_counter_dimensions(counter_id);

  for (auto &dim : dims) {
    size_t pos = 0;
    rocprofiler_query_record_dimension_position(rec.id, dim.id, &pos);
    out.emplace(dim.name, pos);
  }
  return out;
}

void device_collector::sample_counters(const std::vector<std::string> &counters,
                                       std::vector<rocprofiler_record_counter_t> &out) {
  auto profile_cached = cached_profiles_.find(counters);
  if (profile_cached == cached_profiles_.end()) {
    size_t expected_size = 0;
    rocprofiler_profile_config_id_t profile = {};
    std::vector<rocprofiler_counter_id_t> gpu_counters;
    auto roc_counters = get_supported_counters(agent_);
    for (const auto &counter : counters) {
      auto it = roc_counters.find(counter);
      if (it == roc_counters.end()) {
        std::cerr << "Counter " << counter << " not found\n";
        continue;
      }
      gpu_counters.push_back(it->second);
      expected_size += get_counter_size(it->second);
    }
    ROCPROFILER_CALL(rocprofiler_create_profile_config(agent_, gpu_counters.data(),
                                                       gpu_counters.size(), &profile),
                     "Could not create profile");
    cached_profiles_.emplace(counters, profile);
    profile_sizes_.emplace(profile.handle, expected_size);
    profile_cached = cached_profiles_.find(counters);
  }

  out.resize(profile_sizes_.at(profile_cached->second.handle));
  profile_ = profile_cached->second;
  rocprofiler_start_context(ctx_);
  size_t out_size = out.size();
  rocprofiler_sample_device_counting_service(ctx_, {}, ROCPROFILER_COUNTER_FLAG_NONE, out.data(),
                                             &out_size);
  out.resize(out_size);
}

std::vector<rocprofiler_agent_v0_t> device_collector::get_agents() {
  std::vector<rocprofiler_agent_v0_t> agents;
  rocprofiler_query_available_agents_cb_t iterate_cb = [](rocprofiler_agent_version_t agents_ver,
                                                          const void **agents_arr,
                                                          size_t num_agents, void *udata) {
    if (agents_ver != ROCPROFILER_AGENT_INFO_VERSION_0)
      throw std::runtime_error{"unexpected rocprofiler agent version"};
    auto *agents_v = static_cast<std::vector<rocprofiler_agent_v0_t> *>(udata);
    for (size_t i = 0; i < num_agents; ++i) {
      const auto *rocp_agent = static_cast<const rocprofiler_agent_v0_t *>(agents_arr[i]);
      if (rocp_agent->type == ROCPROFILER_AGENT_TYPE_GPU)
        agents_v->emplace_back(*rocp_agent);
    }
    return ROCPROFILER_STATUS_SUCCESS;
  };

  ROCPROFILER_CALL(rocprofiler_query_available_agents(
                       ROCPROFILER_AGENT_INFO_VERSION_0, iterate_cb, sizeof(rocprofiler_agent_t),
                       const_cast<void *>(static_cast<const void *>(&agents))),
                   "query available agents");
  return agents;
}

void device_collector::set_profile(rocprofiler_context_id_t ctx,
                                   rocprofiler_agent_set_profile_callback_t cb) const {
  if (profile_.handle != 0) {
    cb(ctx, profile_);
  }
}

size_t device_collector::get_counter_size(rocprofiler_counter_id_t counter) {
  size_t size = 1;
  rocprofiler_iterate_counter_dimensions(
      counter,
      [](rocprofiler_counter_id_t, const rocprofiler_record_dimension_info_t *dim_info,
         size_t num_dims, void *user_data) {
        size_t *s = static_cast<size_t *>(user_data);
        for (size_t i = 0; i < num_dims; i++) {
          *s *= dim_info[i].instance_size;
        }
        return ROCPROFILER_STATUS_SUCCESS;
      },
      static_cast<void *>(&size));
  return size;
}

std::unordered_map<std::string, rocprofiler_counter_id_t>
device_collector::get_supported_counters(rocprofiler_agent_id_t agent) {
  std::unordered_map<std::string, rocprofiler_counter_id_t> out;
  std::vector<rocprofiler_counter_id_t> gpu_counters;

  ROCPROFILER_CALL(rocprofiler_iterate_agent_supported_counters(
                       agent,
                       [](rocprofiler_agent_id_t, rocprofiler_counter_id_t *counters,
                          size_t num_counters, void *user_data) {
                         std::vector<rocprofiler_counter_id_t> *vec =
                             static_cast<std::vector<rocprofiler_counter_id_t> *>(user_data);
                         for (size_t i = 0; i < num_counters; i++) {
                           vec->push_back(counters[i]);
                         }
                         return ROCPROFILER_STATUS_SUCCESS;
                       },
                       static_cast<void *>(&gpu_counters)),
                   "Could not fetch supported counters");
  for (auto &counter : gpu_counters) {
    rocprofiler_counter_info_v0_t version;
    ROCPROFILER_CALL(rocprofiler_query_counter_info(counter, ROCPROFILER_COUNTER_INFO_VERSION_0,
                                                    static_cast<void *>(&version)),
                     "Could not query info for counter");
    out.emplace(version.name, counter);
  }
  return out;
}

std::vector<rocprofiler_record_dimension_info_t>
device_collector::get_counter_dimensions(rocprofiler_counter_id_t counter) {
  std::vector<rocprofiler_record_dimension_info_t> dims;
  rocprofiler_available_dimensions_cb_t cb = [](rocprofiler_counter_id_t,
                                                const rocprofiler_record_dimension_info_t *dim_info,
                                                size_t num_dims, void *user_data) {
    std::vector<rocprofiler_record_dimension_info_t> *vec =
        static_cast<std::vector<rocprofiler_record_dimension_info_t> *>(user_data);
    for (size_t i = 0; i < num_dims; i++) {
      vec->push_back(dim_info[i]);
    }
    return ROCPROFILER_STATUS_SUCCESS;
  };
  ROCPROFILER_CALL(rocprofiler_iterate_counter_dimensions(counter, cb, &dims),
                   "Could not iterate counter dimensions");
  return dims;
}

std::atomic<bool> done(false);
std::vector<std::shared_ptr<device_collector>> collectors = {};

} // namespace

int tool_init(rocprofiler_client_finalize_t fini_func, void *) {
  auto agents = device_collector::get_agents();
  if (agents.empty()) {
    std::cerr << "No agents found\n";
    return -1;
  }

  for (auto agent : agents) {
    collectors.push_back(std::make_shared<device_collector>(agent.id));
  }

  return 0;
}

void tool_fini(void *user_data) {
  for (auto c : collectors) {
    c->stop();
  }

  auto *output_stream = static_cast<std::ostream *>(user_data);
  *output_stream << std::flush;
  if (output_stream != &std::cout && output_stream != &std::cerr)
    delete output_stream;
}

extern "C" rocprofiler_tool_configure_result_t *rocprofiler_configure(uint32_t version,
                                                                      const char *runtime_version,
                                                                      uint32_t priority,
                                                                      rocprofiler_client_id_t *id) {
  id->name = "device-counters";

  uint32_t major = version / 10000;
  uint32_t minor = (version % 10000) / 100;
  uint32_t patch = version % 100;

  auto info = std::stringstream{};
  info << id->name << " (priority=" << priority << ") is using rocprofiler-sdk v" << major << "."
       << minor << "." << patch << " (" << runtime_version << ")";

  std::cerr << info.str() << std::endl;

  std::ostream *output_stream = &std::cout;
  static auto cfg =
      rocprofiler_tool_configure_result_t{sizeof(rocprofiler_tool_configure_result_t), &tool_init,
                                          &tool_fini, static_cast<void *>(output_stream)};

  return &cfg;
}

void signal_handler(int signal) {
  if (signal == SIGTERM || signal == SIGINT) {
    std::cerr << "Terminating collector\n";
    done.store(true);
  }
}

std::unordered_map<std::string, double>
process_records(const std::vector<rocprofiler_record_counter_t> &records,
                const std::shared_ptr<device_collector> &collector) {
  // Accumulate all records by name to display a single value.
  std::unordered_map<std::string, double> accumulated_values;
  for (const auto &record : records) {
    if (record.id) {
      auto name = collector->decode_record_name(record);
      accumulated_values[name] += record.counter_value;
    }
  }
  return accumulated_values;
}

void print_values(const std::unordered_map<std::string, double> &values) {
  std::cout << "- gpu:\n";
  for (const auto &pair : values) {
    std::cout << "  - " << pair.first << ": " << pair.second << "\n";
  }
}

int main(int argc, char **argv) {
  signal(SIGTERM, signal_handler);
  signal(SIGINT, signal_handler);

  int num_devices = 0;
  auto status = hipGetDeviceCount(&num_devices);

  bool valid = true;
  const int interval_seconds = 1;

  std::vector<std::string> counters = {"GRBM_COUNT"};
  for (int i = 1; i < argc; ++i) {
    counters.push_back(argv[i]);
  }

  std::vector<rocprofiler_record_counter_t> records;
  std::vector<double> grbm_counts;

  std::cout << "start:\n";
  for (auto collector : collectors) {
    collector->sample_counters(counters, records);
    auto values = process_records(records, collector);
    print_values(values);
    grbm_counts.push_back(values["GRBM_COUNT"]);
  }

  while (!done) {
    std::this_thread::sleep_for(std::chrono::seconds(interval_seconds));
    for (int i = 0; i < grbm_counts.size(); i++) {
      auto collector = collectors[i];
      collector->sample_counters(counters, records);
      auto values = process_records(records, collector);

      // Make sure GRBM_COUNT is always increasing. If it's not, there's
      // likely another profiling process and the numbers are no longer
      // reliable.
      auto previous = grbm_counts[i];
      grbm_counts[i] = values["GRBM_COUNT"];
      if (grbm_counts[i] < previous) {
        std::cerr << "Invalid session: " << previous << " " << grbm_counts[i] << "\n";
        valid = false;
      }
    }
  }

  std::cout << "end:\n";
  for (auto collector : collectors) {
    collector->sample_counters(counters, records);
    auto values = process_records(records, collector);
    print_values(values);
  }
  std::cout << "valid: " << valid << "\n";
}
