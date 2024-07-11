#ifndef DEVICE_SESSION_PY_TYPE_H
#define DEVICE_SESSION_PY_TYPE_H

#define PY_SSIZE_T_CLEAN

#include <Python.h>
#include <structmember.h>

#include "device_session.hpp"

typedef struct {
  PyObject_HEAD DeviceSession* m_device_session;
} DeviceSessionObject;

PyObject* DeviceSession_new(PyTypeObject* subtype, PyObject* args, PyObject* kwds);
int DeviceSession_init(PyObject* self, PyObject* args, PyObject* kwds);
void DeviceSession_dealloc(DeviceSessionObject* self);

PyObject* DeviceSession_create(PyObject* self, PyObject* args);
PyObject* DeviceSession_destroy(PyObject* self, PyObject* args);
PyObject* DeviceSession_start(PyObject* self, PyObject* args);
PyObject* DeviceSession_stop(PyObject* self, PyObject* args);
PyObject* DeviceSession_poll(PyObject* self, PyObject* args);

static PyMethodDef DeviceSession_methods[] = {
  {"create", (PyCFunction)DeviceSession_create, METH_VARARGS,
   PyDoc_STR("Create device profiling session")},
  {"destroy", (PyCFunction)DeviceSession_destroy, METH_NOARGS,
   PyDoc_STR("Destroy device profiling session")},
  {"start", (PyCFunction)DeviceSession_start, METH_NOARGS,
   PyDoc_STR("Start device profiling session")},
  {"stop", (PyCFunction)DeviceSession_stop, METH_NOARGS,
   PyDoc_STR("Stop device profiling session")},
  {"poll", (PyCFunction)DeviceSession_poll, METH_NOARGS,
   PyDoc_STR("Read counters from GPU device")},
  {NULL, NULL} /* Sentinel */
};

static struct PyMemberDef DeviceSession_members[] = {
  {NULL} /* Sentinel */
};

static PyType_Slot DeviceSession_slots[] = {
  {Py_tp_new, (void*)DeviceSession_new},         {Py_tp_init, (void*)DeviceSession_init},
  {Py_tp_dealloc, (void*)DeviceSession_dealloc}, {Py_tp_members, DeviceSession_members},
  {Py_tp_methods, DeviceSession_methods},        {0, 0}};

static PyType_Spec DeviceSession_spec = {
  "DeviceSession",                                     // name
  sizeof(DeviceSessionObject) + sizeof(DeviceSession), // basicsize
  0,                                                   // itemsize
  Py_TPFLAGS_DEFAULT | Py_TPFLAGS_BASETYPE,            // flags
  DeviceSession_slots                                  // slots
};

#endif
