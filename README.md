# MOD Desktop

**MOD Audio is on the desktop!**

This is the source code repository for MOD Desktop, a little tool by [MOD Audio](https://mod.audio/) that combines all the goodies from MOD for the desktop platform packaged in a convenient installer.

![screenshot](mod-desktop.png "mod-desktop")

What this actually means is that you get a virtual pedalboard setup in a node/patchbay-like fashion, where you load "pedals" which are basically just LV2 audio plugins.  
Everything is drag & drop based, so you drop plugins from the bottom plugin bar into the main pedalboard view (called "constructor") and then drag & drop output-facing cables into either other plugins or the right side of the constructor.  
Unlike typical physical pedalboards where the signal flows from right to left, on MOD Desktop the signal flows from left to right as that is more common on desktop UIs.

See [https://wiki.mod.audio/wiki/MOD_Web_GUI_User_Guide](https://wiki.mod.audio/wiki/MOD_Web_GUI_User_Guide) for a more in-depth explanation of UI details, though please note a few things will not be the same due to platform differences.

## Download

MOD Desktop has builds for:

- Linux x86_64
- macOS universal (Intel + Apple Sillicon)
- Windows 64bit

You can find them in the [releases section](https://github.com/moddevices/mod-desktop/releases).

These downloads contain both MOD Desktop and a couple of plugins ready for usage.

## Installing

Installation depends on your operating system.

For **Linux** systems we currently provide a binary tarball, you just extract and run the startup script inside.
Eventually we want to have MOD Desktop under Flathub, please get in touch if you want to help make that happen.

For **macOS** we provide a signed pkg installer, compatible with both Intel and Apple Sillicon systems.
Double-click the package to install.
After installation you can find "MOD Desktop" under your "Applications" folder.  

And finally for **Windows** there is a simple installer executable, that shows an installer wizard as typical for most Windows applications.

## Usage

By default MOD Desktop will show you as few controls as possible, to not get in the way.
You just need to pick a soundcard you wish to use and press "Start".
This will start up the audio engine and (local) web service that manages the session and plugins.

Once the engine is running, click the "Open Web GUI" button to open the MOD UI view in your default web browser.  
NOTE: even though this uses a web browser, the page is being served locally; the use of web technologies is an intentional design choice for making the UI cross-platform compatible.

If anything fails you can enable debug logs in the "GUI Options" section, that might provide some information.

MOD Desktop will close to the "system tray" by default, but this can also be changed in the "GUI Options".

### Handling files

There are a few plugins on the MOD platform, like AIDA-X and NAM, that load external files.
On their GUIs they will list the files as available under $Documents/MOD Desktop/user-files directory (the actual file path depends on the operating system).

You are meant to copy the files you wish to load into the relevant directory for them.
For convenience, MOD Desktop includes a "Open User Files" button that will automatically open your file explorer in the directory dedicated to such files.
So when wishing to load NAM models for the "Neural Amp Modeller" plugin for example, simply copy your model files into the "NAM Models" subdirectory.

![screenshot](docs/user-files-1.png "user-files-1")

![screenshot](docs/user-files-2.png "user-files-2")

### Your own plugins

MOD Desktop also loads LV2 plugins you build or download yourself, built natively for your computer.
Copy the `.lv2` bundle into `$Documents/MOD Desktop/lv2` and restart the audio.
See [docs/plugins.md](docs/plugins.md) for what to build, where MOD Desktop looks, and what to check when a plugin does not load.

## Current status

At this point this tool should be considered in beta state.
Most things already work but we are still tweaking and fixing a lot, specially due to MOD related software and plugins never been tested on Windows systems before.
Feedback and testing is very much appreciated, make sure to report issues you find during your own testing.
When reporting issues make sure to create 1 ticket per issue, and give some information about your system (what OS and version, what soundcard you use)

Current known issues:

- Handling of Windows filepaths is not always correct (differences between POSIX vs Windows path separators)
- When mod-host crashes it will stop the UI process, instead of being automatically restarted like in MOD units

## mod-ui: one code base with MOD OS

MOD Desktop ships the same [mod-ui](https://github.com/mod-audio/mod-ui) as the MOD devices, from the
**same commit as the MOD OS release line it belongs to** (`hotfix-<version>` in mod-ui). Rules:

- `src/mod-ui` always points at a commit on the current release line of mod-ui. Never at `master`,
  never at a Desktop-only branch. Bumping the pin is how a mod-ui fix reaches the Desktop.
- Desktop-only behaviour is implemented **in mod-ui**, behind `MOD_DESKTOP=1` (set by the launcher),
  and is inert on devices. This repository never carries a modified copy of a mod-ui file; it only
  decides what gets packaged (`utils/pack-html.sh`, `utils/win64/win64-installer.iss`,
  `utils/macos/macos-pkg.sh`). When mod-ui gains a new directory under `html/`, the packagers must
  learn it; a package is verified by inspecting its payload, not by its exit status.
- `VERSION` holds the version, `0.<MOD OS line>.<build>` (since 0.14.1): `0` while MOD Desktop is in beta,
  the MOD OS line whose mod-ui it pins (`14` = MOD OS 1.14), and a build number that restarts at 1 on each
  new line and only goes up (published builds may skip numbers). Versions compare as numbers, never as text.
  Before 0.14.1 the scheme was `0.0.N` (last: 0.0.13; test builds 0.0.14.N). It shows in the web UI's address bar
  (`?v=`), in the launcher's settings dialog and in every package name, so a report can always be
  tied to a build. The launcher and the plugin compile it in; changing `VERSION` rebuilds both.
- The Tone3000 client id is a publishable identifier passed as `MOD_TONE3000_CLIENT_ID` in the
  environment at freeze time and baked into the frozen mod-ui; it is never committed.

See `CONTRIBUTING.md` in mod-ui for the branch model and how a change travels to both products.

## Development

### Native Linux build with system dependencies (experimental)

`SYSTEM_DEPS=1` uses the native compiler, system development libraries, and
system Python packages instead of PawPaw. The default portable build is unchanged.
This mode connects to an **already running JACK or PipeWire-JACK server**; it
does not build, bundle, start, or stop JACK. A PipeWire JACK compatibility package
is sufficient: a separate `jackd` installation is not required.

On Fedora, install the build and Python dependencies:

```sh
sudo dnf install gcc gcc-c++ make cmake pkgconf-pkg-config \
    pipewire-jack-audio-connection-kit-devel alsa-lib-devel portaudio-devel \
    lilv-devel lv2-devel qt5-qtbase-devel qt5-qtsvg-devel \
    python3 python3-aggdraw python3-pillow python3-tornado python3-pycryptodomex
```

Modern Tornado requires a compatible mod-ui checkout. The release-pinned
`src/mod-ui` still uses Tornado 4 APIs; building against current Fedora packages
requires the Fedora port, including its corrected coroutine and stream-callback
compatibility support. Use `MOD_UI_DIR` to select that checkout without changing
the release submodule pin:

```sh
make SYSTEM_DEPS=1 MOD_UI_DIR=../mod-ui
make SYSTEM_DEPS=1 MOD_UI_DIR=../mod-ui run
```

The selected checkout supplies the UI features as well as its compatibility
code; the Fedora branch currently has an older baseline than the release pin.

`CC`, `CXX`, `CFLAGS`, `CXXFLAGS`, `LDFLAGS`, `PKG_CONFIG`, and `PYTHON` can be
provided through the usual make/environment settings. Outputs are isolated under
`build-system/`; the Make-based native components currently rebuild on each
invocation to avoid mixing bundled and system objects. The staged runtime refers
to the source checkouts, so it is a development build, not a relocatable package.
Use `make SYSTEM_DEPS=1 clean` to remove only these outputs.

The launcher runs mod-host and the MIDI merger/broadcaster as standalone clients.
Device, sample-rate, buffer-size, and MIDI-backend selection belong to the
external server; launcher controls for selecting its hardware/backend are
disabled. For PipeWire, select the default input/output devices externally.
The launcher enables `jack.default-as-system` for its clients so saved
pedalboards can continue to use `system:capture_*` and `system:playback_*`.
Other `PIPEWIRE_PROPS` settings are retained; `JACK_DEFAULT_SERVER` selects a
non-default classic JACK server. Stop the standalone MOD services first if
another mod-ui installation is already running.

The bundled plugin collection, MOD Desktop plugin variant, and portable
installers are not built in this mode. Install LV2 plugins separately; system
plugins and plugins without MOD-specific GUIs are shown by default. The
launcher still allows changing these plugin filters. With no supplied
`LV2_PATH`, discovery includes `~/.lv2`, `/usr/local/lib/lv2`, `/usr/lib/lv2`,
and their `lib64` counterparts. An explicit `LV2_PATH` supplies the system
search directories instead.

Build/runtime staging and client cleanup regression tests:

```sh
python3 -m unittest discover -s tests -p 'test_system_build.py'
```

If you want to contribute, here are a few items where help would be appreciated:

- Debugging and fixing Windows specific issues within mod-ui (*)
- Documentation regarding "universal" ASIO drivers, like ASIO4ALL and FlexASIO, and how to set them nicely for MOD Desktop

(*) Note: on Windows the default installation has html/css/js files in `C:\Program Files\MOD Desktop\html` and python files in `C:\Program Files\MOD Desktop\mod`, which can be directly modified, making it very easy and convenient to try out any changes.

Also help in these areas, but they are much more involved:
- Create a JACK-API-compatible node-based audio graph, to be used for eventually running "mod-desktop as a plugin" (there are a few opensource libs for this already, like the one included in miniaudio)
- Create a virtual sound device for macOS that can send audio into a JACK client, similar to JACK-Router and WineASIO projects

## License

MOD Desktop is licensed under AGPLv3+, see [LICENSE](LICENSE) for more details.

That licence does not cover the logo. The MOD logo is a registered trademark (EU trade mark no. 016228827; UK trade mark no. UK00916228827). See [TRADEMARKS.md](TRADEMARKS.md).
