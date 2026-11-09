# Lap-timing transponder (CH32V003J4M6). Needs ch32fun and a RISC-V GCC:
#   git clone https://github.com/cnlohr/ch32fun ~/ch32fun
#   make build      build
#   make flash CAR=3   flash through a WCH-LinkE (minichlink, from ch32fun) as car 3 (1..15);
#                      without CAR the board's solder jumpers pick the number
# ESP-IDF's RISC-V GCC does the job (rv32ec / ilp32e):
#   PATH=~/.espressif/tools/riscv32-esp-elf/<version>/riscv32-esp-elf/bin:$PATH make build PREFIX=riscv32-esp-elf

all : flash

TARGET := transponder
TARGET_MCU := CH32V003
TARGET_MCU_PACKAGE := CH32V003J4M6
CH32FUN ?= $(HOME)/ch32fun/ch32fun
CAR ?= 0
EXTRA_CFLAGS += -DCAR_ID=$(CAR)

include $(CH32FUN)/ch32fun.mk

# Rebuild every time: the car number is compiled in.
flash :
	$(MAKE) cv_clean
	$(MAKE) cv_flash
clean : cv_clean
