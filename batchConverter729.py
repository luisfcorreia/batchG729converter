#!/usr/bin/env python3
import ctypes
import wave
import sys
import struct
import os
import subprocess
import tempfile
import glob
import argparse

# Load bcg729 library
libbcg729 = ctypes.CDLL('libbcg729.so')

# Define function prototypes
libbcg729.initBcg729EncoderChannel.restype = ctypes.c_void_p
libbcg729.initBcg729EncoderChannel.argtypes = []
libbcg729.closeBcg729EncoderChannel.argtypes = [ctypes.c_void_p]
libbcg729.bcg729Encoder.argtypes = [
    ctypes.c_void_p,
    ctypes.POINTER(ctypes.c_int16),
    ctypes.POINTER(ctypes.c_uint8),
    ctypes.POINTER(ctypes.c_uint8),
    ctypes.c_uint8
]

def convert_to_wav(input_file):
    """Convert any audio file to 16-bit mono 8000Hz WAV using FFmpeg"""
    with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as temp_wav:
        temp_path = temp_wav.name
    
    cmd = [
        'ffmpeg', '-y', '-i', input_file,
        '-ac', '1',             # Mono
        '-ar', '8000',          # 8000Hz sample rate
        '-acodec', 'pcm_s16le', # 16-bit little-endian PCM
        '-hide_banner', '-loglevel', 'error',
        temp_path
    ]
    
    try:
        subprocess.run(cmd, check=True)
        return temp_path
    except subprocess.CalledProcessError as e:
        os.unlink(temp_path)
        raise RuntimeError(f"FFmpeg conversion failed: {e}")
    except FileNotFoundError:
        os.unlink(temp_path)
        raise RuntimeError("FFmpeg not found. Please install ffmpeg")

def encode_wav_to_g729(input_wav, output_g729):
    """Encode WAV file to G.729 with RIFF header"""
    # Initialize encoder
    encoder = libbcg729.initBcg729EncoderChannel()
    if not encoder:
        raise RuntimeError("Encoder initialization failed")
    
    frame_size = 80  # 10ms frame
    frame_bytes = frame_size * 2  # 160 bytes per frame
    output_buffer = (ctypes.c_uint8 * 10)()
    bitstream_len = ctypes.c_uint8(0)
    
    try:
        with wave.open(input_wav, 'rb') as wav_file:
            # Validate WAV parameters
            if wav_file.getnchannels() != 1:
                raise ValueError("Converted file is not mono")
            if wav_file.getsampwidth() != 2:
                raise ValueError("Converted file is not 16-bit")
            if wav_file.getframerate() != 8000:
                raise ValueError("Converted file is not 8000 Hz")
            
            with open(output_g729, 'wb') as out_file:
                # Write the exact RIFF header
                header_bytes = bytes.fromhex(
                    "52494646B614000057415645666D74201600000033010100401F0000" +
                    "E80300000A000000040000000000646174618C140000"
                )
                out_file.write(header_bytes)
                total_data_size = 0
                
                while True:
                    # Read PCM data
                    pcm_data = wav_file.readframes(frame_size)
                    if not pcm_data:
                        break
                    
                    # Pad partial frames with zeros
                    if len(pcm_data) < frame_bytes:
                        pcm_data += b'\x00' * (frame_bytes - len(pcm_data))
                    
                    # Convert to ctypes buffer
                    samples = struct.unpack(f'<{frame_size}h', pcm_data)
                    pcm_frame = (ctypes.c_int16 * frame_size)(*samples)
                    
                    # Encode frame
                    libbcg729.bcg729Encoder(
                        encoder,
                        pcm_frame,
                        output_buffer,
                        ctypes.byref(bitstream_len),
                        0
                    )
                    
                    # Write encoded frame to output
                    if bitstream_len.value > 0:
                        frame_data = bytes(output_buffer[:bitstream_len.value])
                        out_file.write(frame_data)
                        total_data_size += len(frame_data)
                
                # Update data size in header (offset 46)
                out_file.seek(46)
                out_file.write(total_data_size.to_bytes(4, 'little'))
                
                # Update RIFF size in header (offset 4)
                riff_size = 36 + total_data_size
                out_file.seek(4)
                out_file.write(riff_size.to_bytes(4, 'little'))
                
                return total_data_size
                
    finally:
        libbcg729.closeBcg729EncoderChannel(encoder)

def process_file(input_file):
    """Process a single file with conversion and encoding"""
    base_name = os.path.splitext(input_file)[0]
    output_file = f"{base_name}.g729.wav"
    
    if os.path.exists(output_file):
        print(f"Skipping {input_file} - output already exists")
        return False
    
    temp_wav = None
    try:
        print(f"Processing {input_file}...")
        temp_wav = convert_to_wav(input_file)
        data_size = encode_wav_to_g729(temp_wav, output_file)
        print(f"Created {output_file} ({data_size} bytes)")
        return True
    except Exception as e:
        print(f"Error processing {input_file}: {str(e)}")
        return False
    finally:
        if temp_wav and os.path.exists(temp_wav):
            os.unlink(temp_wav)

def main():
    """Main function with batch processing support"""
    parser = argparse.ArgumentParser(
        description='Batch convert audio files to G.729 format with .g729.wav extension'
    )
    parser.add_argument(
        'inputs', 
        nargs='+',
        help='Input files or directories (supports wildcards)'
    )
    
    args = parser.parse_args()
    
    # Expand input patterns
    input_files = []
    for pattern in args.inputs:
        if os.path.isfile(pattern):
            input_files.append(pattern)
        elif os.path.isdir(pattern):
            for root, _, files in os.walk(pattern):
                for file in files:
                    input_files.append(os.path.join(root, file))
        else:
            # Try glob pattern
            matches = glob.glob(pattern, recursive=True)
            if matches:
                input_files.extend(matches)
    
    if not input_files:
        print("No valid input files found")
        return
    
    # Process each file
    success_count = 0
    for input_file in input_files:
        if process_file(input_file):
            success_count += 1
    
    print(f"\nProcessing complete: {success_count}/{len(input_files)} files converted")

if __name__ == "__main__":
    main()
