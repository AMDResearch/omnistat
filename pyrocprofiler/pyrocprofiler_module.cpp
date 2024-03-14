#include "device_session_py_type.h"

PyModuleDef pyrocprofiler = {
  PyModuleDef_HEAD_INIT,
  "pyrocprofiler", // Module name
  "Python wrapper for rocprofiler's device mode",
  -1,   // Optional size of the module state memory
  NULL, // Optional module methods
  NULL, // Optional slot definitions
  NULL, // Optional traversal function
  NULL, // Optional clear function
  NULL  // Optional module deallocation function
};

PyMODINIT_FUNC PyInit_pyrocprofiler(void) {
  PyObject* module = PyModule_Create(&pyrocprofiler);

  PyObject* device_session = PyType_FromSpec(&DeviceSession_spec);
  if (device_session == NULL) {
    return NULL;
  }
  Py_INCREF(device_session);

  if (PyModule_AddObject(module, "DeviceSession", device_session) < 0) {
    Py_DECREF(device_session);
    Py_DECREF(module);
    return NULL;
  }
  return module;
}
