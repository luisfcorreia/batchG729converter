#!/usr/bin/env python3
import ctypes
import wave
import sys
import struct
import os
import subprocess
import tempfile

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
        '-ar', '8000',           # 8000Hz sample rate
        '-acodec', 'pcm_s16le',  # 16-bit little-endian PCM
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

def main(input_file, output_file):
    """Main processing function with FFmpeg conversion"""
    temp_wav = None
    try:
        # Convert input to proper WAV format
        temp_wav = convert_to_wav(input_file)
        
        # Encode to G.729
        data_size = encode_wav_to_g729(temp_wav, output_file)
        print(f"Encoded {input_file} to {output_file}, {data_size} bytes")
        
    finally:
        # Clean up temporary file
        if temp_wav and os.path.exists(temp_wav):
            os.unlink(temp_wav)

if __name__ == "__main__":
    if len(sys.argv) != 3:
        print(f"Usage: {sys.argv[0]} input_audio output.g729")
        print("Supports any audio format that FFmpeg can read")
        sys.exit(1)
    
    main(sys.argv[1], sys.argv[2])
