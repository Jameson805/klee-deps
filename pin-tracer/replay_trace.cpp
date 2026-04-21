#include "pin.H"

#include <fstream>
#include <iostream>
#include <string>

namespace {

KNOB<std::string> knob_output(
    KNOB_MODE_WRITEONCE,
    "pintool",
    "o",
    "replay_trace.log",
    "Path to the replay trace log"
);

std::ofstream trace_stream;

VOID record_instruction(ADDRINT ip) {
    trace_stream << "I " << std::showbase << std::hex << ip << '\n';
}

VOID record_read(ADDRINT ip, ADDRINT address) {
    trace_stream << "R " << std::showbase << std::hex << ip << ' ' << address << '\n';
}

VOID record_write(ADDRINT ip, ADDRINT address) {
    trace_stream << "W " << std::showbase << std::hex << ip << ' ' << address << '\n';
}

VOID instrument_instruction(INS ins, VOID *) {
    INS_InsertCall(ins, IPOINT_BEFORE, AFUNPTR(record_instruction), IARG_INST_PTR, IARG_END);

    const UINT32 operand_count = INS_MemoryOperandCount(ins);
    for (UINT32 operand_index = 0; operand_index < operand_count; ++operand_index) {
        if (INS_MemoryOperandIsRead(ins, operand_index)) {
            INS_InsertPredicatedCall(
                ins,
                IPOINT_BEFORE,
                AFUNPTR(record_read),
                IARG_INST_PTR,
                IARG_MEMORYOP_EA,
                operand_index,
                IARG_END
            );
        }
        if (INS_MemoryOperandIsWritten(ins, operand_index)) {
            INS_InsertPredicatedCall(
                ins,
                IPOINT_BEFORE,
                AFUNPTR(record_write),
                IARG_INST_PTR,
                IARG_MEMORYOP_EA,
                operand_index,
                IARG_END
            );
        }
    }
}

VOID finish(INT32, VOID *) {
    trace_stream.flush();
    trace_stream.close();
}

}  // namespace

int main(int argc, char *argv[]) {
    if (PIN_Init(argc, argv)) {
        return 1;
    }

    trace_stream.open(knob_output.Value().c_str(), std::ios::out | std::ios::trunc);
    if (!trace_stream.is_open()) {
        std::cerr << "Failed to open trace output: " << knob_output.Value() << std::endl;
        return 1;
    }

    INS_AddInstrumentFunction(instrument_instruction, 0);
    PIN_AddFiniFunction(finish, 0);
    PIN_StartProgram();
    return 0;
}
