from g729a.py import *

# Initialize the codec
codec = G729ACodec("sl_g729a.dll")

# Encode PCM audio to G.729A (compression)
pcm_audio_data = b'...'  # Your 16-bit PCM data at 8kHz
encoded_g729a = codec.encode_pcm_to_g729a(pcm_audio_data)

# Decode G.729A back to PCM (decompression)  
decoded_pcm = codec.decode_g729a_to_pcm(encoded_g729a)


