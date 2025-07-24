# PCM to G.729 Encoder Makefile
CC = gcc
CFLAGS = -Wall -Wextra -O2
LDFLAGS = -lbcg729
TARGET = pcm2g729
SRC = pcm2g729.c

# Default build
all: $(TARGET)

$(TARGET): $(SRC)
	$(CC) $(CFLAGS) -o $@ $< $(LDFLAGS)

# Install to /usr/local/bin
install: $(TARGET)
	install -m 0755 $(TARGET) /usr/local/bin/

# Clean build artifacts
clean:
	rm -f $(TARGET)

# Run tests (requires sample.wav)
test: $(TARGET)
	./$(TARGET) sample.wav sample.g729.wav

.PHONY: all clean install test
