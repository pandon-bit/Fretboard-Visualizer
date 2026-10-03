# ==============================================================================
# Makefile — Cross-Platform Build for fretboard_math Shared Library
# Targets: Windows (.dll), Linux (.so), macOS (.dylib)
# ==============================================================================

CXX ?= g++
CXXFLAGS ?= -O3 -Wall -Wextra -std=c++17 -fPIC
CPPFLAGS ?= -DFRETENGINE_EXPORTS -I.

SRC = fretboard_math.cpp

# Platform detection
ifeq ($(OS),Windows_NT)
    TARGET = fretboard_math.dll
    LDFLAGS = -shared -Wl,--out-implib,libfretboard_math.a
    RM = del /Q /F
else
    UNAME_S := $(shell uname -s)
    ifeq ($(UNAME_S),Darwin)
        TARGET = libfretboard_math.dylib
        LDFLAGS = -shared -dynamiclib
    else
        TARGET = libfretboard_math.so
        LDFLAGS = -shared -Wl,-soname,$(TARGET)
    endif
    RM = rm -f
endif

.PHONY: all clean

all: $(TARGET)

$(TARGET): $(SRC) fretboard_math.h
	$(CXX) $(CXXFLAGS) $(CPPFLAGS) $(SRC) $(LDFLAGS) -o $(TARGET)
	@echo Successfully built shared library: $(TARGET)

clean:
	$(RM) $(TARGET) *.o *.a *.dll *.so *.dylib 2>nul || true
