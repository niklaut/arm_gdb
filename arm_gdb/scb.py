# SPDX-FileCopyrightText: 2023 Max Sikström
# SPDX-License-Identifier: MIT

# Copyright © 2023 Max Sikström
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the “Software”), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in
# all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED “AS IS”, WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.

import gdb
import argparse
from .common import *
import traceback

# Definition: B3.2.2
# https://developer.arm.com/documentation/ddi0403/latest/

# Implmementaitons:
# M3: https://developer.arm.com/documentation/dui0552/a/cortex-m3-peripherals/system-control-block
# M4: https://developer.arm.com/documentation/100166/0001/System-Control/System-control-registers
# M7: https://developer.arm.com/documentation/dui0646/c/Cortex-M7-Peripherals/System-control-block


def get_scb_regs(model):
    enum_val_en_dis = [
        (0, True, "Normal operation", None),
        (1, False, "Disabled", None)
    ]
    CPACR_enum_fields = [
        (0b00, True, "Access denied",
         "Any attempted access generates a NOCP UsageFault."),
        (0b01, True, "Privileged access only.",
         "An unprivileged access generates a NOCP UsageFault."),
        (0b10, True, "Reserved.", None),
        (0b11, True, "Full access.", None),
    ]

    return {
        'SCB': filt(model, [
            (None, RegisterDef("CPUID", "CPUID Base Register", 0xE000ED00, 4, [
                FieldBitfieldEnum("Implementer", 24, 8, [
                    (0x41, False, "ARM", None)
                ], "Implementer code assigned by Arm"),
                FieldBitfield("Variant", 20, 4),
                FieldBitfield("Architecture", 16, 4, "constant - 1111"),
                FieldBitfieldEnum("PartNo", 4, 12, [
                    (0xc20, False, "Cortex-M0", None),
                    (0xc23, False, "Cortex-M3", None),
                    (0xc24, False, "Cortex-M4", None),
                    (0xc27, False, "Cortex-M7", None),
                    (0xd21, False, "Cortex-M33", None)
                ]),
                FieldBitfield("Revision", 0, 4),
            ])),
            (None, RegisterDef("ICSR", "Interrupt Control and State Register", 0xE000ED04, 4, [
                FieldBitfield("NMIPENDSET", 31, 1),
                FieldBitfield("PENDSVSET", 28, 1),
                FieldBitfield("PENDSTSET", 26, 1),
                FieldBitfield("PENDSTCLR", 25, 1),
                FieldBitfield(
                    "ISRPREEMPT", 23, 1, "Indicates whether a pending exception will be serviced on exit from debug halt state"),
                FieldBitfield(
                    "ISRPENDING", 22, 1, "Indicates whether an external interrupt, generated by the NVIC, is pending"),
                FieldBitfield(
                    "VECTPENDING", 12, 6, "The exception number of the highest priority pending and enabled interrupt"),
                FieldBitfield(
                    "RETTOBASE", 11, 1, "In Handler mode, indicates whether there is an active exception other than the exception indicated by the current value of the IPSR"),
                FieldBitfield("VECTACTIVE", 0, 8),
            ])),
            (None, RegisterDef("VTOR", "Vector Table Offset Register", 0xE000ED08, 4, [
                FieldBitfield("TBLOFF", 7, 25,
                              "Bits[31:7] of the vector table address")
            ])),
            (None, RegisterDef("AIRCR", "Application Interrupt and Reset Control Register", 0xE000ED0C, 4, [
                FieldBitfieldEnum("VECTKEYSTAT", 16, 16, [
                    (0x05fa, True, "Register writes must write 0x05FA to this field, otherwise the write is ignored", None),
                    (0xfa05, True, "On reads, returns 0xFA05", None),
                ]),
                FieldBitfieldEnum("ENDIANNESS", 15, 1, [
                    (0, False, "Little Endian", None),
                    (1, False, "Big Endian", None),
                ]),
                FieldBitfield(
                    "PRIGROUP", 8, 3, "Priority grouping, indicates the binary point position."),
                FieldBitfield("SYSRESETREQ", 2, 1, "System Reset Request"),
            ])),
            (None, RegisterDef("SCR", "System Control Register", 0xE000ED10, 4, [
                FieldBitfield(
                    "SEVONPEND", 4, 1, "Determines whether an interrupt transition from inactive state to pending state is a wakeup event"),
                FieldBitfield(
                    "SLEEPDEEP", 2, 1, "Provides a qualifying hint indicating that waking from sleep might take longer"),
                FieldBitfield(
                    "SLEEPONEXIT", 1, 1, "Determines whether, on an exit from an ISR that returns to the base level of execution priority, the processor enters a sleep state"),
            ])),
            (None, RegisterDef("CCR", "Configuration and Control Register", 0xE000ED14, 4, filt(model, [
                ('M7', FieldBitfield("BP", 18, 1, "Branch prediction enable bit.")),
                ('M7', FieldBitfield("IC", 17, 1, "Instruction cache enable bit.")),
                ('M7', FieldBitfield("DC", 16, 1, "Cache enable bit.")),
                ('M3,M7', FieldBitfield("STKALIGN", 9, 1,
                 "Determines whether the exception entry sequence guarantees 8-byte stack frame alignment")),
                ('M3,M7', FieldBitfieldEnum("BFHFNMIGN", 8, 1, [
                    (0, False, "Precise data access fault causes a lockup", None),
                    (1, False, "Handler ignores the fault.", None),
                ], "Determines the effect of precise data access faults on handlers running at priority -1 or priority -2")),
                ('M3,M7', FieldBitfield("DIV_0_TRP", 4,
                 1, "Controls the trap on divide by 0")),
                ('M3,M7', FieldBitfield("UNALIGN_TRP", 3, 1,
                 "Controls the trapping of unaligned word or halfword accesses")),
                ('M3,M7', FieldBitfield("USERSETMPEND", 1, 1,
                 "Controls whether unprivileged software can access the STIR")),
                ('M3,M7', FieldBitfield("NONBASETHRDENA", 0, 1,
                 "Controls whether the processor can enter Thread mode with exceptions active")),
            ]))),
            (None, RegisterDef("SHPR1", "System Handler Priority Register 1", 0xE000ED18, 4, [
                FieldBitfield("PRI_4 - MemManage", 0, 8,
                              "Priority of system handler 4, MemManage."),
                FieldBitfield("PRI_5 - BusFault", 8, 8,
                              "Priority of system handler 5, BusFault."),
                FieldBitfield("PRI_6 - UsageFault", 16, 8,
                              "Priority of system handler 6, UsageFault."),
                FieldBitfield("PRI_7", 24, 8,
                              "Reserved for priority of system handler 7")
            ])),
            (None, RegisterDef("SHPR2", "System Handler Priority Register 2", 0xE000ED1C, 4, [
                FieldBitfield(
                    "PRI_8", 0, 8, "Reserved for priority of system handler 8."),
                FieldBitfield(
                    "PRI_9", 8, 8, "Reserved for priority of system handler 9."),
                FieldBitfield("PRI_10", 16, 8,
                              "Reserved for priority of system handler 10."),
                FieldBitfield("PRI_11 - SVCall", 24, 8,
                              "Priority of system handler 11, SVCall.")
            ])),
            (None, RegisterDef("SHPR3", "System Handler Priority Register 3", 0xE000ED20, 4, [
                FieldBitfield("PRI_12 - DebugMonitor", 0, 8,
                              "Priority of system handler 12, DebugMonitor."),
                FieldBitfield("PRI_13", 8, 8,
                              "Reserved for priority of system handler 13."),
                FieldBitfield("PRI_14 - PendSV", 16, 8,
                              "Priority of system handler 14, PendSV."),
                FieldBitfield("PRI_15 - SysTick", 24, 8,
                              "Priority of system handler 15, SysTick.")
            ])),
            (None, RegisterDef("SHCSR", "System Handler Control and State Register", 0xE000ED24, 4, [
                FieldBitfield("USGFAULTENA", 18, 1,
                              "Indicates if UsageFault is enabled."),
                FieldBitfield("BUSFAULTENA", 17, 1,
                              "Indicates if BusFault is enabled."),
                FieldBitfield("MEMFAULTENA", 16, 1,
                              "Indicates if MemFault is enabled."),
                FieldBitfield("SVCALLPENDED", 15, 1,
                              "Indicates if SVCall is pending."),
                FieldBitfield("BUSFAULTPENDED", 14, 1,
                              "Indicates if BusFault is pending"),
                FieldBitfield("MEMFAULTPENDED", 13, 1,
                              "Indicates if MemFault is pending"),
                FieldBitfield("USGFAULTPENDED", 12, 1,
                              "Indicates if UsageFault is pending"),
                FieldBitfield("SYSTICKACT", 11, 1,
                              "Indicates if SysTick is active"),
                FieldBitfield("PENDSVACT", 10, 1,
                              "Indicates if PendSV is active"),
                FieldBitfield("MONITORACT", 8, 1,
                              "Indicates if Monitor is active"),
                FieldBitfield("SVCALLACT", 7, 1,
                              "Indicates if SVCall is active"),
                FieldBitfield("USGFAULTACT", 3, 1,
                              "Indicates if UsageFault is active"),
                FieldBitfield("BUSFAULTACT", 1, 1,
                              "Indicates if BusFault is active"),
                FieldBitfield("MEMFAULTACT", 0, 1,
                              "Indicates if MemFault is active"),
            ])),
            (None, RegisterDef("CFSR", "Configurable Fault Status Register", 0xE000ED28, 4, [
                FieldBitfield("MMFSR",       0,    8,
                              "MemManage Fault Status Register", always=True),
                FieldBitfield("MMARVALID",   7+0,  1,
                              "Indicates if MMFAR has valid contents."),
                FieldBitfield("MLSPERR",     5+0,  1,
                              "Indicates if a MemManage fault occurred during FP lazy state preservation."),
                FieldBitfield("MSTKERR",     4+0,  1,
                              "Indicates if a derived MemManage fault occurred on exception entry."),
                FieldBitfield("MUNSTKERR",   3+0,  1,
                              "Indicates if a derived MemManage fault occurred on exception return."),
                FieldBitfield("DACCVIOL",    1+0,  1,
                              "Data access violation. The MMFAR shows the data address that the load or store tried to access."),
                FieldBitfield("IACCVIOL",    0+0,  1,
                              "MPU or Execute Never (XN) default memory map access violation on an instruction fetch has occurred."),
                FieldBitfield("BFSR",        8,    8,
                              "BusFault Status Register", always=True),
                FieldBitfield("BFARVALID",   7+8,  1,
                              "Indicates if BFAR has valid contents."),
                FieldBitfield("LSPERR",      5+8,  1,
                              "Indicates if a bus fault occurred during FP lazy state preservation."),
                FieldBitfield("STKERR",      4+8,  1,
                              "Indicates if a derived bus fault has occurred on exception entry."),
                FieldBitfield("UNSTKERR",    3+8,  1,
                              "Indicates if a derived bus fault has occurred on exception return."),
                FieldBitfield("IMPRECISERR", 2+8,  1,
                              "Indicates if imprecise data access error has occurred."),
                FieldBitfield("PRECISERR",   1+8,  1,
                              "Indicates if a precise data access error has occurred, and the processor has written the faulting address to the BFAR."),
                FieldBitfield("IBUSERR",     0+8,  1,
                              "Indicates if a bus fault on an instruction prefetch has occurred. The fault is signaled only if the instruction is issued."),
                FieldBitfield("UFSR",        16,  16,
                              "UsageFault Status Register", always=True),
                FieldBitfield("DIVBYZERO",   9+16, 1,
                              "Indicates if divide by zero error has occurred."),
                FieldBitfield("UNALIGNED",   8+16, 1,
                              "Indicates if unaligned access error has occurred."),
                FieldBitfield("NOCP",        3+16, 1,
                              "Indicates if a coprocessor access error has occurred. This shows that the coprocessor is disabled or not present."),
                FieldBitfield("INVPC",       2+16, 1,
                              "Indicates if an integrity check error has occurred on EXC_RETURN."),
                FieldBitfield("INVSTATE",    1+16, 1,
                              "Indicates if instruction executed with invalid EPSR.T or EPSR.IT field."),
                FieldBitfield("UNDEFINSTR",  0+16, 1,
                              "Indicates if the processor has attempted to execute an undefined instruction."),
            ])),
            (None, RegisterDef("HFSR", "HardFault Status Register", 0xE000ED2C, 4, [
                FieldBitfield("DEBUGEVT", 31, 1,
                              "Indicates when a Debug event has occurred."),
                FieldBitfield("FORCED", 30, 1,
                              "Indicates that a fault with configurable priority has been escalated to a HardFault exception."),
                FieldBitfield("VECTTBL", 1, 1,
                              "Indicates when a fault has occurred because of a vector table read error on exception processing."),
            ])),
            (None, RegisterDef("DFSR", "Debug Fault Status Register", 0xE000ED30, 4, [
                FieldBitfieldEnum("EXTERNAL", 4, 1, [
                    (0, True, "No external debug request debug event", None),
                    (1, False, "External debug request debug event", None),
                ], "Indicates a debug event generated because of the assertion of an external debug request"),
                FieldBitfieldEnum("VCATCH", 3, 1, [
                    (0, True, "No Vector catch triggered", None),
                    (1, False, "Vector catch triggered", None),
                ], "Indicates triggering of a Vector catch"),
                FieldBitfieldEnum("DWTTRAP", 2, 1, [
                    (0, True, "No debug events generated by the DWT", None),
                    (1, False, "At least one debug event generated by the DWT", None),
                ], "Indicates a debug event generated by the DWT"),
                FieldBitfieldEnum("BKPT", 1, 1, [
                    (0, True, "No breakpoint debug event", None),
                    (1, False, "At least one breakpoint debug event", None),
                ], "Indicates a debug event generated by BKPT instruction execution or a breakpoint match in FPB"),
                FieldBitfieldEnum("HALTED", 0, 1, [
                    (0, True, "No halt request debug event", None),
                    (1, False, "Halt request debug event", None),
                ], "Indicates a debug event generated by either C_HALT, C_STEP or DEMCR.MON_STEP"),
            ])),
            (None, RegisterDef("MMFAR", "MemManage Fault Address Register",
                               0xE000ED34, 4)),
            (None, RegisterDef("BFAR", "BusFault Address Register", 0xE000ED38, 4)),
            ('M3,M4', RegisterDef("AFSR", "Auxiliary Fault Status Register", 0xE000ED3C, 4, [
                FieldBitfield("IMPDEF", 0, 32, "Implemention defined"),
            ])),
            (None, RegisterDef("CPACR", "Coprocessor Access Control Register", 0xE000ED88, 4, [
                FieldBitfieldEnum("CP0", 0, 2, CPACR_enum_fields,
                                  "Access privileges for coprocessor 0"),
                FieldBitfieldEnum("CP1", 2, 2, CPACR_enum_fields,
                                  "Access privileges for coprocessor 1"),
                FieldBitfieldEnum("CP2", 4, 2, CPACR_enum_fields,
                                  "Access privileges for coprocessor 2"),
                FieldBitfieldEnum("CP3", 6, 2, CPACR_enum_fields,
                                  "Access privileges for coprocessor 3"),
                FieldBitfieldEnum("CP4", 8, 2, CPACR_enum_fields,
                                  "Access privileges for coprocessor 4"),
                FieldBitfieldEnum("CP5", 10, 2, CPACR_enum_fields,
                                  "Access privileges for coprocessor 5"),
                FieldBitfieldEnum("CP6", 12, 2, CPACR_enum_fields,
                                  "Access privileges for coprocessor 6"),
                FieldBitfieldEnum("CP7", 14, 2, CPACR_enum_fields,
                                  "Access privileges for coprocessor 7"),
                FieldBitfieldEnum("CP10", 20, 2, CPACR_enum_fields,
                                  "Access privileges for coprocessor 10"),
                FieldBitfieldEnum("CP11", 22, 2, CPACR_enum_fields,
                                  "Access privileges for coprocessor 11"),
            ]))
        ]),
        'AUX': filt(model, [
            (None, RegisterDef("ICTR", "Interrupt Controller Type Register", 0xE000E004, 4, [
                FieldBitfieldMap("INTLINESNUM", 0, 4, lambda v: "%d vectors" % (min(32*(v+1), 496),),
                                 "The total number of interrupt lines supported, as 32*(1+N)")
            ])),
            ('M3', RegisterDef("ACTLR - M3", "Auxiliary Control Register - Cortex M3", 0xE000E008, 4, [
                FieldBitfield("DISFOLD", 2, 1),
                FieldBitfield("DISDEFWBUF", 1, 1),
                FieldBitfield("DISMCYCINT", 0, 1),
            ])),
            ('M4', RegisterDef("ACTLR - M4", "Auxiliary Control Register - Cortex M4", 0xE000E008, 4, [
                FieldBitfield("DISOOFP", 9, 1),
                FieldBitfield("DISFPCA", 8, 1),
                FieldBitfield("DISFOLD", 2, 1),
                FieldBitfield("DISDEFWBUF", 1, 1),
                FieldBitfield("DISMCYCINT", 0, 1),
            ])),
            ('M7', RegisterDef("ACTLR - M7", "Auxiliary Control Register - Cortex M7", 0xE000E008, 4, [
                FieldBitfield("DISFPUISSOPT", 28, 1),
                FieldBitfield("DISCRITAXIRUW", 27, 1),
                FieldBitfield("DISDYNADD", 26, 1),
                FieldBitfield("DISISSCH1", 21, 5, always=True),
                FieldBitfieldEnum(
                    "    VFP", 25, 1, [
                        (0, True, "Normal operation", None),
                        (1, False, "might not be issued in channel 1.", None)
                    ], "VFP"),
                FieldBitfieldEnum(
                    "    MAC and MUL", 24, 1, [
                        (0, True, "Normal operation", None),
                        (1, False, "might not be issued in channel 1.", None)
                    ], "Integer MAC and MUL"),
                FieldBitfieldEnum(
                    "    Loads to PC", 23, 1, [
                        (0, True, "Normal operation", None),
                        (1, False, "might not be issued in channel 1.", None)
                    ], "Loads to PC"),
                FieldBitfieldEnum(
                    "    Indirect branches", 22, 1, [
                        (0, True, "Normal operation", None),
                        (1, False, "might not be issued in channel 1.", None)
                    ], "Indirect branches, but not loads to PC"),
                FieldBitfieldEnum(
                    "    Direct branches", 21, 1, [
                        (0, True, "Normal operation", None),
                        (1, False, "might not be issued in channel 1.", None)
                    ], "Direct branches"),
                FieldBitfield("DISDI", 16, 5, always=True),
                FieldBitfieldEnum(
                    "    VFP", 20, 1, [
                        (0, True, "Normal operation", None),
                        (1, False, "Dual issue disabled",
                         "Nothing can be dual-issued when this instruction type is in channel 0.")
                    ], "VFP"),
                FieldBitfieldEnum(
                    "    Integer MAC and MUL", 19, 1, [
                        (0, True, "Normal operation", None),
                        (1, False, "Dual issue disabled",
                         "Nothing can be dual-issued when this instruction type is in channel 0.")
                    ], "Integer MAC and MUL"),
                FieldBitfieldEnum(
                    "    Loads to PC", 18, 1, [
                        (0, True, "Normal operation", None),
                        (1, False, "Dual issue disabled",
                         "Nothing can be dual-issued when this instruction type is in channel 0.")
                    ], "Loads to PC"),
                FieldBitfieldEnum(
                    "    Indirect branches", 17, 1, [
                        (0, True, "Normal operation", None),
                        (1, False, "Dual issue disabled",
                         "Nothing can be dual-issued when this instruction type is in channel 0.")
                    ], "Indirect branches, but not loads to PC"),
                FieldBitfieldEnum(
                    "    Direct branches", 16, 1, [
                        (0, True, "Normal operation", None),
                        (1, False, "Disabled", None)
                    ], "Direct branches"),
                FieldBitfield("DISCRITAXIRUR", 15, 1),
                FieldBitfield("DISBTACALLOC", 14, 1),
                FieldBitfield("DISBTACREAD", 13, 1),
                FieldBitfield("DISITMATBFLUSH", 12, 1),
                FieldBitfield("DISRAMODE", 11, 1),
                FieldBitfield("FPEXCODIS", 10, 1),
                FieldBitfield("DISFOLD", 2, 1),
            ]))
        ])
    }


def get_fpu_regs():
    return [
        RegisterDef("FPCCR", "Floating Point Context Control Register", 0xE000EF34, 4, [
            FieldBitfield("ASPEN",  31, 1,
                          "When this bit is set to 1, execution of a floating-point instruction sets the CONTROL.FPCA bit to 1"),
            FieldBitfield("LSPEN",  30, 1,
                          "Enables lazy context save of FP state"),
            FieldBitfield("MONRDY",  8, 1,
                          "Indicates whether the software executing when the processor allocated the FP stack frame was able to set the DebugMonitor exception to pending"),
            FieldBitfield("BFRDY",   6, 1,
                          "Indicates whether the software executing when the processor allocated the FP stack frame was able to set the BusFault exception to pending"),
            FieldBitfield("MMRDY",   5, 1,
                          "Indicates whether the software executing when the processor allocated the FP stack frame was able to set the MemManage exception to pending"),
            FieldBitfield("HFRDY",   4, 1,
                          "Indicates whether the software executing when the processor allocated the FP stack frame was able to set the HardFault exception to pending"),
            FieldBitfield("THREAD",  3, 1,
                          "Indicates the processor mode when it allocated the FP stack frame"),
            FieldBitfield("USER",    1, 1,
                          "Indicates the privilege level of the software executing when the processor allocated the FP stack frame"),
            FieldBitfield("LSPACT",  0, 1,
                          "Indicates whether Lazy preservation of the FP state is active"),
        ]),
        RegisterDef("FPCAR", "Floating Point Context Address Register", 0xE000EF38, 4, [
            FieldBitfield("FPCAR", 2, 28,
                          "The location of the unpopulated floating-point register space allocated on an exception stack frame.")
        ]),
        RegisterDef("FPDSCR", "Floating Point Default Status Control Register", 0xE000EF3C, 4, [
            FieldBitfield("AHP",   26, 1, "Default value for FPSCR.AHP"),
            FieldBitfield("DN",    25, 1, "Default value for FPSCR.DN"),
            FieldBitfield("FZ",    24, 1, "Default value for FPSCR.FZ"),
            FieldBitfield("RMode", 22, 2, "Default value for FPSCR.RMode"),
        ]),
        RegisterDef("MVFR0", "Media and FP Feature Register 0", 0xE000EF40, 4, [
            FieldBitfieldEnum("FP rounding modes", 28, 4, [
                (0b0000, True, "Not supported", None),
                (0b0001, True, "All rounding modes supported.", None),
            ], "Indicates the rounding modes supported by the FP floating-point hardware."),
            FieldBitfieldEnum("Short vectors", 24, 4, [
                (0b0000, True, "Not supported", None),
                (0b0001, False, "Supported", None)
            ]),
            FieldBitfieldEnum("Square root", 20, 4, [
                (0b0000, True, "Not supported", None),
                (0b0001, False, "Supported", None)
            ]),
            FieldBitfieldEnum("Divide", 16, 4, [
                (0b0000, True, "Not supported", None),
                (0b0001, False, "Supported", None)
            ]),
            FieldBitfieldEnum("FP exception trapping", 12, 4, [
                (0b0000, True, "Not supported", None),
            ]),
            FieldBitfieldEnum("Double-precision",  8, 4, [
                (0b0000, True, "Not supported", None),
                (0b0010, False, "Supported", None)
            ]),
            FieldBitfieldEnum("Single-precision",  4, 4, [
                (0b0000, True, "Not supported", None),
                (0b0010, False, "Supported.",
                 "FP adds an instruction to load a single-precision floating-point constant, and conversions between single-precision and fixed-point values."),
            ], "Indicates the hardware support for FP single-precision operations."),
            FieldBitfieldEnum("A_SIMD registers",  0, 4, [
                (0b0000, True, "Not supported", None),
                (0b0001, False, "Supported, 16 x 64-bit registers.", None),
            ]),
        ]),
        RegisterDef("MVFR1", "Media and FP Feature Register 1", 0xE000EF44, 4, [
            FieldBitfieldEnum("FP fused MAC", 28, 4, [
                (0b0000, True, "Not supported", None),
                (0b0001, False, "Supported", None)
            ]),
            FieldBitfieldEnum("FP HPFP", 24, 4, [
                (0b0000, True, "Not supported", None),
                (0b0001, False, "Supported half-single",
                 "Supports conversion between half-precision and single-precision."),
                (0b0010, False, "Supported half-single-double",
                 "Supports conversion between half-precision and single-precision0b0001, and also supports conversion between half-precision and double-precision."),
            ], "Floating Point half-precision and double-precision. Indicates whether the FP extension implements half-precision and double-precision floating-point conversion instructions."),
            FieldBitfieldEnum("D_NaN mode",  4, 4, [
                (0b0000, True, "Not supported", None),
                (0b0001, False, "Hardware supports propagation of NaN values.", None),
            ], "Indicates whether the FP hardware implementation supports only the Default NaN mode."),
            FieldBitfieldEnum("FtZ mode",  0, 4, [
                (0b0000, True, "Not supported", None),
                (0b0001, False, "Hardware supports full denormalized number arithmetic.", None),
            ], "Indicates whether the FP hardware implementation supports only the Flush-to-zero mode of operation."),
        ]),
        RegisterDef("MVFR2", "Media and FP Feature Register 2", 0xE000EF48, 4, [
            FieldBitfieldEnum("VFP_Misc",  4, 4, [
                (0b0000, True, "No support for miscellaneous features.", None),
                (0b0100, False, "Support for miscellaneous features.",
                 "Support for floating-point selection, floating-point conversion to integer with direct rounding modes, floating-point round to integral floating-point, and floating-point maximum number and minimum number."),
            ], "Indicates the hardware support for FP miscellaneous features"),
        ]),
    ]


class ArmToolsSCB (ArgCommand):
    """Dump of ARM Cortex-M SCB - System Control Block

Usage: arm scb [/habf]

Modifier /h provides descriptions of names where available
Modifier /a Print all fields, including default values
Modifier /b prints bitmasks in binary instead of hex
Modifier /f force printing fields from all Cortex-M models
"""

    def __init__(self):
        super().__init__('arm scb', gdb.COMMAND_DATA)
        self.add_mod('h', 'descr')
        self.add_mod('a', 'all')
        self.add_mod('b', 'binary')
        self.add_mod('f', 'force')

    def invoke(self, argument, from_tty):
        args = self.process_args(argument)
        if args is None:
            self.print_help()
            return

        base = 1 if args['binary'] else 4

        inf = gdb.selected_inferior()

        # Detect CPU type, convert to a useful key for dicts
        CPUID = read_reg(inf, 0xE000ED00, 4)
        impl_partno_idx = format_int(CPUID & 0xff00fff0, 32)
        model = {
            "4100c200": "M0",
            "4100c230": "M3",
            "4100c240": "M4",
            "4100c270": "M7",
            "4100d210": "M33"
        }.get(impl_partno_idx, None)

        print("SCB for model", model if model else "unknown")
        if args['force']:
            print("(printing fields from all Cortex-M models)")
            model = None

        try:
            regs = get_scb_regs(model)
        except:
            traceback.print_exc()

        for sect_name, sect_regs in regs.items():
            print("")
            print("%s registers:" % (sect_name,))
            for reg in sect_regs:
                reg.dump(inf, args['descr'], base=base, all=args['all'])


class ArmToolsFPU (ArgCommand):
    """Dump of ARM Cortex-M FPU - SCB registers for the FP extension

Usage: arm fpu [/hab]

Modifier /h provides descriptions of names where available
Modifier /a Print all fields, including default values
Modifier /b prints bitmasks in binary instead of hex
"""

    def __init__(self):
        super().__init__('arm fpu', gdb.COMMAND_DATA)
        self.add_mod('h', 'descr')
        self.add_mod('a', 'all')
        self.add_mod('b', 'binary')

    def invoke(self, argument, from_tty):
        args = self.process_args(argument)
        if args is None:
            self.print_help()
            return

        base = 1 if args['binary'] else 4

        inf = gdb.selected_inferior()

        print("SCB FP registers:")

        try:
            regs = get_fpu_regs()
        except:
            traceback.print_exc()

        for reg in regs:
            reg.dump(inf, args['descr'], base=base, all=args['all'])
