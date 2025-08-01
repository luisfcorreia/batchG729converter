# batchG729converter

Stupid things for stupid systems

# Pre requisites:

a linux workstation running Fedora or any RPM based system
(other distributions may also work, adjust packager and package names)


# Required packages

## bcg729-devel and ffmpeg

sudo dnf install bcg729-devel ffmpeg

# prepare environment

```
git clone https://github.com/luisfcorreia/batchG729converter
cd batchG729converter

python converter.py sample.wav sample.g729

```

Test the resulting file in your system


