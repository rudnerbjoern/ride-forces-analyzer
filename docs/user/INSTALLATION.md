# Install Ride Forces Analyzer

<!-- cspell:words libegl libopengl libxcb libxkbcommon icccm keysyms -->

Download your platform's package and checksum file from
[GitHub Releases](https://github.com/rudnerbjoern/ride-forces-analyzer/releases).
The application includes Python; no Python installation or setup script is needed.
In commands below, replace `VERSION` with the downloaded version, such as `0.6.0`.

## Windows 10/11 x64

1. Choose **Complete ZIP** for video export with bundled FFmpeg, **Standard ZIP**
   for your existing FFmpeg, or the standalone **EXE**.
2. Compare the downloaded file's SHA-256 with its entry in `WINDOWS-SHA256SUMS.txt`;
   PowerShell's `Get-FileHash -Algorithm SHA256` computes the hash for a chosen file.
3. Extract the ZIP completely and run its EXE, or run the standalone EXE directly.
   Keep the complete package's `ffmpeg.exe` beside the application.
4. Windows binaries are unsigned. For a verified download you trust, a SmartScreen
   warning may offer **More info → Run anyway**. Availability depends on device
   policy; do not disable SmartScreen globally. See
   [Microsoft's SmartScreen guidance](https://learn.microsoft.com/en-us/windows/apps/package-and-deploy/publish-first-app#step-6-handle-smartscreen-for-new-apps).

## Ubuntu 24.04 x64

A desktop session and glibc 2.39 or newer are required. Install the desktop libraries:

```sh
sudo apt update
sudo apt install libegl1 libopengl0 libxcb-cursor0 libxcb-icccm4 \
    libxcb-keysyms1 libxcb-image0 libxcb-render-util0 libxkbcommon-x11-0
```

Download the tarball and `LINUX-X64-SHA256SUMS.txt` into the same directory and verify:

```sh
sha256sum -c LINUX-X64-SHA256SUMS.txt
```

After the checksum passes, extract and launch:

```sh
tar -xzf Ride-Forces-Analyzer-VERSION-linux-x64.tar.gz
cd Ride-Forces-Analyzer
./Ride-Forces-Analyzer
```

Keep `_internal` beside the executable.

## macOS 15 or newer

1. Choose `macos-arm64.zip` for **Apple Silicon** or `macos-x64.zip` for **Intel**.
   Download the matching `MACOS-ARM64-SHA256SUMS.txt` or `MACOS-X64-SHA256SUMS.txt`.
2. In the download directory, run `shasum -a 256 -c MACOS-ARM64-SHA256SUMS.txt`
   (use `MACOS-X64-SHA256SUMS.txt` for Intel). Continue after the checksum passes.
3. Extract the ZIP, move `Ride-Forces-Analyzer.app` to **Applications** and open it.
4. Apps are ad-hoc signed, without Apple Developer ID signing or notarization.
   If macOS blocks the trusted app, open **System Settings → Privacy & Security →
   Open Anyway**, authenticate if requested and confirm opening it. This option
   appears after attempting to open the app. See
   [Apple's opening instructions](https://support.apple.com/en-ie/102445).
   Keep Gatekeeper enabled; no terminal security override is required.

## Enable video export

Windows Complete ZIP includes FFmpeg. Other Windows downloads, Linux and macOS
need a compatible external FFmpeg installation:

- Ubuntu: `sudo apt install ffmpeg`.
- macOS with Homebrew already installed: `brew install ffmpeg`.
- Windows: use the Complete ZIP or select an existing `ffmpeg.exe`.

In **Export 4K…**, use **Browse** to select the FFmpeg executable if automatic
discovery does not find it. Finder launches may not include Homebrew in PATH.
CPU H.264 and ProRes 4444 export do not require an NVIDIA GPU. Installed recording
processing and video export work offline.

## Open your first recording

Click **Open recording** and choose a `.forces` or `.zforces` file exported from the Ride Forces
app. Follow [Explore a recording](EXPLORER.md) for chart navigation, selection,
settings and GPS, or the [video export guide](VIDEO_EXPORT.md) to create an overlay.

## Check for updates

Open **About… → Check for updates…** to check for a newer release for your
platform. **Check for updates at startup (once per day)** enables optional
automatic checks; it is off by default. An unavailable check is not confirmation
that your version is current. You can retry later or visit GitHub Releases.

Updates are not installed automatically. Close the application, download and
verify the new package, and extract it into a separate folder or replace the
macOS app in Applications. Keep the package contents together as described above.
Preferences and export definitions are stored separately from the application;
older unsupported presets/jobs may still need recreating.

## Privacy and offline use

Opening, analyzing and exporting recordings happen locally. Update checks
contact GitHub without sending recordings, GPS data or file paths. They require
internet access; recording processing does not. Opening external links uses
your browser. Downloads and dependency installation also require internet access.

Recordings can contain GPS positions, timestamps and personal metadata. Review
files before sharing them in issues or with other people; they are not
automatically made anonymous.

## If the application does not start

- Verify that the download matches your operating system and processor.
- Check its checksum and extract the complete package before launching.
- On Linux, install the desktop libraries listed above and keep `_internal`
  beside the executable. On macOS, follow the first-launch instructions above.
- If it still fails, report the application version, operating system and error
  message in a [GitHub issue](https://github.com/rudnerbjoern/ride-forces-analyzer/issues).
  Do not attach private recordings or personal paths unnecessarily. Report
  security issues through the [private reporting channels](../../SECURITY.md).

[Back to the project](../../README.md) · [Documentation](../README.md)
