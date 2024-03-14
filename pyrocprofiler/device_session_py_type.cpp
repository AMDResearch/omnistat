#include "device_session_py_type.h"

PyObject* DeviceSession_new(PyTypeObject* type, PyObject* args, PyObject* kwds) {
  DeviceSessionObject* self;
  self = (DeviceSessionObject*)type->tp_alloc(type, 0);
  if (self != NULL) {
    self->m_device_session = NULL;
  }
  return (PyObject*)self;
}

int DeviceSession_init(PyObject* self, PyObject* args, PyObject* kwds) {
  DeviceSessionObject* m = (DeviceSessionObject*)self;

  m->m_device_session = (DeviceSession*)PyObject_Malloc(sizeof(DeviceSession));

  if (!m->m_device_session) {
    PyErr_SetString(PyExc_RuntimeError, "Memory allocation failed");
    return -1;
  }

  try {
    new (m->m_device_session) DeviceSession();
  } catch (const std::exception& ex) {
    PyObject_Free(m->m_device_session);
    m->m_device_session = NULL;
    PyErr_SetString(PyExc_RuntimeError, ex.what());
    return -1;
  } catch (...) {
    PyObject_Free(m->m_device_session);
    m->m_device_session = NULL;
    PyErr_SetString(PyExc_RuntimeError, "Initialization failed");
    return -1;
  }

  return 0;
}

void DeviceSession_dealloc(DeviceSessionObject* self) {
  PyTypeObject* tp = Py_TYPE(self);

  DeviceSessionObject* m = reinterpret_cast<DeviceSessionObject*>(self);

  if (m->m_device_session) {
    m->m_device_session->~DeviceSession();
    PyObject_Free(m->m_device_session);
  }

  tp->tp_free(self);
  Py_DECREF(tp);
};

PyObject* DeviceSession_create(PyObject* self, PyObject* args) {
  assert(self);
  DeviceSessionObject* _self = reinterpret_cast<DeviceSessionObject*>(self);

  PyObject* list;
  PyObject* item;
  PyObject* bytes;

  if (!PyArg_ParseTuple(args, "O!", &PyList_Type, &list)) {
    PyErr_SetString(PyExc_TypeError, "Parameter must be a list");
    return NULL;
  }

  Py_ssize_t num_counters = PyList_Size(list);
  std::vector<const char*> counters;
  counters.reserve(num_counters);
  for (int i = 0; i < num_counters; i++) {
    item = PyList_GetItem(list, i);
    if (!PyUnicode_Check(item)) {
      PyErr_SetString(PyExc_TypeError, "List items must be strings");
      return NULL;
    }
    bytes = PyUnicode_AsUTF8String(item);
    counters.emplace_back(PyBytes_AsString(bytes));
  }

  _self->m_device_session->create(counters);
  Py_RETURN_NONE;
}

PyObject* DeviceSession_destroy(PyObject* self, PyObject* args) {
  assert(self);
  DeviceSessionObject* _self = reinterpret_cast<DeviceSessionObject*>(self);
  _self->m_device_session->destroy();
  Py_RETURN_NONE;
}

PyObject* DeviceSession_start(PyObject* self, PyObject* args) {
  assert(self);
  DeviceSessionObject* _self = reinterpret_cast<DeviceSessionObject*>(self);
  _self->m_device_session->start();
  Py_RETURN_NONE;
}

PyObject* DeviceSession_stop(PyObject* self, PyObject* args) {
  assert(self);
  DeviceSessionObject* _self = reinterpret_cast<DeviceSessionObject*>(self);
  _self->m_device_session->stop();
  Py_RETURN_NONE;
}

PyObject* DeviceSession_poll(PyObject* self, PyObject* args) {
  assert(self);
  DeviceSessionObject* _self = reinterpret_cast<DeviceSessionObject*>(self);
  auto metrics = _self->m_device_session->poll();
  PyObject* python_val = PyList_New(metrics.size());
  int i = 0;
  for (const auto& metric : metrics) {
    PyObject* python_double = Py_BuildValue("d", metric.value.value);
    PyList_SetItem(python_val, i++, python_double);
  }
  return python_val;
}
