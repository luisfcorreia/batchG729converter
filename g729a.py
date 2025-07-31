import ctypes
import ctypes.wintypes
from ctypes import Structure, Union, POINTER, c_uint32, c_uint16, c_uint8, c_char_p, c_void_p
import os

# ACM Constants
ACMDM_DRIVER_NOTIFY = 0x4001
ACMDM_DRIVER_DETAILS = 0x4002
ACMDM_HARDWARE_WAVE_CAPS_INPUT = 0x4020
ACMDM_HARDWARE_WAVE_CAPS_OUTPUT = 0x4021
ACMDM_FORMATTAG_DETAILS = 0x4025
ACMDM_FORMAT_DETAILS = 0x4026
ACMDM_FORMAT_SUGGEST = 0x4027
ACMDM_FILTERTAG_DETAILS = 0x4050
ACMDM_FILTER_DETAILS = 0x4051
ACMDM_STREAM_OPEN = 0x4076
ACMDM_STREAM_CLOSE = 0x4077
ACMDM_STREAM_SIZE = 0x4078
ACMDM_STREAM_CONVERT = 0x4079

# G.729A specific constants
G729A_FRAME_SIZE = 10  # bytes per frame (80 bits)
G729A_SAMPLES_PER_FRAME = 80  # samples per frame at 8kHz
G729A_SAMPLE_RATE = 8000
G729A_BITRATE = 8000

# Error codes
MMSYSERR_NOERROR = 0
MMSYSERR_ERROR = 1
MMSYSERR_BADDEVICEID = 2
MMSYSERR_NOTENABLED = 3
MMSYSERR_ALLOCATED = 4
MMSYSERR_INVALHANDLE = 5
MMSYSERR_NODRIVER = 6

# Map error codes to human-readable messages
ACM_ERROR_MESSAGES = {
    MMSYSERR_ERROR: "Unspecified error",
    MMSYSERR_BADDEVICEID: "Invalid device ID",
    MMSYSERR_NOTENABLED: "Driver not enabled",
    MMSYSERR_ALLOCATED: "Device already allocated",
    MMSYSERR_INVALHANDLE: "Invalid handle",
    MMSYSERR_NODRIVER: "No driver available"
}

class WAVEFORMATEX(Structure):
    _fields_ = [
        ("wFormatTag", c_uint16),
        ("nChannels", c_uint16),
        ("nSamplesPerSec", c_uint32),
        ("nAvgBytesPerSec", c_uint32),
        ("nBlockAlign", c_uint16),
        ("wBitsPerSample", c_uint16),
        ("cbSize", c_uint16),
    ]

class ACMDRVSTREAMINSTANCE(Structure):
    _fields_ = [
        ("cbStruct", c_uint32),
        ("pwfxSrc", POINTER(WAVEFORMATEX)),
        ("pwfxDst", POINTER(WAVEFORMATEX)),
        ("pwfltr", c_void_p),
        ("dwCallback", c_uint32),
        ("dwInstance", c_uint32),
        ("fdwOpen", c_uint32),
        ("fdwDriver", c_uint32),
        ("dwDriver", c_uint32),  # Driver stores stream handle here
    ]

class ACMDRVSTREAMHEADER(Structure):
    _fields_ = [
        ("cbStruct", c_uint32),
        ("fdwStatus", c_uint32),
        ("dwUser", c_uint32),
        ("pbSrc", POINTER(c_uint8)),
        ("cbSrcLength", c_uint32),
        ("cbSrcLengthUsed", c_uint32),
        ("dwSrcUser", c_uint32),
        ("pbDst", POINTER(c_uint8)),
        ("cbDstLength", c_uint32),
        ("cbDstLengthUsed", c_uint32),
        ("dwDstUser", c_uint32),
    ]

class G729ACodec:
    """Python interface for VoiceAge G.729A codec DLL"""
    
    def __init__(self, dll_path="sl_g729a.dll"):
        if not os.path.exists(dll_path):
            raise FileNotFoundError(f"G.729A codec DLL not found: {dll_path}")
        
        self.dll = ctypes.WinDLL(dll_path)
        self.driver_proc = self.dll.DriverProc
        self.driver_proc.argtypes = [
            c_uint32,  # dwDriverId
            c_uint32,  # hdrvr
            c_uint32,  # uMsg
            c_uint32,  # lParam1
            c_uint32   # lParam2
        ]
        self.driver_proc.restype = c_uint32
        
        self.stream_handle = None
        self.is_initialized = False
        
    def initialize(self):
        """Initialize the codec driver"""
        if self.is_initialized:
            return True
            
        result = self.driver_proc(0, 0, ACMDM_DRIVER_NOTIFY, 0, 0)
        self.is_initialized = (result == 1)  # Driver-specific success code
        if not self.is_initialized:
            raise RuntimeError(f"Driver initialization failed: {result}")
        return True
    
    def create_pcm_format(self, sample_rate=8000, channels=1, bits_per_sample=16):
        """Create PCM WAVEFORMATEX structure"""
        fmt = WAVEFORMATEX()
        fmt.wFormatTag = 1  # WAVE_FORMAT_PCM
        fmt.nChannels = channels
        fmt.nSamplesPerSec = sample_rate
        fmt.wBitsPerSample = bits_per_sample
        fmt.nBlockAlign = (channels * bits_per_sample) // 8
        fmt.nAvgBytesPerSec = fmt.nBlockAlign * sample_rate
        fmt.cbSize = 0
        return fmt
    
    def create_g729a_format(self):
        """Create G.729A WAVEFORMATEX structure"""
        fmt = WAVEFORMATEX()
        fmt.wFormatTag = 0x0032  # Common G.729 format tag
        fmt.nChannels = 1
        fmt.nSamplesPerSec = G729A_SAMPLE_RATE
        fmt.nAvgBytesPerSec = G729A_BITRATE // 8
        fmt.nBlockAlign = G729A_FRAME_SIZE
        fmt.wBitsPerSample = 0  # Not applicable for compressed format
        fmt.cbSize = 0
        return fmt
    
    def open_stream(self, src_format, dst_format):
        """Open a conversion stream"""
        if not self.is_initialized and not self.initialize():
            raise RuntimeError("Codec initialization failed")
        
        stream_instance = ACMDRVSTREAMINSTANCE()
        stream_instance.cbStruct = ctypes.sizeof(ACMDRVSTREAMINSTANCE)
        stream_instance.pwfxSrc = ctypes.pointer(src_format)
        stream_instance.pwfxDst = ctypes.pointer(dst_format)
        stream_instance.pwfltr = None
        stream_instance.fdwOpen = 0
        
        # Pass pointer to stream_instance as lParam1
        result = self.driver_proc(
            0, 
            0, 
            ACMDM_STREAM_OPEN,
            ctypes.addressof(stream_instance),
            0
        )
        
        if result != MMSYSERR_NOERROR:
            msg = ACM_ERROR_MESSAGES.get(result, f"Unknown error: {result}")
            raise RuntimeError(f"Failed to open stream: {msg}")
        
        self.stream_handle = stream_instance.dwDriver
        return True
    
    def close_stream(self):
        """Close the conversion stream"""
        if self.stream_handle:
            result = self.driver_proc(0, self.stream_handle, ACMDM_STREAM_CLOSE, 0, 0)
            self.stream_handle = None
            if result != MMSYSERR_NOERROR:
                msg = ACM_ERROR_MESSAGES.get(result, f"Unknown error: {result}")
                raise RuntimeError(f"Failed to close stream: {msg}")
        return True
    
    def convert_data(self, input_data, output_buffer_size):
        """Convert audio data using the codec"""
        if not self.stream_handle:
            raise RuntimeError("Stream not opened")
        
        input_buffer = (c_uint8 * len(input_data))(*input_data)
        output_buffer = (c_uint8 * output_buffer_size)()
        
        header = ACMDRVSTREAMHEADER()
        header.cbStruct = ctypes.sizeof(ACMDRVSTREAMHEADER)
        header.pbSrc = ctypes.cast(input_buffer, POINTER(c_uint8))
        header.cbSrcLength = len(input_data)
        header.pbDst = ctypes.cast(output_buffer, POINTER(c_uint8))
        header.cbDstLength = output_buffer_size
        
        # Pass pointer to header as lParam1
        result = self.driver_proc(
            0, 
            self.stream_handle, 
            ACMDM_STREAM_CONVERT,
            ctypes.addressof(header),
            0
        )
        
        if result != MMSYSERR_NOERROR:
            msg = ACM_ERROR_MESSAGES.get(result, f"Unknown error: {result}")
            raise RuntimeError(f"Conversion failed: {msg}")
        
        return bytes(output_buffer[:header.cbDstLengthUsed]), header.cbSrcLengthUsed
    
    def encode_pcm_to_g729a(self, pcm_data):
        """Encode PCM audio to G.729A format"""
        # Ensure input length is multiple of frame size (160 bytes for 80 samples at 16-bit)
        frame_size = 160  # 80 samples * 2 bytes/sample
        if len(pcm_data) % frame_size != 0:
            raise ValueError("PCM data length must be multiple of 160 bytes")
        
        pcm_format = self.create_pcm_format()
        g729a_format = self.create_g729a_format()
        
        self.open_stream(pcm_format, g729a_format)
        try:
            # Calculate output buffer size (10 bytes per 80 samples)
            num_frames = len(pcm_data) // frame_size
            output_size = num_frames * G729A_FRAME_SIZE
            encoded_data, _ = self.convert_data(pcm_data, output_size)
            return encoded_data
        finally:
            self.close_stream()
    
    def decode_g729a_to_pcm(self, g729a_data):
        """Decode G.729A audio to PCM format"""
        # Ensure input length is multiple of frame size (10 bytes)
        if len(g729a_data) % G729A_FRAME_SIZE != 0:
            raise ValueError("G.729 data length must be multiple of 10 bytes")
        
        g729a_format = self.create_g729a_format()
        pcm_format = self.create_pcm_format()
        
        self.open_stream(g729a_format, pcm_format)
        try:
            # Calculate output buffer size (160 bytes per 10-byte frame)
            num_frames = len(g729a_data) // G729A_FRAME_SIZE
            output_size = num_frames * 160  # 80 samples * 2 bytes/sample
            decoded_data, _ = self.convert_data(g729a_data, output_size)
            return decoded_data
        finally:
            self.close_stream()
    
    def __del__(self):
        """Safe cleanup when object is destroyed"""
        # Check if attribute exists before accessing
        if hasattr(self, 'stream_handle') and self.stream_handle:
            try:
                self.close_stream()
            except Exception:
                # Prevent exceptions during destruction
                pass

# Example usage
def example_usage():
    """Example of how to use the G.729A codec"""
    try:
        codec = G729ACodec("sl_g729a.dll")
        
        # Generate synthetic PCM data (1600 samples = 10 frames)
        sample_pcm_data = b"".join(
            b"\x00\x7F" * 80 +  # High sample
            b"\x00\x00" * 80    # Low sample
            for _ in range(5)
        )
        
        print("Encoding PCM to G.729A...")
        encoded_data = codec.encode_pcm_to_g729a(sample_pcm_data)
        print(f"Encoded {len(sample_pcm_data)} bytes PCM -> {len(encoded_data)} bytes G.729")
        
        print("Decoding G.729A to PCM...")
        decoded_data = codec.decode_g729a_to_pcm(encoded_data)
        print(f"Decoded {len(encoded_data)} bytes G.729 -> {len(decoded_data)} bytes PCM")
        
        return encoded_data, decoded_data
        
    except Exception as e:
        print(f"Error: {e}")
        return None, None

if __name__ == "__main__":
    example_usage()
