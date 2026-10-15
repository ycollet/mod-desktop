# Native Linux development build. The portable release build remains in Makefile.
ifeq (,$(findstring linux,$(shell $(CC) -dumpmachine)))
$(error SYSTEM_DEPS=1 is only supported for native Linux builds)
endif

.DEFAULT_GOAL := all
PYTHON ?= python3
PKG_CONFIG ?= pkg-config
MOD_UI_DIR ?= $(CURDIR)/src/mod-ui
export CC CXX CFLAGS CXXFLAGS LDFLAGS PKG_CONFIG MOD_UI_DIR
# Let component Makefiles append their required flags to user-supplied flags.
MAKEOVERRIDES :=
SYSTEM_BUILD := $(CURDIR)/build-system
SYSTEM_PACKAGES := jack lilv-0 lv2 alsa portaudio-2.0 Qt5Core Qt5Gui Qt5Svg Qt5Widgets

.PHONY: all check-system-deps check-system-python system-host system-utils system-midi system-launcher system-stage run clean

all: system-stage

check-system-deps:
	$(PKG_CONFIG) --print-errors --exists $(SYSTEM_PACKAGES)
	@command -v cmake >/dev/null || { echo "cmake is required" >&2; exit 1; }

check-system-python:
	$(PYTHON) -c 'import aggdraw, PIL, tornado, Cryptodome'
	$(PYTHON) utils/linux/system-build.py check-python $(SYSTEM_BUILD)

system-host system-utils system-launcher: check-system-deps

system-host:
	$(PYTHON) utils/linux/system-build.py prepare $(SYSTEM_BUILD) $@
	$(MAKE) -C $(SYSTEM_BUILD)/src/mod-host SKIP_READLINE=1 SKIP_FFTW335=1 MOD_DESKTOP=0 mod-host

system-utils:
	$(PYTHON) utils/linux/system-build.py prepare $(SYSTEM_BUILD) $@
	$(MAKE) -C $(SYSTEM_BUILD)/src/mod-utils MOD_DESKTOP=1

system-launcher:
	$(PYTHON) utils/linux/system-build.py prepare $(SYSTEM_BUILD) $@
	$(MAKE) -C $(SYSTEM_BUILD)/src/systray SYSTEM_DEPS=1

system-midi: check-system-deps
	cmake -S src/mod-midi-merger -B $(SYSTEM_BUILD)/midi -DCMAKE_BUILD_TYPE=Release -DCMAKE_C_COMPILER="$(CC)" -DCMAKE_POLICY_VERSION_MINIMUM=3.5
	cmake --build $(SYSTEM_BUILD)/midi --target mod-midi-merger-standalone mod-midi-broadcaster-standalone

system-stage: check-system-python system-host system-utils system-midi system-launcher
	$(PYTHON) utils/linux/system-build.py stage $(SYSTEM_BUILD) "$(PYTHON)"

run: all
	$(SYSTEM_BUILD)/mod-desktop

clean:
	$(PYTHON) utils/linux/system-build.py clean $(SYSTEM_BUILD)
