/*
 * This file is part of the MicroPython project, http://micropython.org/
 *
 * The MIT License (MIT)
 *
 * Copyright (c) 2022 microDev
 *
 * Permission is hereby granted, free of charge, to any person obtaining a copy
 * of this software and associated documentation files (the "Software"), to deal
 * in the Software without restriction, including without limitation the rights
 * to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
 * copies of the Software, and to permit persons to whom the Software is
 * furnished to do so, subject to the following conditions:
 *
 * The above copyright notice and this permission notice shall be included in
 * all copies or substantial portions of the Software.
 *
 * THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
 * IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
 * FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
 * AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
 * LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
 * OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
 * THE SOFTWARE.
 */

#include "bindings/espulp/ULPAlarm.h"

#include "py/runtime.h"

//| class ULPAlarm:
//|     """Trigger an alarm when the ULP requests wake-up."""
//|
//|     def __init__(self) -> None:
//|         """Create an alarm that will be triggered when the ULP requests wake-up.
//|
//|         The alarm is not active until it is passed to an `alarm`-enabling function, such as
//|         `alarm.light_sleep_until_alarms()` or `alarm.exit_and_deep_sleep_until_alarms()`.
//|
//|         """
//|         ...
//|
STATIC mp_obj_t espulp_ulpalarm_make_new(const mp_obj_type_t *type,
    size_t n_args, size_t n_kw, const mp_obj_t *all_args) {

    espulp_ulpalarm_obj_t *self = m_new_obj(espulp_ulpalarm_obj_t);
    self->base.type = &espulp_ulpalarm_type;
    common_hal_espulp_ulpalarm_construct(self);
    return MP_OBJ_FROM_PTR(self);
}

const mp_obj_type_t espulp_ulpalarm_type = {
    { &mp_type_type },
    .name = MP_QSTR_ULPAlarm,
    .make_new = espulp_ulpalarm_make_new,
};
