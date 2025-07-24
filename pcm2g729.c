#include <bcg729/encoder.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdint.h>

#define FRAME_SIZE 80        // 80 samples = 10ms at 8kHz
#define ENCODED_FRAME_SIZE 10
#define WAV_HEADER_SIZE 58   // Updated header size with fact chunk

void write_wav_header(FILE *file, uint32_t data_size, uint32_t sample_count) {
    // RIFF header
    fwrite("RIFF", 1, 4, file);
    uint32_t chunk_size = 4 + 24 + 12 + 8 + data_size;  // WAVE + fmt + fact + data
    fwrite(&chunk_size, 4, 1, file);
    fwrite("WAVE", 1, 4, file);
    
    // fmt chunk
    fwrite("fmt ", 1, 4, file);
    uint32_t fmt_size = 16;
    fwrite(&fmt_size, 4, 1, file);
    //uint16_t audio_format = 0x001B;  // G.729A format tag

    uint16_t audio_format = 0x0133;  // G.729 whatever I got as example

    uint16_t num_channels = 1;
    uint32_t sample_rate = 8000;
    uint32_t byte_rate = 8000;       // 8 kbps
    uint16_t block_align = 10;       // Max frame size
    uint16_t bits_per_sample = 0;    // Not applicable for compressed audio
    fwrite(&audio_format, 2, 1, file);
    fwrite(&num_channels, 2, 1, file);
    fwrite(&sample_rate, 4, 1, file);
    fwrite(&byte_rate, 4, 1, file);
    fwrite(&block_align, 2, 1, file);
    fwrite(&bits_per_sample, 2, 1, file);
    
    // fact chunk (required for compressed formats)
    fwrite("fact", 1, 4, file);
    uint32_t fact_size = 4;
    fwrite(&fact_size, 4, 1, file);
    fwrite(&sample_count, 4, 1, file);
    
    // data chunk
    fwrite("data", 1, 4, file);
    fwrite(&data_size, 4, 1, file);
}

int main(int argc, char *argv[]) {
    if (argc != 3) {
        fprintf(stderr, "Usage: %s <input.pcm> <output.g729wav>\n", argv[0]);
        return 1;
    }

    FILE *pcmFile = fopen(argv[1], "rb");
    if (!pcmFile) {
        perror("Input file open error");
        return 1;
    }

    FILE *outFile = fopen(argv[2], "wb");
    if (!outFile) {
        perror("Output file open error");
        fclose(pcmFile);
        return 1;
    }

    // Initialize encoder
    bcg729EncoderChannelContextStruct *encoder = initBcg729EncoderChannel(0);
    if (!encoder) {
        fprintf(stderr, "Encoder initialization failed\n");
        fclose(pcmFile);
        fclose(outFile);
        return 1;
    }

    // First pass: count frames and calculate sizes
    int16_t pcmFrame[FRAME_SIZE];
    size_t bytesRead;
    uint32_t frame_count = 0;
    uint32_t total_data_size = 0;
    uint8_t bitStreamLength[1];

    // Temporary storage for encoded frames
    typedef struct {
        uint8_t data[ENCODED_FRAME_SIZE];
        uint8_t size;
    } EncodedFrame;

    // Count frames first to know sample count
    while ((bytesRead = fread(pcmFrame, sizeof(int16_t), FRAME_SIZE, pcmFile)) > 0) {
        frame_count++;
    }
    rewind(pcmFile);
    
    uint32_t sample_count = frame_count * FRAME_SIZE;
    EncodedFrame *frames = malloc(frame_count * sizeof(EncodedFrame));
    
    // Second pass: encode all frames
    for (uint32_t i = 0; i < frame_count; i++) {
        bytesRead = fread(pcmFrame, sizeof(int16_t), FRAME_SIZE, pcmFile);
        if (bytesRead < FRAME_SIZE) {
            memset(pcmFrame + bytesRead, 0, (FRAME_SIZE - bytesRead) * sizeof(int16_t));
        }
        
        bcg729Encoder(encoder, pcmFrame, frames[i].data, bitStreamLength);
        frames[i].size = bitStreamLength[0];
        total_data_size += bitStreamLength[0];
    }
    
    // Write header with known sizes
    write_wav_header(outFile, total_data_size, sample_count);
    
    // Write encoded data
    for (uint32_t i = 0; i < frame_count; i++) {
        fwrite(frames[i].data, 1, frames[i].size, outFile);
    }

    // Cleanup
    free(frames);
    closeBcg729EncoderChannel(encoder);
    fclose(pcmFile);
    fclose(outFile);
    
    printf("Encoded %u frames (%u bytes audio data)\n", frame_count, total_data_size);
    return 0;
}