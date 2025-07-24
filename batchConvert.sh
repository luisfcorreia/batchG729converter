#!/bin/bash

# Batch convert audio files to 16-bit mono 8kHz WAV (with RIFF header)
# Usage: ./batch_convert_pcm.sh input_dir output_dir

if [ $# -ne 2 ]; then
    echo "Usage: $0 <input_dir> <output_dir>"
    exit 1
fi

INPUT_DIR="$1"
OUTPUT_DIR="$2"

# Create output directory if it doesn't exist
mkdir -p "$OUTPUT_DIR"

# Supported audio extensions
EXTENSIONS=("wav" "mp3" "ogg" "flac" "aac" "m4a" "wma" "opus" "amr")

# Convert files
find "$INPUT_DIR" -type f | while read -r INPUT_FILE; do
    # Get filename and extension
    FILENAME=$(basename -- "$INPUT_FILE")
    EXTENSION="${FILENAME##*.}"
    BASENAME="${FILENAME%.*}"

    # Check if extension is supported
    EXT_LOWER=$(echo "$EXTENSION" | tr '[:upper:]' '[:lower:]')
    SUPPORTED=0
    for ext in "${EXTENSIONS[@]}"; do
        if [ "$ext" = "$EXT_LOWER" ]; then
            SUPPORTED=1
            break
        fi
    done

    if [ $SUPPORTED -eq 1 ]; then
        OUTPUT_FILE="$OUTPUT_DIR/${BASENAME}.wav"
        echo "Converting: $FILENAME -> ${BASENAME}.wav"
        
        # Convert to WAV with RIFF header, 16-bit, mono, 8kHz
        ffmpeg -i "$INPUT_FILE" \
            -hide_banner -loglevel error -nostats \
            -vn \
            -acodec pcm_s16le \
            -ar 8000 \
            -ac 1 \
            -y \
            "$OUTPUT_FILE"

        pcm2g729 "$OUTPUT_FILE" g729-"$OUTPUT_FILE"
    else
        echo "Skipping unsupported format: $FILENAME"
    fi
done

echo "Batch conversion complete!"
echo "Output directory: $OUTPUT_DIR"
echo "Output format: WAV with RIFF header (16-bit, mono, 8kHz)"
