# Host tests for the decoder and lap tracker: make -C test
CC ?= cc
CFLAGS ?= -std=c11 -O2 -Wall -Wextra -Werror

run: test_lap_arch
	./test_lap_arch

test_lap_arch: test_lap_arch.c ../main/ir_decode.c ../main/laps.c ../main/ir_decode.h ../main/laps.h
	$(CC) $(CFLAGS) -o $@ test_lap_arch.c ../main/ir_decode.c ../main/laps.c

clean:
	rm -f test_lap_arch

.PHONY: run clean
